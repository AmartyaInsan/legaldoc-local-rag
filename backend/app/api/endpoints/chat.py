from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any, Optional, AsyncGenerator
import uuid
import json
import logging
import time
import re
from datetime import datetime

from app.core.config import settings
from app.schemas.chat import ChatRequest, Thread, ThreadCreate, ThreadUpdate, ChatMessage
from app.services.llm import llm_service
from app.services.local_db import local_db_service
from app.services.retrieval import detect_query_language_and_mode
from app.services.tools.router import agent_router
from app.services.subagents.analyst import clean_boilerplate_signatures
from app.api.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/models")
async def get_models():
    """Get the list of local Ollama models available on this computer."""
    health = await llm_service.check_health()
    raw_models = health.get("available_models", [])
    # Hide embedding models from the chat model dropdown
    chat_models = [m for m in raw_models if "embed" not in m.lower()]
    if not chat_models and health.get("active_model"):
        chat_models = [health.get("active_model")]
    return {
        "active_model": health.get("active_model"),
        "subagent_model": settings.SUBAGENT_MODEL,
        "available_models": chat_models,
        "provider": health.get("provider"),
    }


async def _generate_rag_stream(
    request: ChatRequest,
    thread_id: str,
    user_id: Optional[str],
) -> AsyncGenerator[str, None]:
    """
    Learning Note (Main Chat Streaming Pipeline - assisted by AI for SSE format):
    1. Send the user's question to AgentRouter to find relevant document chunks
       (from local ChromaDB + SQLite) or run tools like Text-to-SQL / Sub-Agents.
    2. Stream tool status and citation sources to the frontend first.
    3. Put the retrieved document text into the system prompt.
    4. Stream the answer token-by-token from local Ollama.
    5. Save the final response into our local SQLite database (legal_rag.db).
    """
    start_time = time.time()
    last_user_msg = next((m.content for m in reversed(request.messages) if m.role == "user"), "")

    orchestration: Dict[str, Any] = {
        "tool_events": [],
        "augmented_context": "",
        "sources_payload": [],
        "tools_used": [],
    }

    if last_user_msg:
        try:
            orchestration = await agent_router.orchestrate(
                query=last_user_msg,
                user_id=user_id,
                metadata_filter=request.metadata_filter,
                search_mode=request.search_mode or "hybrid",
                enable_web_fallback=True,
                enable_sql=True,
                subagent_model=request.subagent_model,
            )
        except Exception as e:
            logger.warning(f"Agent router orchestration error: {e}")

    # Send tool events to frontend
    tool_events = orchestration.get("tool_events", [])
    if tool_events:
        yield f"data: {json.dumps({'tool_events': tool_events})}\n\n"

    # Send sub-agent events if a full-document task was triggered (Module 8)
    subagent_events = orchestration.get("subagent_events", [])
    if subagent_events:
        yield f"data: {json.dumps({'subagent_events': subagent_events})}\n\n"

    # Send retrieved document sources to frontend
    sources_payload = orchestration.get("sources_payload", [])
    if sources_payload:
        yield f"data: {json.dumps({'sources': sources_payload})}\n\n"

    # ------------------------------------------------------------------
    # CASE A: SUB-AGENT DIRECT STREAMING (For full document audit / comparison)
    # ------------------------------------------------------------------
    # Stream directly from the Sub-Agent prompt so we don't have to wait for
    # two separate LLM generations on local hardware.
    if orchestration.get("is_subagent_direct"):
        target_model = orchestration.get("subagent_model") or request.subagent_model or request.model
        sys_prompt = orchestration.get("subagent_system_prompt", "")
        usr_prompt = orchestration.get("subagent_user_prompt", last_user_msg)

        assistant_tokens: List[str] = []
        try:
            async for chunk in llm_service.stream_chat(
                messages=[ChatMessage(role="user", content=usr_prompt)],
                model=target_model,
                temperature=0.3,
                system_prompt=sys_prompt,
            ):
                if chunk.startswith("data: ") and not chunk.startswith("data: [DONE]"):
                    try:
                        payload = json.loads(chunk[6:].strip())
                        if "token" in payload and payload["token"]:
                            assistant_tokens.append(payload["token"])
                    except Exception:
                        pass
                yield chunk
        finally:
            elapsed = round(time.time() - start_time, 2)
            raw_content = "".join(assistant_tokens).strip()
            full_content = clean_boilerplate_signatures(raw_content)

            if subagent_events:
                subagent_events[0]["status"] = "completed"
                subagent_events[0]["elapsed_seconds"] = elapsed
                for st in subagent_events[0].get("steps", []):
                    st["status"] = "done"
                subagent_events[0]["summary"] = (
                    f"Penyusunan selesai oleh {subagent_events[0].get('name')} ({target_model}) dalam {elapsed}s."
                )
                yield f"data: {json.dumps({'subagent_events': subagent_events})}\n\n"

            if full_content:
                assistant_msg_id = str(uuid.uuid4())
                tools_used = orchestration.get("tools_used", [])
                msg_meta: Dict[str, Any] = {"subagent_model": target_model}
                if sources_payload:
                    msg_meta["sources"] = sources_payload
                if tools_used:
                    msg_meta["tools_used"] = tools_used
                if subagent_events:
                    msg_meta["subagent_events"] = subagent_events

                local_db_service.save_message(
                    message_id=assistant_msg_id,
                    thread_id=thread_id,
                    role="assistant",
                    content=full_content,
                    metadata=msg_meta,
                )
        return

    # ------------------------------------------------------------------
    # CASE B: NORMAL RAG CHAT STREAMING (Multi-Domain, Bilingual ID/EN & Modernization)
    # ------------------------------------------------------------------
    lang_mode = detect_query_language_and_mode(last_user_msg)
    resp_lang = lang_mode["response_lang"]
    is_translation = lang_mode["is_translation"]
    is_modernization = lang_mode["is_modernization"]
    is_concise = lang_mode.get("is_concise", False)
    is_detailed = lang_mode.get("is_detailed", False)

    is_quote_explicit = bool(
        re.search(
            r"\b(?:kutip|kutipan|quote|quotes|caption|cantumkan\s+kutipan|sertakan\s+kutipan|with\s+quote|include\s+quote|cit(?:e|ation))\b",
            last_user_msg,
            re.IGNORECASE,
        )
    )

    source_langs = set()
    for s in sources_payload:
        fn = (s.get("filename") or "").lower()
        if any(f in fn for f in ["patent act", "deck", "pitch", "inventory"]) or s.get("language") == "en":
            source_langs.add("en")
        else:
            source_langs.add("id")

    is_cross_lingual = (
        (resp_lang == "id" and "en" in source_langs)
        or (resp_lang == "en" and "id" in source_langs)
        or is_translation
        or is_modernization
    )
    requires_quotes = is_quote_explicit or is_cross_lingual

    if is_concise:
        if resp_lang == "en":
            quote_rule = (
                "2. **CONCISE QUOTE SNIPPET**: Include 1 short quote snippet (3-8 words + ellipsis `...`): `\"[Opening words...] \" (Page X - Document Name)`.\n"
                if requires_quotes
                else "2. **NO VERBATIM QUOTES**: Answer directly without quote captions.\n"
            )
            base_instructions = (
                "You are an expert Multi-Domain AI Analyst in a Closed-Environment Agentic RAG system (ChromaDB + SQLite).\n"
                "MANDATORY FAST & CONCISE RULES:\n"
                "1. **DIRECT & TO-THE-POINT**: The user explicitly requested a BRIEF/CONCISE answer. Do NOT generate repetitive breakdowns. Provide a single unified, compact explanation (1-2 short paragraphs or 2-3 bullet points).\n"
                f"{quote_rule}"
                "3. Never invent placeholder signatures like `[Your Name]` or `[Reviewer's Name]`."
            )
        else:
            quote_rule = (
                "2. **FORMAT KUTIPAN RINGKAS (KONDISIONAL)**: Sertakan 1 cuplikan ringkas (3-8 kata awal diikuti tanda elipsis `...`): `\"[Cuplikan awal...] \" (Page X / Slide Y / Pasal Z - Nama Dokumen)`.\n"
                if requires_quotes
                else "2. **TIDAK PERLU KUTIPAN/CAPTION**: Langsung pada inti jawaban tanpa menyertakan kutipan/caption verbatim karena tidak diminta pengguna.\n"
            )
            base_instructions = (
                "Anda adalah Asisten Riset & Analitik AI Lintas-Domain ahli dalam sistem Agentic RAG Close-Environment (ChromaDB + SQLite).\n"
                "PEDOMAN WAJIB RESPON RINGKAS, CEPAT & TEPAT SASARAN:\n"
                "1. **LANGSUNG TO-THE-POINT**: Pengguna meminta penjelasan RINGKAS ('ringkas saja' / 'singkat'). Sajikan satu penjelasan terpadu yang padat dan jelas (1-2 paragraf atau 2-3 poin ringkas).\n"
                f"{quote_rule}"
                "3. Dilarang menyertakan salam pembuka/penutup yang bertele-tele atau placeholder tanda tangan."
            )
    elif is_detailed:
        if resp_lang == "en":
            quote_rule = (
                "2. **CONCISE QUOTE SNIPPET**: Include 1-2 short quote snippets (3-8 opening words + ellipsis `...`): `\"[Opening words...] \" (Page X - Document Name)`.\n"
                if requires_quotes
                else "2. **NO VERBATIM QUOTES**: Deliver the thorough analysis directly without separate quote captions.\n"
            )
            base_instructions = (
                "You are an expert Senior Multi-Domain AI Research & Legal/Business Analyst in a Closed-Environment Agentic RAG system (ChromaDB + SQLite).\n"
                "MANDATORY IN-DEPTH & THOROUGH ANALYSIS RULES:\n"
                "1. **COMPREHENSIVE & THOROUGH EXPLANATION**: The user requested a DETAILED / IN-DEPTH explanation. Provide a deep, substantive, and fully rounded breakdown covering the statutory/factual background, exact article numbers/sections, procedural steps, prerequisite criteria, rights and obligations, and practical implications.\n"
                f"{quote_rule}"
                "3. **RIGOROUS & WELL-STRUCTURED**: Use clear markdown headings, numbered sequential stages, and analytical bullet points. Do NOT summarize superficially—explain the full mechanisms and nuances clearly.\n"
                "4. **HIGH INFORMATION DENSITY & SPEED**: Keep the prose dense, informative, and authoritative without conversational fluff or signature placeholders like `[Your Name]` or `[Reviewer's Name]`."
            )
        else:
            quote_rule = (
                "2. **KUTIPAN RINGKAS (DIMINTA PENGGUNA)**: Pengguna meminta kutipan. Sertakan 1-2 cuplikan kutipan ringkas (3-8 kata awal) diikuti tanda elipsis `...`: `\"[Cuplikan awal...] \" (Page X / Slide Y / Pasal Z - Nama Dokumen)` sebelum menjelaskan.\n"
                if requires_quotes
                else "2. **TIDAK PERLU KUTIPAN/CAPTION**: Langsung pada pemaparan analisis mendalam tanpa menyertakan kutipan/caption verbatim karena tidak diminta oleh pengguna.\n"
            )
            base_instructions = (
                "Anda adalah Analis Riset & Hukum/Bisnis AI Senior Lintas-Domain ahli dalam sistem Agentic RAG Close-Environment (ChromaDB + SQLite).\n"
                "PEDOMAN WAJIB EKSPLIKASI MENDALAM & ANALISIS KOMPREHENSIF (DETAIL MODE):\n"
                "1. **PENJELASAN MENDALAM, LENGKAP & BERBOBOT**: Pengguna meminta penjelasan DETAIL/MENDALAM. Berikan penjelasan yang komprehensif, kaya fakta, dan tuntas. Uraikan landasan hukum/dokumen, nomor pasal/klausul spesifik, syarat kelayakan, tahapan alur secara sistematis, pengecualian, serta konsekuensi atau implikasi praktisnya.\n"
                f"{quote_rule}"
                "3. **STRUKTUR AKADEMIS & SISTEMATIS**: Susun uraian menggunakan sub-judul Markdown yang runtut, tahapan bernomor, atau poin-poin analitis yang tajam. DILARANG membatasi diri pada ringkasan pendek; berikan pemaparan yang mendalam dan memuaskan rasa ingin tahu pengguna.\n"
                "4. **PADAT INFORMASI & CEPAT**: Pertahankan informasi yang berbobot tinggi tanpa salam pembuka/penutup basa-basi, dan dilarang menyertakan placeholder tanda tangan seperti `[Your Name]` atau `[Reviewer's Name]`."
            )
    elif is_translation or is_modernization:
        if resp_lang == "en":
            base_instructions = (
                "You are an expert Bilingual Document Translator, Language Modernization Specialist, and Multi-Domain AI Analyst in a Closed-Environment Agentic RAG system (ChromaDB + SQLite).\n"
                "MANDATORY TRANSLATION & MODERNIZATION RULES:\n"
                "1. Focus strictly on the user's latest request.\n"
                "2. **CONCISE QUOTE SNIPPET**: Cite the key excerpt in original language using a short snippet (3-8 opening words + ellipsis `...`) formatted as `\"[Opening words...] \" (Page X / Pasal Y - Document Name)`.\n"
                "3. **MODERNIZED / TRANSLATED VERSION**: Immediately provide a clear, natural, contemporary **ENGLISH** translation or modernized phrasing (Terminology: Indonesian *Paten* = Patent, *Merek* = Trademark, *Desain Industri* = Industrial Design, *Hak Cipta* = Copyright).\n"
                "4. **PRACTICAL EXPLANATION**: Explain the core meaning and business/legal impact in plain English.\n"
                "5. Never include placeholder signatures like `[Your Name]` or `[Reviewer's Name]`."
            )
        else:
            base_instructions = (
                "Anda adalah Spesialis Penerjemahan Dokumen, Modernisasi Bahasa, dan Analis AI Lintas-Domain dalam sistem Agentic RAG Close-Environment (ChromaDB + SQLite).\n"
                "PEDOMAN WAJIB PENERJEMAHAN & MODERNISASI BAHASA (BAHASA YANG LEBIH BARU):\n"
                "1. Fokus sepenuhnya menjawab instruksi TERAKHIR pengguna secara mengalir dan padat.\n"
                "2. **KUTIPAN RINGKAS ASLI (ORIGINAL QUOTE SNIPPET)**: Jangan mengutip kalimat dinding teks yang panjang. Cukup cuplikan frasa awal (3-8 kata) diikuti elipsis `...`: `\"[Cuplikan awal...] \" (Page X / Pasal Y - Nama Dokumen)`.\n"
                "3. **VERSI BAHASA BARU (MODERN & MUDAH DIPAHAMI)**: Sajikan hasil terjemahan atau pengubahan gaya bahasa ke dalam **Bahasa Indonesia masa kini yang lugas, komunikatif, dan jernih** tanpa mengurangi ketepatan makna.\n"
                "4. **PENJELASAN INTI & IMPLIKASI PRAKTIS**: Jelaskan maksud pokok dan penerapannya dalam Bahasa Indonesia.\n"
                "5. Dilarang menyertakan placeholder tanda tangan seperti `[Your Name]` atau `[Reviewer's Name]`."
            )
    elif resp_lang == "en":
        quote_rule = (
            "2. **CONCISE ORIGINAL QUOTES**: Whenever citing source documents, use a concise quote snippet (3-8 opening words followed by ellipsis `...`): `\"[Opening words...] \" (Page X / Slide Y / Pasal Z - Document Name)`, then explain thoroughly in ENGLISH.\n"
            if requires_quotes
            else "2. **NO VERBATIM QUOTES**: Explain findings directly without quote captions.\n"
        )
        base_instructions = (
            "You are an expert Multi-Domain AI Research & Business Analyst in a Closed-Environment Agentic RAG system (ChromaDB + SQLite), specializing in Legal/Regulatory documents, Inventory & Supply Chain spreadsheets, Client Presentations, KPI Performance Decks, Financial Reports, and Technical Guides.\n"
            "MANDATORY EXECUTION RULES:\n"
            "1. **ANSWER IN ENGLISH**: You MUST write your entire response, headings, and analysis in clear, professional **ENGLISH**.\n"
            f"{quote_rule}"
            "3. **THOROUGH & SATISFACTORY EXPLANATION**: Provide a clear, substantive, and well-rounded answer. Do not overly condense the explanation; clearly explain the core principles, procedural steps, and practical context.\n"
            "4. **DOMAIN ADAPTABILITY**:\n"
            "   - For **Legal/Procedural** questions (e.g., registration flow, patent rules, nuclear liability), provide a structured Step-by-Step breakdown citing exact Articles/Sections.\n"
            "   - For **Inventory, KPI Presentations, or Client Presentations**, present exact numbers, targets vs. actuals, stock statuses, and timelines clearly.\n"
            "5. **EXTERNAL WEB SOURCES & CLICKABLE LINKS**: When Web Search results are provided, cite verified sources as direct, clickable Markdown hyperlinks: [Source Title](URL). You MUST NOT wrap links in backticks (do NOT write `[Source](URL)` or `http...`), so users can click them directly to visit the original site. Never invent placeholder signatures like `[Your Name]`."
        )
    else:
        # Default Monolingual Indonesian: balanced, thorough, informative, and fast
        quote_rule = (
            "2. **KUTIPAN RINGKAS (DIMINTA PENGGUNA)**: Pengguna meminta kutipan. Sertakan cuplikan kutipan ringkas (3-8 kata awal) diikuti tanda elipsis `...`: `\"[Cuplikan awal...] \" (Page X / Slide Y / Pasal Z - Nama Dokumen)` sebelum menjelaskan.\n"
            if requires_quotes
            else "2. **TIDAK PERLU KUTIPAN/CAPTION**: Langsung pada substansi jawaban tanpa menyertakan kutipan/caption verbatim karena tidak diminta oleh pengguna.\n"
        )
        base_instructions = (
            "Anda adalah Analis Riset AI Ahli dalam sistem Agentic RAG Close-Environment (ChromaDB + SQLite).\n"
            "PEDOMAN RESPON BERBOBOT TINGGI, CEPAT & MEMADAI:\n"
            "1. **SUBSTANSIAL & MEMADAI**: Jawab pertanyaan pengguna dalam **BAHASA INDONESIA** secara lugas, akurat, dan berbobot. Berikan penjelasan yang memuaskan dan menyeluruh (tidak disingkat secara berlebihan, dan tetap tidak bertele-tele).\n"
            f"{quote_rule}"
            "3. **STRUKTUR RAPI & JELAS**: Susun penjelasan dengan alur yang runtut (gunakan penomoran tahapan, butir-butir ketentuan, rujukan pasal/dokumen, atau tabel ringkas jika relevan) agar pengguna memahami informasi secara utuh dan jelas.\n"
            "4. **KONTEN BERBOBOT TANPA BASA-BASI**: Sajikan informasi secara fokus dan berdasar pada konteks dokumen. Dilarang menyertakan salam pembuka/penutup panjang atau placeholder tanda tangan seperti `[Your Name]` atau `[Reviewer\'s Name]`."
            "5. **STRICT GROUNDING, SITASI & TAUTAN WEB**: Setiap fakta wajib bersumber dari dokumen rujukan atau web. Jika menyertakan tautan web, WAJIB sajikan sebagai hyperlink Markdown langsung: [Judul Sumber](URL) tanpa tanda backtick agar pengguna dapat langsung mengkliknya. Sematkan sitasi sebaris nomor seperti [1], [2] tepat di akhir kalimat fakta yang diambil dari Dokumen 1, 2. Jika suatu informasi tidak tertulis dalam dokumen aktif, nyatakan secara jujur bahwa informasi tersebut tidak ditemukan."
        )

    system_prompt = request.system_prompt or base_instructions

    if orchestration.get("augmented_context"):
        system_prompt = f"{system_prompt}\n\n{orchestration['augmented_context']}"

    # Sanitize conversation history so massive previous Sub-Agent comparative reports
    # do not cause the local 7B model to mimic a 3-document comparison on a specific follow-up question
    sanitized_messages: List[ChatMessage] = []
    total_msgs = len(request.messages)
    for idx, m in enumerate(request.messages):
        is_last_msg = (idx == total_msgs - 1)
        if not is_last_msg and m.role == "assistant":
            content_lower = (m.content or "").lower()
            if (
                len(m.content or "") > 1600
                or "analisis komparatif" in content_lower
                or "matriks perbandingan" in content_lower
                or "tabel matriks" in content_lower
            ):
                sanitized_messages.append(
                    ChatMessage(
                        role="assistant",
                        content=(
                            "[Catatan Riwayat: Laporan perbandingan/audit dokumen pada giliran sebelumnya telah selesai disajikan. "
                            "Siap menjawab pertanyaan spesifik berikutnya sesuai instruksi baru pengguna.]"
                        ),
                    )
                )
                continue
        sanitized_messages.append(m)

    assistant_tokens: List[str] = []
    try:
        async for chunk in llm_service.stream_chat(
            messages=sanitized_messages,
            model=request.model,
            temperature=request.temperature or 0.3,
            system_prompt=system_prompt,
        ):
            if chunk.startswith("data: ") and not chunk.startswith("data: [DONE]"):
                try:
                    payload = json.loads(chunk[6:].strip())
                    if "token" in payload and payload["token"]:
                        assistant_tokens.append(payload["token"])
                except Exception:
                    pass
            yield chunk

    finally:
        # Save assistant reply into local SQLite database
        raw_content = "".join(assistant_tokens).strip()
        full_content = clean_boilerplate_signatures(raw_content)
        if full_content:
            assistant_msg_id = str(uuid.uuid4())
            tools_used = orchestration.get("tools_used", [])
            msg_meta = {}
            if sources_payload:
                msg_meta["sources"] = sources_payload
            if tools_used:
                msg_meta["tools_used"] = tools_used
            if subagent_events:
                msg_meta["subagent_events"] = subagent_events

            local_db_service.save_message(
                message_id=assistant_msg_id,
                thread_id=thread_id,
                role="assistant",
                content=full_content,
                metadata=msg_meta,
            )


@router.post("/stream")
async def stream_chat(
    request: ChatRequest,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    SSE streaming chat endpoint backed by local ChromaDB and SQLite.
    """
    user_id = user.get("id")
    thread_id = request.thread_id or str(uuid.uuid4())

    # Make sure the thread exists in local SQLite
    first_user_msg = next((m.content for m in request.messages if m.role == "user"), "New Conversation")
    title = (first_user_msg[:30] + "...") if len(first_user_msg) > 30 else first_user_msg
    local_db_service.create_or_get_thread(thread_id=thread_id, title=title, user_id=user_id)

    # Save the incoming user message to local SQLite
    last_user_msg = next((m for m in reversed(request.messages) if m.role == "user"), None)
    if last_user_msg:
        user_msg_id = last_user_msg.id or str(uuid.uuid4())
        local_db_service.save_message(
            message_id=user_msg_id,
            thread_id=thread_id,
            role="user",
            content=last_user_msg.content,
            created_at=last_user_msg.created_at,
        )

    generator = _generate_rag_stream(request, thread_id, user_id)

    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/threads", response_model=List[Thread])
async def list_threads(user: Dict[str, Any] = Depends(get_current_user)):
    """List all chat threads saved in local SQLite."""
    return local_db_service.list_threads(user_id=user.get("id"))


@router.get("/threads/{thread_id}/messages", response_model=List[ChatMessage])
async def get_thread_messages(
    thread_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """Load message history for a specific thread from local SQLite."""
    msgs = local_db_service.get_thread_messages(thread_id)
    return [
        ChatMessage(
            id=m["id"],
            role=m["role"],
            content=m["content"],
            created_at=m.get("created_at"),
            metadata=m.get("metadata", {}),
        )
        for m in msgs
    ]


@router.post("/threads", response_model=Thread)
async def create_thread(
    body: ThreadCreate,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """Create a new chat thread in local SQLite."""
    thread_id = str(uuid.uuid4())
    return local_db_service.create_or_get_thread(
        thread_id=thread_id,
        title=body.title or "New Conversation",
        user_id=user.get("id"),
    )


@router.patch("/threads/{thread_id}", response_model=Thread)
@router.put("/threads/{thread_id}", response_model=Thread)
async def update_thread(
    thread_id: str,
    body: ThreadUpdate,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """Rename a chat thread or toggle its pinned status in local SQLite."""
    updated = local_db_service.update_thread(
        thread_id=thread_id,
        title=body.title,
        is_pinned=body.is_pinned,
    )
    if not updated:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Thread not found")
    return updated


@router.delete("/threads/{thread_id}")
async def delete_thread(
    thread_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """Delete a chat thread and its messages from local SQLite."""
    local_db_service.delete_thread(thread_id)
    return {"status": "success", "id": thread_id}
