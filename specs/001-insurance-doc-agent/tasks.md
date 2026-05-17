---
description: "Task list for Insurance Document Intelligence Agent"
---

# Tasks: Insurance Document Intelligence Agent

**Input**: Design documents from `specs/001-insurance-doc-agent/`

**Prerequisites**: plan.md ✅ · spec.md ✅ · research.md ✅ · data-model.md ✅ · contracts/ ✅

**Tests**: Not requested — no test tasks generated.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths included in all descriptions

## Path Conventions

- Backend: `backend/` at repository root
- Frontend: `frontend/` at repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the full project skeleton so both backend and frontend can start.

- [X] T001 Create backend directory structure: `backend/core/`, `backend/tools/`, `backend/api/`, `backend/sample_docs/`
- [X] T002 Create frontend project using Vite + React + TypeScript: `frontend/` (run `npm create vite@latest frontend -- --template react-ts`)
- [X] T003 [P] Create `backend/requirements.txt` with pinned dependencies: fastapi==0.110.0, uvicorn==0.29.0, langchain==0.1.20, langchain-community==0.0.38, langchain-ollama==0.1.0, chromadb==0.4.24, rank-bm25==0.2.2, unstructured[pdf]==0.13.0, pydantic==2.7.0, python-dotenv==1.0.1, python-multipart==0.0.9
- [X] T004 [P] Create `backend/.env.example` with content: `OLLAMA_BASE_URL=http://localhost:11434`
- [X] T005 [P] Create `backend/main.py` — FastAPI app instance, CORS middleware allowing `http://localhost:5173`, mount router from `backend/api/routes.py` under prefix `/api/v1`
- [X] T006 [P] Create `backend/core/__init__.py`, `backend/tools/__init__.py`, `backend/api/__init__.py` as empty files
- [X] T007 [P] Install Tailwind CSS in `frontend/`: run `npm install -D tailwindcss postcss autoprefixer && npx tailwindcss init -p`, configure `frontend/tailwind.config.ts` content paths for `./src/**/*.{ts,tsx}`
- [X] T008 [P] Configure Vite dev proxy in `frontend/vite.config.ts`: proxy `/api` → `http://localhost:8000`
- [X] T009 [P] Create `frontend/src/main.tsx` — React 18 root render with `ReactDOM.createRoot`
- [X] T010 [P] Add Tailwind directives to `frontend/src/index.css`; install axios: `npm install axios`
- [X] T011 [P] Create `backend/sample_docs/sample_policy.txt` with realistic fake AMAN insurance policy (policy number AMAN-2025-INS-004892, holder Ahmed Mohamed Hassan, comprehensive health, EGP 4800/yr premium, EGP 500k limit, 6 exclusions, full coverage list)
- [X] T012 [P] Create `.gitignore` at repo root: ignore `backend/chroma_db/`, `backend/.env`, `backend/__pycache__/`, `backend/.venv/`, `frontend/node_modules/`, `frontend/dist/`

**Checkpoint**: Both `uvicorn main:app --reload` (backend) and `npm run dev` (frontend) start without errors.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared services and API layer used by all three user stories.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T013 Create `frontend/src/services/api.ts` — typed axios functions: `uploadDoc(file: File)`, `askQuestion(query: string)`, `extractPolicy()`, `clearStore()`; base URL `/api/v1`; all functions return typed response interfaces matching the 4 API contracts
- [X] T014 [P] Create `frontend/src/App.tsx` — two-tab layout ("Ask a Question" / "Extract Policy Data") using React state for active tab; `documentLoaded: boolean` state gates whether tabs are interactive; renders `FileUpload` in sidebar area and tab content area
- [X] T015 [P] Add `UPLOAD_RESPONSE`, `ASK_RESPONSE`, `EXTRACT_RESPONSE` TypeScript interfaces to `frontend/src/services/api.ts` matching the contracts in `specs/001-insurance-doc-agent/contracts/`

**Checkpoint**: Frontend compiles with no TypeScript errors; backend starts and `/docs` shows FastAPI Swagger UI.

---

## Phase 3: User Story 1 — Upload a Policy Document (Priority: P1) 🎯 MVP

**Goal**: User uploads a PDF → system parses, chunks, and indexes it → UI shows chunk count and metadata.

**Independent Test**: Upload `backend/sample_docs/sample_policy.txt` (renamed to `.pdf`) → UI shows chunk count ≥ 1 and filename → backend `/api/v1/upload` returns 200 with `chunks_indexed` and `metadata`.

### Implementation for User Story 1

- [X] T016 [US1] Create `backend/core/parser.py` — `parse_and_chunk(file_path: str) -> list[Document]`: use `UnstructuredFileLoader` in `elements` mode, `RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)`, preserve `page_number` from element metadata, add `chunk_index` to each chunk's metadata
- [X] T017 [US1] Create `backend/core/vectorstore.py` — four functions: `ingest_documents(docs)` clears existing collection then embeds + stores docs using `OllamaEmbeddings(model="nomic-embed-text:latest")` and `Chroma(collection_name="insurance_docs", persist_directory="./chroma_db")`, also stores raw chunk list in module-level `_chunks` variable for BM25; `get_retriever(k=4)` returns ChromaDB retriever; `get_chunks()` returns stored `_chunks` list (reloads from ChromaDB collection on first call if empty); `clear_store()` deletes the ChromaDB collection and clears `_chunks`
- [X] T018 [US1] Create `backend/api/routes.py` — `APIRouter` with two routes: `POST /upload` validates `content_type == "application/pdf"` (HTTP 415 if not), saves to temp file, calls `parse_and_chunk()` + `ingest_documents()`, returns `{chunks_indexed, metadata}`; `DELETE /store` calls `clear_store()`, returns `{cleared: true}`
- [X] T019 [P] [US1] Create `frontend/src/components/FileUpload.tsx` — accepts PDF only (`accept=".pdf"`), calls `uploadDoc()` from api.ts on file select, shows loading spinner during upload, on success updates parent state with chunk count and filename, on error shows inline error message; disable if non-PDF selected
- [X] T020 [US1] Wire `FileUpload` into `frontend/src/App.tsx`: on successful upload set `documentLoaded = true` and display "✓ {filename} — {chunks_indexed} chunks indexed" success banner; on new upload clear previous state

**Checkpoint**: US1 fully functional — upload succeeds, chunk count displayed, non-PDF rejected with error message, second upload replaces the first.

---

## Phase 4: User Story 2 — Ask Natural Language Questions (Priority: P2)

**Goal**: User types a question → ReAct agent selects a tool → answer shown with tool badge + source chunk.

**Independent Test**: With document indexed, type "What is excluded from this policy?" → receive answer with blue "Hybrid Search" badge and at least one source chunk with page number. Type "What is the policy number?" → receive answer with green "Structured Extraction" badge.

### Implementation for User Story 2

- [X] T021 [US2] Create `backend/core/extractor.py` — define `PolicyData(BaseModel)` with 8 fields each with `Field(description=...)` annotation; define `extract_policy_data(retriever) -> PolicyData` that retrieves top-10 chunks, constructs prompt with system instructions ("Return 'Not specified' if field not found"), calls `ChatOllama(model="llama3.1:latest").with_structured_output(PolicyData)`, returns `PolicyData` instance
- [X] T022 [P] [US2] Create `backend/tools/search_tool.py` — `@tool` function `hybrid_search(query: str) -> str`: (1) run BM25 over `get_chunks()` using `rank_bm25.BM25Okapi`, get top-k indices; (2) run `get_retriever(k=4).get_relevant_documents(query)` for vector results; (3) merge both ranked lists using Reciprocal Rank Fusion (`score += 1/(rank+60)` per list); (4) return top-4 chunks as formatted string `"Page {n}: {content}\n---\n"`
- [X] T023 [P] [US2] Create `backend/tools/extract_tool.py` — `@tool` function `structured_extract(field_name: str) -> str`: calls `extract_policy_data(get_retriever())`, maps `field_name` string to the matching `PolicyData` field, returns value as string
- [X] T024 [US2] Create `backend/core/agent.py` — `run_agent(query: str) -> dict`: initialize `ChatOllama(model="llama3.1:latest", temperature=0)`, build `create_react_agent` with tools `[hybrid_search_tool, structured_extract_tool]` and system prompt (cite sources, no hallucination), wrap in `AgentExecutor(return_intermediate_steps=True)`, invoke with query, parse `intermediate_steps` to extract `tool_used` (first tool name: `"hybrid_search"` or `"structured_extract"`) and `source_chunks` + `page_refs` from tool output; return `{answer, tool_used, source_chunks, page_refs}`
- [X] T025 [US2] Add `POST /ask` route to `backend/api/routes.py`: validate query non-empty (HTTP 400), check collection non-empty (HTTP 409 if no document indexed), call `run_agent(query)`, return `AgentResponse` shape
- [X] T026 [P] [US2] Create `frontend/src/components/ToolBadge.tsx` — renders a pill badge: blue background + "Hybrid Search" text for `tool_used === "hybrid_search"`; green background + "Structured Extraction" for `tool_used === "structured_extract"`
- [X] T027 [P] [US2] Create `frontend/src/components/SourceChunk.tsx` — renders a `<details>` collapsible element; summary shows "Source — Page {pageRef}"; body shows chunk text in a `<pre>` block with monospace font
- [X] T028 [P] [US2] Create `frontend/src/components/AnswerCard.tsx` — renders answer text in a large block, `ToolBadge` below it, then one `SourceChunk` per source chunk (zipped with page refs)
- [X] T029 [P] [US2] Create `frontend/src/components/QuestionPanel.tsx` — textarea for question input, submit button disabled when empty or `documentLoaded === false`, shows "Upload a document first" helper text when no document loaded, calls `askQuestion()` from api.ts on submit, passes result up to parent via callback
- [X] T030 [US2] Create `frontend/src/pages/AskPage.tsx` — composes `QuestionPanel` + `AnswerCard`; manages local `answer` state; shows loading state during API call; shows inline error on HTTP 4xx/5xx
- [X] T031 [US2] Wire `AskPage` into `frontend/src/App.tsx` tab 1

**Checkpoint**: US1 + US2 both independently functional — upload works, hybrid search and structured questions return correctly badged answers with source chunks.

---

## Phase 5: User Story 3 — Extract Structured Policy Data (Priority: P3)

**Goal**: User clicks "Extract Structured Data" → all 8 policy fields returned in a table.

**Independent Test**: With document indexed, click Extract button → table shows all 8 rows with values; any missing field shows "Not specified"; `key_exclusions` renders as a bullet list.

### Implementation for User Story 3

- [X] T032 [US3] Add `POST /extract` route to `backend/api/routes.py`: check collection non-empty (HTTP 409 if no document), call `extract_policy_data(get_retriever())`, return `{policy_data: policydata.model_dump()}`
- [X] T033 [P] [US3] Create `frontend/src/components/ExtractTable.tsx` — renders a table with 8 rows (one per `PolicyData` field); `key_exclusions` row renders as a `<ul>` with one `<li>` per exclusion; all other fields render as plain text; empty `key_exclusions` array shows "Not specified"
- [X] T034 [US3] Create `frontend/src/pages/ExtractPage.tsx` — "Extract Structured Data" button (disabled if `documentLoaded === false`, shows "Upload a document first"); loading spinner during API call; renders `ExtractTable` on success; shows inline error on failure
- [X] T035 [US3] Wire `ExtractPage` into `frontend/src/App.tsx` tab 2

**Checkpoint**: All 3 user stories independently functional — upload, Q&A with badges, and structured extraction all work end-to-end.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Error handling, edge cases from spec, README, and golden-path validation.

- [X] T036 [P] Add "no document indexed" guard to `/api/v1/ask` and `/api/v1/extract` in `backend/api/routes.py` — check if ChromaDB collection exists and has documents; return HTTP 409 with `"No document indexed. Please upload a PDF first."` if empty
- [X] T037 [P] Add error display component to `frontend/src/App.tsx` — if any API call returns 4xx/5xx, show a dismissible error banner at the top of the page with the `detail` message from the response body
- [X] T038 [P] Add loading/disabled state to `frontend/src/components/FileUpload.tsx` — disable file input and show spinner text "Parsing and indexing document..." during upload; re-enable on completion
- [X] T039 Create `README.md` at repository root — include: what this demonstrates, architecture text diagram (User → React → FastAPI → LangChain Agent → BM25+ChromaDB hybrid / Pydantic extractor / Ollama), setup instructions (Prerequisites, Backend Setup, Frontend Setup, Demo Flow), key design decisions (two-tool separation, hybrid BM25+vector search with RRF, local-first, Pydantic schema), what would be added in production
- [X] T040 [P] Run quickstart.md validation checklist — manually execute all 10 checklist items in `specs/001-insurance-doc-agent/quickstart.md`; document any failures

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Phase 2 — no dependency on US2 or US3
- **US2 (Phase 4)**: Depends on Phase 2 + `vectorstore.py` from Phase 3 (T017)
- **US3 (Phase 5)**: Depends on Phase 2 + `extractor.py` from Phase 4 (T021)
- **Polish (Phase 6)**: Depends on all user story phases complete

### Within Each Phase

- Models/services before routes
- Routes before frontend components
- Frontend components before pages
- Pages before App.tsx wiring

### Cross-Story Dependencies

- **US2 depends on US1**: Needs `vectorstore.py` (`get_retriever`) — complete T017 before starting US2
- **US3 depends on US2**: Needs `extractor.py` (`extract_policy_data`) — complete T021 before starting US3
- **US3 is otherwise independent**: `ExtractTable`, `ExtractPage`, and `/extract` route have no dependency on US2 components

### Parallel Opportunities

- All [P] tasks within a phase can run simultaneously
- T016 (parser.py) and T017 (vectorstore.py) can run in parallel
- T022 (search_tool.py with hybrid_search), T023 (extract_tool.py) can run in parallel after T021
- T026, T027, T028, T029 (all frontend components for US2) can run in parallel
- T033 (ExtractTable) and T034 (ExtractPage) can run in parallel

---

## Parallel Example: User Story 2

```bash
# After T021 (extractor.py) is done, launch all these in parallel:
Task T022: Create backend/tools/search_tool.py
Task T023: Create backend/tools/extract_tool.py

# After T022 + T023 done, T024 (agent.py) can start

# Frontend components for US2 — all parallel:
Task T026: Create frontend/src/components/ToolBadge.tsx
Task T027: Create frontend/src/components/SourceChunk.tsx
Task T028: Create frontend/src/components/AnswerCard.tsx
Task T029: Create frontend/src/components/QuestionPanel.tsx
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1 (T016–T020)
4. **STOP and VALIDATE**: Upload sample_policy.txt → confirm chunks indexed → confirm non-PDF rejected
5. Demo-able: Document ingestion pipeline is live

### Incremental Delivery

1. Setup + Foundational → skeleton runs
2. US1 → upload pipeline → MVP demo ✅
3. US2 → agentic Q&A → full interview demo ✅✅
4. US3 → structured extraction → complete feature set ✅✅✅
5. Polish → production-ready demo

---

## Notes

- [P] = different files, no blocking dependencies — safe to parallelise
- [USN] label maps each task to its user story for traceability
- Each user story produces an independently testable increment
- Commit after each phase checkpoint
- `backend/chroma_db/` must be git-ignored (contains binary embeddings)
- Test with `backend/sample_docs/sample_policy.txt` renamed to `.pdf` for the file picker
