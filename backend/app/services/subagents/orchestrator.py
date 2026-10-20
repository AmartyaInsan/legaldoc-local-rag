import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from app.services.retrieval import retrieval_service
from app.services.subagents.analyst import DocumentAnalystSubAgent, clean_boilerplate_signatures
from app.services.subagents.comparator import DocumentComparatorSubAgent
from app.core.config import settings

logger = logging.getLogger(__name__)

DEEP_ANALYSIS_TRIGGERS = [
    r"\banalisis (?:mendalam|menyeluruh|komprehensif|lengkap|kritis)\b",
    r"\bdeep (?:analysis|dive|audit|review)\b",
    r"\bfull[- ]document\b",
    r"\brangkum(?:kan)? seluruh (?:isi|dokumen|file|laporan|presentasi)\b",
    r"\bringkas(?:kan)? seluruh (?:isi|dokumen|file|laporan|presentasi)\b",
    r"\bsummarize (?:the )?(?:entire|whole|full) (?:document|file|presentation|report)\b",
    r"\bdari awal (?:sampai|hingga) akhir\b",
    r"\baudit (?:dokumen|kepatuhan|risiko|lengkap|menyeluruh|inventaris|kpi)\b",
    r"\bringkasan eksekutif\b",
    r"\bexecutive (?:report|summary)\b",
    r"\bcomprehensive (?:audit|summary|review)\b",
    r"\bswot\b",
    r"\bbedah (?:dokumen|isi|file|presentasi)\b",
    r"\bekstrak semua (?:kesimpulan|temuan|risiko|rekomendasi|kpi)\b",
    r"\blaporan (?:lengkap|audit|komprehensif)\b",
    r"\btelaah (?:menyeluruh|lengkap|kritis)\b",
    r"\bterjemahkan seluruh (?:isi|dokumen|file|presentasi)\b",
    r"\btranslate (?:the )?(?:entire|whole|full) (?:document|file|presentation)\b",
]

COMPARISON_TRIGGERS = [
    r"\bbandingkan\b",
    r"\bmembandingkan\b",
    r"\bperbandingan\b",
    r"\bkomparasi\b",
    r"\bkomparatif\b",
    r"\bcompare\b",
    r"\bcomparison\b",
    r"\bcomparative\b",
    r"\bperbedaan (?:antara|kedua|ketiga|semua|tiap|masing-masing)\b",
    r"\bpersamaan dan perbedaan\b",
    r"\bdifference(?:s)? between\b",
    r"\bsimilarities and differences\b",
    r"\bmatriks perbandingan\b",
    r"\bcomparison matrix\b",
    r"\bversus\b",
    r"\bvs\.?\b",
]

MULTI_DOC_SUMMARY_TRIGGERS = [
    r"\bdetail inti (?:saja )?(?:untuk )?(?:tiap|setiap|masing-masing|semua) dokumen\b",
    r"\b(?:rangkum|ringkas|jelaskan|analisis) (?:satu per satu|tiap|setiap|masing-masing) dokumen\b",
    r"\bcek semua dokumen.*berikan detail inti\b",
    r"\b(?:summarize|analyze|explain) each document (?:one by one|individually)\b",
]

SPECIFIC_QA_PATTERNS = [
    r"\bbagaimana\s+(?:alur|prosedur|tahapan|proses|tata\s+cara|cara|mekanisme|ketentuan|aturan|syarat|target|capaian|stok|isi)\b",
    r"\b(?:alur|prosedur|tahapan|tata\s+cara|proses|mekanisme)\s+(?:pendaftaran|permohonan|pemeriksaan|pengumuman|penghapusan|pembatalan|pengajuan|perlindungan)\b",
    r"\b(?:apa\s+saja|apa\s+itu|apa\s+yang\s+dimaksud|jelaskan\s+tentang|sebutkan)\s+(?:alur|prosedur|tahapan|syarat|persyaratan|definisi|pengertian|sanksi|jangka\s+waktu|hak|kewajiban|kpi|target|stok|inventaris|solusi)\b",
    r"\b(?:berapa\s+lama|berapa\s+biaya|pasal\s+berapa|siapa\s+yang|kapan\s+mulai|berapa\s+target|berapa\s+stok)\b",
    r"\b(?:what\s+is|what\s+are|how\s+does|how\s+to|explain\s+the|describe\s+the)\s+(?:the\s+)?(?:registration|flow|procedure|process|requirements|penalty|penalties|liability|kpi|target|inventory|stock|pricing|roadmap|timeline|article|pasal)\b",
    r"\b(?:terjemahkan|translate|moderni[sz]e|jelaskan)\s+(?:pasal|ayat|bab|bagian|slide|tabel|klausul|ketentuan|article|section)\b",
]


def extract_core_task_query(query: str) -> str:
    """
    Strip source-grounding preambles (e.g. 'Okay, sekarang berdasarkan dokumen yang aku berikan.',
    'Based on the documents provided...') so the router and retrieval engine focus on the user's actual task.
    """
    if not query:
        return ""
    cleaned = query.strip()
    preambles = [
        r"^(?:okay|oke|ok|baik|nah|hey\s+chat|halo|hai|hello|hi|sekarang|jadi|now|so)[\s,.:!\-]+",
        r"^(?:sekarang\s+)?(?:berdasarkan|mengacu\s+pada|menurut|dari|pada|di\s+dalam)\s+(?:semua\s+|seluruh\s+|ketiga\s+|kedua\s+)?(?:dokumen|file|peraturan|uu|undang-undang|presentasi|laporan|data)(?:\s+yang\s+(?:aku|saya|telah|sudah)\s+(?:berikan|upload|unggah|kasih|kirim)|\s+yang\s+ada|\s+tersebut|\s+ini)?[\s,.:;\-]+",
        r"^(?:tolong\s+|coba\s+|bisakah\s+|mohon\s+)?"
        r"(?:berdasarkan|mengacu\s+pada|menurut|dari)\s+(?:semua\s+|seluruh\s+)?(?:dokumen|file|peraturan|presentasi|laporan)(?:\s+yang\s+(?:aku|saya)\s+(?:berikan|upload|unggah)|\s+yang\s+ada|\s+ini)?[\s,.:;\-]+",
        r"^(?:please\s+|can\s+you\s+|could\s+you\s+)?"
        r"(?:based\s+on|according\s+to|from|in)\s+(?:the\s+|all\s+|these\s+)?(?:provided\s+|uploaded\s+)?(?:documents|files|presentations|reports|laws|regulations)(?:\s+that\s+i\s+(?:provided|uploaded|shared|gave))?[\s,.:;\-]+",
    ]
    for _ in range(2):
        for pat in preambles:
            cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE).strip()

    return cleaned if len(cleaned) >= 3 else query.strip()


# Learning Note:
# The SubAgentOrchestrator decides whether a user's question can be answered by normal RAG
# or if it should be handed over to a specialist Sub-Agent (like the Document Analyst or Comparator).

class SubAgentOrchestrator:
    """
    Coordinates detection, spawning, and preparation of isolated Sub-Agents (Module 8).
    Supports dual-model Ollama architecture and direct single-pass streaming.
    """

    def __init__(self):
        self.analyst = DocumentAnalystSubAgent()
        self.comparator = DocumentComparatorSubAgent()

    def detect_scenario(
        self,
        query: str,
        metadata_filter: Optional[Dict[str, Any]] = None,
        available_docs: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze the user's prompt task first:
        - Specific procedural/topical questions (e.g. 'Bagaimana alur pendaftaran merek?') return None
          so they are answered directly and accurately by Hybrid RAG (ChromaDB + BM25 + Reranker).
        - Multi-document comparisons trigger DocumentComparatorSubAgent ONLY when comparison or
          per-document breakdown is explicitly requested.
        - Single-document deep audits trigger DocumentAnalystSubAgent ONLY when a full-document
          audit/executive summary is explicitly requested.
        """
        core_query = extract_core_task_query(query)
        q_lower = query.lower()
        core_lower = core_query.lower()

        docs = available_docs or retrieval_service.get_all_documents_metadata()
        if not docs:
            return None

        # 1. Check explicit comparison or explicit per-document breakdown triggers
        is_comparison = any(re.search(pat, q_lower) for pat in COMPARISON_TRIGGERS)
        is_multi_doc_summary = any(re.search(pat, q_lower) for pat in MULTI_DOC_SUMMARY_TRIGGERS)
        is_deep = any(re.search(pat, core_lower) for pat in DEEP_ANALYSIS_TRIGGERS)
        is_specific_qa = any(re.search(pat, core_lower) for pat in SPECIFIC_QA_PATTERNS)

        # GUARD: If the user is asking a specific procedural/factoid question (like "Bagaimana alur pendaftaran merek?")
        # and did NOT explicitly ask to compare documents, NEVER hijack the query with a Sub-Agent!
        if is_specific_qa and not is_comparison and not is_multi_doc_summary:
            logger.info(
                f"Task classified as specific Q&A ('{core_query}'). Routing to Hybrid RAG instead of Sub-Agent."
            )
            return None

        # Deduplicate docs list by id and filename
        unique_docs = []
        seen_keys = set()
        for d in docs:
            k = (d.get("id"), d.get("filename", "").strip().lower())
            if k not in seen_keys:
                seen_keys.add(k)
                unique_docs.append(d)
        docs = unique_docs

        # Honor workspace active document filters (NotebookLM Paradigm)
        active_filter_ids = None
        if metadata_filter:
            if metadata_filter.get("document_ids") and isinstance(metadata_filter["document_ids"], list) and len(metadata_filter["document_ids"]) > 0:
                active_filter_ids = set(str(x) for x in metadata_filter["document_ids"])
            elif metadata_filter.get("document_id"):
                active_filter_ids = {str(metadata_filter["document_id"])}

        if active_filter_ids:
            filtered = [d for d in docs if str(d.get("id")) in active_filter_ids]
            if filtered:
                docs = filtered

        # 2. Check for Comparative Analysis Scenario (comparing 2+ documents)
        if (is_comparison or is_multi_doc_summary) and len(docs) >= 2:
            wants_all_docs = bool(
                is_multi_doc_summary
                or re.search(
                    r"\b(?:semua|seluruh|all|tiap|setiap|masing-masing|ketiga|keempat)\s+(?:isi\s+)?(?:dokumen|file|laporan|peraturan|uu)\b",
                    q_lower,
                )
                or re.search(r"\bdokumen\s+(?:yang\s+ada|yang\s+(?:aku|saya)\s+(?:berikan|upload|unggah))\b", q_lower)
            )

            # Check geographic / jurisdiction scope in query
            asks_indonesia = bool(
                re.search(
                    r"\b(?:indonesia|di\s+indonesia|hukum\s+indonesia|peraturan\s+indonesia|uu\s+indonesia)\b",
                    q_lower,
                )
            )
            asks_us_or_foreign = bool(
                re.search(
                    r"\b(?:amerika|united\s+states|u\.?s\.?|us\b|foreign|luar\s+negeri)\b",
                    q_lower,
                )
            )

            scoped_docs = list(docs)
            if asks_indonesia and not asks_us_or_foreign:
                # Filter out foreign / US laws like Patent Act 1952 unless explicitly mentioned in query
                scoped_docs = [
                    d for d in docs
                    if not any(f in d.get("filename", "").lower() for f in ["patent act", "united states", "us_code", "1952"])
                    and d.get("language") != "en"
                ]
                if len(scoped_docs) < 2:
                    scoped_docs = list(docs)
            elif asks_us_or_foreign and not asks_indonesia:
                scoped_docs = [
                    d for d in docs
                    if any(f in d.get("filename", "").lower() for f in ["patent act", "united states", "us_code", "1952"])
                    or d.get("language") == "en"
                ]
                if len(scoped_docs) < 2:
                    scoped_docs = list(docs)

            matched_docs = []
            if wants_all_docs:
                matched_docs = list(scoped_docs)
            else:
                for d in scoped_docs:
                    fn = d.get("filename", "").lower()
                    fn_stem = fn.split(".")[0]
                    title = (d.get("title") or "").lower()
                    tokens = [t for t in re.split(r"[\s_\-\.]+", fn) if len(t) >= 4]
                    if (
                        fn in q_lower
                        or (len(fn_stem) >= 3 and fn_stem in q_lower)
                        or (title and title in q_lower)
                        or any(t.lower() in q_lower for t in tokens)
                    ):
                        matched_docs.append(d)

                if len(matched_docs) < 2:
                    matched_docs = list(scoped_docs)

            # Strict deduplication of matched_docs
            dedup_matched = []
            seen_m = set()
            for d in matched_docs:
                k = (d.get("id"), d.get("filename", "").strip().lower())
                if k not in seen_m:
                    seen_m.add(k)
                    dedup_matched.append(d)
            matched_docs = dedup_matched

            return {
                "type": "comparative_analysis",
                "docs": matched_docs,
                "reason": (
                    f"Main Agent mendeteksi instruksi komparasi untuk {len(matched_docs)} dokumen. "
                    f"Mendelegasikan ke Document Comparator Sub-Agent untuk analisis silang komprehensif."
                ),
            }

        # 3. Check for Deep Single-Document Analysis Scenario (ONLY when explicitly requested)
        if is_deep and not is_specific_qa:
            target_doc = None

            if metadata_filter and metadata_filter.get("document_id"):
                target_doc = next((d for d in docs if d["id"] == metadata_filter["document_id"]), None)

            if not target_doc:
                for d in docs:
                    fn = d.get("filename", "").lower()
                    fn_stem = fn.split(".")[0]
                    title = (d.get("title") or "").lower()
                    tokens = [t for t in re.split(r"[\s_\-\.]+", fn) if len(t) >= 4]
                    if (
                        fn in q_lower
                        or (len(fn_stem) >= 3 and fn_stem in q_lower)
                        or (title and title in q_lower)
                        or any(t.lower() in q_lower for t in tokens)
                    ):
                        target_doc = d
                        break

            if not target_doc and len(docs) == 1:
                target_doc = docs[0]

            if not target_doc and docs:
                target_doc = max(docs, key=lambda x: x.get("chunk_count", 0))

            if target_doc:
                return {
                    "type": "deep_analysis",
                    "doc": target_doc,
                    "reason": (
                        f"Main Agent mendeteksi instruksi audit mendalam seluruh dokumen untuk '{target_doc.get('filename')}'. "
                        f"Mendelegasikan ke Document Analyst Sub-Agent dengan alat baca sekuensial lengkap."
                    ),
                }

        return None

    async def prepare_scenario(
        self,
        scenario: Dict[str, Any],
        query: str,
        subagent_model: Optional[str] = None,
        web_context: Optional[str] = None,
        web_sources: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Prepare the system prompt, user prompt, and UI step events for the selected Sub-Agent
        so the response can be streamed directly to the user in a single pass.
        """
        scenario_type = scenario.get("type")
        target_model = subagent_model or settings.SUBAGENT_MODEL or settings.LLM_MODEL
        sources_payload: List[Dict[str, Any]] = []

        if scenario_type == "deep_analysis":
            doc = scenario["doc"]
            prep = await self.analyst.prepare_analysis(
                document_id=doc["id"],
                document_meta=doc,
                query=query,
                model=target_model,
                web_context=web_context,
            )

            event = {
                "agent_id": self.analyst.agent_id,
                "name": self.analyst.name,
                "role": self.analyst.role,
                "status": "executing",
                "model_used": target_model,
                "scenario_type": "deep_analysis",
                "target_document": doc.get("filename"),
                "delegation_reason": scenario.get("reason"),
                "steps": prep["steps"],
                "summary": f"Audit komprehensif sedang diproses oleh {self.analyst.name} menggunakan model '{target_model}'.",
            }

            sources_payload.append({
                "id": f"subagent-doc-{doc['id']}",
                "document_id": doc["id"],
                "filename": doc.get("filename", "Dokumen"),
                "title": f"Sub-Agent Audit: {doc.get('title') or doc.get('filename')}",
                "document_type": "subagent_audit",
                "similarity": 1.0,
                "search_mode": "subagent",
                "snippet": f"Audit menyeluruh dokumen {doc.get('filename')} ({prep.get('chunk_count')} chunks).",
            })

            if web_sources:
                sources_payload.extend(web_sources)

            return {
                "scenario_type": scenario_type,
                "subagent_events": [event],
                "system_prompt": prep["system_prompt"],
                "user_prompt": prep["user_prompt"],
                "subagent_model": target_model,
                "sources_payload": sources_payload,
            }

        elif scenario_type == "comparative_analysis":
            target_docs = scenario["docs"]
            prep = await self.comparator.prepare_comparison(
                docs=target_docs,
                query=query,
                model=target_model,
                web_context=web_context,
            )

            doc_names_label = " vs ".join(d.get("filename", "Dokumen") for d in target_docs)
            event = {
                "agent_id": self.comparator.agent_id,
                "name": self.comparator.name,
                "role": self.comparator.role,
                "status": "executing",
                "model_used": target_model,
                "scenario_type": "comparative_analysis",
                "target_document": doc_names_label,
                "delegation_reason": scenario.get("reason"),
                "steps": prep["steps"],
                "summary": f"Matriks komparasi {len(target_docs)} dokumen sedang disusun oleh {self.comparator.name} ({target_model}).",
            }

            for d in target_docs:
                sources_payload.append({
                    "id": f"subagent-comp-{d['id']}",
                    "document_id": d["id"],
                    "filename": d.get("filename", "Dokumen"),
                    "title": f"Sub-Agent Komparasi: {d.get('filename')}",
                    "document_type": "subagent_comparison",
                    "similarity": 0.98,
                    "search_mode": "subagent",
                    "snippet": f"Pembacaan representatif dan analisis komparatif dokumen {d.get('filename')}.",
                })

            if web_sources:
                sources_payload.extend(web_sources)

            return {
                "scenario_type": scenario_type,
                "subagent_events": [event],
                "system_prompt": prep["system_prompt"],
                "user_prompt": prep["user_prompt"],
                "subagent_model": target_model,
                "sources_payload": sources_payload,
            }

        raise ValueError(f"Unknown sub-agent scenario: {scenario_type}")


subagent_orchestrator = SubAgentOrchestrator()
