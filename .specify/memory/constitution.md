<!--
SYNC IMPACT REPORT
==================
Version change: (none) → 1.0.0 (initial ratification)

Modified principles: N/A (initial draft)

Added sections:
  - Core Principles (I–VI)
  - Tech Stack Constraints
  - Development Workflow
  - Governance

Removed sections: N/A

Templates requiring updates:
  ✅ .specify/templates/plan-template.md  — Constitution Check section aligns with principles below
  ✅ .specify/templates/spec-template.md  — User stories and FR structure compatible
  ✅ .specify/templates/tasks-template.md — Phase/story structure compatible; web-app path option applies

Deferred TODOs: None
-->

# IntelliDoc — Insurance Document Intelligence Agent Constitution

## Core Principles

### I. Full-Stack Separation (NON-NEGOTIABLE)

The application MUST maintain a strict boundary between frontend and backend:

- **Frontend**: React.js (TypeScript) — UI only, no business logic, no direct LLM calls
- **Backend**: Python / FastAPI — all AI/ML logic, PDF processing, vector search, agent reasoning
- Communication MUST use a versioned REST API (`/api/v1/...`)
- Frontend MUST never import Python packages or call OpenAI directly
- Each layer is independently runnable, testable, and deployable

**Rationale**: The demo must reflect production architecture at AMAN scale. Mixing UI and AI logic in Streamlit would not demonstrate the engineering depth expected of an Agentic AI Lead.

### II. Agentic Reasoning — Two-Tool Design (NON-NEGOTIABLE)

The LangChain agent MUST expose exactly two tools with distinct responsibilities:

- **`hybrid_search`** — combines BM25 keyword matching and ChromaDB vector similarity, merged via Reciprocal Rank Fusion, for open-ended policy questions
- **`structured_extract`** — Pydantic-typed field extraction for specific data lookups

Rules:
- Tools MUST NOT be merged into one generic tool
- The agent MUST use `create_react_agent` (ReAct pattern) from LangChain
- Every agent response MUST identify which tool was used
- Tool selection logic MUST be driven by LLM reasoning, not hard-coded routing
- `hybrid_search` MUST combine both BM25 (`rank-bm25` library) and vector retrieval — neither alone is sufficient

**Rationale**: Hybrid retrieval significantly outperforms pure vector search on insurance documents containing specific terminology, policy numbers, and exclusion clauses where exact keyword matching matters. Forcing the agent to choose between retrieval and extraction is what makes the system *agentic*.

### III. Structured Output with Pydantic (NON-NEGOTIABLE)

All structured data extracted from documents MUST use Pydantic schemas:

- `PolicyData` model MUST define all eight fields with `Field(description=...)` annotations
- LLM responses for extraction MUST be parsed through the Pydantic output parser
- Unknown/missing fields MUST return `"Not specified"` — never `null`, never hallucinated values
- Schema changes MUST be backward-compatible within v1 of the API

**Rationale**: Type safety at the AI boundary is a core production requirement. Pydantic schemas also serve as self-documenting contracts between the agent and the API consumer.

### IV. Local-First Infrastructure (NON-NEGOTIABLE)

The demo MUST run entirely on a local machine without any cloud infrastructure:

- Vector store: **ChromaDB** persisted to `./chroma_db/` — no Pinecone, no Weaviate
- LLM: **gpt-4o-mini** via OpenAI API (only external dependency, requires `OPENAI_API_KEY`)
- Embeddings: **text-embedding-3-small** (cost-optimal, good quality)
- No Docker required; `pip install -r requirements.txt` MUST be sufficient to bootstrap backend
- `npm install && npm run dev` MUST be sufficient to bootstrap frontend

**Rationale**: Interview demos must start reliably in under 5 minutes on any laptop. Cloud dependencies introduce failure points that cannot be debugged in a live interview.

### V. Transparency — Show Your Work

Every AI response displayed to the user MUST include:

- The final answer text
- A badge indicating which tool the agent used (`semantic_search` or `structured_extract`)
- The source chunk(s) the answer was derived from, with page reference
- The agent MUST state clearly when it cannot find an answer — no silent failures

Frontend display rules:
- Tool badge: blue for `semantic_search`, green for `structured_extract`
- Source chunk shown in a collapsible expander
- Structured extraction results shown as a formatted table

**Rationale**: Explainability is a first-class requirement for AI systems in regulated industries like insurance. Demonstrating this during the interview directly addresses AMAN's use case.

### VI. Simplicity Over Abstraction

- No over-engineering: implement exactly what CLAUDE.md specifies, no more
- No premature abstractions: three similar lines are better than an unnecessary helper
- No feature flags, no backwards-compatibility shims
- No comments explaining *what* code does — only *why* when non-obvious
- Dependencies MUST be pinned in `requirements.txt` (backend) and `package.json` (frontend)

**Rationale**: A clean, readable codebase demonstrates engineering maturity more than a complex one. The interviewer will read the code.

## Tech Stack Constraints

| Layer | Technology | Version | Notes |
|-------|-----------|---------|-------|
| Frontend UI | React.js + TypeScript | 18.x | Vite for bundling |
| Frontend styling | Tailwind CSS | 3.x | Clean, minimal UI |
| Backend API | FastAPI | 0.110.x | Auto-generates OpenAPI docs |
| Backend server | Uvicorn | 0.29.x | ASGI server |
| AI orchestration | LangChain + langchain-ollama | 0.1.x | Agent + chains |
| Vector store | ChromaDB | 0.4.x | Local persistence |
| LLM | llama3.1:latest | — | Local via Ollama |
| Embeddings | nomic-embed-text:latest | — | Local via Ollama |
| PDF parsing | unstructured[pdf] | 0.13.x | With chunking via LangChain |
| Schema validation | Pydantic | 2.7.x | Structured extraction |
| Environment | python-dotenv | 1.0.x | `.env` file for configuration |

**No substitutions** to the above stack without updating this constitution and all dependent specs.

## Development Workflow

1. **Spec first**: Every feature starts with a spec under `specs/[###-feature-name]/spec.md`
2. **Plan before code**: Architecture decisions are documented in `plan.md` before any implementation
3. **Backend before frontend**: API contracts MUST be defined before React components are built
4. **Test the golden path**: After implementation, manually verify the full upload → ask → answer flow
5. **No partial implementations**: Each phase MUST be complete and runnable before the next begins

### Project Structure

```
intellidoc-demo/
├── backend/
│   ├── main.py                  ← FastAPI entry point
│   ├── requirements.txt
│   ├── .env.example
│   ├── core/
│   │   ├── parser.py            ← PDF parsing + chunking
│   │   ├── vectorstore.py       ← ChromaDB setup + ingestion
│   │   ├── agent.py             ← LangChain ReAct agent
│   │   └── extractor.py        ← Pydantic structured extraction
│   ├── tools/
│   │   ├── search_tool.py       ← semantic_search tool
│   │   └── extract_tool.py     ← structured_extract tool
│   ├── api/
│   │   └── routes.py            ← FastAPI route handlers
│   └── sample_docs/
│       └── sample_policy.txt
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── FileUpload.tsx
│   │   │   ├── QuestionPanel.tsx
│   │   │   ├── AnswerCard.tsx
│   │   │   ├── ToolBadge.tsx
│   │   │   ├── SourceChunk.tsx
│   │   │   └── ExtractTable.tsx
│   │   ├── pages/
│   │   │   ├── AskPage.tsx
│   │   │   └── ExtractPage.tsx
│   │   └── services/
│   │       └── api.ts           ← typed fetch wrappers for backend
└── specs/
    └── (spec kit artifacts)
```

### API Contract (Backend → Frontend)

```
POST /api/v1/upload          → { chunks_indexed: int, metadata: obj }
POST /api/v1/ask             → { answer: str, tool_used: str, source_chunks: str[], page_refs: int[] }
POST /api/v1/extract         → { policy_data: PolicyData }
DELETE /api/v1/store         → { cleared: true }
```

## Governance

- This constitution supersedes all other practices and preferences within this project
- Any deviation from a NON-NEGOTIABLE principle requires updating this document first
- Amendments follow semantic versioning: MAJOR for principle removals/redefinitions, MINOR for additions, PATCH for clarifications
- All implementation plans and specs MUST include a "Constitution Check" section verifying compliance with Principles I–VI
- Complexity beyond what is specified here MUST be justified in the plan's Complexity Tracking table

**Version**: 1.0.0 | **Ratified**: 2026-05-17 | **Last Amended**: 2026-05-17
