import re
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.services.llm import llm_service
from app.services.retrieval import retrieval_service, detect_query_language_and_mode
from app.core.config import settings

logger = logging.getLogger(__name__)


# Learning Note:
# This Sub-Agent handles Cross-Document Comparison (comparing 2 or more documents side-by-side).
# It adapts its comparison parameters to the document domains (Legal, Inventory, KPI Report, Client Presentation, or Mixed)
# and responds in the language requested/used by the user (Bahasa Indonesia or English) while preserving original quotes.

class DocumentComparatorSubAgent:
    """
    Sub-Agent for Cross-Document Comparison (Module 8).
    - Supports comparing 2 or more documents at the same time across Legal, Inventory, KPI, and Client Presentation domains.
    - Reads representative chunks from each document so it fits in local GPU/CPU memory.
    - Builds a side-by-side Markdown comparison matrix in Bahasa Indonesia or English based on the user's prompt.
    """

    def __init__(self, agent_id: str = "subagent-doc-comparator-1"):
        self.agent_id = agent_id
        self.name = "Document Comparator Sub-Agent"
        self.role = "Multi-Domain Cross-Document Comparison Specialist"

    def _select_representative_chunks(self, chunks: List[Dict[str, Any]], max_chars: int = 3500) -> str:
        """Select representative chunks from the beginning, middle, and end of each document."""
        if not chunks:
            return ""

        total = len(chunks)
        if total <= 5:
            selected = chunks
        else:
            selected = []
            selected.extend(chunks[:2])
            step = max(1, (total - 4) // 2)
            for i in range(2, total - 2, step):
                if len(selected) < 4:
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

    async def prepare_comparison(
        self,
        docs: Optional[List[Dict[str, Any]]] = None,
        query: str = "",
        model: Optional[str] = None,
        doc_a_meta: Optional[Dict[str, Any]] = None,
        doc_b_meta: Optional[Dict[str, Any]] = None,
        web_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Prepare the multi-document comparison context for 2 or more documents,
        plus optional verified web search context if requested.
        """
        target_docs: List[Dict[str, Any]] = []
        if docs:
            target_docs = list(docs)
        elif doc_a_meta and doc_b_meta:
            target_docs = [doc_a_meta, doc_b_meta]

        if not target_docs:
            raise ValueError("DocumentComparatorSubAgent requires at least 2 documents to compare.")

        num_docs = len(target_docs)
        doc_names = [d.get("filename", f"Document {i+1}") for i, d in enumerate(target_docs)]
        doc_types = {str(d.get("doc_type") or "general").lower() for d in target_docs}
        is_pure_legal = doc_types.issubset({"legal", "general"}) and any(
            any(k in d.get("filename", "").lower() for k in ["uu", "permen", "perka", "peraturan", "hukum", "merek", "paten", "law"])
            for d in target_docs
        )

        lang_mode = detect_query_language_and_mode(query)
        resp_lang = lang_mode["response_lang"]

        # Character budget per document is scaled so total prompt fits comfortably in local context window
        budget_per_doc = max(2000, min(4000, 10000 // num_docs))

        steps: List[Dict[str, Any]] = [
            {
                "step": "delegation",
                "name": "Main Agent Delegation",
                "status": "done",
                "detail": f"Main Agent delegated cross-document comparison for {num_docs} documents: {', '.join(doc_names)}.",
            }
        ]

        doc_sections: List[str] = []
        for idx, d in enumerate(target_docs, 1):
            fn = d.get("filename", f"Document {idx}")
            doc_id = d.get("id")
            d_type = d.get("doc_type", "general")
            chunks = await retrieval_service.get_document_chunks_ordered(doc_id)
            total_chars = sum(len(c.get("content", "")) for c in chunks)

            steps.append({
                "step": f"read_doc_{idx}",
                "name": f"Sequential Read: {fn}",
                "status": "done",
                "detail": f"'{fn}' [{d_type}]: {len(chunks)} chunks ({total_chars:,} characters).",
            })

            text_sample = self._select_representative_chunks(chunks, max_chars=budget_per_doc)
            doc_sections.append(
                f"=== DOCUMENT {idx}: {fn} (Category: {d_type}, {len(chunks)} chunks, Title: {d.get('title') or fn}) ===\n{text_sample}"
            )

        if web_context:
            steps.append({
                "step": "web_updates_integration",
                "name": "Verified Web Context Integration",
                "status": "done",
                "detail": "Connecting comparative analysis with verified web research for latest updates.",
            })

        steps.append({
            "step": "comparative_synthesis",
            "name": f"Multi-Document Comparison Matrix ({num_docs} Docs)",
            "status": "executing",
            "detail": "Synthesizing document-by-document breakdown, comparison matrix table, similarities, differences, and insights.",
        })

        is_concise = lang_mode.get("is_concise", False) or bool(
            re.search(r"\b(?:langsung\s+(?:ke|kepada)\s+intinya|inti\s+saja|ringkas|singkat|to\s+the\s+point|cepat)\b", query, re.IGNORECASE)
        )
        is_quote_explicit = bool(
            re.search(r"\b(?:kutip|kutipan|quote|quotes|caption|cantumkan\s+kutipan|sertakan\s+kutipan|with\s+quote|include\s+quote|cit(?:e|ation))\b", query, re.IGNORECASE)
        )
        doc_langs = {d.get("language", "id") for d in target_docs}
        is_cross_lingual = (resp_lang == "id" and "en" in doc_langs) or (resp_lang == "en" and "id" in doc_langs) or lang_mode.get("is_translation", False)
        requires_quotes = is_quote_explicit or is_cross_lingual

        numbered_doc_list = "\n".join(
            f"     {i+1}. **{d.get('filename')}** (*{d.get('doc_type', 'general')}*) — *{d.get('title') or d.get('filename')}*"
            for i, d in enumerate(target_docs)
        )

        if resp_lang == "en":
            quote_instruction = (
                "2. **ORIGINAL QUOTES (CONDITIONAL)**: Include concise quote snippets (`\"[3-8 words...] \" (Page X - Document Name)`) as requested/cross-lingual.\n"
                if requires_quotes
                else "2. **NO VERBATIM QUOTES NEEDED**: Do NOT output quote captions or blockquotes. Focus directly on substantive comparative analysis.\n"
            )
            system_prompt = (
                f"You are {self.name}, an expert multi-domain analyst and cross-document comparison specialist.\n"
                f"PRIMARY TASK: Perform a comprehensive, high-quality comparative analysis of EXACTLY {num_docs} local documents:\n"
                f"{numbered_doc_list}\n\n"
                f"MANDATORY EXECUTION & STRUCTURE RULES:\n"
                f"1. You MUST write your entire analysis and explanations in **ENGLISH**.\n"
                f"{quote_instruction}"
                f"3. **ANTI-DUPLICATION & TABLE ROW COUNT (EXACTLY {num_docs} ROWS)**:\n"
                f"   - Compare EXACTLY the {num_docs} unique documents listed above ({', '.join(doc_names)}).\n"
                f"   - The comparison table MUST have EXACTLY {num_docs} data rows (Row 1 to Row {num_docs}), exactly one row for each document.\n"
                f"   - Every document must appear EXACTLY ONCE. Never repeat or duplicate any document.\n"
                f"4. **REPORT STRUCTURE (DIRECT & SUBSTANTIVE)**:\n"
                f"   - ## 1. Executive Overview (1 compact paragraph)\n"
                f"   - ## 2. Primary Comparison Matrix Table\n"
                f"     Present the Markdown table DIRECTLY under Section 2 (do NOT output individual document summaries before the table):\n"
                f"     | No | Document Name | Scope & Regulated Object | Core Principles & Provisions | Key Procedures & Mechanism | Unique Distinctions & Implications |\n"
                f"     | --- | --- | --- | --- | --- | --- |\n"
                f"     CRITICAL TABLE RULE: Fill every cell with 1-2 complete, substantive explanatory sentences (NEVER use 2-3 word fragments!).\n"
                f"   - ## 3. Core Distinctions & Key Takeaways\n"
                f"     Bullet-point summary highlighting the fundamental differences and practical impacts among the documents.\n"
            )
            if web_context:
                system_prompt += (
                    f"   - ## 4. Latest External Updates (From Verified Web Sources)\n"
                    f"     Cite verified URLs using `[Source Title](URL)`.\n"
                )
            system_prompt += "5. Do NOT include any signature placeholders like '[Your Name]' or '[Reviewer\\'s Name]'."
        else:
            quote_instruction = (
                "2. **KUTIPAN ASLI (KONDISIONAL)**: Sertakan cuplikan kutipan ringkas berelipsis (`\"[3-8 kata awal...] \" (Page X / Pasal Y - Nama Dokumen)`) karena diminta pengguna atau adanya terjemahan lintas-bahasa.\n"
                if requires_quotes
                else "2. **TIDAK PERLU KUTIPAN/CAPTION**: DILARANG menyertakan kutipan/caption verbatim karena tidak diminta oleh pengguna. Langsung jelaskan substansinya.\n"
            )
            system_prompt = (
                f"Anda adalah {self.name}, spesialis analisis komparatif dokumen hukum dan bisnis lintas-domain ahli.\n"
                f"TUGAS UTAMA: Melakukan analisis komparatif mendalam dan langsung pada intinya terhadap TEPAT {num_docs} dokumen lokal berikut:\n"
                f"{numbered_doc_list}\n\n"
                f"PEDOMAN WAJIB STRUKTUR & KUALITAS LAPORAN:\n"
                f"1. Anda WAJIB menjawab dalam **BAHASA INDONESIA** yang profesional, lugas, dan berbobot.\n"
                f"{quote_instruction}"
                f"3. **ANTI-DUPLIKASI & JUMLAH BARIS TABEL TEPAT {num_docs} BARIS**:\n"
                f"   - Anda membandingkan TEPAT {num_docs} dokumen unik di atas ({', '.join(doc_names)}).\n"
                f"   - Tabel Matriks Komparasi Utama WAJIB memiliki TEPAT {num_docs} baris data (Baris 1 s.d. Baris {num_docs}), tepat 1 baris untuk masing-masing dokumen.\n"
                f"   - SETIAP DOKUMEN HANYA BOLEH MUNCUL TEPAT SATU KALI. DILARANG KERAS menduplikasi atau mengulang dokumen apa pun!\n"
                f"4. **STRUKTUR LAPORAN (LANGSUNG TO-THE-POINT & BERBOBOT)**:\n"
                f"   - ## 1. Ringkasan Eksekutif (1 paragraf padat)\n"
                f"   - ## 2. Tabel Matriks Komparasi Utama\n"
                f"     LANGSUNG sajikan Tabel Markdown di bawah judul Bagian 2 (DILARANG membuat ringkasan/poin teks terpisah per-dokumen sebelum tabel):\n"
                f"     | No | Nama Dokumen Regulasi | Objek & Ruang Lingkup Pengaturan | Asas & Ketentuan Pokok | Prosedur / Mekanisme Kunci | Karakteristik Unik & Pembeda |\n"
                f"     | --- | --- | --- | --- | --- | --- |\n"
                f"     PEDOMAN KUALITAS SEL TABEL: Pastikan SETIAP SEL memuat penjelasan substansial yang utuh (1-2 kalimat lengkap dan informatif, DILARANG hanya menulis 2-3 kata potongan singkat!).\n"
                f"   - ## 3. Poin Pembeda Inti & Implikasi Praktis\n"
                f"     Jelaskan butir-butir pembeda kunci antar dokumen (misalnya memperjelas mana dokumen yang spesifik mengatur paten, mana yang merek, atau mana yang hak cipta/royalti).\n"
            )
            if web_context:
                system_prompt += (
                    f"   - ## 4. Pembaruan Terkini Terkait (Berdasarkan Web Terverifikasi)\n"
                    f"     Cantumkan tautan [Judul Sumber](URL). Dilarang mengarang nomor peraturan fiktif!\n"
                )
            system_prompt += (
                f"5. LARANGAN KERAS: DILARANG menyertakan placeholder tanda tangan seperti '[Your Name]' atau '[Reviewer\\'s Name]'."
            )

        all_docs_text = "\n\n".join(doc_sections)
        user_prompt_parts = [
            f"User Query / Instruction: {query}\n",
            f"MANDATORY LIST OF {num_docs} DOCUMENTS TO COMPARE (Use These Exact Filenames):\n{numbered_doc_list}\n",
            "--- EXCERPTS OF DOCUMENTS TO COMPARE ---",
            all_docs_text,
            "--- END OF DOCUMENT EXCERPTS ---",
        ]

        if web_context:
            user_prompt_parts.extend([
                "\n--- VERIFIED WEB SEARCH RESULTS ---",
                web_context,
                "--- END OF WEB RESULTS ---",
            ])

        if resp_lang == "en":
            quote_suffix = " including verbatim original quotes (`> \"...\"`)" if requires_quotes else ""
            table_cols_en = "| No | Document Name | Scope & Regulated Object | Core Principles & Provisions | Key Procedures & Mechanism | Unique Distinctions & Implications |"
            user_prompt_parts.append(
                f"\nProvide a comprehensive, high-quality comparative analysis for ALL {num_docs} unique documents above ({', '.join(doc_names)}){quote_suffix} directly structured as:\n"
                f"1. ## 1. Executive Overview (1 compact paragraph)\n"
                f"2. ## 2. Primary Comparison Matrix Table (Table columns: {table_cols_en})\n"
                f"3. ## 3. Core Distinctions & Key Practical Takeaways\n"
                f"CRITICAL: Do NOT list individual document summaries before the table. Directly render the 6-column matrix table with substantive explanatory sentences in each cell."
            )
        else:
            quote_suffix = " beserta kutipan asli (`> \"...\"`)" if requires_quotes else ""
            table_cols_id = "| No | Nama Dokumen Regulasi | Objek & Ruang Lingkup Pengaturan | Asas & Ketentuan Pokok | Prosedur / Mekanisme Kunci | Karakteristik Unik & Pembeda |"
            user_prompt_parts.append(
                f"\nSajikan analisis komparatif berbobot dan mendalam untuk SELURUH {num_docs} dokumen unik di atas ({', '.join(doc_names)}){quote_suffix} secara langsung terstruktur:\n"
                f"1. ## 1. Ringkasan Eksekutif (1 paragraf padat)\n"
                f"2. ## 2. Tabel Matriks Komparasi Utama (WAJIB gunakan kolom: {table_cols_id})\n"
                f"3. ## 3. Poin Pembeda Inti & Implikasi Praktis\n"
                f"PENTING: Dilarang membuat daftar ringkasan terpisah per-dokumen sebelum tabel. Di bawah Bagian 2, LANGSUNG sajikan tabel matriks 6-kolom lengkap (tepat {num_docs} baris dokumen tanpa duplikasi) dan isi setiap sel dengan 1-2 kalimat penjelasan substansial yang utuh."
            )
        user_prompt = "\n".join(user_prompt_parts)

        target_model = model or settings.SUBAGENT_MODEL or settings.LLM_MODEL

        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role,
            "target_documents": doc_names,
            "doc_count": num_docs,
            "model_used": target_model,
            "steps": steps,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
        }
