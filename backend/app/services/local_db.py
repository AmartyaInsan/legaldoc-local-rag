import os
import json
import sqlite3
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from app.core.config import settings, BACKEND_DIR

logger = logging.getLogger(__name__)


class LocalDatabaseService:
    """
    Learning Note (Close-Environment Database Service):
    Originally, the YouTube tutorial used Supabase (cloud Postgres + pgvector).
    Because this project is designed for confidential legal documents in a closed environment,
    I replaced Supabase with two 100% local databases that require no external server setup:
    1. ChromaDB (PersistentClient): Handles 768-dim vector embeddings and fast HNSW similarity search.
    2. SQLite (legal_rag.db): Handles chat threads, messages, document records, and Text-to-SQL analytics.
    """

    def __init__(self):
        # Resolve local_data folder path inside backend/
        raw_dir = settings.LOCAL_DATA_DIR
        if not os.path.isabs(raw_dir):
            self.data_dir = os.path.abspath(os.path.join(BACKEND_DIR, raw_dir))
        else:
            self.data_dir = raw_dir

        os.makedirs(self.data_dir, exist_ok=True)

        self.sqlite_path = os.path.join(self.data_dir, "legal_rag.db")
        self.chroma_path = os.path.join(self.data_dir, "chroma")

        # 1. Initialize Persistent SQLite
        self.conn = sqlite3.connect(self.sqlite_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_sqlite_tables()

        # 2. Initialize Persistent ChromaDB for HNSW Vector Search
        self.chroma_client = None
        self.collection = None
        self._init_chroma()

    def _init_sqlite_tables(self):
        """Create local SQLite tables for threads, messages, documents, and chunks if they don't exist."""
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")

        # Chat threads table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS threads (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                title TEXT NOT NULL DEFAULT 'New Conversation',
                is_pinned INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)

        # Migration: ensure is_pinned column exists in case the table was created previously
        try:
            cursor.execute("ALTER TABLE threads ADD COLUMN is_pinned INTEGER DEFAULT 0;")
            self.conn.commit()
        except Exception:
            pass

        # Chat messages history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata_json TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY (thread_id) REFERENCES threads (id) ON DELETE CASCADE
            );
        """)

        # Uploaded documents table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                filename TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                content_hash TEXT,
                status TEXT DEFAULT 'completed',
                chunk_count INTEGER DEFAULT 0,
                doc_type TEXT DEFAULT 'general',
                title TEXT,
                metadata_json TEXT DEFAULT '{}',
                error_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)

        # Document chunks table (used for BM25 keyword search, Sub-Agent full reading, and SQL analytics)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                user_id TEXT,
                chunk_index INTEGER NOT NULL,
                char_length INTEGER NOT NULL,
                content TEXT NOT NULL,
                doc_title TEXT,
                doc_type TEXT,
                keywords TEXT,
                metadata_json TEXT DEFAULT '{}',
                embedding_json TEXT DEFAULT '[]',
                FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
            );
        """)
        self.conn.commit()
        logger.info(f"Local SQLite database ready at: {self.sqlite_path}")

    def _init_chroma(self):
        """Initialize local ChromaDB persistent vector store using cosine similarity."""
        try:
            import chromadb
            os.makedirs(self.chroma_path, exist_ok=True)
            self.chroma_client = chromadb.PersistentClient(path=self.chroma_path)
            self.collection = self.chroma_client.get_or_create_collection(
                name=settings.CHROMA_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(
                f"Local ChromaDB vector store ready at: {self.chroma_path} "
                f"(collection='{settings.CHROMA_COLLECTION_NAME}', vectors={self.collection.count()})"
            )
        except Exception as e:
            logger.warning(f"ChromaDB initialization warning (using SQLite vector fallback): {e}")
            self.chroma_client = None
            self.collection = None

    def check_health(self) -> Dict[str, Any]:
        """Return health status and statistics of the local ChromaDB + SQLite storage."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) as cnt FROM documents;")
            doc_count = cursor.fetchone()["cnt"]
            cursor.execute("SELECT COUNT(*) as cnt FROM document_chunks;")
            chunk_count = cursor.fetchone()["cnt"]

            chroma_vectors = self.collection.count() if self.collection is not None else chunk_count
            engine_label = "ChromaDB (HNSW) + SQLite" if self.collection is not None else "SQLite Local"

            return {
                "status": "connected",
                "engine": engine_label,
                "path": self.data_dir,
                "documents_count": doc_count,
                "vectors_count": chroma_vectors,
            }
        except Exception as e:
            return {
                "status": "error",
                "engine": "ChromaDB + SQLite",
                "error": str(e),
            }

    # ------------------------------------------------------------------
    # THREADS & MESSAGES (Chat History Persistence)
    # ------------------------------------------------------------------
    def list_threads(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM threads ORDER BY is_pinned DESC, updated_at DESC;")
        rows = cursor.fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["is_pinned"] = bool(d.get("is_pinned", 0))
            results.append(d)
        return results

    def create_or_get_thread(self, thread_id: str, title: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM threads WHERE id = ?;", (thread_id,))
        existing = cursor.fetchone()
        if existing:
            d = dict(existing)
            d["is_pinned"] = bool(d.get("is_pinned", 0))
            return d

        now_iso = datetime.utcnow().isoformat()
        cursor.execute(
            "INSERT INTO threads (id, user_id, title, is_pinned, created_at, updated_at) VALUES (?, ?, ?, 0, ?, ?);",
            (thread_id, user_id or "local-user", title, now_iso, now_iso),
        )
        self.conn.commit()
        return {
            "id": thread_id,
            "user_id": user_id or "local-user",
            "title": title,
            "is_pinned": False,
            "created_at": now_iso,
            "updated_at": now_iso,
        }

    def update_thread(
        self,
        thread_id: str,
        title: Optional[str] = None,
        is_pinned: Optional[bool] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update thread title (rename) and/or pinned status."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM threads WHERE id = ?;", (thread_id,))
        row = cursor.fetchone()
        if not row:
            return None

        updates = []
        params = []
        if title is not None:
            updates.append("title = ?")
            params.append(title.strip())
        if is_pinned is not None:
            updates.append("is_pinned = ?")
            params.append(1 if is_pinned else 0)

        if updates:
            updates.append("updated_at = ?")
            now_iso = datetime.utcnow().isoformat()
            params.append(now_iso)
            params.append(thread_id)
            cursor.execute(f"UPDATE threads SET {', '.join(updates)} WHERE id = ?;", params)
            self.conn.commit()

        cursor.execute("SELECT * FROM threads WHERE id = ?;", (thread_id,))
        updated = cursor.fetchone()
        if updated:
            d = dict(updated)
            d["is_pinned"] = bool(d.get("is_pinned", 0))
            return d
        return None

    def delete_thread(self, thread_id: str) -> None:
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM messages WHERE thread_id = ?;", (thread_id,))
        cursor.execute("DELETE FROM threads WHERE id = ?;", (thread_id,))
        self.conn.commit()

    def save_message(
        self,
        message_id: str,
        thread_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[str] = None,
    ) -> None:
        now_iso = created_at or datetime.utcnow().isoformat()
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO messages (id, thread_id, role, content, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (message_id, thread_id, role, content, meta_json, now_iso),
        )
        cursor.execute(
            "UPDATE threads SET updated_at = ? WHERE id = ?;",
            (now_iso, thread_id),
        )
        self.conn.commit()

    def get_thread_messages(self, thread_id: str) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM messages WHERE thread_id = ? ORDER BY created_at ASC;",
            (thread_id,),
        )
        rows = cursor.fetchall()
        results = []
        for r in rows:
            try:
                meta = json.loads(r["metadata_json"] or "{}")
            except Exception:
                meta = {}
            results.append({
                "id": r["id"],
                "role": r["role"],
                "content": r["content"],
                "created_at": r["created_at"],
                "metadata": meta,
            })
        return results

    # ------------------------------------------------------------------
    # DOCUMENTS & RECORD MANAGER (SHA-256 Deduplication)
    # ------------------------------------------------------------------
    def find_existing_document(
        self, filename: str, content_hash: str
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Check SQLite for an identical content_hash (duplicate) or same filename (update)."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM documents;")
        rows = cursor.fetchall()

        exact_hash_match = None
        filename_match = None
        for r in rows:
            doc = self._row_to_doc_dict(r)
            if doc.get("content_hash") == content_hash:
                exact_hash_match = doc
            if doc.get("filename") == filename:
                filename_match = doc

        return exact_hash_match, filename_match

    def _row_to_doc_dict(self, r: sqlite3.Row) -> Dict[str, Any]:
        try:
            meta = json.loads(r["metadata_json"] or "{}")
        except Exception:
            meta = {}
        return {
            "id": r["id"],
            "user_id": r["user_id"],
            "filename": r["filename"],
            "file_size": r["file_size"],
            "content_hash": r["content_hash"],
            "status": r["status"],
            "chunk_count": r["chunk_count"],
            "doc_type": r["doc_type"],
            "title": r["title"],
            "metadata": meta,
            "error_message": r["error_message"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }

    def list_documents(self) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM documents ORDER BY created_at DESC;")
        return [self._row_to_doc_dict(r) for r in cursor.fetchall()]

    def upsert_document(self, doc_record: Dict[str, Any]) -> None:
        meta = doc_record.get("metadata") or {}
        doc_type = meta.get("document_type") or meta.get("doc_type") or "general"
        title = meta.get("title") or doc_record["filename"]
        meta_json = json.dumps(meta, ensure_ascii=False)

        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO documents
            (id, user_id, filename, file_size, content_hash, status, chunk_count, doc_type, title, metadata_json, error_message, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                doc_record["id"],
                doc_record.get("user_id") or "local-user",
                doc_record["filename"],
                doc_record["file_size"],
                doc_record.get("content_hash"),
                doc_record.get("status", "completed"),
                doc_record.get("chunk_count", 0),
                doc_type,
                title,
                meta_json,
                doc_record.get("error_message"),
                doc_record["created_at"],
                doc_record["updated_at"],
            ),
        )
        self.conn.commit()

    # ------------------------------------------------------------------
    # CHUNKS & CHROMADB VECTOR OPERATIONS
    # ------------------------------------------------------------------
    def store_chunks_and_vectors(self, records: List[Dict[str, Any]]) -> None:
        """
        Save chunk records to SQLite and their 768-dim embeddings to ChromaDB.
        """
        if not records:
            return

        cursor = self.conn.cursor()
        chroma_ids = []
        chroma_embeddings = []
        chroma_documents = []
        chroma_metadatas = []

        for r in records:
            cid = r["id"]
            doc_id = r["document_id"]
            user_id = r.get("user_id") or "local-user"
            idx = r["chunk_index"]
            content = r["content"]
            meta = r.get("metadata", {})
            emb = r.get("embedding", [])

            doc_title = str(meta.get("doc_title") or meta.get("title") or meta.get("filename") or "")
            doc_type = str(meta.get("doc_type") or meta.get("document_type") or "general")
            kws_list = meta.get("keywords", [])
            keywords_str = ", ".join(str(k) for k in kws_list) if isinstance(kws_list, list) else str(kws_list)

            cursor.execute(
                """
                INSERT OR REPLACE INTO document_chunks
                (id, document_id, user_id, chunk_index, char_length, content, doc_title, doc_type, keywords, metadata_json, embedding_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    cid,
                    doc_id,
                    user_id,
                    idx,
                    len(content),
                    content,
                    doc_title,
                    doc_type,
                    keywords_str,
                    json.dumps(meta, ensure_ascii=False),
                    json.dumps(emb),
                ),
            )

            chroma_ids.append(cid)
            chroma_embeddings.append(emb)
            chroma_documents.append(content)
            # Chroma metadata only accepts str, int, float, or bool
            chroma_metadatas.append({
                "document_id": str(doc_id),
                "filename": str(meta.get("filename", "unknown")),
                "doc_title": doc_title,
                "doc_type": doc_type.lower(),
                "chunk_index": int(idx),
                "keywords": keywords_str.lower(),
                "language": str(meta.get("language", "id")),
            })

        self.conn.commit()

        if self.collection is not None:
            try:
                self.collection.upsert(
                    ids=chroma_ids,
                    embeddings=chroma_embeddings,
                    documents=chroma_documents,
                    metadatas=chroma_metadatas,
                )
                logger.info(f"Indexed {len(records)} chunk vectors into local ChromaDB.")
            except Exception as e:
                logger.warning(f"Could not upsert vectors to ChromaDB: {e}")

    def query_chroma_vectors(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        threshold: float = 0.25,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Query ChromaDB HNSW index for the closest vectors.
        Returns None if ChromaDB is unavailable so the caller can fall back to SQLite cosine similarity.
        """
        if self.collection is None:
            return None

        try:
            total_count = self.collection.count()
            if total_count == 0:
                return []

            where_clause: Optional[Dict[str, Any]] = None
            if metadata_filter:
                doc_ids = metadata_filter.get("document_ids")
                if doc_ids and isinstance(doc_ids, list):
                    if len(doc_ids) == 1:
                        where_clause = {"document_id": str(doc_ids[0])}
                    elif len(doc_ids) > 1:
                        where_clause = {"document_id": {"$in": [str(d) for d in doc_ids]}}
                elif metadata_filter.get("document_id"):
                    where_clause = {"document_id": str(metadata_filter["document_id"])}
                elif metadata_filter.get("document_type"):
                    where_clause = {"doc_type": str(metadata_filter["document_type"]).lower()}

            n_results = min(max(top_k * 2, 10), total_count)
            res = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where_clause,
                include=["documents", "metadatas", "distances"],
            )

            ids = res.get("ids", [[]])[0]
            docs = res.get("documents", [[]])[0]
            metas = res.get("metadatas", [[]])[0]
            distances = res.get("distances", [[]])[0]

            results = []
            for cid, content, cmeta, dist in zip(ids, docs, metas, distances):
                # Chroma cosine distance = 1 - cosine_similarity
                sim = max(0.0, 1.0 - float(dist))
                if sim < threshold:
                    continue

                # Optional keyword filter check
                if metadata_filter and metadata_filter.get("keyword"):
                    kw_target = str(metadata_filter["keyword"]).lower()
                    if kw_target not in str(cmeta.get("keywords", "")).lower():
                        continue

                # Fetch full rich metadata from SQLite if available
                full_meta = self.get_chunk_metadata(cid) or cmeta
                results.append({
                    "id": cid,
                    "document_id": cmeta.get("document_id"),
                    "content": content,
                    "metadata": full_meta,
                    "similarity": round(sim, 4),
                })

            results.sort(key=lambda x: x["similarity"], reverse=True)
            return results
        except Exception as e:
            logger.warning(f"ChromaDB vector query error: {e}")
            return None

    def get_chunk_metadata(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT metadata_json FROM document_chunks WHERE id = ?;", (chunk_id,))
        row = cursor.fetchone()
        if row and row["metadata_json"]:
            try:
                return json.loads(row["metadata_json"])
            except Exception:
                pass
        return None

    def get_chunk_by_doc_and_index(self, document_id: str, chunk_index: int) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, content, chunk_index FROM document_chunks WHERE document_id = ? AND chunk_index = ? LIMIT 1;",
            (document_id, chunk_index),
        )
        row = cursor.fetchone()
        if row:
            return {"id": row["id"], "content": row["content"], "chunk_index": row["chunk_index"]}
        return None

    def get_all_chunks(self, metadata_filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Load chunks from SQLite for BM25 keyword search or fallback vector similarity."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM document_chunks ORDER BY document_id, chunk_index ASC;")
        rows = cursor.fetchall()

        chunks = []
        for r in rows:
            try:
                meta = json.loads(r["metadata_json"] or "{}")
            except Exception:
                meta = {}
            try:
                emb = json.loads(r["embedding_json"] or "[]")
            except Exception:
                emb = []

            if metadata_filter:
                doc_ids = metadata_filter.get("document_ids")
                if doc_ids and isinstance(doc_ids, list) and len(doc_ids) > 0:
                    if str(r["document_id"]) not in [str(d) for d in doc_ids]:
                        continue
                elif metadata_filter.get("document_id") and str(r["document_id"]) != str(metadata_filter["document_id"]):
                    continue
                if metadata_filter.get("document_type"):
                    chunk_type = meta.get("doc_type", r["doc_type"] or "general")
                    if str(chunk_type).lower() != str(metadata_filter["document_type"]).lower():
                        continue
                if metadata_filter.get("keyword"):
                    kws = [str(k).lower() for k in meta.get("keywords", [])]
                    if str(metadata_filter["keyword"]).lower() not in kws:
                        continue

            chunks.append({
                "id": r["id"],
                "document_id": r["document_id"],
                "user_id": r["user_id"],
                "chunk_index": r["chunk_index"],
                "content": r["content"],
                "metadata": meta,
                "embedding": emb,
            })
        return chunks

    def get_document_chunks_ordered(self, document_id: str) -> List[Dict[str, Any]]:
        """Get all chunks for a specific document in reading order (0..N) for Sub-Agents."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM document_chunks WHERE document_id = ? ORDER BY chunk_index ASC;",
            (document_id,),
        )
        rows = cursor.fetchall()
        results = []
        for r in rows:
            try:
                meta = json.loads(r["metadata_json"] or "{}")
            except Exception:
                meta = {}
            results.append({
                "id": r["id"],
                "document_id": r["document_id"],
                "chunk_index": r["chunk_index"],
                "content": r["content"],
                "metadata": meta,
            })
        return results

    def delete_document_and_chunks(self, document_id: str, delete_doc_record: bool = True) -> int:
        """
        Cascade delete all chunks and embeddings for a document from both ChromaDB and SQLite.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM document_chunks WHERE document_id = ?;", (document_id,))
        deleted_count = cursor.fetchone()["cnt"]

        cursor.execute("DELETE FROM document_chunks WHERE document_id = ?;", (document_id,))
        if delete_doc_record:
            cursor.execute("DELETE FROM documents WHERE id = ?;", (document_id,))
        self.conn.commit()

        if self.collection is not None:
            try:
                self.collection.delete(where={"document_id": str(document_id)})
            except Exception as e:
                logger.debug(f"ChromaDB delete chunks notice: {e}")

        logger.info(f"Cascade deleted {deleted_count} chunks from ChromaDB & SQLite for doc_id={document_id}")
        return deleted_count


local_db_service = LocalDatabaseService()
