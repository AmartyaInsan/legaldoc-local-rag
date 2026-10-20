import re
import math
import logging
from typing import List, Dict, Any, Optional
import uuid

from app.services.local_db import local_db_service
from app.services.embeddings import embedding_service
from app.services.reranker import reranker_service

logger = logging.getLogger(__name__)


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """
    Calculate cosine similarity between two vectors.
    Used as a fallback if ChromaDB is not active.
    """
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot_product = sum(a * b for a, b in zip(v1, v2))
    magnitude_v1 = math.sqrt(sum(a * a for a in v1))
    magnitude_v2 = math.sqrt(sum(b * b for b in v2))
    if magnitude_v1 == 0.0 or magnitude_v2 == 0.0:
        return 0.0
    return dot_product / (magnitude_v1 * magnitude_v2)


class BM25Searcher:
    """
    Learning Note (Module 6 - Keyword Search):
    This is a simple Python implementation of BM25 (helped by AI for the math formula).
    Why we need this: Vector search is great for general meaning, but in legal documents
    we often look for exact article numbers (e.g., "Pasal 12") or specific legal terms.
    BM25 scores chunks based on exact word frequency.
    """
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b

    def score_chunks(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not query.strip() or not chunks:
            return []

        query_tokens = [w for w in re.findall(r"\b\w+\b", query.lower()) if len(w) > 1]
        if not query_tokens:
            return []

        N = len(chunks)
        doc_tokens_list = []
        doc_lens = []
        for c in chunks:
            tokens = [w for w in re.findall(r"\b\w+\b", c.get("content", "").lower()) if len(w) > 1]
            doc_tokens_list.append(tokens)
            doc_lens.append(len(tokens))

        avgdl = sum(doc_lens) / max(1, N)

        # Count how many chunks contain each query word
        df: Dict[str, int] = {}
        for qt in query_tokens:
            df[qt] = sum(1 for tokens in doc_tokens_list if qt in tokens)

        # Calculate BM25 score for each chunk
        scored = []
        for idx, c in enumerate(chunks):
            tokens = doc_tokens_list[idx]
            dl = doc_lens[idx]
            if dl == 0:
                continue

            tf: Dict[str, int] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1

            score = 0.0
            for qt in query_tokens:
                if qt not in tf:
                    continue
                n_qt = df[qt]
                idf = math.log(((N - n_qt + 0.5) / (n_qt + 0.5)) + 1.0)
                term_tf = tf[qt]
                numerator = term_tf * (self.k1 + 1.0)
                denominator = term_tf + self.k1 * (1.0 - self.b + self.b * (dl / max(1.0, avgdl)))
                score += idf * (numerator / denominator)

            if score > 0.0:
                item = dict(c)
                item["bm25_score"] = round(score, 4)
                scored.append(item)

        scored.sort(key=lambda x: x["bm25_score"], reverse=True)
        return scored


def reciprocal_rank_fusion(
    dense_results: List[Dict[str, Any]],
    sparse_results: List[Dict[str, Any]],
    k: int = 60,
) -> List[Dict[str, Any]]:
    """
    Learning Note (Module 6 - Reciprocal Rank Fusion / RRF):
    Combines the ranking from Vector Search (ChromaDB) and Keyword Search (BM25)
    into one unified list using the formula: RRF_score = sum(1 / (k + rank)).
    """
    fused_scores: Dict[str, float] = {}
    fused_items: Dict[str, Dict[str, Any]] = {}

    # 1. Add rankings from ChromaDB Vector Search
    for rank_idx, item in enumerate(dense_results, 1):
        cid = item["id"]
        rrf_contrib = 1.0 / (k + rank_idx)
        fused_scores[cid] = fused_scores.get(cid, 0.0) + rrf_contrib
        if cid not in fused_items:
            fused_items[cid] = dict(item)
        fused_items[cid]["vector_rank"] = rank_idx
        fused_items[cid]["vector_similarity"] = item.get("similarity", 0.0)

    # 2. Add rankings from BM25 Keyword Search
    for rank_idx, item in enumerate(sparse_results, 1):
        cid = item["id"]
        rrf_contrib = 1.0 / (k + rank_idx)
        fused_scores[cid] = fused_scores.get(cid, 0.0) + rrf_contrib
        if cid not in fused_items:
            fused_items[cid] = dict(item)
        fused_items[cid]["keyword_rank"] = rank_idx
        fused_items[cid]["bm25_score"] = item.get("bm25_score", 0.0)

    # 3. Sort by combined RRF score
    fused_list = []
    for cid, total_rrf in fused_scores.items():
        doc = fused_items[cid]
        doc["rrf_score"] = round(total_rrf, 5)
        doc["search_mode"] = "hybrid"
        fused_list.append(doc)

    fused_list.sort(key=lambda x: x["rrf_score"], reverse=True)
    return fused_list


BILINGUAL_DOMAIN_GLOSSARY: List[tuple[str, str]] = [
    # Legal & Regulatory (ID <-> EN)
    (r"\b(?:trademark|trademarks|brand\s+mark)\b", "merek pendaftaran merek hak atas merek label merek"),
    (r"\bmerek\b", "trademark brand registration mark"),
    (r"\b(?:patent|patents|invention)\b", "paten invensi pemegang paten paten sederhana"),
    (r"\bpaten\b", "patent invention holder"),
    (r"\b(?:registration\s+flow|registration\s+process|application\s+procedure|how\s+to\s+register|filing\s+procedure|steps\s+to\s+register)\b",
     "alur prosedur tahapan syarat dan tata cara permohonan pemeriksaan kelengkapan persyaratan pengumuman pemeriksaan substantif penerbitan sertifikat"),
    (r"\b(?:requirements|filing\s+requirements|application\s+requirements|prerequisites|eligibility)\b",
     "syarat permohonan persyaratan kelengkapan dokumen tanggal penerimaan pemohon"),
    (r"\b(?:well[- ]known\s+mark|famous\s+mark|similar\s+mark|bad\s+faith|rejection|refusal|rejected)\b",
     "merek terkenal persamaan pada pokoknya atau keseluruhannya itikad tidak baik permohonan ditolak tidak dapat didaftar"),
    (r"\b(?:penalty|penalties|sanction|sanctions|criminal|fine|imprisonment|infringement|violation)\b",
     "sanksi pidana ketentuan pidana denda penjara pelanggaran ganti rugi gugatan"),
    (r"\b(?:nuclear|radiation|liability|indemnity|batan)\b",
     "nuklir ketenaganukliran pertanggungjawaban kerugian nuklir instalasi nuklir batas tanggung jawab operator"),
    (r"\b(?:duration|validity|protection\s+period|renewal|extension)\b",
     "jangka waktu perlindungan masa berlaku perpanjangan 10 sepuluh tahun 20 dua puluh tahun"),
    (r"\b(?:article|section|chapter|clause|law|regulation|ministerial)\b",
     "pasal ayat bab bagian undang-undang peraturan menteri"),

    # KPI & Performance Presentation (ID <-> EN)
    (r"\b(?:kpi|indikator\s+kinerja|capaian|kinerja|target|realisasi|performa|pertumbuhan|kuartal)\b",
     "kpi key performance indicator metrics target actual achievement growth quarter q1 q2 q3 q4 okr scorecard"),
    (r"\b(?:key\s+performance|metrics|achievement|actual\s+vs\s+target|okr|scorecard|retention|churn|conversion|nps)\b",
     "kpi indikator kinerja utama target realisasi capaian retensi konversi kepuasan pelanggan"),

    # Client Presentation / Pitch Deck / Proposal (ID <-> EN)
    (r"\b(?:presentasi\s+klien|presentasi\s+client|proposal\s+klien|nilai\s+jual|solusi|jadwal|implementasi|biaya\s+proyek|paket\s+harga|studi\s+kasus)\b",
     "client presentation pitch deck value proposition solution architecture roadmap timeline milestones pricing tier deliverables case study roi"),
    (r"\b(?:client\s+presentation|pitch\s+deck|value\s+proposition|roadmap|timeline|milestone|deliverables|pricing|roi|executive\s+summary)\b",
     "presentasi klien nilai jual utama solusi peta jalan jadwal tahapan hasil kerja harga biaya ringkasan eksekutif"),

    # Inventory & Supply Chain (ID <-> EN)
    (r"\b(?:inventaris|stok|persediaan|barang|gudang|pemasok|pembelian\s+ulang|habis|menipis|harga\s+satuan|kuantitas)\b",
     "inventory stock warehouse item sku supplier reorder level low stock out of stock unit price quantity status"),
    (r"\b(?:inventory|stock|warehouse|sku|supplier|reorder|low\s+stock|out\s+of\s+stock|unit\s+price|quantity)\b",
     "inventaris stok persediaan gudang kode barang pemasok batas pesan ulang stok menipis habis harga satuan jumlah"),

    # Financial & Business Report (ID <-> EN)
    (r"\b(?:pendapatan|laba|keuntungan|biaya|anggaran|arus\s+kas|neraca|margin)\b",
     "revenue profit net income cost expense budget cash flow balance sheet margin ebitda"),
    (r"\b(?:revenue|profit|net\s+income|expense|budget|cash\s+flow|balance\s+sheet|margin|ebitda)\b",
     "pendapatan laba bersih biaya pengeluaran anggaran arus kas neraca margin keuangan"),
]


def detect_query_language_and_mode(query: str) -> Dict[str, Any]:
    """
    Detect:
    1. What language the user wants the response in ('en' or 'id'):
       - Checks explicit language requests first ('in English', 'dalam Bahasa Indonesia', 'translate to English', etc.)
       - Otherwise detects the language of the user's prompt itself.
    2. Whether the user is asking for document translation or language modernization
       ('terjemahkan ke bahasa yang lebih baru', 'bahasa modern', 'translate', etc.).
    """
    if not query or not query.strip():
        return {"response_lang": "id", "is_translation": False, "is_modernization": False}

    q_lower = query.lower().strip()

    is_modernization = bool(
        re.search(
            r"\b(?:bahasa\s+(?:yang\s+)?(?:lebih\s+)?(?:baru|modern|mudah\s+dipahami|sederhana|sehari-hari|populer|masa\s+kini|kontemporer|kekinian)|"
            r"moderni[sz]e|plain\s+language|simplify|simplified\s+language|contemporary\s+language|easier\s+to\s+understand)\b",
            q_lower,
        )
    )
    is_translation = is_modernization or bool(
        re.search(
            r"\b(?:terjemahkan|terjemahan|menerjemahkan|alih\s+bahasa|translate|translation|translated)\b",
            q_lower,
        )
    )

    # 1. Check explicit target language instructions at the end or inside the prompt
    explicit_en = bool(
        re.search(
            r"\b(?:in\s+english|into\s+english|to\s+english|use\s+english|answer\s+in\s+english|respond\s+in\s+english|"
            r"explain\s+in\s+english|ke\s+(?:dalam\s+)?bahasa\s+inggris|dalam\s+bahasa\s+inggris|gunakan\s+bahasa\s+inggris)\b",
            q_lower,
        )
    )
    explicit_id = bool(
        re.search(
            r"\b(?:dalam\s+bahasa\s+indonesia|ke\s+(?:dalam\s+)?bahasa\s+indonesia|gunakan\s+bahasa\s+indonesia|"
            r"in\s+indonesian|into\s+indonesian|to\s+indonesian|in\s+bahasa\s+indonesia|bahasa\s+yang\s+lebih\s+baru)\b",
            q_lower,
        )
    )

    if explicit_en and not explicit_id:
        return {"response_lang": "en", "is_translation": is_translation, "is_modernization": is_modernization}
    if explicit_id and not explicit_en:
        return {"response_lang": "id", "is_translation": is_translation, "is_modernization": is_modernization}

    # 2. Otherwise detect the prompt's primary language
    id_markers = re.findall(
        r"\b(?:apa|apakah|bagaimana|mengapa|kenapa|dimana|kapan|siapa|berapa|tolong|mohon|coba|bisakah|"
        r"jelaskan|rangkum|ringkas|bandingkan|terjemahkan|sebutkan|berikan|cari|cek|yang|dan|di|ke|dari|"
        r"untuk|dengan|pada|dalam|adalah|menurut|berdasarkan|dokumen|peraturan|undang|pasal|syarat|alur|"
        r"inventaris|stok|presentasi|klien|capaian|bahasa|baru|saya|aku|kamu|ini|itu|tersebut|tidak|atau)\b",
        q_lower,
    )
    en_markers = re.findall(
        r"\b(?:what|how|why|where|when|who|which|can|could|would|should|please|explain|summarize|compare|"
        r"translate|tell|give|list|show|does|is|are|was|were|have|has|the|of|in|for|with|from|based|"
        r"according|document|documents|trademark|patent|registration|flow|process|requirements|inventory|"
        r"stock|presentation|client|kpi|target|performance|modernize|simplify|between|about|this|that)\b",
        q_lower,
    )

    is_detailed = bool(
        re.search(
            r"\b(?:detail|mendalam|rinci|rincian|lengkap|komprehensif|jelaskan\s+(?:secara\s+)?lengkap|penjelasan\s+mendalam|in[- ]depth|thorough|detailed|comprehensive|deeply|fully)\b",
            q_lower,
        )
    )

    is_concise = not is_detailed and bool(
        re.search(
            r"\b(?:ringkas(?:\s+saja)?|singkat(?:\s+saja)?|brief|concise|short|pendek|garis\s+besar(?:nya)?|quick\s+summary|overview\s+only)\b",
            q_lower,
        )
    )

    response_lang = "en" if len(en_markers) > len(id_markers) else "id"
    return {
        "response_lang": response_lang,
        "is_translation": is_translation,
        "is_modernization": is_modernization,
        "is_concise": is_concise,
        "is_detailed": is_detailed,
    }


class RetrievalService:
    """
    Main retrieval service connecting local ChromaDB (for vector search)
    and local SQLite (for BM25 keyword search and full-document reading).
    """
    def __init__(self):
        self._bm25 = BM25Searcher()

    async def store_document_chunks(
        self,
        document_id: str,
        user_id: Optional[str],
        chunks: List[str],
        embeddings: List[List[float]],
        document_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Save document chunks and their 768-dim embeddings to local ChromaDB and SQLite.
        """
        doc_meta = document_metadata or {}
        records: List[Dict[str, Any]] = []

        for idx, (chunk_text, emb) in enumerate(zip(chunks, embeddings)):
            chunk_id = str(uuid.uuid4())
            record = {
                "id": chunk_id,
                "document_id": document_id,
                "user_id": user_id or "local-user",
                "chunk_index": idx,
                "content": chunk_text,
                "metadata": {
                    "chunk_index": idx,
                    "filename": doc_meta.get("filename", "unknown"),
                    "doc_title": doc_meta.get("title") or doc_meta.get("filename"),
                    "doc_type": doc_meta.get("document_type") or doc_meta.get("type", "general"),
                    "keywords": doc_meta.get("keywords", []),
                    "language": doc_meta.get("language", "id"),
                    **doc_meta,
                },
                "embedding": emb,
            }
            records.append(record)

        # Save to persistent ChromaDB + SQLite
        local_db_service.store_chunks_and_vectors(records)
        return records

    def _detect_explicit_doc_filter(
        self,
        query: str,
        existing_filter: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        If the user didn't select a UI document filter, check if their prompt explicitly names
        one specific document in the database (e.g., 'menurut Permenkum Nomor 5 Tahun 2026'
        or 'menurut Perka BATAN Nomor 4 Tahun 2016').
        """
        if existing_filter and existing_filter.get("document_id"):
            return existing_filter

        q_lower = query.lower()
        docs = local_db_service.list_documents()
        if len(docs) <= 1:
            return existing_filter

        matched_ids: List[str] = []
        for d in docs:
            doc_id = d["id"]
            fn_lower = d.get("filename", "").lower()
            fn_stem = fn_lower.rsplit(".", 1)[0]
            title_lower = (d.get("title") or "").lower()

            # Check direct filename stem or specific regulation number/year patterns
            is_match = False
            if fn_stem and fn_stem in q_lower:
                is_match = True
            elif title_lower and title_lower in q_lower:
                is_match = True
            else:
                # Extract regulation number & year from filename (e.g. "no 5 tahun 2026" or "nomor 15 tahun 2001")
                num_year = re.search(r"(?:no(?:mor)?\.?\s*(\d+)\s*tahun\s*(\d{4}))", fn_lower + " " + title_lower)
                if num_year:
                    num, yr = num_year.group(1), num_year.group(2)
                    if re.search(rf"\b(?:no(?:mor)?\.?\s*)?{num}\s*(?:tahun|/)\s*{yr}\b", q_lower):
                        is_match = True
                if "batan" in fn_lower and "batan" in q_lower:
                    is_match = True

            if is_match:
                matched_ids.append(doc_id)

        # Only auto-filter if the user specifically named exactly ONE document
        if len(matched_ids) == 1:
            merged = dict(existing_filter or {})
            merged["document_id"] = matched_ids[0]
            logger.info(f"Auto-scoped retrieval to explicitly mentioned document_id={matched_ids[0]}")
            return merged

        return existing_filter

    def _clean_and_expand_rag_query(self, raw_query: str) -> tuple[str, str]:
        """
        1. Strip conversational/source-grounding preambles ('Okay, berdasarkan dokumen yang aku berikan...',
           'Based on the documents provided...') for cleaner dense vector embedding.
        2. Expand cross-lingual (ID <-> EN) and multi-domain terms (Legal, Inventory, KPI, Client Presentation,
           Financial) for both dense vector and BM25 keyword search.
        Returns (clean_dense_query, expanded_bm25_query).
        """
        cleaned = raw_query.strip()
        preambles = [
            r"^(?:okay|oke|ok|baik|nah|hey\s+chat|halo|hai|hello|hi|sekarang|jadi|lalu|kemudian|now|so)[\s,.:!\-]+",
            r"^(?:sekarang\s+)?(?:berdasarkan|mengacu\s+pada|menurut|dari|pada|di\s+dalam)\s+(?:semua\s+|seluruh\s+|ketiga\s+|kedua\s+)?(?:dokumen|file|peraturan|uu|undang-undang|presentasi|laporan|data)(?:\s+yang\s+(?:aku|saya|telah|sudah)\s+(?:berikan|upload|unggah|kasih|kirim)|\s+yang\s+ada|\s+tersebut|\s+ini)?[\s,.:;\-]+",
            r"^(?:based\s+on|according\s+to|from|in)\s+(?:the\s+|all\s+|these\s+)?(?:provided\s+|uploaded\s+)?(?:documents|files|presentations|reports|laws|regulations)(?:\s+that\s+i\s+(?:provided|uploaded|shared|gave))?[\s,.:;\-]+",
        ]
        for _ in range(2):
            for pat in preambles:
                cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE).strip()

        if len(cleaned) < 3:
            cleaned = raw_query.strip()

        expansions: List[str] = [cleaned]
        dense_bridges: List[str] = [cleaned]

        # Statutory procedural & substantive expansions
        if re.search(r"\b(?:alur|prosedur|tahapan|tata\s+cara|proses|mekanisme|langkah|registration\s+flow|registration\s+process|application\s+procedure|how\s+to\s+register|steps\s+to\s+register)\b", cleaned, re.IGNORECASE):
            expansions.append(
                "BAB II syarat dan tata cara permohonan pemeriksaan kelengkapan persyaratan tanggal penerimaan "
                "pengumuman permohonan berita resmi merek keberatan sanggahan BAB III pemeriksaan substantif "
                "pendaftaran merek penerbitan sertifikat merek"
            )
            dense_bridges.append("syarat dan tata cara permohonan pemeriksaan substantif pendaftaran merek")

        if re.search(r"\b(?:syarat|persyaratan|kelengkapan|requirements|filing\s+requirements|prerequisites)\b", cleaned, re.IGNORECASE):
            expansions.append(
                "BAB II Bagian Kesatu Syarat Permohonan tanggal bulan tahun nama alamat kewarganegaraan "
                "label merek kelas jenis barang jasa tanda tangan bukti pembayaran biaya"
            )

        if re.search(r"\b(?:merek\s+terkenal|mirip|persamaan|ditolak|itikad\s+tidak\s+baik|well[- ]known\s+mark|famous\s+mark|bad\s+faith|rejected|refusal)\b", cleaned, re.IGNORECASE):
            expansions.append(
                "Pasal 4 Pasal 5 Pasal 6 permohonan ditolak persamaan pada pokoknya atau keseluruhannya "
                "merek terkenal milik pihak lain barang sejenis tidak sejenis itikad tidak baik kriteria pemeriksaan substantif"
            )

        # Bidirectional ID <-> EN glossary only when cross-lingual markers or terms are present
        is_cross_lingual_query = bool(
            re.search(
                r"\b(?:english|inggris|terjemahkan|translate|patent\s+act|deck|pitch|kpi|inventory|presentation|revenue|target|stock|how\s+to|what\s+is|explain\s+in)\b",
                cleaned,
                re.IGNORECASE,
            )
        )
        if is_cross_lingual_query:
            for pattern, bilingual_terms in BILINGUAL_DOMAIN_GLOSSARY:
                if re.search(pattern, cleaned, re.IGNORECASE):
                    expansions.append(bilingual_terms)
                    dense_bridges.append(bilingual_terms)

        clean_dense = " ".join(dense_bridges)
        expanded_bm25 = " ".join(expansions)
        return clean_dense, expanded_bm25

    def _ensure_procedural_stage_coverage(
        self,
        query: str,
        reranked_results: List[Dict[str, Any]],
        candidate_pool: List[Dict[str, Any]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """
        When a user asks for a registration flow ('alur', 'prosedur', 'tahapan', 'registration flow', 'procedure'),
        ensure the returned chunks cover the key chronological stages of the legal process
        (1. Syarat & Pengajuan Permohonan, 2. Pemeriksaan Kelengkapan/Pengumuman, 3. Pemeriksaan Substantif & Sertifikat).
        """
        if not re.search(
            r"\b(?:alur|prosedur|tahapan|tata\s+cara|proses|mekanisme|registration\s+flow|registration\s+process|application\s+procedure|how\s+to\s+register|steps\s+to\s+register)\b",
            query,
            re.IGNORECASE,
        ):
            return reranked_results[:top_k]

        q_lower = query.lower()
        asks_merek = ("merek" in q_lower or "trademark" in q_lower) and ("paten" not in q_lower and "patent" not in q_lower)

        # Filter pool to relevant domain
        domain_pool = [
            c for c in candidate_pool
            if not (asks_merek and "paten" in (c.get("metadata", {}).get("filename", "").lower()))
        ]
        if not domain_pool:
            domain_pool = candidate_pool

        stage_patterns = [
            ("stage_1_syarat_permohonan", r"\bbab\s+ii\b.*?\bsyarat\s+dan\s+tata\s+cara\s+permohonan\b|\bbagian\s+kesatu\s+syarat\s+permohonan\b"),
            ("stage_2_pemeriksaan_formalitas", r"\bpemeriksaan\s+kelengkapan\s+persyaratan\b|\bdokumen\s+persyaratan\s+dinyatakan\s+lengkap\b"),
            ("stage_3_pengumuman_keberatan", r"\bpengumuman\s+permohonan\b|\bdiumumkan\s+dalam\s+berita\s+resmi\s+merek\b|\bkeberatan\s+dan/atau\s+sanggahan\b"),
            ("stage_4_pemeriksaan_substantif", r"\bbab\s+iii\b.*?\bpemeriksaan\s+substantif\b|\btata\s+cara\s+pemeriksaan\s+substantif\b"),
            ("stage_5_sertifikat_pendaftaran", r"\bditerbitkan\s+sertifikat\s+merek\b|\bpenerbitan\s+sertifikat\b|\bdaftar\s+umum\s+merek\b"),
        ]

        selected_by_id: Dict[str, Dict[str, Any]] = {}
        # First, find the best matching chunk for each stage
        for stage_name, pat in stage_patterns:
            for c in domain_pool:
                content_norm = re.sub(r"\s+", " ", c.get("content", "")).lower()
                if re.search(pat, content_norm) and c["id"] not in selected_by_id:
                    item = dict(c)
                    item["similarity"] = item.get("similarity") or 0.85
                    item["rerank_score"] = max(item.get("rerank_score") or 0.0, 0.92)
                    item["rerank_reason"] = f"Stage coverage ({stage_name})"
                    selected_by_id[c["id"]] = item
                    break

        # Fill remaining slots up to top_k with top reranked results
        for r in reranked_results:
            if len(selected_by_id) >= top_k:
                break
            if r["id"] not in selected_by_id:
                selected_by_id[r["id"]] = r

        final_list = list(selected_by_id.values())[:top_k]
        # Sort by document and chunk_index so the LLM reads the procedure in chronological order
        final_list.sort(key=lambda x: (str(x.get("document_id", "")), int(x.get("chunk_index", 0))))
        for idx, item in enumerate(final_list, 1):
            item["rerank_rank"] = idx
        return final_list

    async def retrieve_relevant_chunks(
        self,
        query: str,
        user_id: Optional[str] = None,
        top_k: int = 5,
        threshold: float = 0.25,
        metadata_filter: Optional[Dict[str, Any]] = None,
        search_mode: str = "hybrid",  # "hybrid" | "vector" | "keyword"
        rerank: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Hybrid Search Pipeline (Module 6):
        1. Auto-detect explicit document mention in query if no filter was manually set.
        2. Vector Search using local ChromaDB (HNSW index with 768-dim Ollama embeddings).
        3. Keyword Search using BM25 over chunks stored in local SQLite.
        4. Combine results with Reciprocal Rank Fusion (RRF) + Top Dense/Sparse Union.
        5. Rerank and ensure procedural stage coverage for flow queries.
        """
        if not query or not query.strip():
            return []

        effective_filter = self._detect_explicit_doc_filter(query, metadata_filter)
        clean_query, bm25_query = self._clean_and_expand_rag_query(query)
        search_mode = (search_mode or "hybrid").lower()
        candidate_pool = local_db_service.get_all_chunks(metadata_filter=effective_filter)

        vector_results: List[Dict[str, Any]] = []
        keyword_results: List[Dict[str, Any]] = []

        # 1. Dense Vector Search via ChromaDB (or SQLite fallback)
        if search_mode in ["hybrid", "vector"]:
            try:
                query_embedding = await embedding_service.get_embedding(clean_query)
                chroma_hits = local_db_service.query_chroma_vectors(
                    query_embedding=query_embedding,
                    top_k=max(top_k * 8, 50),
                    threshold=threshold,
                    metadata_filter=effective_filter,
                )
                if chroma_hits is not None:
                    vector_results = chroma_hits
                else:
                    for c in candidate_pool:
                        sim = cosine_similarity(query_embedding, c.get("embedding", []))
                        if sim >= threshold:
                            vector_results.append({
                                "id": c["id"],
                                "document_id": c["document_id"],
                                "chunk_index": c.get("chunk_index", 0),
                                "content": c["content"],
                                "metadata": c.get("metadata", {}),
                                "similarity": round(sim, 4),
                            })
                    vector_results.sort(key=lambda x: x["similarity"], reverse=True)
            except Exception as e:
                logger.error(f"Vector search step failed: {e}")

        # 2. Sparse Keyword Search via BM25
        if search_mode in ["hybrid", "keyword"]:
            try:
                keyword_results = self._bm25.score_chunks(bm25_query, candidate_pool)
            except Exception as e:
                logger.error(f"BM25 keyword search step failed: {e}")

        # 3. Combine results based on selected search mode
        fused_candidates: List[Dict[str, Any]] = []
        if search_mode == "hybrid":
            if vector_results and keyword_results:
                fused_candidates = reciprocal_rank_fusion(vector_results, keyword_results, k=60)
            elif vector_results:
                fused_candidates = [
                    dict(v, search_mode="vector", rrf_score=round(v["similarity"] * 0.03, 5))
                    for v in vector_results
                ]
            else:
                fused_candidates = [
                    dict(k, search_mode="keyword", rrf_score=round(min(0.03, k.get("bm25_score", 0) * 0.005), 5))
                    for k in keyword_results
                ]
        elif search_mode == "vector":
            fused_candidates = [dict(v, search_mode="vector") for v in vector_results]
        elif search_mode == "keyword":
            fused_candidates = [dict(k, search_mode="keyword") for k in keyword_results]

        # 4. Rerank top candidates (including union of top RRF + top BM25 + top Vector so exact statutory hits are never missed)
        if rerank and fused_candidates:
            pool_map: Dict[str, Dict[str, Any]] = {}
            for item in fused_candidates[:20]:
                pool_map[item["id"]] = item
            for item in keyword_results[:12]:
                if item["id"] not in pool_map:
                    pool_map[item["id"]] = dict(item, search_mode=search_mode)
            for item in vector_results[:10]:
                if item["id"] not in pool_map:
                    pool_map[item["id"]] = dict(item, search_mode=search_mode)

            pool_to_rerank = list(pool_map.values())
            reranked = reranker_service.rerank(clean_query, pool_to_rerank, top_k=max(top_k, 8))
            final_results = self._ensure_procedural_stage_coverage(
                query=clean_query,
                reranked_results=reranked,
                candidate_pool=candidate_pool,
                top_k=top_k,
            )
            logger.info(f"Retrieved & reranked {len(final_results)} chunks from local DB (mode={search_mode}).")
            return final_results

        return fused_candidates[:top_k]

    def delete_document_chunks(self, document_id: str) -> int:
        """
        Delete all chunks and embeddings for a document from ChromaDB and SQLite.
        """
        return local_db_service.delete_document_and_chunks(document_id, delete_doc_record=False)

    def format_rag_context(self, chunks: List[Dict[str, Any]]) -> str:
        """
        Format retrieved chunks into a clean text block to inject into the LLM system prompt.
        """
        if not chunks:
            return ""

        context_lines = [
            "### RETRIEVED KNOWLEDGE BASE CONTEXT (Local ChromaDB + BM25 Hybrid Search)",
            "Gunakan fakta di bawah untuk menjawab. Cantumkan sitasi sebaris nomor seperti [1], [2] (merujuk pada Kutipan Dokumen 1, 2) tepat di akhir kalimat klaim/fakta yang Anda ambil dari dokumen.",
            "Setiap klaim hukum, pasal, syarat, atau data wajib bersumber dari kutipan di bawah.",
            "---",
        ]
        for idx, chunk in enumerate(chunks, 1):
            meta = chunk.get("metadata", {})
            filename = meta.get("filename", "Document")
            doc_title = meta.get("doc_title") or meta.get("title") or filename
            doc_type = meta.get("doc_type")
            content_str = chunk.get("content", "").strip()

            # Detect exact location (Page X, Slide Y, Sheet Z, or Pasal N)
            loc_label = ""
            page_val = meta.get("page") or meta.get("page_number")
            if page_val:
                loc_label = f"Page {page_val}"
            else:
                page_match = re.search(r"---\s*(Page\s*\d+)\s*---", content_str, re.IGNORECASE)
                if page_match:
                    loc_label = page_match.group(1).title()
                else:
                    slide_match = re.search(r"---\s*(Slide\s*\d+)\s*---", content_str, re.IGNORECASE)
                    if slide_match:
                        loc_label = slide_match.group(1).title()
                    else:
                        sheet_match = re.search(r"###\s*Worksheet:\s*([^\n]+)", content_str, re.IGNORECASE)
                        if sheet_match:
                            loc_label = f"Sheet {sheet_match.group(1).strip()}"
                        else:
                            pasal_match = re.search(r"\b(Pasal\s+\d+[A-Za-z]?)\b", content_str, re.IGNORECASE)
                            if pasal_match:
                                loc_label = pasal_match.group(1).title()

            loc_str = f" ({loc_label} - {doc_title})" if loc_label else f" ({doc_title})"
            mode = chunk.get("search_mode", "hybrid")
            rerank_score = chunk.get("rerank_score")

            stat_str = f" [rerank: {rerank_score:.0%}]" if rerank_score else ""

            context_lines.append(f"[Kutipan Dokumen {idx}{loc_str}{stat_str}]")
            context_lines.append(content_str)
            context_lines.append("---")

        return "\n".join(context_lines)

    async def get_document_chunks_ordered(self, document_id: str) -> List[Dict[str, Any]]:
        """
        Fetch all chunks for a document in reading order (0..N) from local SQLite.
        Used by Sub-Agents when auditing or comparing full legal documents.
        """
        return local_db_service.get_document_chunks_ordered(document_id)

    async def get_document_complete_text(self, document_id: str) -> str:
        """Join all chunks in order into the full document text."""
        chunks = await self.get_document_chunks_ordered(document_id)
        return "\n\n".join(c.get("content", "") for c in chunks).strip()

    def get_all_documents_metadata(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return a summary list of all documents stored in the local database."""
        docs = local_db_service.list_documents()
        return [
            {
                "id": d["id"],
                "filename": d["filename"],
                "title": d.get("title") or d["filename"],
                "doc_type": d.get("doc_type", "general"),
                "chunk_count": d.get("chunk_count", 0),
            }
            for d in docs
        ]


retrieval_service = RetrievalService()
