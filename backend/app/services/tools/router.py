import re
import logging
from typing import List, Dict, Any, Optional
from app.services.retrieval import retrieval_service
from app.services.tools.text_to_sql import text_to_sql_service
from app.services.tools.web_search import web_search_service, clean_search_query, extract_targeted_web_query
from app.services.subagents.orchestrator import subagent_orchestrator

logger = logging.getLogger(__name__)


SQL_TRIGGERS = [
    r"\bhow many (?:documents|files|chunks|rows|records|tables)\b",
    r"\b(?:count|total|average)\s+(?:of\s+)?(?:documents|files|chunks|rows|tables)\b",
    r"\blist (?:all )?(?:documents|files|chunks|tables)\b",
    r"\bwhat (?:documents|files) (?:are|do we have)\b",
    r"\bsql\b", r"\bdatabase\b", r"\bsqlite\b", r"\btable\b", r"\bcsv\b",
    r"\b(?:berapa\s+banyak|jumlah|total|daftar)\s+(?:dokumen|file|chunk|chunks|baris|data|tabel)\b",
    r"\b(?:dokumen|file|chunk)\s+(?:yang\s+tersimpan|di\s+database|terbanyak|terbesar)\b",
]

WEB_TRIGGERS = [
    # English explicit web search triggers (including "see/look in the web", "search the internet", etc.)
    r"\b(?:see|look(?:\s+up)?|search|find|check|browse|query|get)\s+(?:in|into|on|at|across|from|through)?\s*(?:the\s+)?(?:web|internet)\b",
    r"\b(?:see|look(?:\s+up)?|search|find|check|browse)\s+online\b",
    r"\b(?:in|into|on|across|from|through)\s+the\s+(?:web|internet)\b",
    r"\bweb\s+search\b",
    r"\bsearch\s+(?:the\s+)?web\b",
    r"\bonline\s+search\b",
    r"\b(?:google|bing|duckduckgo)\s+(?:search|it|for)\b",
    r"\bsearch\s+(?:with|on|via)?\s*(?:google|bing|duckduckgo)\b",

    # English freshness, news, and update queries
    r"\blatest\b",
    r"\bnews\b",
    r"\bcurrent\b",
    r"\bupdated?\s+(?:trademark|patent|law|rule|rules|regulation|regulations|policy|policies|guideline|guidelines|status|version|news|info|act)\b",
    r"\bupdates?\s+(?:on|about|regarding|for)\b",
    r"\b(?:any|is there any|are there any)\s+updates?\b",

    # Indonesian explicit web search triggers
    r"\b(?:cari(?:kan)?|lihat|cek|tinjau|periksa)\s+(?:di|lewat|melalui|pada)?\s*(?:web|internet|google|bing|duckduckgo|online)\b",
    r"\b(?:di|lewat|melalui|pada)\s+(?:web|internet)\b",
    r"\bcari(?:\s+secara)?\s+online\b",

    # Indonesian freshness & update triggers
    r"\bberita terbaru\b",
    r"\btren\b",
    r"\bapa(?:kah)?\s+ada\s+update\b",
    r"\bupdate\s+(?:terbaru|terkini|peraturan|hukum|aturan|uu)\b",
    r"\brilis\s+(?:terbaru|terkini)\b",
]


class AgentRouter:
    """
    Learning Note (Modules 7 & 8 - Agent Tool Router):
    Decides which tool(s) to run before sending the prompt to the main LLM:
    1. If the user asks for a full-document audit or multi-document comparison -> delegate to Sub-Agents.
    2. If the user asks a counting/table question -> run the Text-to-SQL tool on local SQLite.
    3. If the user asks for online updates -> run the Web Search tool.
    4. For normal document questions -> run Hybrid Search (ChromaDB Vector + BM25 + Reranker).
    """

    def detect_sql_intent(self, query: str) -> bool:
        q_lower = query.lower()
        return any(re.search(pat, q_lower) for pat in SQL_TRIGGERS)

    def detect_web_intent(self, query: str) -> bool:
        q_lower = query.lower()
        return any(re.search(pat, q_lower) for pat in WEB_TRIGGERS)

    async def orchestrate(
        self,
        query: str,
        user_id: Optional[str] = None,
        metadata_filter: Optional[Dict[str, Any]] = None,
        search_mode: str = "hybrid",
        enable_web_fallback: bool = True,
        enable_sql: bool = True,
        subagent_model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute necessary tools based on user intent and fallback policies.
        Returns tool events, context, sources, and direct sub-agent streaming config.
        """
        tool_events: List[Dict[str, Any]] = []
        subagent_events: List[Dict[str, Any]] = []
        context_blocks: List[str] = []
        sources_payload: List[Dict[str, Any]] = []
        tools_used: List[str] = []

        is_sql_intent = enable_sql and self.detect_sql_intent(query)
        is_web_explicit = enable_web_fallback and self.detect_web_intent(query)

        # -------------------------------------------------------------
        # 0. SUB-AGENT DEEP ANALYSIS & MULTI-DOC COMPARISON (Module 8)
        # -------------------------------------------------------------
        if not is_sql_intent:
            subagent_scenario = subagent_orchestrator.detect_scenario(
                query=query,
                metadata_filter=metadata_filter,
            )
            if subagent_scenario:
                logger.info(f"Sub-agent scenario detected: {subagent_scenario.get('type')}")
                web_context = ""
                web_sources: List[Dict[str, Any]] = []

                if is_web_explicit:
                    clean_web_q = extract_targeted_web_query(query)
                    tool_events.append({"tool": "web_search", "status": "executing", "query": clean_web_q})
                    try:
                        web_results = await web_search_service.search(clean_web_q, max_results=4)
                        if web_results:
                            tools_used.append("web_search")
                            tool_events.append({
                                "tool": "web_search",
                                "status": "success",
                                "count": len(web_results),
                            })
                            web_context = web_search_service.format_web_context(web_results)
                            for idx, w in enumerate(web_results, 1):
                                web_sources.append({
                                    "id": f"web-src-{idx}",
                                    "filename": w.get("url", "Web Link"),
                                    "title": w.get("title", "Web Page"),
                                    "url": w.get("url"),
                                    "document_type": "web",
                                    "similarity": 0.95,
                                    "search_mode": "web",
                                    "snippet": w.get("snippet", ""),
                                })
                        else:
                            tool_events.append({"tool": "web_search", "status": "no_results"})
                    except Exception as e:
                        logger.warning(f"Composite web search error: {e}")
                        tool_events.append({"tool": "web_search", "status": "failed", "error": str(e)})

                try:
                    prep = await subagent_orchestrator.prepare_scenario(
                        scenario=subagent_scenario,
                        query=query,
                        subagent_model=subagent_model,
                        web_context=web_context if web_context else None,
                        web_sources=web_sources if web_sources else None,
                    )
                    agent_name = prep["subagent_events"][0].get("name")
                    tool_events.append({
                        "tool": "subagent_spawn",
                        "status": "executing",
                        "scenario": subagent_scenario.get("type"),
                        "agent": agent_name,
                        "model": prep.get("subagent_model"),
                    })
                    subagent_tools = ["subagent_" + prep["scenario_type"]]
                    if web_sources:
                        subagent_tools.append("web_search")

                    return {
                        "is_subagent_direct": True,
                        "tool_events": tool_events,
                        "subagent_events": prep["subagent_events"],
                        "subagent_system_prompt": prep["system_prompt"],
                        "subagent_user_prompt": prep["user_prompt"],
                        "subagent_model": prep["subagent_model"],
                        "sources_payload": prep["sources_payload"],
                        "tools_used": subagent_tools,
                    }
                except Exception as e:
                    logger.error(f"Sub-agent preparation error: {e}", exc_info=True)
                    tool_events.append({"tool": "subagent_spawn", "status": "failed", "error": str(e)})

        # -------------------------------------------------------------
        # 1. TEXT-TO-SQL TOOL (if quantitative, aggregation, or metadata query)
        # -------------------------------------------------------------
        sql_executed = False
        if is_sql_intent:
            tool_events.append({"tool": "text_to_sql", "status": "executing", "query": query})
            try:
                sql_res = await text_to_sql_service.run_text_to_sql(query)
                if sql_res and sql_res.get("success"):
                    sql_executed = True
                    tools_used.append("text_to_sql")
                    tool_events.append({
                        "tool": "text_to_sql",
                        "status": "success",
                        "sql": sql_res.get("sql"),
                        "row_count": sql_res.get("row_count", 0),
                    })
                    context_blocks.append(
                        f"### HASIL KUERI DATABASE TERSTRUKTUR (SQLite Text-to-SQL)\n"
                        f"Kueri SQL yang Dieksekusi: `{sql_res.get('sql')}`\n"
                        f"Hasil:\n{sql_res.get('markdown_table')}\n"
                        f"---"
                    )
                    sources_payload.append({
                        "id": "sql-result-1",
                        "filename": "Database Analytics (SQL)",
                        "title": f"SQL: {sql_res.get('sql')}",
                        "document_type": "sql_query",
                        "similarity": 1.0,
                        "search_mode": "sql",
                        "snippet": sql_res.get("markdown_table", "")[:250],
                    })
            except Exception as e:
                logger.warning(f"Text-to-SQL tool failed: {e}")
                tool_events.append({"tool": "text_to_sql", "status": "failed", "error": str(e)})

        # -------------------------------------------------------------
        # 2. EXPLICIT WEB SEARCH (Prioritized when user explicitly asks for web search)
        # -------------------------------------------------------------
        web_search_executed = False
        if is_web_explicit:
            clean_q = extract_targeted_web_query(query)
            tool_events.append({"tool": "web_search", "status": "executing", "query": clean_q})
            try:
                web_results = await web_search_service.search(clean_q, max_results=4)
                if web_results:
                    web_search_executed = True
                    tools_used.append("web_search")
                    tool_events.append({
                        "tool": "web_search",
                        "status": "success",
                        "count": len(web_results),
                    })
                    web_context = web_search_service.format_web_context(web_results)
                    context_blocks.append(web_context)

                    for idx, w in enumerate(web_results, 1):
                        sources_payload.append({
                            "id": f"web-src-{idx}",
                            "filename": w.get("url", "Web Link"),
                            "title": w.get("title", "Web Page"),
                            "url": w.get("url"),
                            "document_type": "web",
                            "similarity": 0.95,
                            "search_mode": "web",
                            "snippet": w.get("snippet", ""),
                        })
                else:
                    tool_events.append({"tool": "web_search", "status": "no_results"})
            except Exception as e:
                logger.warning(f"Explicit web search failed: {e}")
                tool_events.append({"tool": "web_search", "status": "failed", "error": str(e)})

        # -------------------------------------------------------------
        # 3. LOCAL HYBRID RETRIEVAL TOOL (Vector + BM25 + RRF + Reranker)
        # -------------------------------------------------------------
        retrieved_chunks = []
        also_mentions_local_docs = bool(
            re.search(
                r"\b(?:dokumen|file|upload|berikan|presentasi|inventaris|kpi|laporan|document|documents|files|uploaded|provided|presentation|inventory|report)\b",
                query,
                re.IGNORECASE,
            )
        )
        is_detailed_query = bool(
            re.search(
                r"\b(?:detail|mendalam|rinci|rincian|lengkap|komprehensif|jelaskan\s+(?:secara\s+)?lengkap|penjelasan\s+mendalam|in[- ]depth|thorough|detailed|comprehensive|deeply|fully)\b",
                query,
                re.IGNORECASE,
            )
        )
        is_concise_query = not is_detailed_query and bool(
            re.search(
                r"\b(?:ringkas(?:\s+saja)?|singkat(?:\s+saja)?|brief|concise|short|pendek|garis\s+besar(?:nya)?|quick\s+summary|overview\s+only)\b",
                query,
                re.IGNORECASE,
            )
        )
        is_procedural_flow_query = bool(
            re.search(
                r"\b(?:alur|prosedur|tahapan|tata\s+cara|proses|mekanisme|syarat|registration\s+flow|registration\s+process|application\s+procedure|how\s+to\s+register|steps\s+to\s+register|requirements)\b",
                query,
                re.IGNORECASE,
            )
        )

        # Skip local RAG if user is ONLY asking a pure external web search question OR pure SQL inventory query
        if not (is_web_explicit and web_search_executed and not also_mentions_local_docs) and not sql_executed:
            try:
                similarity_thresh = 0.55 if is_web_explicit else 0.25
                if is_detailed_query or is_procedural_flow_query:
                    adaptive_top_k = 7
                elif is_concise_query:
                    adaptive_top_k = 3
                else:
                    adaptive_top_k = 5
                raw_chunks = await retrieval_service.retrieve_relevant_chunks(
                    query=query,
                    user_id=user_id,
                    top_k=adaptive_top_k,
                    threshold=similarity_thresh,
                    metadata_filter=metadata_filter,
                    search_mode=search_mode,
                    rerank=True,
                )

                if is_web_explicit and web_search_executed:
                    retrieved_chunks = [
                        c for c in raw_chunks
                        if (c.get("similarity", 0) or c.get("vector_similarity", 0)) >= 0.55
                    ]
                else:
                    retrieved_chunks = raw_chunks

            except Exception as e:
                logger.warning(f"Local retrieval error: {e}")

        if retrieved_chunks:
            tools_used.append(f"retrieval_{search_mode}")
            tool_events.append({
                "tool": "local_retrieval",
                "status": "success",
                "count": len(retrieved_chunks),
                "mode": search_mode,
            })
            rag_context = retrieval_service.format_rag_context(retrieved_chunks)
            context_blocks.append(rag_context)

            # Map chunk sources
            # Map chunk sources with citation indices and full content for interactive highlights
            for idx, c in enumerate(retrieved_chunks, 1):
                meta = c.get("metadata", {})
                content_str = c.get("content", "")

                page_val = meta.get("page") or meta.get("page_number")
                if page_val:
                    loc_label = f"Page {page_val}"
                else:
                    pm = re.search(r"---\s*(Page\s*\d+|Slide\s*\d+)\s*---", content_str, re.IGNORECASE)
                    if pm:
                        loc_label = pm.group(1).title()
                    else:
                        pasal_m = re.search(r"\b(Pasal\s+\d+[A-Za-z]?)\b", content_str, re.IGNORECASE)
                        loc_label = pasal_m.group(1).title() if pasal_m else ""

                sources_payload.append({
                    "id": c.get("id"),
                    "citation_index": idx,
                    "document_id": c.get("document_id"),
                    "filename": meta.get("filename", "Document"),
                    "title": meta.get("doc_title") or meta.get("title") or meta.get("filename", "Document"),
                    "document_type": meta.get("doc_type", "general"),
                    "keywords": meta.get("keywords", []),
                    "similarity": c.get("similarity", 0) or c.get("vector_similarity", 0),
                    "search_mode": c.get("search_mode", search_mode),
                    "rrf_score": c.get("rrf_score"),
                    "rerank_score": c.get("rerank_score"),
                    "rerank_rank": c.get("rerank_rank") or idx,
                    "rerank_reason": c.get("rerank_reason"),
                    "page_label": loc_label,
                    "content": content_str,
                    "snippet": (content_str[:160] + "...") if len(content_str) > 160 else content_str,
                })

        # -------------------------------------------------------------
        # 4. STRICT GROUNDING GUARDRAIL (Zero-Evidence Out-of-Scope Protection)
        # -------------------------------------------------------------
        # Web search is STRICTLY OPT-IN: only runs when user explicitly requests it.
        # If no relevant chunks exist in the selected documents, strictly instruct LLM to refuse rather than hallucinate.
        if not web_search_executed and not sql_executed and len(retrieved_chunks) == 0:
            guardrail_text = (
                "### STRICT GROUNDING & ZERO-EVIDENCE GUARDRAIL\n"
                "PERINGATAN SISTEM: Informasi yang ditanyakan pengguna TIDAK DITEMUKAN sama sekali di dalam dokumen aktif yang dipilih di ruang kerja (knowledge base).\n"
                "PEDOMAN WAJIB:\n"
                "1. Nyatakan dengan sopan dan lugas bahwa fakta atau informasi tersebut tidak tercantum dalam dokumen aktif yang dipilih.\n"
                "2. DILARANG KERAS mengarang jawaban, berhalusinasi, atau menggunakan pengetahuan luar untuk memvalidasi fakta yang tidak ada di dokumen.\n"
                "3. Beri tahu pengguna bahwa jika mereka ingin mencari informasi eksternal di luar dokumen, mereka dapat menambahkan kata kunci pencarian web (misalnya 'cari di web')."
            )
            context_blocks.append(guardrail_text)

        augmented_context = "\n\n".join(context_blocks).strip()

        return {
            "tool_events": tool_events,
            "subagent_events": subagent_events,
            "augmented_context": augmented_context,
            "sources_payload": sources_payload,
            "tools_used": tools_used,
        }


agent_router = AgentRouter()
