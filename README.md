# LegalDoc & Multi-Domain Agentic RAG (100% Local Close-Environment: Ollama + ChromaDB + SQLite)

A privacy-first, fully offline-capable **Agentic RAG (Retrieval-Augmented Generation)** system built from scratch. Originally created to analyze, search clauses/articles, and compare **Indonesian legal documents**, this system has evolved into a comprehensive **Multi-Domain & Bilingual (Bahasa Indonesia ↔ English)** knowledge engine inspired by **Google NotebookLM**. It effortlessly processes **Legal Statutes (`.pdf`), Contracts (`.docx`), Inventory Spreadsheets (`.xlsx`/`.csv`), Client Pitch Decks (`.pptx`), KPI Performance Reports, Financial Statements, and Technical Documentation** without a single byte of data leaving your machine.

---

## 📌 Project Reference & Background

This project began as my learning journey following the architectural foundation from this YouTube masterclass:
👉 **[Agentic RAG Masterclass - YouTube Tutorial](https://www.youtube.com/watch?v=xgPWCuqLoek&t=1801s)**

As someone learning to build modern Agentic RAG systems with FastAPI and React, I developed this codebase **with AI coding assistance** while studying, testing, and customizing each module step-by-step. While the original tutorial relied on cloud LLMs (OpenAI/OpenRouter) and cloud database services (Supabase pgvector), I rebuilt and customized this project into an **autonomous, 100% close-environment local system** (so confidential legal and business documents never leave the local computer), complete with hybrid retrieval, deep legal/analytical sub-agents, and interactive NotebookLM-inspired features.

---

## 🚀 Key Architectural Evolution & Enhancements

### 1. 100% Close-Environment & Local Offline Storage
- **Replaced Cloud Supabase (`pgvector`) with Local ChromaDB + SQLite**:
  - **ChromaDB (`chromadb.PersistentClient`)**: Persists 768-dimensional vector embeddings on disk at `backend/local_data/chroma` and executes fast HNSW cosine similarity search locally. Zero external database configuration required.
  - **SQLite (`legal_rag.db`)**: Native to Python (`sqlite3`). Persists conversation threads, message logs, chunk tables for BM25 keyword matching, and powers the **Text-to-SQL tool** that automatically synchronizes uploaded `.csv` and `.xlsx` spreadsheets into queryable relational SQL tables.

### 2. Local AI Engine & Embeddings (Ollama)
- **Primary & Sub-Agent LLM**: Powered by local `qwen2.5:7b` (or any local GGUF model via Ollama) running at full speed on local consumer GPUs (e.g., NVIDIA RTX 4070 Laptop, RTX 3060/4060).
- **Embedding Model**: Local `nomic-embed-text:latest` (768 dimensions), batching multi-page document embeddings rapidly without external API latency.

### 3. Multi-Format & Multi-Domain Document Intelligence
- **Universal Format Support**: Parses `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.csv`, `.html`, `.md`, `.txt`, and `.json`.
- **Zero-Dependency Native XML Parsing**: Custom fast XML extractors parse PowerPoint slides (`.pptx`) and Excel worksheets (`.xlsx`) row-by-row and slide-by-slide without requiring heavyweight external desktop dependencies.
- **6 Domain Categories**: Automatic metadata extraction categorizes uploads into:
  - `legal` (Laws, regulations, ministerial decrees, contracts)
  - `inventory` (Stock levels, SKUs, warehouse supplies)
  - `presentation` (Client pitch decks, marketing slides, project roadmaps)
  - `kpi_report` (Quarterly targets vs. actuals, team milestones)
  - `financial` (Revenue statements, balance sheets, budgets)
  - `technical` (API specifications, engineering manuals, guidelines)

### 4. Bilingual Cross-Lingual RAG (`ID ↔ EN`) & Language Modernization
- **Adaptive Language Mirroring**: Automatically matches the user's prompt language or follows explicit instructions (`"in English"`, `"dalam Bahasa Indonesia"`).
- **Original Quote Preservation**: When translating across languages (e.g. explaining an Indonesian statutory decree in English, or explaining a US Patent Act in Indonesian), the AI preserves key original excerpt snippets with page/article citations before providing the translated explanation.
- **Statutory Language Modernization (*Bahasa Baru*)**: Capable of converting archaic, dense, or convoluted legal phraseology (e.g., older statutes like UU 2001) into contemporary, plain Indonesian (*bahasa yang lebih baru dan mudah dipahami*) while retaining full legal validity.

### 5. NotebookLM-Inspired Features
- **Interactive Inline Citations (`[1]`, `[2]`)**: Claims in AI answers feature clickable citation badges. Clicking any badge opens the **Grounding Passage Inspector** modal displaying the exact source excerpt, page/slide/article number, similarity match score, and a 1-click copy button.
- **Workspace Paradigm (Multi-Document Selection)**: A multi-select checkbox menu in the chat input (`📚 X/Y Dokumen Aktif`) lets users toggle exactly which uploaded documents serve as active reference material. Includes quick-actions: *Pilih Semua* (Select All), *Kosongkan* (Clear), and *Hanya Ini* (Solo focus on one document).
- **Strict Grounding & Anti-Hallucination Guardrail**: The system strictly grounds answers in the active documents. If a question cannot be answered from the retrieved context and the user did not ask for web search, the AI politely refuses rather than hallucinating from open weights. Web search is strictly opt-in.
- **Conversation Management**:
  - **Rename Chat**: Inline editing of chat thread titles with `Enter` to save and `Esc` to cancel.
  - **Pin Chat to Top**: 1-click pin toggling; pinned chats display an amber badge and stay anchored at the top of the conversation list.

### 6. Zero-Pause Inference Optimization
- Warm Time-To-First-Token (TTFT) optimized to **~0.88 seconds**, ensuring instantaneous token streaming without runner recreation delays.

---

## 🧭 Developer Customization Guide (Codebase Roadmap)

If you wish to modify or customize any layer of this system (AI model, parser/chunking, or vector database), here is the exact map of files and configuration points:

```
claude-code-agentic-rag-masterclass/
├── backend/
│   ├── .env.example                   <-- Environment variables template (copy to .env)
│   ├── app/
│   │   ├── core/
│   │   │   └── config.py              <-- [1] AI models, ports, paths, and settings
│   │   ├── services/
│   │   │   ├── llm.py                 <-- [1] LLM client & streaming generation
│   │   │   ├── chunking.py            <-- [2] Text splitter, chunk size & overlap
│   │   │   ├── document_parser.py     <-- [2] Multi-format file parsers (.pdf, .docx, .pptx, etc.)
│   │   │   ├── metadata_extractor.py  <-- [2] Domain category & keyword extraction
│   │   │   ├── embeddings.py          <-- [3] Embedding model & vector generation
│   │   │   ├── local_db.py            <-- [3] ChromaDB vector store & SQLite schema
│   │   │   ├── retrieval.py           <-- [3] Hybrid Search (Vector + BM25 + RRF)
│   │   │   ├── reranker.py            <-- [3] Cross-scoring reranker
│   │   │   ├── tools/
│   │   │   │   └── router.py          <-- [4] Agent tools router (SQL, Web, Retrieval)
│   │   │   └── subagents/
│   │   │       ├── orchestrator.py    <-- [4] Sub-Agent delegation logic
│   │   │       ├── analyst.py         <-- [4] Deep Legal & Contract Audit Sub-Agent
│   │   │       └── comparator.py      <-- [4] Multi-Document Comparison Sub-Agent
│   │   └── api/
│   │       └── endpoints/
│   │           ├── chat.py            <-- System prompts, tone, citations, threads
│   │           └── documents.py       <-- Ingestion pipeline & document CRUD
└── frontend/
    └── src/
        ├── components/
        │   ├── ChatMessage.tsx        <-- Citation badges & Grounding Inspector Modal
        │   ├── ChatInput.tsx          <-- Multi-document checkbox selector & search modes
        │   ├── Sidebar.tsx            <-- Thread list, Rename Chat & Pin Chat UI
        │   └── DocumentManager.tsx    <-- File upload & Knowledge Base manager
        └── services/
            └── api.ts                 <-- API client for FastAPI endpoints
```

---

### A. How to Change the AI / LLM Model & Provider
| Setting | File Location | How to Change |
|---|---|---|
| **Primary LLM Model** | `backend/.env` & [`backend/app/core/config.py`](./backend/app/core/config.py) | Change `LLM_MODEL="qwen2.5:7b"` to any model available in your Ollama library (e.g. `llama3.1:8b`, `mistral:7b`, `gemma2:9b`). |
| **Sub-Agent Model** | `backend/.env` & [`backend/app/core/config.py`](./backend/app/core/config.py) | Change `SUBAGENT_MODEL="qwen2.5:7b"`. You can use a lighter model for sub-agents or a larger one for complex comparisons. |
| **Switch Provider (OpenAI, vLLM, DeepSeek)** | [`backend/app/services/llm.py`](./backend/app/services/llm.py) | The `LLMService` uses `AsyncOpenAI`. Change `LLM_BASE_URL` in `.env` to point to any OpenAI-compatible endpoint (e.g., `http://localhost:8000/v1` for vLLM, or `https://api.openai.com/v1`). |
| **System Prompts & Personas** | [`backend/app/api/endpoints/chat.py`](./backend/app/api/endpoints/chat.py) | Modify `base_instructions` inside lines 190–300 to adjust tone, strictness, legal structure, or concise/detailed thresholds. |

---

### B. How to Change Document Parsers & Chunking
| Setting | File Location | How to Change |
|---|---|---|
| **Chunk Size & Overlap** | [`backend/app/services/chunking.py`](./backend/app/services/chunking.py) | Edit `chunk_size` (default: `800` characters) and `overlap` (default: `150` characters) in the `chunk_text()` function. |
| **Chunk Breakpoint Rules** | [`backend/app/services/chunking.py`](./backend/app/services/chunking.py) | Modify `separators = ["\n\n", "\n", ". ", "? ", "! ", " "]` to adjust how paragraphs and sentences are split. |
| **File Type Parsers** | [`backend/app/services/document_parser.py`](./backend/app/services/document_parser.py) | Add or modify custom extractors inside `DocumentParserService`. For example, replace or combine PDF parsers with OCR tools (`pytesseract`, `pdfplumber`, or `docling`). |
| **Metadata Extraction** | [`backend/app/services/metadata_extractor.py`](./backend/app/services/metadata_extractor.py) | Adjust the Pydantic schema `DocumentMetadata` or the extraction prompt to extract custom fields (e.g., contract value, expiration date, author). |

---

### C. How to Change Vector Database & Embeddings
| Setting | File Location | How to Change |
|---|---|---|
| **Embedding Model** | `backend/.env` & [`backend/app/core/config.py`](./backend/app/core/config.py) | Change `EMBEDDING_MODEL="nomic-embed-text:latest"` to another local embedding model (e.g. `bge-m3`, `all-minilm`) or cloud embeddings (`text-embedding-3-small`). |
| **Embedding Dimensions** | [`backend/app/core/config.py`](./backend/app/core/config.py) | Set `EMBEDDING_DIMENSIONS: int = 768` (ensure it matches your embedding model's output vector size). |
| **ChromaDB Path & Metric** | [`backend/app/services/local_db.py`](./backend/app/services/local_db.py) | Inside `_init_chroma()`, adjust `metadata={"hnsw:space": "cosine"}` to `"l2"` (Euclidean) or `"ip"` (Inner Product). Change `CHROMA_COLLECTION_NAME` in `config.py` to reindex into a fresh collection. |
| **Swap to Qdrant / Milvus / pgvector** | [`backend/app/services/local_db.py`](./backend/app/services/local_db.py) | Replace `self.chroma_client` calls in `store_chunks_and_vectors`, `query_chroma_vectors`, and `delete_document_and_chunks` with your database client SDK of choice. |
| **Hybrid Search & BM25 Weights** | [`backend/app/services/retrieval.py`](./backend/app/services/retrieval.py) | Adjust `k1` and `b` in `BM25Searcher`, or modify the RRF formula constant (`60.0`) inside `retrieve_relevant_chunks()`. |

---

### D. How to Add New Agent Tools or Sub-Agents
| Setting | File Location | How to Change |
|---|---|---|
| **Agent Tool Router** | [`backend/app/services/tools/router.py`](./backend/app/services/tools/router.py) | Add new tools (e.g., calculator, weather API, external CRM connector) in `orchestrate()`. |
| **Sub-Agent Logic** | [`backend/app/services/subagents/`](./backend/app/services/subagents/) | Create new specialist sub-agents inheriting from isolated prompt execution templates in `orchestrator.py`. |

---

## 🛠️ Tech Stack Overview

| Layer | Technology Used | Purpose |
|---|---|---|
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS, Lucide Icons | Responsive UI with real-time SSE streaming, interactive citation inspection, and workspace management |
| **Backend** | Python 3.10+, FastAPI, Pydantic v2 | High-performance async REST API and SSE endpoints (no LangChain/LangGraph dependencies) |
| **Local LLM** | Ollama (`qwen2.5:7b`) | In-depth reasoning, statutory analysis, bilingual translation, and sub-agent synthesis |
| **Local Embeddings** | Ollama (`nomic-embed-text`) | 768-dimensional dense vector embeddings |
| **Vector DB** | ChromaDB (`chromadb.PersistentClient`) | On-disk HNSW index with cosine similarity search |
| **Relational DB** | SQLite (`sqlite3`) | Persistent thread history, document registry, BM25 text corpus, and dynamic Text-to-SQL tables |
| **Document Parsers** | `pypdf`, `python-docx`, native XML parsers for `.pptx`/`.xlsx` | Fast multi-domain structured text and table extraction |

---

## 🚀 How to Run Locally

Everything runs locally on your machine—no cloud API keys or external database setup required.

### 1. Prerequisites
- [Ollama](https://ollama.com/) installed and running.
- Python 3.10 or newer.
- Node.js 18 or newer and npm.

Pull the recommended local models via terminal:
```bash
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

### 2. Backend Setup (FastAPI)
```bash
# 1. Navigate to backend directory
cd backend

# 2. Create and activate virtual environment
# Windows PowerShell:
python -m venv venv
.\venv\Scripts\Activate.ps1

# Linux / macOS:
python3 -m venv venv
source venv/bin/activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Copy environment configuration
cp .env.example .env   # (Windows: copy .env.example .env)

# 5. Start the backend server
python -m uvicorn app.main:app --reload --port 8000
```
*Note: The backend automatically creates the `backend/local_data/` directory and initializes SQLite (`legal_rag.db`) and ChromaDB upon first run.*

### 3. Frontend Setup (React + Vite)
Open a new terminal window:
```bash
# 1. Navigate to frontend directory
cd frontend

# 2. Install Node dependencies
npm install

# 3. Start Vite development server
npm run dev
```
Open your browser and navigate to **`http://localhost:5173`**.

---

## 🧪 Verification & Testing

To test the system pipeline, run the verification scripts in `scratch/`:
```bash
# Run end-to-end verification (Search, Strict Grounding, Citations, Thread Management):
.\backend\venv\Scripts\python.exe scratch/test_rename_pin_and_speed.py
```
To verify the frontend build:
```bash
cd frontend
npm run build
```

---

## 📄 License & Attribution

This project is open-source under the MIT License. Feel free to use, modify, and adapt it for your own research, enterprise document automation, or learning journey!
