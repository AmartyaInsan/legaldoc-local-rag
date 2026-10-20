import hashlib
import uuid
from datetime import datetime
from typing import List, Dict, Any
import logging

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from app.schemas.document import DocumentResponse
from app.api.deps import get_current_user
from app.services.chunking import chunk_text
from app.services.embeddings import embedding_service
from app.services.retrieval import retrieval_service
from app.services.local_db import local_db_service
from app.services.document_parser import parse_document
from app.services.metadata_extractor import metadata_extractor
from app.services.tools.text_to_sql import text_to_sql_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=List[DocumentResponse])
async def list_documents(user: Dict[str, Any] = Depends(get_current_user)):
    """List all uploaded documents stored in local SQLite."""
    raw_docs = local_db_service.list_documents()
    docs = []
    for d in raw_docs:
        docs.append(
            DocumentResponse(
                id=d["id"],
                filename=d["filename"],
                file_size=d["file_size"],
                content_hash=d.get("content_hash"),
                status=d.get("status", "completed"),
                chunk_count=d.get("chunk_count", 0),
                doc_action="indexed",
                metadata=d.get("metadata"),
                message=None,
                error_message=d.get("error_message"),
                created_at=d["created_at"],
                updated_at=d.get("updated_at", d["created_at"]),
            )
        )
    return docs


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Learning Note (Document Upload & Ingestion Pipeline - Modules 2 to 5):
    1. Calculate a SHA-256 hash of the uploaded file bytes.
       - If the exact same hash already exists in SQLite -> skip re-embedding to save time!
       - If the filename exists but the content changed -> delete old chunks and update.
    2. Extract plain text from the file (PDF, DOCX, HTML, MD, TXT, CSV).
    3. Use local Ollama (qwen2.5:7b) to extract basic metadata (title, summary, keywords).
    4. Split the text into overlapping chunks and generate 768-dim vectors via Ollama (nomic-embed-text).
    5. Save the vectors to local ChromaDB and document records to local SQLite (legal_rag.db).
    """
    filename = file.filename or "uploaded_file.txt"
    content_bytes = await file.read()
    file_size = len(content_bytes)

    if file_size == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # 1. Calculate SHA-256 content hash for deduplication
    content_hash = hashlib.sha256(content_bytes).hexdigest()
    user_id = user.get("id")
    now_str = datetime.utcnow().isoformat()

    # 2. Check local SQLite database for existing file or duplicate hash
    exact_hash_match, filename_match = local_db_service.find_existing_document(filename, content_hash)

    # CASE A: Exact same file content already exists -> Skip embedding
    if exact_hash_match:
        logger.info(f"Duplicate file detected ({filename}). Hash matches doc {exact_hash_match['id']}.")
        return DocumentResponse(
            id=exact_hash_match["id"],
            filename=filename,
            file_size=file_size,
            content_hash=content_hash,
            status="completed",
            chunk_count=exact_hash_match.get("chunk_count", 0),
            doc_action="skipped",
            metadata=exact_hash_match.get("metadata"),
            message=f"Duplicate content detected ({exact_hash_match['filename']}). Skipped re-embedding.",
            created_at=exact_hash_match["created_at"],
            updated_at=exact_hash_match.get("updated_at", now_str),
        )

    # 3. Parse text from file (PDF, DOCX, HTML, TXT, MD, etc.)
    try:
        text_content, doc_type = parse_document(filename, content_bytes)
    except Exception as e:
        logger.error(f"Failed to parse document {filename}: {e}")
        raise HTTPException(status_code=400, detail=f"Document parsing error: {e}")

    # 4. Extract structured metadata using local Ollama
    extracted_meta = await metadata_extractor.extract_metadata(filename, text_content)
    meta_dict = extracted_meta.model_dump()

    # 5. Split text into chunks
    chunks = chunk_text(text_content, chunk_size=800, overlap=150)
    if not chunks:
        raise HTTPException(status_code=400, detail="No readable text content extracted from file.")

    # 6. Generate 768-dim vector embeddings using local Ollama nomic-embed-text
    try:
        embeddings = await embedding_service.get_embeddings_batch(chunks)
    except Exception as e:
        logger.error(f"Failed to generate embeddings for {filename}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Embedding generation with Ollama failed: {e}. Make sure Ollama is running locally.",
        )

    # CASE B: Same filename with modified content -> Replace old chunks in ChromaDB & SQLite
    if filename_match:
        doc_id = filename_match["id"]
        logger.info(f"Updating existing document '{filename}' (doc_id={doc_id}).")

        # Delete old chunks before saving new ones
        retrieval_service.delete_document_chunks(doc_id)

        doc_record = {
            "id": doc_id,
            "filename": filename,
            "file_size": file_size,
            "content_hash": content_hash,
            "status": "completed",
            "chunk_count": len(chunks),
            "doc_action": "updated",
            "metadata": meta_dict,
            "message": f"Document '{filename}' updated ({len(chunks)} chunks re-indexed in ChromaDB).",
            "error_message": None,
            "created_at": filename_match["created_at"],
            "updated_at": now_str,
            "user_id": user_id,
        }
        local_db_service.upsert_document(doc_record)

        await retrieval_service.store_document_chunks(
            document_id=doc_id,
            user_id=user_id,
            chunks=chunks,
            embeddings=embeddings,
            document_metadata={"filename": filename, "file_size": file_size, "type": doc_type, **meta_dict},
        )
        if filename.lower().endswith(".csv"):
            text_to_sql_service.sync_csv_table(filename, content_bytes)
        elif filename.lower().endswith(".xlsx"):
            text_to_sql_service.sync_excel_tables(filename, content_bytes)

        return DocumentResponse(**doc_record)

    # CASE C: Brand new document -> Save to SQLite and ChromaDB
    doc_id = str(uuid.uuid4())
    doc_record = {
        "id": doc_id,
        "filename": filename,
        "file_size": file_size,
        "content_hash": content_hash,
        "status": "completed",
        "chunk_count": len(chunks),
        "doc_action": "created",
        "metadata": meta_dict,
        "message": f"Indexed {len(chunks)} chunks into local ChromaDB & SQLite.",
        "error_message": None,
        "created_at": now_str,
        "updated_at": now_str,
        "user_id": user_id,
    }
    local_db_service.upsert_document(doc_record)

    await retrieval_service.store_document_chunks(
        document_id=doc_id,
        user_id=user_id,
        chunks=chunks,
        embeddings=embeddings,
        document_metadata={"filename": filename, "file_size": file_size, "type": doc_type, **meta_dict},
    )
    if filename.lower().endswith(".csv"):
        text_to_sql_service.sync_csv_table(filename, content_bytes)
    elif filename.lower().endswith(".xlsx"):
        text_to_sql_service.sync_excel_tables(filename, content_bytes)

    return DocumentResponse(**doc_record)


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Cascade delete a document and all of its chunks/vectors from local SQLite and ChromaDB.
    """
    deleted_chunks = local_db_service.delete_document_and_chunks(document_id, delete_doc_record=True)

    return {
        "status": "success",
        "id": document_id,
        "deleted_chunks": deleted_chunks,
        "message": f"Document {document_id} and {deleted_chunks} vector chunks removed from local storage.",
    }
