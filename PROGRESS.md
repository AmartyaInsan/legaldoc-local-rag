# Learning Progress Notes (PROGRESS.md)

I use this file to keep track of the modules I completed while following the [Agentic RAG Masterclass YouTube tutorial](https://www.youtube.com/watch?v=xgPWCuqLoek&t=1801s), adapted with AI assistance to run in a **100% local closed-environment** (using **Ollama**, **ChromaDB**, and **SQLite**) for confidential legal and multi-domain business documents.

## Status Legend
- `[ ]` = Not started
- `[-]` = In progress
- `[x]` = Completed

## Module Checklist

### Module 1: App Shell + Basic Streaming
- [x] Set up project folders (Frontend: React + TypeScript + Vite + Tailwind; Backend: Python FastAPI inside `venv`)
- [x] Configure LLM connection to **local Ollama** (`qwen2.5:7b` and `nomic-embed-text`) instead of cloud OpenAI APIs
- [x] Create SSE streaming chat endpoint (`/api/chat/stream`)
- [x] Build dark-mode chat UI (conversation sidebar, markdown rendering, copy button)
- [x] Set up local database storage (`local_db.py`) so no external cloud setup is needed
- [x] Test end-to-end chat streaming from React frontend to FastAPI and local Ollama

### Module 2: BYO Retrieval + Persistent Memory
- [x] Build Knowledge Base page for drag-and-drop document uploads
- [x] Save document status and chunk counts in local SQLite (`legal_rag.db`)
- [x] Write text splitter (`chunking.py`) & 768-dim vector embedding service via Ollama (`nomic-embed-text`)
- [x] Store and search vectors locally using **ChromaDB** (`chromadb.PersistentClient` with cosine similarity)
- [x] Inject retrieved document chunks into the system prompt with source citations
- [x] Save chat threads and message history in SQLite so the AI remembers previous turns
- [x] Test uploading a legal PDF/Word document and asking questions about its contents

### Module 3: Record Manager (Deduplication)
- [x] Calculate SHA-256 content hashes in SQLite so uploading the exact same file twice is automatically skipped
- [x] Automatically replace old chunks in SQLite and ChromaDB when a file with the same filename is uploaded with updated content
- [x] Add parsers for PDF, Word (`.docx`), Markdown, TXT, CSV, and JSON files
- [x] Test uploading a duplicate file to confirm the deduplication notice works

### Module 4: Metadata Extraction
- [x] Extract structured document info (title, short summary, document category, keywords) using Ollama + Pydantic validation
- [x] Support 6 domain categories (`legal`, `inventory`, `presentation`, `kpi_report`, `financial`, `technical`)
- [x] Save extracted metadata onto each chunk in SQLite and ChromaDB so searches can be filtered
- [x] Display document type badges and keyword tags on Knowledge Base cards

### Module 5: Multi-Format Support (`.pptx`, `.xlsx`, `.pdf`, `.docx`) & Cascade Delete
- [x] Improve multi-format parsing (`document_parser.py`), including zero-dependency native XML parsers for PowerPoint slides (`.pptx`) and Excel spreadsheets (`.xlsx`)
- [x] Implement **Cascade Delete**: deleting a document removes its metadata, all text chunks from SQLite, and all vector embeddings from ChromaDB
- [x] Add a confirmation modal in the UI before deleting a document

### Module 6: Hybrid Search & Reranking
- [x] Add BM25 keyword search over local SQLite chunks to complement ChromaDB dense vector search
- [x] Combine Vector Search and BM25 rankings using **Reciprocal Rank Fusion (RRF)** (math formula structured with AI assistance)
- [x] Build a lightweight local reranker (`reranker.py`) that boosts chunks with exact legal article/phrase matches
- [x] Add a search mode selector in the chat UI (Hybrid / Vector Only / Keyword Only)

### Module 7: Additional Tools (Text-to-SQL & Opt-In Web Search)
- [x] Connect the Text-to-SQL tool (`text_to_sql.py`) directly to the persistent `legal_rag.db` SQLite database and automatically sync uploaded `.csv` and `.xlsx` spreadsheets into queryable SQL tables
- [x] Add a keyless Web Search tool (`web_search.py`) that only runs when explicitly requested by the user (strict anti-hallucination guardrail)
- [x] Build a query router (`router.py`) to decide when to use local RAG, SQL, or Web Search

### Module 8: Sub-Agents (Deep Document Audit & Multi-Document Comparison)
- [x] Automatically detect when the user asks for a full-document audit or a side-by-side comparison of multiple documents
- [x] Create isolated Sub-Agents (`DocumentAnalystSubAgent` and `DocumentComparatorSubAgent`) that read representative chunks sequentially from the start, middle, and end of documents
- [x] Stream Sub-Agent output directly to the user in a single pass so it runs fast on a local laptop
- [x] Add a secondary model selector in the Header UI so the Sub-Agent can use its own Ollama model

### Module 9: NotebookLM-Inspired Features & Bilingual Cross-Lingual RAG
- [x] **Interactive Inline Citations (`[1]`, `[2]`):** Clickable citation badges in chat answers that open a Grounding Passage Inspector modal with the exact source quote, page/slide/article number, and similarity score
- [x] **Multi-Document Workspace Selector:** Checkbox menu in the chat input (`📚 X/Y Dokumen Aktif`) to toggle which documents are active for the current query
- [x] **Bilingual (`ID ↔ EN`) & Statutory Language Modernization:** Support cross-lingual Q&A with original quote snippets and translating older legal language into modern, easy-to-understand Indonesian (*bahasa yang lebih baru*)
- [x] **Thread Management:** Inline Rename Chat and 1-click Pin Chat to Top stored in local SQLite
