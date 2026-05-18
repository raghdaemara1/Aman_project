# IntelliDoc — Insurance Document Intelligence Agent

> **A fully local, privacy-first Agentic RAG system — reads insurance policy PDFs, answers questions about them, and extracts structured data, all without sending a single byte to the cloud.**

---

## What Does This App Do?

IntelliDoc lets you upload any insurance policy PDF and then:

| Feature | What You Can Do |
|---|---|
| **Smart Upload** | Upload a PDF — the AI automatically parses every page, chunks it, embeds it, and indexes it |
| **Ask Questions** | Ask anything in plain English: *"What is covered under this policy?"* or *"What are the exclusions?"* |
| **Conversational AI** | Have a back-and-forth conversation — the AI remembers every previous message in the session |
| **Multi-Agent Orchestration** | A Supervisor Agent classifies your question and routes it to the right specialist (Retrieval or Extraction) |
| **Extract Policy Data** | Click one button to extract all 8 key policy fields into a structured table, validated by a Pydantic schema |
| **Transparent AI** | See every reasoning step the agent took, which specialist handled it, and which page the answer came from |
| **Document Memory** | Upload the same file again — the system recognizes it via MD5 hash and skips re-processing |
| **Live Pipeline Logs** | Watch each step of the ingestion or inference pipeline appear in real-time |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       Your Browser                          │
│              React 18 + TypeScript + Vite                   │
│  Upload Policy │ Ask (single) │ Chat (multi-turn) │ Extract │
└───────────────────────┬─────────────────────────────────────┘
                        │  HTTP / REST API
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                 FastAPI Backend (Python)                     │
│                      Port :8000                             │
│                                                             │
│  ┌──────────┐  ┌───────┐  ┌───────────────┐  ┌──────────┐  │
│  │ /upload  │  │ /ask  │  │     /chat     │  │ /extract │  │
│  └────┬─────┘  └───┬───┘  └──────┬────────┘  └────┬─────┘  │
│       │            │             │                 │        │
│       ▼            ▼             ▼                 ▼        │
│  ┌─────────┐  ┌─────────┐  ┌──────────────────┐  ┌───────┐ │
│  │ parser  │  │  agent  │  │   orchestrator   │  │extrac-│ │
│  │  .py    │  │   .py   │  │       .py        │  │tor.py │ │
│  └────┬────┘  └────┬────┘  │  ┌────────────┐  │  └───┬───┘ │
│       │            │       │  │ Supervisor │  │      │     │
│       │            │       │  └─────┬──────┘  │      │     │
│       │            │       │        │ routes  │      │     │
│       │            │       │  ┌─────┴──────┐  │      │     │
│       │            │       │  │  Retrieval │  │      │     │
│       │            │       │  │   Agent    │  │      │     │
│       │            │       │  ├────────────┤  │      │     │
│       │            │       │  │ Extraction │  │      │     │
│       │            │       │  │   Agent    │  │      │     │
│       │            │       │  └────────────┘  │      │     │
│       │            │       │  memory.py        │      │     │
│       │            │       │  (session store)  │      │     │
│       │            │       └──────────────────┘      │     │
│       ▼            ▼                  ▼               ▼     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                   vectorstore.py                     │   │
│  │   ChromaDB (vectors on disk)                        │   │
│  │   BM25 (keyword index in memory)                    │   │
│  │   Hybrid search via RRF                             │   │
│  └──────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────┘
                            │  Local HTTP (port 11434)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                     Ollama (Local AI)                       │
│   llama3.1:latest         — Reasoning & Generation          │
│   nomic-embed-text:latest — Text Embeddings                 │
│                                                             │
│   Runs 100% on your machine. No API key needed.             │
└─────────────────────────────────────────────────────────────┘
```

---

## The Three Pipelines

### Pipeline 1 — Document Upload & Indexing

```
Policy PDF Uploaded
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

### Pipeline 3 — Conversational AI Pipeline  (`/chat` endpoint — multi-turn memory)

This pipeline adds **session memory** so follow-up questions work naturally.

```
User message  (e.g. "And when does it expire?")
      │
      ▼
1. Load session history from memory.py
   (all previous HumanMessage / AIMessage pairs for this session_id)
      │
      ▼
2. Supervisor Agent (llama3.1, structured output)
   Reads: history + new question → RouteDecision { destination, reasoning }
      │
      ├── "extraction_agent" → Extraction Agent (structured_extract tool)
      └── "retrieval_agent"  → Retrieval Agent  (hybrid_search tool)
      │
      ▼
3. Specialist Agent executes its tool
   Receives: conversation context (last 2 exchanges) + current query
      │
      ▼
4. Save exchange to session memory
   human: "And when does it expire?"  assistant: "August 1, 2014"
      │
      ▼
5. Return answer + agent_used + source_chunks + session_id
```

**Why session memory matters:** The Supervisor reads conversation history before routing. If the user asked about the policy number first, a follow-up asking "who is the policyholder?" is still correctly classified as an extraction question — the agent doesn't need context re-stated each turn.

---

### Pipeline 4 — Multi-Agent Orchestration  (`/chat` endpoint — agent routing)

Every `/chat` call runs through an **Orchestrator** that coordinates three specialized agents:

```
User Question
      │
      ▼
┌─────────────────────────────────────────────────┐
│              Supervisor Agent                   │
│  llama3.1 + RouteDecision (Pydantic schema)     │
│  Reads full conversation history + new question │
│  Outputs: { destination, reasoning }            │
└────────────────┬────────────────────────────────┘
                 │
      ┌──────────┴──────────┐
      ▼                     ▼
┌─────────────┐    ┌──────────────────┐
│  Retrieval  │    │   Extraction     │
│   Agent     │    │    Agent         │
│             │    │                  │
│ tool:       │    │ tool:            │
│ hybrid_     │    │ structured_      │
│ search      │    │ extract          │
│             │    │                  │
│ BM25 +      │    │ All 53 chunks →  │
│ ChromaDB +  │    │ Pydantic schema  │
│ RRF         │    │ → typed fields   │
└──────┬──────┘    └────────┬─────────┘
       │                    │
       └──────────┬─────────┘
                  ▼
           Final Answer
     agent_used badge shown in UI
```

**Each agent is a separate `create_react_agent` instance** with its own system prompt and tool set. The Supervisor never sees the tool implementations — it only sees the question and the routing options. This is what makes the system genuinely "agentic": the routing logic lives entirely inside the LLM's reasoning, not in if/else code.

---

### Pipeline 5 — Structured Data Extraction  (`/extract` endpoint — NO agent)

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
| **Keyword Search** | BM25 (`rank-bm25`) | Exact match for policy numbers & amounts |
| **AI Agent** | LangGraph `create_react_agent` | ReAct loop, tool routing, stateful graph |
| **Orchestrator** | LangGraph `StateGraph` | Supervisor routes to specialist agents |
| **Session Memory** | In-memory dict (per session_id) | Conversation history across turns |
| **AI Framework** | LangChain | Prompt templates, chains, tool wrappers |
| **PDF Parsing** | pypdf | Extract text from every PDF page |
| **Data Validation** | Pydantic | Type-safe structured output from LLM |
| **API Docs** | Swagger UI (built-in) | Interactive API explorer at `/docs` |

> **Zero cloud dependencies.** Everything runs locally. No policy data leaves your machine.

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
4. Ask questions in the **Ask a Question** tab
5. Click **Extract Policy Data** in the **Extract** tab

---

## API Reference

Interactive docs: **`http://localhost:8000/docs`** (Swagger UI)

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/upload` | `POST` | Upload a PDF and trigger the full ingestion pipeline |
| `/api/v1/ask` | `POST` | Send a question to the single LangGraph ReAct agent |
| `/api/v1/chat` | `POST` | Conversational multi-agent endpoint (Supervisor + specialists + memory) |
| `/api/v1/chat/history/{id}` | `GET` | Return full conversation history for a session |
| `/api/v1/chat/sessions/{id}` | `DELETE` | Clear a conversation session |
| `/api/v1/extract` | `POST` | Extract all 8 structured policy fields |
| `/api/v1/logs` | `GET` | Poll for live pipeline step messages |
| `/api/v1/store` | `DELETE` | Clear the vector store and start fresh |
| `/health` | `GET` | Health check |

---

## Key Design Decisions

**Why Hybrid Search instead of pure vector search?**
Vector search misses exact identifiers. A policy number like `US151741` has no semantic relationship to the query "what is the policy number?" — BM25 catches it perfectly. Combining both via RRF gives the best of both worlds.

**Why two separate tools?**
Search returns text passages. Extraction fills a typed schema. They are fundamentally different operations. Keeping them separate forces the agent to reason explicitly about retrieval strategy — that reasoning is what makes this system "agentic".

**Why RRF instead of averaging scores?**
BM25 produces TF-IDF counts (0–100s). ChromaDB produces cosine similarity (0–1). These scales are incomparable — averaging would let BM25 dominate. RRF uses only rank position (1st, 2nd, 3rd...) so the scales never matter.

**Why temperature=0?**
Extraction and tool routing must be deterministic. Temperature 0 always picks the highest-probability token — the same question always gives the same tool choice and the same extracted fields. Never use temperature > 0 for structured extraction.

**Why a Supervisor Agent instead of a single agent with all tools?**
A single agent with both tools works but is opaque — you can't see *why* it chose one tool over another. The Supervisor makes the routing decision explicit and logged. It also separates concerns: each specialist agent has a focused system prompt, not a long one trying to cover everything. With a local LLM, smaller focused prompts produce more reliable results.

**Why session memory stored in-memory (not a database)?**
For this demo, in-memory storage is sufficient — a Python dict keyed by `session_id` resets when the server restarts, which is fine for a local presentation. In production, this would be a Redis or Postgres store so sessions survive restarts and scale across instances.

**Why does the Supervisor receive conversation history but the specialist agents don't (full history)?**
The Supervisor needs history to correctly route follow-up questions ("And when does it expire?" needs context to know it's an extraction question). The specialist agents only need the current query plus a brief history summary — sending the full history to every specialist call would slow down every inference step with a local LLM.

**Why a regex override after LLM extraction?**
Local LLMs occasionally confuse visually similar identifiers. This document has `Policy Number: US151741` at the top and `GAP 26932-FL` at the bottom — both look like identifiers. After LLM extraction, `_regex_override()` scans the raw text for explicit `Label: value` patterns and overwrites any wrong LLM answer deterministically. LLM handles complex fields (exclusions), regex handles labeled fields (number, holder, dates).

**Why Ollama instead of OpenAI?**
Insurance documents contain sensitive PII. Running everything locally ensures complete privacy with zero cost. The LangChain abstraction makes swapping to `gpt-4o` a one-line change.

**Why page 1 always sorted first?**
Policy headers (number, holder, dates) are always on page 1. Sorting chunks by page number before sending to the LLM ensures critical fields appear before any other content — regardless of how chunking split the page.

**Why pass all_chunks to the tool, not just use the retriever?**
The retriever only returns the top-k semantically similar chunks. For extraction, you need ALL chunks — a field like the premium amount might be on a page that isn't semantically close to "policy number". Passing `get_chunks()` guarantees nothing is missed.

---

## Common Questions

**Q: How does the agent decide which tool to call?**
The `@tool` decorator sends the function's docstring to the LLM as the tool description. The LLM reads both descriptions and picks based on the question. There is no if/else in code — all routing is done by the LLM reasoning.

**Q: What is the ReAct loop?**
Think → Act → Observe. The LLM outputs a tool call JSON (not an answer). LangGraph runs the Python function and adds the result as a ToolMessage. The LLM re-reads all messages and either calls another tool or writes the final answer.

**Q: What is Pydantic used for here?**
Two places, same function: `llm.with_structured_output(PolicyData)` forces the LLM to return JSON matching the `PolicyData` schema exactly. Pydantic validates every field type. If validation fails, the system falls back to raw JSON mode.

**Q: What is the difference between the Ask tab and the Chat tab?**
Ask tab → single stateless question, one LangGraph ReAct agent with both tools, answer is forgotten after the response. Chat tab → multi-turn conversation with session memory, Supervisor routes each message to a specialist agent, follow-up questions have full context.

**Q: How does the Supervisor Agent decide which specialist to call?**
It uses `llm.with_structured_output(RouteDecision)` — the LLM must return a Pydantic object `{ destination: "retrieval_agent" | "extraction_agent", reasoning: str }`. The reasoning field is logged in the pipeline steps so you can see exactly why it routed the way it did. There is no if/else in code — all routing is done by the LLM.

**Q: What happens if the Supervisor's structured output fails?**
There is a keyword fallback: if the structured output call raises an exception (which can happen with a local LLM under load), the code checks for field-lookup keywords ("number", "date", "premium", etc.) and falls back to `extraction_agent` if any match, otherwise `retrieval_agent`.

**Q: What is the difference between the Ask tab and the Extract tab?**
Ask tab → agent decides which tool to call (may use either tool). Extract tab → bypasses the agent entirely, always runs structured extraction directly. Two different endpoints: `/ask` vs `/extract`.

**Q: How is this different from Snowflake Cortex Search?**
Cortex Search does hybrid BM25 + vector + RRF internally — this app implements the same pattern manually. The logic is identical; the difference is scale (local vs cloud) and that this app makes the retrieval steps transparent and inspectable.

**Q: What would you change for production?**
Replace Ollama with GPT-4o (one-line LangChain swap), ChromaDB with Snowflake Cortex Search, add LangSmith for agent tracing, JWT auth, and Server-Sent Events instead of polling for live logs.

---

## What Would Come Next in Production

| Current (Demo) | Production |
|---|---|
| Ollama llama3.1 (local) | GPT-4o or Claude — one-line LangChain swap |
| ChromaDB on disk | Snowflake Cortex Search — millions of documents |
| In-memory BM25 | Elasticsearch — persistent, distributed |
| In-memory session store | Redis — sessions survive restarts, scale horizontally |
| Polling `/logs` every 1.5s | Server-Sent Events — true real-time streaming |
| No auth | JWT — staff login, document ownership |
| Single document | Multi-document — compare policy versions |
| 2 specialist agents | Domain-specific agents: Claims Agent, Coverage Agent, Compliance Agent |
| No tracing | LangSmith — trace every agent step, measure latency |

---

## Docs

All explainer files are in the `docs/` folder:

| File | What it covers |
|---|---|
| [docs/PIPELINES.md](docs/PIPELINES.md) | Visual step-by-step diagrams for all 3 pipelines |
| [docs/LANGGRAPH_AGENT.md](docs/LANGGRAPH_AGENT.md) | Full LangGraph agent code with message trace |
| [docs/WALKTHROUGH.md](docs/WALKTHROUGH.md) | File-by-file code walkthrough |
| [docs/CONCEPTS.md](docs/CONCEPTS.md) | All technical concepts explained from scratch |
| [docs/GUIDE.md](docs/GUIDE.md) | Q&A and pipeline output shapes |

---

*Built with LangGraph · LangChain · FastAPI · React · ChromaDB · Ollama*
