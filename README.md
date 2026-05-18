# IntelliDoc — Insurance Document Intelligence Agent

> **A fully local, privacy-first Agentic RAG system — reads insurance policy PDFs, answers questions about them, and extracts structured data, all without sending a single byte to the cloud.**

---

## What Does This App Do?

IntelliDoc lets you upload any insurance policy PDF and then:

| Feature | What You Can Do |
|---|---|
| **Smart Upload** | Upload a PDF — the AI automatically parses every page, chunks it, embeds it, and indexes it |
| **Ask Questions** | Ask anything in plain English: *"What is covered under this policy?"* or *"What are the exclusions?"* |
| **Extract Policy Data** | Click one button to extract all 8 key policy fields into a structured table, validated by a Pydantic schema |
| **Transparent AI** | See every reasoning step the agent took, which tool it selected, and which page the answer came from |
| **Document Memory** | Upload the same file again — the system recognizes it via MD5 hash and skips re-processing |
| **Live Pipeline Logs** | Watch each step of the ingestion or inference pipeline appear in real-time |

---

## System Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Your Browser                      │
│          React 18 + TypeScript + Vite               │
│  Upload Contract │ Ask Questions │ Extract Data     │
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

```
Contract PDF Uploaded
      │
      ▼
1. MD5 Hash Check — same file already indexed? Skip re-ingestion.
      │ New file
      ▼
2. Parse with pypdf — extract text from every page
      │
      ▼
3. Chunk — 500-token chunks, 50-token overlap
   (overlap ensures no sentence is lost at a boundary)
      │
      ▼
4. Embed with nomic-embed-text — each chunk → 768-dim vector
      │
      ▼
5. Store in ChromaDB (disk) + build BM25 index (memory)
      │
      ▼
   "53 chunks indexed and searchable"
```

---

### Pipeline 2 — Agentic Q&A  (`/ask` endpoint — uses the agent)

The AI reasons about HOW to answer — not just what to output.
The agent runs a Reason → Act → Observe loop until it has an answer:

```
User Question  (e.g. "What is the policy number?")
      │
      ▼
LangGraph ReAct Agent (llama3.1) — Reason + Act loop
      │
      ▼
  THINK: "Is this a specific field lookup or a general question?"
      │
      ├── Specific field? (policy number, holder, dates, premium, limit...)
      │         │
      │         ▼
      │      Tool: structured_extract
      │         Sends all chunks to llama3.1 with a strict Pydantic schema
      │         LLM must return JSON — Pydantic validates every field and type
      │         Returns the exact field value → "US151741"
      │
      └── General question? (what does it say about X, coverage terms...)
                │
                ▼
             Tool: hybrid_search
                Runs two searches in parallel:
                  ① BM25 keyword search (exact word match, in memory)
                  ② ChromaDB vector search (semantic meaning, from disk)
                Merges results with RRF (rank-based fusion, no score scaling)
                Returns top-4 chunks as text → LLM reads and writes the answer
```

**Why two tools?** Semantic search finds *concepts*. Structured extraction finds *precise typed fields*. Making the agent choose is what makes this system "agentic" — it reasons about retrieval strategy, not just content.

**Hybrid Search = BM25 + ChromaDB + RRF**
- BM25: exact keyword matching — great for policy numbers, dates, exact terms
- ChromaDB: cosine similarity of 768-dim embeddings — great for concepts like "what is excluded"
- RRF: rank-fusion that is scale-invariant — merges both ranked lists using position, not raw scores

---

### Pipeline 3 — Structured Data Extraction  (`/extract` endpoint — NO agent)

This is a **direct extraction** — it bypasses the agent entirely.
It always runs the same path: all chunks → Pydantic schema → structured table.

```
"Extract Policy Data" Button Clicked
      │
      ▼
1. Load ALL indexed chunks, sort by page number (page 1 first)
      │
      ▼
2. Build full context string, trim to 6,000 characters
      │
      ▼
3. llm.with_structured_output(PolicyData)
   LangChain sends PolicyData schema to llama3.1 as a tool definition
   llama3.1 MUST return JSON — Pydantic validates every field and type
      │
      ├── SUCCESS → return PolicyData object
      └── FAILURE → fallback: re-prompt with format="json" (Ollama JSON mode)
                    → parse raw JSON manually → build PolicyData
      │
      ▼
   Structured table — 8 fields filled from YOUR uploaded document
```

**Extracted fields (insurance schema):**
| Field | Example |
|---|---|
| Policy Number | US151741 |
| Policy Holder | School District of Hillsborough County |
| Coverage Type | Blanket Benefits Accident Only |
| Effective Date | August 1, 2013 |
| Expiration Date | August 1, 2014 |
| Premium Amount | Not specified |
| Coverage Limit | Not specified |
| Key Exclusions & Conditions | Benefits not payable for loss due to sickness... |

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **Frontend** | React 18 + TypeScript + Vite | Fast, type-safe, modern UI |
| **Backend** | FastAPI + Uvicorn | Async Python API, auto Swagger docs |
| **LLM** | Ollama `llama3.1:latest` | 100% local, no API key, no cost |
| **Embeddings** | Ollama `nomic-embed-text` | Local text → 768-dim vectors |
| **Vector Store** | ChromaDB | Local persistent vector database |
| **Keyword Search** | BM25 (`rank-bm25`) | Exact match for contract numbers & amounts |
| **AI Agent** | LangGraph `create_react_agent` | ReAct loop, tool routing, stateful graph |
| **AI Framework** | LangChain | Prompt templates, chains, tool wrappers |
| **PDF Parsing** | pypdf | Extract text from every PDF page |
| **Data Validation** | Pydantic | Type-safe structured output from LLM |
| **API Docs** | Swagger UI (built-in) | Interactive API explorer at `/docs` |

> **Zero cloud dependencies.** Everything runs locally. No contract data leaves your machine.

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
2. Upload any consumer finance contract PDF using the sidebar
3. Watch the **Ingestion Pipeline (Live)** logs appear in real-time
4. Ask questions in the **Ask a Question** tab
5. Click **Extract Policy Data** in the **Extract** tab

---

## API Reference

Interactive docs: **`http://localhost:8000/docs`** (Swagger UI)

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/upload` | `POST` | Upload a PDF and trigger the full ingestion pipeline |
| `/api/v1/ask` | `POST` | Send a question to the LangGraph ReAct agent |
| `/api/v1/extract` | `POST` | Extract all 8 structured contract fields |
| `/api/v1/logs` | `GET` | Poll for live pipeline step messages |
| `/api/v1/store` | `DELETE` | Clear the vector store and start fresh |
| `/health` | `GET` | Health check |

---

## Key Design Decisions

**Why Hybrid Search instead of pure vector search?**
Vector search misses exact identifiers. A contract number like `AMAN-FIN-2025-CF-047832` has no semantic relationship to the query "what is the contract number?" — BM25 catches it perfectly. Combining both via RRF gives the best of both worlds.

**Why two separate tools?**
Search finds relevant passages. Extraction fills a typed schema. Keeping them separate forces the agent to reason explicitly about retrieval strategy — that reasoning is what makes the system "agentic".

**Why Ollama instead of OpenAI?**
Consumer finance contracts contain sensitive personal and financial data. Running everything locally ensures complete privacy with zero cost. The LangChain abstraction makes swapping to `gpt-4o` a one-line change.

**Why page 1 is always included first?**
Contract headers (contract number, customer name, financial terms) are always on page 1. By sorting chunks with page 1 first, the LLM always sees the critical fields before any other content — regardless of how chunking divided the page.

---

## What Would Come Next in Production

| Current (Demo) | Production at Aman Scale |
|---|---|
| Ollama local llama3.1 | OpenAI GPT-4o or Anthropic Claude (one-line swap) |
| ChromaDB local disk | Snowflake Cortex Search for millions of contracts |
| In-memory BM25 | Elasticsearch for persistent keyword index |
| No authentication | JWT — agent/branch staff login, contract ownership |
| Single document | Multi-contract portfolio — compare versions, flag discrepancies |
| Polling for logs | Server-Sent Events (SSE) — real-time streaming |
| No observability | LangSmith — trace every agent step, measure latency |
| No knowledge graph | Neo4j — link contracts → customers → payment history |

---

*Built with LangGraph · LangChain · FastAPI · React · ChromaDB · Ollama*
