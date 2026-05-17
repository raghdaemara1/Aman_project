# Implementation Plan: Insurance Document Intelligence Agent

**Branch**: `001-insurance-doc-agent` | **Date**: 2026-05-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-insurance-doc-agent/spec.md`

## Summary

Build a local-first Insurance Document Intelligence Agent with a React.js + TypeScript frontend and a Python FastAPI backend. Users upload insurance policy PDFs; the backend parses, chunks, and indexes them into ChromaDB. A LangChain ReAct agent with two distinct tools (`hybrid_search`, `structured_extract`) answers natural language questions, always returning the tool used and the source chunk. The `hybrid_search` tool merges BM25 keyword results with ChromaDB vector results via Reciprocal Rank Fusion for higher recall on insurance terminology. A separate one-click extraction flow returns all eight policy fields via a Pydantic-validated schema. All AI inference runs locally via Ollama (llama3.1 + nomic-embed-text).

## Technical Context

**Language/Version**: Python 3.10+ (backend) · Node 18+ / TypeScript 5.x (frontend)

**Primary Dependencies**:
- Backend: FastAPI 0.110, Uvicorn 0.29, LangChain 0.1 + langchain-community, langchain-ollama, ChromaDB 0.4, rank-bm25 0.2, unstructured[pdf] 0.13, Pydantic 2.7, python-dotenv 1.0
- Frontend: React 18, TypeScript 5, Vite 5, Tailwind CSS 3, axios

**Storage**: ChromaDB persisted to `./backend/chroma_db/` (local disk, reloads on restart per clarification Q1)

**Testing**: Manual golden-path verification against sample_policy.txt; no automated test suite in scope for v1

**Target Platform**: Local desktop (macOS/Windows/Linux), desktop browsers only

**Project Type**: Web application (React frontend + FastAPI backend)

**Performance Goals**: Upload + index ≤ 30 s · Q&A response ≤ 15 s (SC-001, SC-002)

**Constraints**: Fully local execution; only external process is Ollama on localhost:11434; no Docker required

**Scale/Scope**: Single user, single active document at a time

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Gate Condition | Status |
|-----------|---------------|--------|
| I. Full-Stack Separation | React talks to FastAPI only via `/api/v1/...`; no Python in frontend | ✅ PASS |
| II. Two-Tool Agentic Design | `hybrid_search` (BM25 + ChromaDB via RRF) + `structured_extract` are separate `@tool` functions; `create_react_agent` selects between them | ✅ PASS |
| III. Pydantic Structured Output | `PolicyData` v2 model, all 8 fields with `Field(description=...)`, missing → "Not specified" | ✅ PASS |
| IV. Local-First Infrastructure | ChromaDB on disk + Ollama (llama3.1 + nomic-embed-text); `pip install` + `npm install` only | ✅ PASS |
| V. Transparency | `/api/v1/ask` returns `tool_used`, `source_chunks`, `page_refs`; frontend renders badge + collapsible chunk | ✅ PASS |
| VI. Simplicity | No extra abstractions; flat component tree; single routes.py file | ✅ PASS |

All gates pass.

## Project Structure

### Documentation (this feature)

```text
specs/001-insurance-doc-agent/
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── upload.md
│   ├── ask.md
│   ├── extract.md
│   └── store.md
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── main.py                    ← FastAPI app, CORS config, router mount
├── requirements.txt           ← pinned backend dependencies
├── .env.example               ← OLLAMA_BASE_URL=http://localhost:11434
├── chroma_db/                 ← ChromaDB persistence directory (git-ignored)
├── core/
│   ├── __init__.py
│   ├── parser.py              ← unstructured PDF → LangChain Documents + chunking
│   ├── vectorstore.py         ← ChromaDB init, ingest_documents, get_retriever, clear_store
│   ├── agent.py               ← LangChain ReAct agent via create_react_agent + run_agent()
│   └── extractor.py           ← PolicyData Pydantic schema + extraction chain
├── tools/
│   ├── __init__.py
│   ├── search_tool.py         ← @tool hybrid_search merging BM25 + ChromaDB via RRF
│   └── extract_tool.py        ← @tool structured_extract wrapping extractor
├── api/
│   ├── __init__.py
│   └── routes.py              ← all /api/v1/ route handlers
└── sample_docs/
    └── sample_policy.txt      ← realistic fake insurance policy for demo

frontend/
├── package.json               ← pinned frontend dependencies
├── vite.config.ts             ← dev proxy: /api → http://localhost:8000
├── tailwind.config.ts
├── tsconfig.json
└── src/
    ├── main.tsx
    ├── App.tsx                ← two-tab layout: "Ask a Question" / "Extract Policy Data"
    ├── components/
    │   ├── FileUpload.tsx     ← drag-drop + file input, calls POST /api/v1/upload
    │   ├── QuestionPanel.tsx  ← text input + submit button
    │   ├── AnswerCard.tsx     ← renders answer text + ToolBadge + SourceChunk
    │   ├── ToolBadge.tsx      ← blue pill for semantic_search / green for structured_extract
    │   ├── SourceChunk.tsx    ← collapsible <details> with chunk text + page reference
    │   └── ExtractTable.tsx   ← 8-row table; key_exclusions rendered as <ul>
    ├── pages/
    │   ├── AskPage.tsx        ← composes QuestionPanel + AnswerCard
    │   └── ExtractPage.tsx    ← "Extract" button + ExtractTable
    └── services/
        └── api.ts             ← typed axios functions: uploadDoc, askQuestion, extractPolicy, clearStore
```

**Structure Decision**: Option 2 (Web application) — `backend/` and `frontend/` at repository root, per constitution §Development Workflow.

## Complexity Tracking

> No constitution violations. No complexity justification required.
