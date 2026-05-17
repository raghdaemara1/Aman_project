# 🛡️ IntelliDoc — Insurance Document Intelligence Agent

> **A fully local, privacy-first AI system that reads insurance policy PDFs, answers questions about them, and extracts structured data — all without sending a single byte to the cloud.**

---

## ✨ What Does This App Do?

IntelliDoc lets you upload any insurance policy PDF and then:

| Feature | What You Can Do |
|---|---|
| 📤 **Smart Upload** | Upload a PDF — the AI automatically reads, chunks, and indexes it |
| 💬 **Ask Questions** | Ask anything in plain English: *"What is covered under this policy?"* |
| 📋 **Extract Data** | Click one button to extract all 8 key policy fields into a structured table |
| 🔍 **Transparent AI** | See every step the AI took, which tool it used, and which page it found the answer on |
| ⚡ **Document Memory** | Upload the same file again — the system recognizes it and skips re-processing |

---

## 🏗️ System Architecture

### Big Picture

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
│  │           vectorstore.py                     │   │
│  │   ChromaDB (vectors) + BM25 (keywords)       │   │
│  └──────────────────────────────────────────────┘   │
│                       │                             │
└───────────────────────┼─────────────────────────────┘
                        │  Local HTTP
                        ▼
┌─────────────────────────────────────────────────────┐
│                  Ollama (Local AI)                  │
│   llama3.1:latest        — Reasoning & Generation   │
│   nomic-embed-text:latest — Text Embeddings         │
│                                                     │
│   ✅ Runs 100% on your machine. No API key needed.  │
└─────────────────────────────────────────────────────┘
```

---

## 🔄 The Three Pipelines Explained

### 📤 Pipeline 1 — Document Upload & Indexing

When you upload a PDF, this is exactly what happens step by step:

```
PDF File Uploaded
      │
      ▼
┌─────────────────────────────────┐
│  1. MD5 Hash Check              │
│  Is this the same file as last  │
│  time? → Skip if yes ✅         │
└─────────────┬───────────────────┘
              │ New file
              ▼
┌─────────────────────────────────┐
│  2. Parse (pypdf)               │
│  Extract raw text from each     │
│  page of the PDF                │
└─────────────┬───────────────────┘
              │
              ▼
┌─────────────────────────────────┐
│  3. Chunk                       │
│  Split text into 500-token      │
│  chunks with 50-token overlap   │
│  (so context is never lost at   │
│   chunk boundaries)             │
└─────────────┬───────────────────┘
              │
              ▼
┌─────────────────────────────────┐
│  4. Embed (nomic-embed-text)    │
│  Convert each chunk into a      │
│  768-dimensional vector that    │
│  captures its meaning           │
└─────────────┬───────────────────┘
              │
              ▼
┌──────────────────────────────────────────┐
│  5. Store in ChromaDB + Build BM25 Index │
│  • ChromaDB: stores vectors on disk      │
│  • BM25: keyword index built in memory   │
│  Both used together for hybrid search    │
└─────────────┬────────────────────────────┘
              │
              ▼
        ✅ Document Ready
     "47 chunks indexed and searchable"
```

---

### 💬 Pipeline 2 — Agentic Q&A (The Brain)

This is what makes the app "agentic" — the AI **reasons** about HOW to answer before answering:

```
User Types a Question
e.g. "What is the policy number?"
         │
         ▼
┌─────────────────────────────────────────────┐
│  LangChain ReAct Agent (llama3.1)           │
│                                             │
│  Thought: "What kind of question is this?"  │
│                                             │
│  ┌────────────────────┐                     │
│  │ Is it asking for a │                     │
│  │ specific data field│──Yes──► Tool 2      │
│  │ (number, date, etc)│        structured   │
│  └────────────────────┘        _extract     │
│           │ No                              │
│           ▼                                 │
│  ┌────────────────────┐                     │
│  │ Is it a general    │──Yes──► Tool 1      │
│  │ question about     │        hybrid       │
│  │ coverage/terms?    │        _search      │
│  └────────────────────┘                     │
└─────────────────────────────────────────────┘
         │                      │
         ▼                      ▼
┌─────────────────┐    ┌──────────────────────┐
│  TOOL 1:        │    │  TOOL 2:             │
│  hybrid_search  │    │  structured_extract  │
│                 │    │                      │
│  BM25 keyword   │    │  Pydantic schema     │
│  search results │    │  forced JSON output  │
│       +         │    │                      │
│  ChromaDB vector│    └──────────┬───────────┘
│  search results │               │
│       │         │               │
│  Merged via RRF │               │
│  (best of both) │               │
└────────┬────────┘               │
         │                        │
         └──────────┬─────────────┘
                    ▼
         llama3.1 generates the Answer
                    │
                    ▼
        ┌───────────────────────┐
        │  Response returned:   │
        │  ✅ Answer text        │
        │  🔧 Tool used          │
        │  📄 Source page chunks │
        │  📊 Pipeline steps     │
        └───────────────────────┘
```

**Why two tools?** Semantic search finds relevant *concepts*. Structured extraction finds precise *facts*. The agent picks the right one for each question automatically.

**What is Hybrid Search?** Instead of just one search method, we combine two:
- **BM25** — keyword search (great for exact matches like policy numbers, dates)
- **ChromaDB Vector** — semantic search (great for concepts like "what is covered")
- **RRF** — Reciprocal Rank Fusion merges both ranked lists into one superior result

---

### 📋 Pipeline 3 — Structured Data Extraction

One click extracts all 8 key fields from the policy:

```
"Extract Policy Data" Button Clicked
              │
              ▼
┌─────────────────────────────────────────────────┐
│  Step 1: Pin Page 1 (Declarations Page)         │
│  The policy number, holder, and dates are       │
│  ALWAYS on page 1 — always included first       │
└─────────────────────┬───────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│  Step 2: Semantic Search for Coverage Details   │
│  Retrieves top-10 chunks about:                 │
│  premium, coverage limits, exclusions           │
└─────────────────────┬───────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│  Step 3: Merge + Deduplicate                    │
│  Page 1 chunks + semantic results combined      │
│  No duplicate chunks sent to the AI             │
└─────────────────────┬───────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│  Step 4: LLM Extraction with Pydantic Schema    │
│  llama3.1 must return EXACTLY:                  │
│                                                 │
│  {                                              │
│    "policy_number":   "US151741",               │
│    "policy_holder":   "School District of...", │
│    "coverage_type":   "Accident Only Policy",   │
│    "start_date":      "August 1, 2013",         │
│    "end_date":        "August 1, 2014",         │
│    "premium_amount":  "Not specified",          │
│    "coverage_limit":  "$25,000 per accident",   │
│    "key_exclusions":  ["Pre-existing...", ...]  │
│  }                                              │
└─────────────────────┬───────────────────────────┘
                      │
                      ▼
           ✅ Structured Table in the UI
```

---

## 🧱 Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **Frontend** | React 18 + TypeScript + Vite | Fast, type-safe, modern UI |
| **Backend** | FastAPI + Uvicorn | Async Python API, auto Swagger docs |
| **LLM** | Ollama `llama3.1:latest` | 100% local, no API key, no cost |
| **Embeddings** | Ollama `nomic-embed-text` | Local text-to-vector conversion |
| **Vector Store** | ChromaDB | Local persistent vector database |
| **Keyword Search** | BM25 (`rank-bm25`) | Exact match for policy numbers & dates |
| **AI Framework** | LangChain | ReAct agent, tool routing, prompt chaining |
| **PDF Parsing** | pypdf | Extract text from PDF pages |
| **Data Validation** | Pydantic | Guarantees structured JSON output from LLM |
| **API Docs** | Swagger UI (built-in) | Interactive API explorer at `/docs` |

> **Zero cloud dependencies.** Everything runs locally. Your insurance documents never leave your machine.

---

## 🚀 How to Run It

### Prerequisites

```
✅ Python 3.10+
✅ Node.js 18+
✅ Ollama installed → https://ollama.ai
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
Backend is now running at `http://localhost:8000`

### Step 4 — Start the Frontend (new terminal)
```powershell
cd frontend
npm install
npm run dev
```
App is now running at `http://localhost:5173`

### Step 5 — Use the App
1. Open `http://localhost:5173`
2. Upload any insurance policy PDF using the sidebar
3. Watch the **Ingestion Pipeline (Live)** logs appear in real-time
4. Ask a question in the **Ask a Question** tab
5. Click **Extract Policy Data** in the **Extract** tab

---

## 🔌 API Reference

Interactive docs: **`http://localhost:8000/docs`** (Swagger UI)
Alternative docs: **`http://localhost:8000/redoc`** (ReDoc)

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/upload` | `POST` | Upload a PDF and trigger ingestion pipeline |
| `/api/v1/ask` | `POST` | Send a question to the ReAct agent |
| `/api/v1/extract` | `POST` | Extract all 8 structured policy fields |
| `/api/v1/logs` | `GET` | Poll for live pipeline step messages |
| `/api/v1/store` | `DELETE` | Clear the vector store and start fresh |
| `/health` | `GET` | Health check |

---

## 💡 Key Design Decisions

**Why Hybrid Search instead of pure vector search?**
Vector search finds semantically similar text but can miss exact identifiers. A policy number like `US151741` has no semantic relationship to the query "what is the policy number?" — BM25 keyword search catches it perfectly. Combining both via Reciprocal Rank Fusion (RRF) gives the best of both worlds.

**Why does the agent have two separate tools?**
Search and extraction are fundamentally different operations. Search finds relevant text passages. Extraction pulls a specific field with a defined schema. Making the AI *choose* between them is what makes this system "agentic" — it reasons about the best retrieval strategy for each question.

**Why Ollama instead of OpenAI?**
Insurance documents are sensitive enterprise data. Running everything locally ensures complete privacy with zero cost and zero rate limits. The architecture is identical to a production system — swapping to OpenAI `gpt-4o` is a one-line change.

**Why is Page 1 always injected into extraction context?**
The declarations page (policy number, holder, effective dates) is always on page 1 but the chunker splits it across multiple chunks. Semantic search cannot reliably retrieve exact identifiers. By always pinning page 1 chunks first, the LLM always has the critical fields in context.

---

## 🗺️ What Would Come Next in Production

- **Snowflake Cortex Search** — replacing ChromaDB for enterprise-scale retrieval
- **LangSmith Tracing** — full observability of every agent reasoning step
- **Multi-document comparison** — compare two policy versions side by side with diff highlighting
- **Streaming responses** — real-time token-by-token output via Server-Sent Events
- **Authentication** — JWT-based user sessions and document ownership
- **Neo4j Knowledge Graph** — link policies → claims → customers for multi-hop reasoning

---

*Built with LangChain · FastAPI · React · ChromaDB · Ollama*
