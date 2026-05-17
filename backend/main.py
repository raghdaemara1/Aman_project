import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from api.routes import router

load_dotenv()

description = """
## Consumer Finance Document Intelligence Agent — Backend API

This API powers a **local-first Agentic RAG system** for Aman consumer finance contract analysis.

### Pipeline Overview

1. **Upload** a PDF → parsed with `pypdf`, chunked (500 tokens), embedded with `nomic-embed-text` via Ollama, stored in **ChromaDB**.
2. **Ask** a question → a **LangGraph ReAct Agent** decides which tool to use:
   - 🔍 `hybrid_search` — BM25 keyword + ChromaDB vector search merged via Reciprocal Rank Fusion (RRF)
   - 📋 `structured_extract` — Pydantic schema extraction of 8 contract fields
3. **Extract** structured data → Retrieves all chunks, sends them to `llama3.1` with a strict Pydantic schema, returns all 8 fields.
4. **Logs** — Poll this endpoint while any operation is running to get live pipeline step messages.

### Local AI Stack
- **LLM**: `llama3.1:latest` via Ollama (no API key needed)
- **Embeddings**: `nomic-embed-text:latest` via Ollama
- **Vector Store**: ChromaDB (local persistence at `./chroma_db`)
- **BM25**: `rank-bm25` library (in-memory, rebuilt on each upload)
"""

tags_metadata = [
    {
        "name": "documents",
        "description": "Upload and manage consumer finance contract PDFs. Triggers the full ingestion pipeline (parse → chunk → embed → index).",
    },
    {
        "name": "agent",
        "description": "Send natural language questions to the LangGraph ReAct agent. Always returns the tool used and source chunks.",
    },
    {
        "name": "extraction",
        "description": "One-click structured extraction of all 8 contract fields via Pydantic schema validation.",
    },
    {
        "name": "monitoring",
        "description": "Live pipeline logs and health check endpoints.",
    },
]

app = FastAPI(
    title="IntelliDoc — Consumer Finance Document Agent API",
    description=description,
    version="1.0.0",
    openapi_tags=tags_metadata,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/health", tags=["monitoring"], summary="Health check")
async def health():
    """Returns `ok` if the server is running."""
    return {"status": "ok"}
