# IntelliDoc — Insurance Document Intelligence Agent

> **A fully local, privacy-first Agentic RAG system that reads insurance policy PDFs, answers questions about them, and extracts structured data — all without sending a single byte to the cloud.**

---

## What Does This App Do?

IntelliDoc lets you upload any insurance policy PDF and then:

| Feature | What You Can Do |
|---|---|
| **Smart Upload** | Upload a PDF — the AI automatically parses every page, chunks it, embeds it, and indexes it in under 30 seconds |
| **Ask Questions** | Ask anything in plain English: *"What sports are excluded?"* or *"What is the claims procedure?"* |
| **Extract Data** | Click one button to extract all 8 key policy fields into a structured table, validated by a Pydantic schema |
| **Transparent AI** | See every reasoning step the agent took, which tool it selected, and which page the answer came from |
| **Document Memory** | Upload the same file again — the system recognizes it via MD5 hash and skips re-processing |
| **Live Pipeline Logs** | Watch each step of the ingestion or inference pipeline appear in real-time as it runs |

---

## System Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Your Browser                      │
│          React 18 + TypeScript + Vite               │
│   Upload PDF │ Ask Questions │ Extract Policy Data  │
└───────────────────┬─────────────────────────────────┘
                    │  HTTP / REST API
                    ▼
┌─────────────────────────────────────────────────────┐
│              FastAPI Backend (Python)               │
│                  Port :8000                         │
│                                                     │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ /upload  │  │    /ask      │  │  /extract    │  │
│  └────┬─────┘  └──────┬───────┘  └──────┬───────┘  │
│       │               │                 │           │
│       ▼               ▼                 ▼           │
│  ┌─────────┐   ┌────────────┐   ┌────────────────┐  │
│  │ parser  │   │   agent   │   │   extractor    │  │
│  │ .py     │   │   .py     │   │   .py          │  │
│  └────┬────┘   └─────┬──────┘   └───────┬────────┘  │
│       │              │                  │            │
│       ▼              ▼                  ▼            │
│  ┌──────────────────────────────────────────────┐   │
│  │              vectorstore.py                  │   │
│  │   ChromaDB (vectors on disk)                 │   │
│  │   BM25 (keyword index in memory)             │   │
│  │   Hybrid search via RRF                      │   │
│  └──────────────────────────────────────────────┘   │
│                       │                             │
└───────────────────────┼─────────────────────────────┘
                        │  Local HTTP (port 11434)
                        ▼
┌─────────────────────────────────────────────────────┐
│                  Ollama (Local AI)                  │
│   llama3.1:latest         — Reasoning & Generation  │
│   nomic-embed-text:latest — Text Embeddings         │
│                                                     │
│   Runs 100% on your machine. No API key needed.     │
└─────────────────────────────────────────────────────┘
```

---

## The Three Pipelines

### Pipeline 1 — Document Upload & Indexing

When you upload a PDF, this is exactly what happens:

```
PDF File Uploaded
      │
      ▼
┌─────────────────────────────────┐
│  1. MD5 Hash Check              │
│  Same file as last time?        │
│  → Skip re-ingestion            │
└─────────────┬───────────────────┘
              │ New file
              ▼
┌─────────────────────────────────┐
│  2. Parse (pypdf)               │
│  Extract raw text from every    │
│  page of the PDF                │
└─────────────┬───────────────────┘
              │
              ▼
┌─────────────────────────────────┐
│  3. Chunk                       │
│  Split text into 500-token      │
│  chunks with 50-token overlap   │
│  Overlap ensures context is     │
│  never lost at chunk boundaries │
└─────────────┬───────────────────┘
              │
              ▼
┌─────────────────────────────────┐
│  4. Embed (nomic-embed-text)    │
│  Each chunk → 768-dimensional   │
│  vector capturing its meaning   │
└─────────────┬───────────────────┘
              │
              ▼
┌──────────────────────────────────────────┐
│  5. Store in ChromaDB + Build BM25 Index │
│  • ChromaDB: persists vectors to disk    │
│  • BM25: keyword index in memory         │
│  Both used together for hybrid search    │
└─────────────┬────────────────────────────┘
              │
              ▼
        Document Ready
     "53 chunks indexed and searchable"
```

---

### Pipeline 2 — Agentic Q&A

This is what makes the app "agentic" — the AI reasons about HOW to answer before answering:

```
User Types a Question
         │
         ▼
┌─────────────────────────────────────────────┐
│  LangGraph ReAct Agent (llama3.1)           │
│                                             │
│  ReAct = Reason + Act loop:                 │
│  Thought → Action → Observation → Answer    │
│                                             │
│  ┌────────────────────┐                     │
│  │ Specific field?    │──Yes──► Tool 2      │
│  │ (number, date,     │        structured   │
│  │  name, limit...)   │        _extract     │
│  └────────────────────┘                     │
│           │ No                              │
│           ▼                                 │
│  ┌────────────────────┐                     │
│  │ General question?  │──Yes──► Tool 1      │
│  │ (coverage, terms,  │        hybrid       │
│  │  conditions...)    │        _search      │
│  └────────────────────┘                     │
└─────────────────────────────────────────────┘
         │                      │
         ▼                      ▼
┌─────────────────┐    ┌──────────────────────┐
│  TOOL 1:        │    │  TOOL 2:             │
│  hybrid_search  │    │  structured_extract  │
│                 │    │                      │
│  BM25 keyword   │    │  Reads all chunks    │
│  search         │    │  → fills Pydantic    │
│       +         │    │    schema            │
│  ChromaDB       │    │  → returns the       │
│  vector search  │    │    specific field    │
│       │         │    └──────────┬───────────┘
│  Merged via RRF │               │
│  (best of both) │               │
└────────┬────────┘               │
         └──────────┬─────────────┘
                    ▼
         llama3.1 generates the Answer
                    │
                    ▼
        ┌───────────────────────────┐
        │  Response returned:       │
        │  • Answer text            │
        │  • Tool used badge        │
        │  • Source page chunks     │
        │  • Full pipeline steps    │
        └───────────────────────────┘
```

**Why two tools?**
Semantic search finds relevant *concepts*. Structured extraction finds precise *facts* with validated types. The agent choosing between them is what makes this system "agentic" — it reasons about the best retrieval strategy for each question rather than blindly applying one approach to everything.

**What is Hybrid Search?**
- **BM25** — keyword scoring via Term Frequency × Inverse Document Frequency. Great for exact matches like policy numbers and dates.
- **ChromaDB Vector** — cosine similarity between 768-dim embeddings. Great for semantic concepts like "what is covered".
- **RRF** — Reciprocal Rank Fusion. Merges both ranked lists using position (not raw scores), so the two methods combine scale-independently.

---

### Pipeline 3 — Structured Data Extraction

One click extracts all 8 key fields from any policy:

```
"Extract Policy Data" Button Clicked
              │
              ▼
┌─────────────────────────────────────────────────┐
│  Step 1: Load All Chunks                        │
│  Retrieve all indexed chunks from ChromaDB      │
│  Sort by page number — page 1 always first      │
│  (declarations page: number, holder, dates)     │
└─────────────────────┬───────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│  Step 2: Build Full Context                     │
│  Concatenate sorted chunks into one text block  │
│  Trim to 6,000 characters (context window cap)  │
└─────────────────────┬───────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│  Step 3: LLM + Pydantic Schema Enforcement      │
│  llm.with_structured_output(PolicyData)         │
│  LangChain sends schema as a tool definition    │
│  llama3.1 must call it with matching JSON       │
│  Pydantic validates every field and type        │
│                                                 │
│  Fallback: if tool-calling fails →              │
│  re-prompt with format="json" (Ollama mode)     │
│  → parse raw JSON → construct PolicyData        │
└─────────────────────┬───────────────────────────┘
                      │
                      ▼
           Structured Table in the UI
           8/8 fields populated from YOUR PDF
```

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **Frontend** | React 18 + TypeScript + Vite | Fast, type-safe, modern UI |
| **Backend** | FastAPI + Uvicorn | Async Python API, auto Swagger docs |
| **LLM** | Ollama `llama3.1:latest` | 100% local, no API key, no cost |
| **Embeddings** | Ollama `nomic-embed-text` | Local text → 768-dim vectors |
| **Vector Store** | ChromaDB | Local persistent vector database |
| **Keyword Search** | BM25 (`rank-bm25`) | Exact match for identifiers & dates |
| **AI Agent** | LangGraph `create_react_agent` | ReAct loop, tool routing, stateful graph |
| **AI Framework** | LangChain | Prompt templates, chains, tool wrappers |
| **PDF Parsing** | pypdf | Extract text from every PDF page |
| **Data Validation** | Pydantic | Type-safe structured output from LLM |
| **API Docs** | Swagger UI (built-in) | Interactive API explorer at `/docs` |

> **Zero cloud dependencies.** Everything runs locally. Your insurance documents never leave your machine.

---

## How to Run It

### Prerequisites

```
Python 3.10+
Node.js 18+
Ollama installed → https://ollama.ai
```

### Step 1 — Pull the AI Models

```bash
ollama pull llama3.1
ollama pull nomic-embed-text
```

### Step 2 — Clone the Repository

```bash
git clone https://github.com/raghdaemara1/Aman_project.git
cd Aman_project
```

### Step 3 — Start the Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn main:app --reload
```

Backend running at `http://localhost:8000`

### Step 4 — Start the Frontend (new terminal)

```powershell
cd frontend
npm install
npm run dev
```

App running at `http://localhost:5173`

### Step 5 — Use the App

1. Open `http://localhost:5173`
2. Upload any insurance policy PDF using the sidebar
3. Watch the **Ingestion Pipeline (Live)** logs appear in real-time
4. Ask a question in the **Ask a Question** tab
5. Click **Extract Policy Data** in the **Extract** tab

---

## API Reference

Interactive docs: **`http://localhost:8000/docs`** (Swagger UI)
Alternative docs: **`http://localhost:8000/redoc`** (ReDoc)

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/upload` | `POST` | Upload a PDF and trigger the full ingestion pipeline |
| `/api/v1/ask` | `POST` | Send a question to the LangGraph ReAct agent |
| `/api/v1/extract` | `POST` | Extract all 8 structured policy fields |
| `/api/v1/logs` | `GET` | Poll for live pipeline step messages |
| `/api/v1/store` | `DELETE` | Clear the vector store and start fresh |
| `/health` | `GET` | Health check |

---

## Key Design Decisions

**Why Hybrid Search instead of pure vector search?**
Vector search finds semantically similar text but misses exact identifiers. A policy number like `US151741` has no semantic relationship to the query "what is the policy number?" — BM25 keyword search catches it perfectly. Combining both via Reciprocal Rank Fusion gives the best of both worlds.

**Why does the agent have two separate tools?**
Search and extraction are fundamentally different operations. Search finds relevant text passages. Extraction fills a typed schema with validated fields. Keeping them separate forces the agent to reason explicitly about which strategy fits the question — that reasoning is what makes the system "agentic".

**Why Ollama instead of OpenAI?**
Insurance documents are sensitive enterprise data. Running everything locally ensures complete privacy with zero cost and zero rate limits. The LangChain abstraction makes swapping to `gpt-4o` a one-line change — the architecture is identical to a production system.

**Why is page 1 always included first in extraction?**
The declarations page (policy number, holder, effective dates) is always on page 1, but the chunker splits it into multiple pieces. Semantic search cannot reliably retrieve exact identifiers from it. By sorting all chunks with page 1 first, the LLM always has the critical fields in context — regardless of how chunking divided the page.

**Why FastAPI with a ThreadPoolExecutor?**
Ollama calls (LLM inference + embeddings) are synchronous and blocking. Running them directly in async endpoints would freeze the entire event loop, making the `/logs` polling endpoint unresponsive. The thread pool keeps the event loop free for other requests while Ollama processes.

---

## What Would Come Next in Production

| Current (Demo) | Production |
|---|---|
| Ollama local llama3.1 | OpenAI GPT-4o or Anthropic Claude (one-line swap) |
| ChromaDB local disk | Snowflake Cortex Search for enterprise-scale retrieval |
| In-memory BM25 | Elasticsearch for persistent keyword index |
| No authentication | JWT-based user sessions and document ownership |
| Polling for logs | Server-Sent Events (SSE) for real-time streaming |
| No observability | LangSmith for full agent tracing and latency metrics |
| Single document | Multi-document portfolio with cross-policy comparison |
| No knowledge graph | Neo4j linking policies → claims → customers |

---

*Built with LangGraph · LangChain · FastAPI · React · ChromaDB · Ollama*
