import re
import math
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

STOP_WORDS = {
    "a", "an", "the", "in", "on", "at", "to", "for", "of", "with", "by", "from",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "and", "or", "but", "if", "then", "else", "when",
    "what", "which", "who", "whom", "this", "that", "these", "those",
    "dan", "di", "ke", "dari", "ini", "itu", "yang", "untuk", "pada", "adalah",
    "dengan", "dalam", "sebagai", "oleh", "atau", "jika", "karena", "maka"
}


def tokenize(text: str) -> List[str]:
    """Tokenize and normalize text into alphanumeric words."""
    return [w for w in re.findall(r"\b\w+\b", text.lower()) if len(w) > 1]


class RerankerService:
    """
    Learning Note (Module 6 - Reranker, assisted by AI):
    After we get candidate chunks from Vector Search (ChromaDB) + BM25,
    this reranker re-scores them to push the most relevant chunks to the top based on:
    1. Exact phrase match with the user's query.
    2. How many query words appear in the chunk.
    3. Whether the query matches the document title or keywords.
    """

    def compute_cross_relevance(self, query: str, chunk: Dict[str, Any]) -> Dict[str, Any]:
        content = chunk.get("content", "")
        meta = chunk.get("metadata", {})
        doc_title = meta.get("doc_title") or meta.get("title") or meta.get("filename", "")
        keywords = meta.get("keywords", [])

        content_lower = content.lower()
        query_lower = query.lower()
        query_tokens = [t for t in tokenize(query) if t not in STOP_WORDS]

        if not query_tokens:
            query_tokens = tokenize(query)

        if not query_tokens:
            return {"score": 0.5, "reason": "Default semantic score"}

        # 1. Exact phrase match bonus
        exact_match_score = 0.0
        if len(query.strip()) > 5 and query_lower in content_lower:
            exact_match_score = 0.40
        else:
            # Check for multi-word sub-phrases (n-grams of size 2-3)
            q_words = query_lower.split()
            subphrases = [" ".join(q_words[i:i+2]) for i in range(len(q_words)-1)]
            for sp in subphrases:
                if len(sp) > 5 and sp in content_lower:
                    exact_match_score = max(exact_match_score, 0.25)
                    break

        # 2. Term coverage score (fraction of query terms present in chunk)
        content_tokens_set = set(tokenize(content))
        matched_terms = [t for t in query_tokens if t in content_tokens_set]
        coverage_ratio = len(matched_terms) / len(query_tokens)
        term_coverage_score = coverage_ratio * 0.35

        # 3. Term frequency / density in content
        tf_count = sum(content_tokens_set.__contains__(t) for t in query_tokens)
        density_score = min(0.15, (tf_count / (len(tokenize(content)) + 10)) * 5.0)

        # 4. Title & Keywords bonus + Domain alignment (e.g. Merek vs Paten)
        title_lower = doc_title.lower()
        kw_str_lower = " ".join(str(k).lower() for k in keywords)
        title_match = any(t in title_lower for t in query_tokens)
        kw_match = any(t in kw_str_lower for t in query_tokens)
        meta_bonus = (0.12 if title_match else 0.0) + (0.06 if kw_match else 0.0)

        # Penalize cross-domain mismatch if query exclusively asks about 'merek/trademark' vs 'paten/patent'
        asks_merek = ("merek" in query_tokens or "trademark" in query_tokens or "trademarks" in query_tokens) and (
            "paten" not in query_tokens and "patent" not in query_tokens
        )
        asks_paten = ("paten" in query_tokens or "patent" in query_tokens or "patents" in query_tokens) and (
            "merek" not in query_tokens and "trademark" not in query_tokens
        )
        if asks_merek and "paten" in (title_lower + " " + kw_str_lower) and "merek" not in title_lower:
            meta_bonus -= 0.25
        elif asks_paten and "merek" in (title_lower + " " + kw_str_lower) and "paten" not in title_lower:
            meta_bonus -= 0.25

        # Multi-domain bonus when query domain matches chunk's doc_type (inventory, kpi_report, presentation, financial, legal)
        doc_type_lower = str(meta.get("doc_type") or meta.get("document_type") or "").lower()
        if doc_type_lower == "inventory" and re.search(r"\b(?:inventaris|inventory|stok|stock|sku|gudang|warehouse|reorder|barang)\b", query_lower):
            meta_bonus += 0.20
        elif doc_type_lower == "kpi_report" and re.search(r"\b(?:kpi|kinerja|performance|target|realisasi|actual|q[1-4]|kuartal|okr|metrics)\b", query_lower):
            meta_bonus += 0.20
        elif doc_type_lower == "presentation" and re.search(r"\b(?:presentasi|presentation|klien|client|pitch|deck|slide|roadmap|proposal|solusi|pricing)\b", query_lower):
            meta_bonus += 0.20
        elif doc_type_lower == "financial" and re.search(r"\b(?:keuangan|financial|revenue|pendapatan|laba|profit|budget|anggaran|ebitda)\b", query_lower):
            meta_bonus += 0.20

        # 5. Procedural / Flow & Substantive Legal Criteria Bonus (Bilingual ID + EN)
        procedural_bonus = 0.0
        is_procedural_query = bool(
            re.search(
                r"\b(?:alur|prosedur|tahapan|tata\s+cara|proses|mekanisme|langkah|registration\s+flow|registration\s+process|application\s+procedure|how\s+to\s+register|steps\s+to\s+register)\b",
                query_lower,
            )
        )
        is_syarat_query = bool(
            re.search(
                r"\b(?:syarat|persyaratan|kelengkapan|dokumen\s+permohonan|pengajuan|requirements|filing\s+requirements|prerequisites)\b",
                query_lower,
            )
        )
        is_rejection_case_query = bool(
            re.search(
                r"\b(?:merek\s+terkenal|mirip|persamaan|ditolak|diterima|itikad\s+tidak\s+baik|tidak\s+dapat\s+didaftar|well[- ]known\s+mark|famous\s+mark|similar\s+mark|bad\s+faith|rejected|refusal)\b",
                query_lower,
            )
        )

        if is_procedural_query or is_syarat_query:
            statutory_flow_markers = [
                r"\bbab\s+ii\b",
                r"\bbab\s+iii\b",
                r"\btata\s+cara\s+permohonan\b",
                r"\bsyarat\s+dan\s+tata\s+cara\b",
                r"\bsyarat\s+permohonan\b",
                r"\bpemeriksaan\s+kelengkapan\b",
                r"\bpemeriksaan\s+substantif\b",
                r"\btata\s+cara\s+pemeriksaan\b",
                r"\bpengumuman\s+permohonan\b",
                r"\bdiumumkan\s+dalam\s+berita\s+resmi\b",
                r"\bpenerbitan\s+sertifikat\b",
                r"\bsertifikat\s+merek\b",
                r"\btanggal\s+penerimaan\b",
                r"\blabel\s+merek\b",
            ]
            hit_markers = sum(1 for pat in statutory_flow_markers if re.search(pat, content_lower))
            if hit_markers > 0:
                procedural_bonus += min(0.35, hit_markers * 0.14)

            # Strongly penalize Transitional/Closing/Repeal provisions (Ketentuan Peralihan/Penutup)
            # and Revocation/Transfer provisions when user asks for registration flow or filing requirements
            if re.search(
                r"\b(?:ketentuan\s+penutup|ketentuan\s+peralihan|pada\s+saat\s+peraturan\s+menteri\s+ini\s+mulai\s+berlaku|"
                r"dicabut\s+dan\s+dinyatakan\s+tidak\s+berlaku|penghapusan\s+pendaftaran|pembatalan\s+pendaftaran|"
                r"pengalihan\s+hak\s+atas\s+merek|perpanjangan\s+jangka\s+waktu)\b",
                content_lower,
            ) and not re.search(r"\b(?:bab\s+ii|bab\s+iii|syarat\s+permohonan|tata\s+cara\s+pemeriksaan\s+substantif)\b", content_lower):
                procedural_bonus -= 0.30

        if is_rejection_case_query:
            rejection_markers = [
                r"\bmerek\s+terkenal\b",
                r"\bpersamaan\s+pada\s+pokoknya\b",
                r"\bitikad\s+tidak\s+baik\b",
                r"\bpermohonan\s+ditolak\b",
                r"\btidak\s+dapat\s+didaftar\b",
                r"\bkriteria\s+pemeriksaan\s+substantif\b",
                r"\bbarang\s+dan/atau\s+jasa\s+yang\s+tidak\s+sejenis\b",
            ]
            hit_rej = sum(1 for pat in rejection_markers if re.search(pat, content_lower))
            if hit_rej > 0:
                procedural_bonus += min(0.35, hit_rej * 0.14)

        # 6. Base score from previous retrieval (RRF or Vector)
        base_retrieval_signal = 0.0
        if "rrf_score" in chunk:
            base_retrieval_signal = min(0.20, chunk["rrf_score"] * 5.0)
        elif "similarity" in chunk:
            base_retrieval_signal = chunk["similarity"] * 0.20

        raw_score = (
            exact_match_score
            + term_coverage_score
            + density_score
            + meta_bonus
            + procedural_bonus
            + base_retrieval_signal
        )
        normalized_score = min(1.0, max(0.05, round(raw_score, 4)))

        # Generate descriptive reason
        reasons = []
        if procedural_bonus >= 0.10:
            reasons.append("Statutory provision match")
        if exact_match_score >= 0.3:
            reasons.append("Exact phrase match")
        elif exact_match_score > 0:
            reasons.append("Key phrase alignment")
        if coverage_ratio >= 0.75:
            reasons.append("High query coverage")
        elif coverage_ratio >= 0.5:
            reasons.append("Partial term coverage")
        if title_match:
            reasons.append("Title match")
        if not reasons:
            reasons.append("Semantic similarity")

        return {
            "score": normalized_score,
            "reason": " + ".join(reasons),
        }

    def rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Rerank retrieved candidates and return the top_k best matching chunks.
        """
        if not candidates or not query.strip():
            return candidates[:top_k]

        scored_candidates = []
        for c in candidates:
            cross_eval = self.compute_cross_relevance(query, c)
            item = dict(c)
            item["rerank_score"] = cross_eval["score"]
            item["rerank_reason"] = cross_eval["reason"]
            scored_candidates.append(item)

        # Sort descending by rerank score
        scored_candidates.sort(key=lambda x: x["rerank_score"], reverse=True)

        for rank_idx, item in enumerate(scored_candidates, 1):
            item["rerank_rank"] = rank_idx

        return scored_candidates[:top_k]


reranker_service = RerankerService()
