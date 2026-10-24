import re
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.services.llm import llm_service
from app.services.retrieval import retrieval_service, detect_query_language_and_mode
from app.core.config import settings

logger = logging.getLogger(__name__)


# Learning Note:
# This Sub-Agent is specialized for Deep Document Analysis, Full-Document Translation, and Language Modernization.
# Standard RAG only retrieves the top 5 chunks, which is insufficient if the user asks "Summarize this entire presentation/law"
# or "Translate/modernize this document into contemporary language".
# This sub-agent fetches representative chunks from the beginning, middle, and end of the document.

def clean_boilerplate_signatures(text: str) -> str:
    """
    Helper to clean up unwanted template placeholders at the end of LLM responses, such as:
    'Laporan ini disiapkan oleh: [Your Name]'
    """
    if not text:
        return text
    # 1. Remove signature block if found near the end of the response
    text = re.sub(
        r"(?i)\n\s*(?:laporan ini\s+)?(?:disiapkan|disusun|prepared)\s+oleh\s*:?.*$",
        "",
        text,
        flags=re.DOTALL
    )
    text = re.sub(
        r"(?i)\n\s*(?:diperiksa|reviewed|disetujui|approved)\s+oleh\s*:?.*$",
        "",
        text,
        flags=re.DOTALL
    )

    # 2. Line-by-line cleanup of any leftover placeholder lines
    patterns = [
        r"(?mi)^\s*\[?['\"\\]*(?:your name|nama(?:\s+anda)?|nama penyusun)['\"\\]*\]?\s*$",
        r"(?mi)^\s*\[?['\"\\]*(?:your position|jabatan(?:\s+anda)?)['\"\\]*\]?\s*$",
        r"(?mi)^\s*\[?['\"\\]*(?:reviewer(?:['\"\\]*s)? name|nama pemeriksa)['\"\\]*\]?\s*$",
        r"(?mi)^\s*\[?['\"\\]*(?:reviewer(?:['\"\\]*s)? position|jabatan pemeriksa)['\"\\]*\]?\s*$",
        r"(?mi)^\s*\[?['\"\\]*(?:date|tanggal)[\'\"\\]*\]?\s*$",
        r"(?mi)^\s*(?:prepared|reviewed|approved) by\s*:?.*$",
    ]
    for pat in patterns:
        text = re.sub(pat, "", text)

    # 3. Clean backticks wrapping markdown links or URLs so they stay clickable in UI
    text = re.sub(r"`(\[[^\]]+\]\([^\)]+\))`", r"\1", text)
    text = re.sub(r"`(https?://[^\s`\)]+)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]:\s*(https?://[^\s\)]+)", r"[\1](\2)", text)

    return text.rstrip()


class DocumentAnalystSubAgent:
    """
    Sub-Agent for Deep Single-Document Analysis, Translation & Language Modernization (Module 8).
    - Reads representative chunks sequentially from start, middle, and end of a document.
    - Adapts its report structure to the document domain (Legal, Inventory, KPI Report, Client Presentation, Financial, Technical).
    - Responds in the language requested/used by the user (Bahasa Indonesia or English) while preserving original quotes.
    - Supports modernizing archaic/complex document phrasing into clear contemporary language.
    """

    def __init__(self, agent_id: str = "subagent-doc-analyst-1"):
        self.agent_id = agent_id
        self.name = "Document Analyst Sub-Agent"
        self.role = "Multi-Domain Document Auditor, Translator & Synthesizer"

    def _select_representative_chunks(self, chunks: List[Dict[str, Any]], max_chars: int = 7000) -> str:
        """
        Pick representative text chunks from the beginning, middle, and end of the document
        so we don't overload the local Ollama context window while still covering the whole file.
        """
        if not chunks:
            return ""

        total = len(chunks)
        if total <= 8:
            selected = chunks
        else:
            selected = []
            selected.extend(chunks[:3])
            step = max(1, (total - 5) // 3)
            for i in range(3, total - 2, step):
                if len(selected) < 7:
                    selected.append(chunks[i])
            selected.extend(chunks[-2:])

        text_blocks = []
        cur_chars = 0
        for idx, c in enumerate(selected):
            content = c.get("content", "").strip()
            chunk_num = c.get("chunk_index", idx) + 1
            block = f"[Section/Chunk {chunk_num} of {total}]\n{content}"
            if cur_chars + len(block) > max_chars:
                break
            text_blocks.append(block)
            cur_chars += len(block)

        return "\n\n".join(text_blocks)

    async def prepare_analysis(
        self,
        document_id: str,
        document_meta: Dict[str, Any],
        query: str,
        model: Optional[str] = None,
        web_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Prepare the document context and audit/translation steps before streaming the LLM response."""
        filename = document_meta.get("filename", "Dokumen")
        doc_title = document_meta.get("title") or filename
        doc_type = str(document_meta.get("doc_type") or document_meta.get("document_type") or "general").lower()

        lang_mode = detect_query_language_and_mode(query)
        resp_lang = lang_mode["response_lang"]
        is_modernization = lang_mode["is_modernization"]
        is_translation = lang_mode["is_translation"]

        all_chunks = await retrieval_service.get_document_chunks_ordered(document_id)
        chunk_count = len(all_chunks)
        total_chars = sum(len(c.get("content", "")) for c in all_chunks)

        steps = [
            {
                "step": "delegation",
                "name": "Main Agent Delegation",
                "status": "done",
                "detail": f"Main Agent delegated full-document task for '{filename}' (domain={doc_type}, lang={resp_lang}).",
            },
            {
                "step": "inspect_outline",
                "name": "Document Structure Inspection",
                "status": "done",
                "detail": f"Document '{filename}' has {chunk_count} chunks ({total_chars:,} characters).",
            },
            {
                "step": "sequential_read",
                "name": "Sequential Representative Reading",
                "status": "done",
                "detail": f"Reading {min(chunk_count, 8)} representative sections from beginning, middle, and end.",
            },
        ]

        if web_context:
            steps.append({
                "step": "web_updates_integration",
                "name": "Verified Web Context Integration",
                "status": "done",
                "detail": "Integrating verified external web research with local document analysis.",
            })

        steps.append({
            "step": "aspect_extraction",
            "name": "Translation & Modernization Synthesis" if is_translation else f"Multi-Domain Audit ({doc_type.upper()})",
            "status": "executing",
            "detail": "Synthesizing structured analysis with verbatim original quotes and clear explanations.",
        })

        synthesized_text = self._select_representative_chunks(all_chunks, max_chars=7000)

        # Build domain- and language-adaptive system prompt
        if is_translation or is_modernization:
            if resp_lang == "en":
                system_prompt = (
                    f"You are {self.name}, an expert bilingual document translator and language modernization specialist.\n"
                    f"PRIMARY TASK: Translate and/or modernize the document '{filename}' into clear, contemporary, and accessible **ENGLISH** while preserving original verbatim excerpts.\n"
                    f"MANDATORY FORMAT & RULES:\n"
                    f"1. Write all explanations, headings, and translations in **ENGLISH**.\n"
                    f"2. Structure your response using these Markdown sections:\n"
                    f"   - ## 1. Document Overview & Core Purpose\n"
                    f"   - ## 2. Section-by-Section Translation & Modernized Explanation\n"
                    f"     For each key section/article/slide in the document, provide:\n"
                    f"     * **Original Quote Snippet:** `\"[Opening 3-8 words...] ... \" (Page X / Pasal Y - {filename})` (never quote full long clauses)\n"
                    f"     * **English Translation / Modernized Phrasing:** Clear, modern English translation.\n"
                    f"     * **Practical Meaning:** Plain-English explanation of what this means in practice.\n"
                    f"   - ## 3. Key Takeaways & Actionable Summary\n"
                    f"3. Do NOT include any signature placeholders like '[Your Name]' or '[Reviewer\\'s Name]'."
                )
            else:
                system_prompt = (
                    f"Anda adalah {self.name}, spesialis penerjemahan lintas-bahasa dan modernisasi bahasa dokumen.\n"
                    f"TUGAS UTAMA: Menerjemahkan dan/atau mengubah gaya bahasa dokumen '{filename}' ke dalam **BAHASA INDONESIA YANG LEBIH BARU (MODERN, LUGAS, DAN MUDAH DIPAHAMI)** dengan tetap menyertakan cuplikan kutipan aslinya.\n"
                    f"PEDOMAN WAJIB FORMAT & PENYAJIAN:\n"
                    f"1. Gunakan **BAHASA INDONESIA MODERN** yang jelas, komunikatif, dan mudah dipahami (hindari kalimat birokratis/kuno yang berbelit-belit).\n"
                    f"2. Susun laporan dengan struktur Markdown berikut:\n"
                    f"   - ## 1. Gambaran Umum & Tujuan Dokumen (Bahasa Modern)\n"
                    f"   - ## 2. Terjemahan & Modernisasi Bahasa Bagian demi Bagian\n"
                    f"     Untuk setiap pasal/bagian/slide penting dalam dokumen, tampilkan:\n"
                    f"     * **Cuplikan Kutipan Asli:** `\"[3-8 kata awal...] ... \" (Page X / Pasal Y - {filename})` (hindari mengutip kalimat panjang penuh)\n"
                    f"     * **Versi Bahasa Baru / Terjemahan Modern:** Kalimat masa kini yang jernih dan komunikatif.\n"
                    f"     * **Penjelasan Praktis:** Makna inti dan contoh penerapannya secara langsung.\n"
                    f"   - ## 3. Intisari & Poin Penting yang Perlu Diingat\n"
                    f"3. DILARANG menyertakan placeholder tanda tangan seperti '[Your Name]' atau '[Reviewer\\'s Name]'."
                )
        elif resp_lang == "en":
            system_prompt = (
                f"You are {self.name}, an expert multi-domain document auditor (covering Legal, Inventory, KPI Reports, Client Presentations, Financial, and Technical documents).\n"
                f"MANDATORY LANGUAGE & CITATION RULES:\n"
                f"1. You MUST write your entire analysis and explanation in **ENGLISH**.\n"
                f"2. **CONCISE ORIGINAL QUOTES**: Whenever citing key rules, metrics, slides, or findings from the document, use a concise quote snippet (3-8 opening words + ellipsis `...`): `\"[Opening words...] ... \" (Page X / Pasal Y - {filename})`, and immediately follow it with your explanation/translation in **English**.\n"
                f"3. Adapt your Markdown sections to the document's domain (`{doc_type}`):\n"
                f"   - ## 1. Executive Summary & Document Scope\n"
                f"   - ## 2. Key Findings, Core Provisions / Metrics & Concise Quotes\n"
                f"   - ## 3. Risk Analysis, Bottlenecks, or Gaps Identified\n"
                f"   - ## 4. Strategic Value & Operational Impact\n"
            )
            if web_context:
                system_prompt += (
                    f"   - ## 5. Latest External Updates (From Verified Web Sources)\n"
                    f"     Cite verified URLs using `[Source Title](URL)`. Never invent fake regulation numbers.\n"
                    f"   - ## 6. Actionable Recommendations\n"
                )
            else:
                system_prompt += "   - ## 5. Actionable Recommendations\n"
            system_prompt += "4. Do NOT include any signature placeholders like '[Your Name]' or '[Reviewer\\'s Name]'."
        else:
            system_prompt = (
                f"Anda adalah {self.name}, auditor dokumen lintas-domain ahli (mencakup dokumen Hukum/Regulasi, Inventaris/Gudang, Presentasi Klien, Laporan KPI/Kinerja, Keuangan, dan Panduan Teknis).\n"
                f"PEDOMAN UTAMA BAHASA & KUTIPAN ASLI:\n"
                f"1. Anda WAJIB menjawab dan menjelaskan dalam **BAHASA INDONESIA** yang profesional, lugas, dan terstruktur.\n"
                f"2. **KUTIPAN RINGKAS ASLI (SNIPPET DENGAN ELIPSIS)**: Setiap kali membahas poin penting dari dokumen (khususnya jika dokumen berbahasa Inggris/asing atau memuat klausa spesifik), cantumkan cuplikan kutipan ringkas (3-8 kata awal diikuti `...`): `\"[3-8 kata awal...] ... \" (Page X / Pasal Y - {filename})`, lalu terjemahkan dan jelaskan maknanya secara mendalam dalam Bahasa Indonesia.\n"
                f"3. Sesuaikan fokus analisis dengan jenis dokumen (`{doc_type}`) menggunakan format Markdown berikut:\n"
                f"   - ## 1. Ringkasan Eksekutif & Ruang Lingkup Dokumen\n"
                f"   - ## 2. Temuan Kunci, Metrik / Ketentuan Pokok & Kutipan Asli\n"
                f"   - ## 3. Analisis Risiko, Kendala, atau Celah Operasional/Regulasi\n"
                f"   - ## 4. Kekuatan & Dampak Strategis\n"
            )
            if web_context:
                system_prompt += (
                    f"   - ## 5. Pembaruan Terkini Terkait (Berdasarkan Web Terverifikasi)\n"
                    f"     Cantumkan tautan [Judul Sumber](URL). Dilarang mengarang nomor peraturan fiktif.\n"
                    f"   - ## 6. Rekomendasi Langkah Konkret\n"
                )
            else:
                system_prompt += "   - ## 5. Rekomendasi Langkah Konkret\n"
            system_prompt += (
                f"4. LARANGAN KERAS: DILARANG menyertakan placeholder tanda tangan seperti '[Your Name]' atau '[Reviewer\\'s Name]'."
            )

        user_prompt_parts = [
            f"User Instruction / Query: {query}\n",
            f"Document Title: {doc_title} (File: {filename}, Domain Category: {doc_type})",
            f"Document Metrics: {chunk_count} total chunks ({total_chars:,} characters)\n",
            "--- REPRESENTATIVE DOCUMENT EXCERPTS ---",
            synthesized_text,
            "--- END OF DOCUMENT EXCERPTS ---",
        ]

        if web_context:
            user_prompt_parts.extend([
                "\n--- VERIFIED WEB SEARCH CONTEXT ---",
                web_context,
                "--- END OF WEB CONTEXT ---",
            ])

        if resp_lang == "en":
            user_prompt_parts.append(
                "\nProvide your comprehensive response in ENGLISH following the required structure. Remember to include verbatim original quotes (`> \"...\"`) from the document and explain them in English."
            )
        else:
            user_prompt_parts.append(
                "\nBerikan respons komprehensif Anda dalam BAHASA INDONESIA mengikuti struktur yang diwajibkan. Pastikan menyertakan kutipan asli (`> \"...\"`) dari dokumen beserta terjemahan/penjelasannya."
            )
        user_prompt = "\n".join(user_prompt_parts)

        target_model = model or settings.SUBAGENT_MODEL or settings.LLM_MODEL

        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role,
            "target_doc_id": document_id,
            "target_filename": filename,
            "target_title": doc_title,
            "chunk_count": chunk_count,
            "total_chars": total_chars,
            "model_used": target_model,
            "steps": steps,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
        }
