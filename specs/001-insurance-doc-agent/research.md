# Research: Insurance Document Intelligence Agent

**Phase 0 Output** | Branch: `001-insurance-doc-agent` | Date: 2026-05-17

---

## 1. LangChain ReAct Agent with Ollama

**Decision**: Use `create_react_agent` from `langchain.agents` with `ChatOllama` from `langchain-ollama`. Bind tools using the agent's native tool-calling interface.

**Rationale**: `create_react_agent` is the standard LangChain entrypoint for ReAct-style agents. `ChatOllama` from the `langchain-ollama` package (v0.1+) supports tool/function calling with llama3.1, which is required for the agent to select between `hybrid_search` and `structured_extract`.

**Pattern**:
```python
from langchain_ollama import ChatOllama
from langchain.agents import create_react_agent, AgentExecutor

llm = ChatOllama(model="llama3.1:latest", temperature=0, base_url=OLLAMA_BASE_URL)
agent = create_react_agent(llm, tools=[hybrid_search_tool, structured_extract_tool], prompt=prompt)
executor = AgentExecutor(agent=agent, tools=[...], verbose=True, return_intermediate_steps=True)
```

**Tool selection transparency**: `return_intermediate_steps=True` on `AgentExecutor` exposes which tool was invoked. Parse `intermediate_steps` to extract `tool_used` and `source_chunks` for the API response.

**Alternatives considered**:
- OpenAI gpt-4o-mini: Rejected — requires API key, breaks local-first principle (constitution IV)
- LangGraph: More powerful but over-engineered for a two-tool demo (constitution VI)

---

## 2. Hybrid Search — BM25 + ChromaDB with Reciprocal Rank Fusion

**Decision**: Implement `hybrid_search` as a fusion of BM25 (keyword) and ChromaDB (vector) retrieval using Reciprocal Rank Fusion (RRF) to merge result lists.

**Rationale**: Insurance documents contain specific terminology (policy numbers, clause names, medical procedure names) where exact keyword matching (BM25) outperforms pure vector similarity. Conversely, paraphrased questions ("What's not covered?" vs "exclusions") benefit from vector retrieval. Combining both maximises recall across both query types. This is a meaningful architectural differentiator worth explaining in the interview.

**Library**: `rank-bm25==0.2.2` — lightweight, no external dependencies, pure Python BM25 implementation.

**Pattern**:
```python
from rank_bm25 import BM25Okapi
from langchain_community.vectorstores import Chroma

def hybrid_search(query: str, chunks: list[Document], chroma_retriever, k: int = 4) -> list[Document]:
    # BM25 over stored chunk texts
    tokenized = [doc.page_content.lower().split() for doc in chunks]
    bm25 = BM25Okapi(tokenized)
    bm25_scores = bm25.get_scores(query.lower().split())
    bm25_ranked = sorted(range(len(chunks)), key=lambda i: bm25_scores[i], reverse=True)[:k]

    # Vector search
    vector_results = chroma_retriever.get_relevant_documents(query)
    vector_ranked = [chunks.index(doc) for doc in vector_results if doc in chunks]

    # Reciprocal Rank Fusion: score = sum(1 / (rank + 60)) per list
    rrf_scores: dict[int, float] = {}
    for rank, idx in enumerate(bm25_ranked):
        rrf_scores[idx] = rrf_scores.get(idx, 0) + 1 / (rank + 60)
    for rank, idx in enumerate(vector_ranked):
        rrf_scores[idx] = rrf_scores.get(idx, 0) + 1 / (rank + 60)

    top_k = sorted(rrf_scores, key=rrf_scores.get, reverse=True)[:k]
    return [chunks[i] for i in top_k]
```

**Storage of chunks for BM25**: After ingestion, store the raw chunk list in a module-level variable in `vectorstore.py` so `search_tool.py` can access it without re-loading from ChromaDB. On backend restart, reload chunks from ChromaDB collection using `chroma_collection.get()`.

**Alternatives considered**:
- Pure ChromaDB vector search: Misses exact keyword matches on policy numbers and exclusion names — rejected
- Elasticsearch BM25: Requires running a separate process — breaks local-first principle (constitution IV) — rejected
- LangChain `EnsembleRetriever`: Wraps the same concept but adds abstraction overhead — constitution VI prefers the explicit implementation

---

## 3. Pydantic v2 Structured Extraction with Ollama

**Decision**: Use `ChatOllama` with `with_structured_output(PolicyData)` which leverages Ollama's JSON mode.

**Rationale**: llama3.1 supports JSON-mode output via Ollama. LangChain's `with_structured_output()` wraps this cleanly and validates against the Pydantic v2 schema automatically.

**Pattern**:
```python
from langchain_ollama import ChatOllama
from core.extractor import PolicyData

llm = ChatOllama(model="llama3.1:latest", temperature=0)
structured_llm = llm.with_structured_output(PolicyData)
chain = prompt | structured_llm
result: PolicyData = chain.invoke({"context": chunks_text})
```

**Fallback**: If `with_structured_output` is unavailable on the installed version, fall back to `PydanticOutputParser` with format instructions injected into the prompt.

**Alternatives considered**:
- Manual JSON parsing: Fragile, bypasses Pydantic validation — rejected
- LangChain `JsonOutputParser`: Loses type safety — rejected

---

## 4. ChromaDB Persistence and Reload

**Decision**: Initialize ChromaDB with `persist_directory="./chroma_db"`. On backend startup, check if the collection exists and load it; do not re-embed unless a new document is uploaded.

**Pattern**:
```python
import chromadb
from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaEmbeddings

embeddings = OllamaEmbeddings(model="nomic-embed-text:latest", base_url=OLLAMA_BASE_URL)

def get_or_create_store() -> Chroma:
    return Chroma(
        collection_name="insurance_docs",
        embedding_function=embeddings,
        persist_directory="./chroma_db"
    )
```

**Reload on startup**: Because ChromaDB persists to disk, `Chroma(persist_directory=...)` automatically reloads existing embeddings. No explicit load call needed — the collection is non-empty if a document was previously indexed.

**Clear on new upload**: Call `chroma_client.delete_collection("insurance_docs")` then recreate before ingesting the new document. This satisfies FR-003.

**Alternatives considered**:
- In-memory Chroma: Does not survive page refresh — rejected per clarification Q1
- SQLite fallback: Unnecessary given ChromaDB covers this — rejected

---

## 5. PDF Parsing with unstructured

**Decision**: Use `UnstructuredFileLoader` from `langchain-community` with `unstructured[pdf]` for parsing. Split with `RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)`.

**Pattern**:
```python
from langchain_community.document_loaders import UnstructuredFileLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

loader = UnstructuredFileLoader(file_path, mode="elements")
documents = loader.load()
splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
chunks = splitter.split_documents(documents)
```

**Metadata**: Preserve `page_number` from unstructured element metadata. Add `chunk_index` manually during splitting. Both are required for FR-008 (source chunk with page reference).

**Error handling**: Wrap in try/except; raise `HTTPException(422)` for corrupt/unreadable PDFs (edge case 2 in spec).

**Alternatives considered**:
- PyPDF2: Simpler but loses layout metadata — rejected
- pdfminer: Good layout but requires more integration work — rejected

---

## 6. FastAPI + React CORS Setup

**Decision**: Enable CORS in FastAPI for `http://localhost:5173` (Vite dev server default). In production build, serve frontend static files from FastAPI directly.

**Pattern**:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Vite proxy**: Configure `vite.config.ts` to proxy `/api` to `http://localhost:8000` so frontend code uses relative URLs (`/api/v1/upload`), not hardcoded ports.

---

## 7. File Upload Handling (FastAPI + React)

**Decision**: Use FastAPI `UploadFile` for multipart form upload. Save to a temp directory, process, then delete. Frontend uses `FormData` + axios with `Content-Type: multipart/form-data`.

**Validation**: Backend rejects non-PDF files by checking `file.content_type != "application/pdf"` → HTTP 415 (FR-013).

**Temp file pattern**:
```python
import tempfile, os

async def upload(file: UploadFile):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        chunks = parse_and_chunk(tmp_path)
        ...
    finally:
        os.unlink(tmp_path)
```

---

## 8. Frontend State Management

**Decision**: React `useState` + `useReducer` per page component. No global state library (Redux, Zustand) needed — the demo is two pages with independent state.

**Upload state**: Managed in `App.tsx` — `documentLoaded: boolean` gates whether Ask/Extract pages are interactive.

**Rationale**: Constitution VI (Simplicity) prohibits premature abstractions. Global state is unnecessary for a two-page app.
