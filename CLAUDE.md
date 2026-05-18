# IntelliDoc — Insurance Document Intelligence Agent
## AMAN Interview Demo — Current Project State

---

## What This Is

A fully local Agentic RAG system for the AMAN Holding interview.
Uploads an insurance policy PDF, answers questions about it, and extracts
structured fields — all without sending data to the cloud.

Demo document: US Fire Insurance Company — Blanket Benefits Accident Only Policy
(Policy Number: US151741, Policyholder: School District of Hillsborough County)

---

## Actual Tech Stack (do not change)

```
Backend:  FastAPI + Uvicorn (Python 3.10+)
Frontend: React 18 + TypeScript + Vite + Tailwind CSS
LLM:      Ollama llama3.1:latest  (local, free, no API key)
Embed:    Ollama nomic-embed-text (local, 768-dim vectors)
Vector:   ChromaDB (persisted to ./backend/chroma_db/)
Keyword:  rank-bm25 (in-memory, rebuilt on each upload)
Agent:    LangGraph create_react_agent (ReAct loop)
PDF:      pypdf (digital PDFs only, no OCR)
Schema:   Pydantic PolicyData (8 fields)
```

---

## Project Structure

```
my-project/
├── README.md               ← main project doc, show this in interview
├── CLAUDE.md               ← this file
├── docs/
│   ├── PIPELINES.md        ← visual pipeline diagrams (best for interview prep)
│   ├── LANGGRAPH_AGENT.md  ← full LangGraph agent code walkthrough
│   ├── WALKTHROUGH.md      ← file-by-file code explanation
│   ├── CONCEPTS.md         ← all technical concepts explained from scratch
│   └── GUIDE.md            ← interview Q&A and pipeline output shapes
├── backend/
│   ├── main.py             ← FastAPI app entry point
│   ├── requirements.txt
│   ├── api/
│   │   └── routes.py       ← /upload /ask /extract /store /logs /health
│   ├── core/
│   │   ├── parser.py       ← pypdf + RecursiveCharacterTextSplitter
│   │   ├── vectorstore.py  ← ChromaDB + nomic-embed-text + _chunks cache
│   │   ├── extractor.py    ← PolicyData schema + LLM extraction + regex override
│   │   └── agent.py        ← create_react_agent with 2 tools
│   └── tools/
│       ├── search_tool.py  ← hybrid_search: BM25 + ChromaDB + RRF
│       └── extract_tool.py ← structured_extract: all_chunks → PolicyData field
└── frontend/
    └── src/
        ├── App.tsx          ← tab state, upload state, both pages always mounted
        ├── pages/
        │   ├── AskPage.tsx  ← question input + answer card + pipeline log
        │   └── ExtractPage.tsx ← extract button + structured table
        ├── components/
        │   ├── AnswerCard.tsx
        │   ├── ExtractTable.tsx ← renders 8 PolicyData fields
        │   ├── PipelineLog.tsx
        │   ├── FileUpload.tsx
        │   ├── QuestionPanel.tsx
        │   ├── SourceChunk.tsx
        │   └── ToolBadge.tsx
        └── services/
            └── api.ts       ← axios calls to FastAPI
```

---

## How to Run

```powershell
# Terminal 1 — Backend
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload

# Terminal 2 — Frontend
cd frontend
npm install
npm run dev
```

App: http://localhost:5173
API docs: http://localhost:8000/docs

Ollama must be running with:
```
ollama pull llama3.1
ollama pull nomic-embed-text
```

---

## Key Design Decisions (know these for interview)

**Why two tools and not one?**
Search returns text passages. Extraction fills a typed schema.
They are fundamentally different operations. Keeping them separate
forces the agent to reason explicitly about retrieval strategy.

**Why hybrid search (BM25 + ChromaDB + RRF)?**
Vector search misses exact identifiers ("US151741" has no semantic
meaning). BM25 catches exact strings. RRF merges rank positions
(not raw scores) so different score scales don't matter.

**Why temperature=0?**
Extraction and tool routing must be deterministic. Temperature 0
always picks the highest-probability token — same question always
gives the same tool choice and same extracted fields.

**Why regex override after LLM extraction?**
Local LLMs (llama3.1) occasionally confuse labeled fields with
nearby identifiers (e.g. "GAP 26932-FL" at the bottom vs
"Policy Number: US151741" at the top). After LLM extraction,
`_regex_override()` in extractor.py scans for explicit "Label: value"
patterns and overwrites any wrong LLM answer deterministically.

**Why pypdf and not OCR?**
This is a digital PDF — text layer is embedded. OCR (Tesseract etc)
is only needed for scanned images. pypdf is faster, free, and accurate.

**Why Ollama and not OpenAI?**
Insurance documents contain sensitive PII. Running locally means
zero data leaves the machine. LangChain abstraction makes it a
one-line swap to GPT-4o in production.

**Why page 1 always sorted first?**
Policy headers (number, holder, dates) are always on page 1.
Sorting chunks by page number before sending to LLM ensures critical
fields appear before any other content — regardless of chunking.

**Why all_chunks passed to structured_extract tool?**
The `@tool` function must pass `all_chunks=get_chunks()` to
`extract_policy_data()`. Without it, only 10 semantic search results
are used instead of all 53 chunks — causing missing or wrong fields.

---

## The Two Tools — Quick Reference

| | hybrid_search | structured_extract |
|---|---|---|
| Use for | Open questions | Specific field lookups |
| Example | "what does it say about sickness?" | "what is the policy number?" |
| Uses BM25 | YES | NO |
| Uses ChromaDB | YES | YES (all chunks) |
| Uses Pydantic | NO | YES |
| Returns | Raw text chunks | Single typed value |

---

## PolicyData Schema (8 fields)

```python
class PolicyData(BaseModel):
    policy_number: str       # "US151741" — from "Policy Number:" label
    policy_holder: str       # "School District of Hillsborough County"
    coverage_type: str       # "Blanket Benefits Accident Only"
    start_date: str          # "August 1, 2013"
    end_date: str            # "August 1, 2014"
    premium_amount: str      # "$3.75 (Day Care), $3.50 (Summer)..."
    coverage_limit: str      # "$25,000.00"
    key_exclusions: list[str] # ["Benefits not payable for sickness", ...]
```

---

## API Endpoints

| Endpoint | Method | What it does |
|---|---|---|
| `/api/v1/upload` | POST | Parse PDF → chunk → embed → store |
| `/api/v1/ask` | POST | Run LangGraph ReAct agent |
| `/api/v1/extract` | POST | Direct structured extraction, no agent |
| `/api/v1/store` | DELETE | Clear ChromaDB + BM25 cache |
| `/api/v1/logs` | GET | Live pipeline steps (polled by frontend) |
| `/health` | GET | Health check |

---

## GitHub

https://github.com/raghdaemara1/Aman_project
