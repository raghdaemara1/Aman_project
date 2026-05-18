import os
import uuid
import hashlib
import tempfile
import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from core.parser import parse_and_chunk
from core.vectorstore import ingest_documents, has_documents, clear_store, get_retriever, get_chunks
from core.agent import run_agent
from core.extractor import extract_policy_data
from core.orchestrator import run_orchestrator
from core.memory import get_history, clear_session

router = APIRouter()

# Thread pool for running synchronous Ollama/embedding calls without blocking the event loop
_executor = ThreadPoolExecutor(max_workers=2)

# Shared pipeline step log — cleared at the start of each operation
current_pipeline_steps: list[str] = []
last_uploaded_hash: str | None = None


def _run(fn):
    """Run a blocking function in the thread pool and await it."""
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(_executor, fn)


class AskRequest(BaseModel):
    query: str


@router.get("/status", tags=["documents"], summary="Check if a document is indexed")
async def get_status():
    """Returns whether a document is already indexed in ChromaDB. Called by the frontend on startup."""
    if not has_documents():
        return {"has_document": False, "chunks_indexed": 0, "pages": 0}
    chunks = get_chunks()
    page_count = max((c.metadata.get("page_number", 1) for c in chunks), default=1)
    return {"has_document": True, "chunks_indexed": len(chunks), "pages": page_count}


@router.get("/logs")
async def get_logs():
    """Return current pipeline steps. Polled by frontend during long operations."""
    return {"steps": list(current_pipeline_steps)}


@router.post("/upload", tags=["documents"], summary="Upload and index a PDF")
async def upload_document(file: UploadFile = File(...)):
    """
    Accepts a PDF file and runs the full ingestion pipeline:
    1. Validates it's a PDF
    2. Computes MD5 hash — skips if same document is already indexed
    3. Parses text from each page using `pypdf`
    4. Splits into 500-token chunks with 50-token overlap
    5. Generates embeddings using `nomic-embed-text` via Ollama
    6. Stores vectors in ChromaDB and caches chunks for BM25
    """
    global current_pipeline_steps, last_uploaded_hash
    current_pipeline_steps.clear()

    print(f"\n>>> [API] Upload received: {file.filename}")

    if file.content_type != "application/pdf":
        raise HTTPException(status_code=415, detail="Only PDF files are accepted.")

    content = await file.read()
    file_hash = hashlib.md5(content).hexdigest()

    # Skip re-ingestion if same file is already indexed
    if last_uploaded_hash == file_hash and has_documents():
        print(">>> [API] Same file already indexed — skipping re-ingestion")
        current_pipeline_steps.append(f"Same document already indexed (MD5: {file_hash[:8]}…) — skipping re-ingestion")
        chunks = get_chunks()
        page_count = max((c.metadata.get("page_number", 1) for c in chunks), default=1)
        return {
            "chunks_indexed": len(chunks),
            "metadata": {
                "filename": file.filename,
                "pages": page_count,
                "indexed_at": datetime.datetime.utcnow().isoformat() + "Z",
            },
            "steps": list(current_pipeline_steps),
        }

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Parse in thread — doesn't need Ollama but keeps pattern consistent
        print(">>> [API] Parsing PDF...")
        chunks = await _run(lambda: parse_and_chunk(tmp_path, steps=current_pipeline_steps))

        if not chunks:
            raise HTTPException(
                status_code=422,
                detail="Could not parse the PDF. The file may be corrupt or password-protected.",
            )

        # Embed + ingest in thread — Ollama embeddings are blocking
        print(f">>> [API] Embedding {len(chunks)} chunks (Ollama running in background)...")
        await _run(lambda: ingest_documents(chunks, steps=current_pipeline_steps))

        page_numbers = [c.metadata.get("page_number", 1) for c in chunks]
        page_count = max(page_numbers) if page_numbers else 1
        current_pipeline_steps.append(f"Document ready — {len(chunks)} chunks indexed and searchable")
        last_uploaded_hash = file_hash
        print(">>> [API] Upload complete!")

        return {
            "chunks_indexed": len(chunks),
            "metadata": {
                "filename": file.filename,
                "pages": page_count,
                "indexed_at": datetime.datetime.utcnow().isoformat() + "Z",
            },
            "steps": list(current_pipeline_steps),
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f">>> [API] Upload error: {e}")
        raise HTTPException(status_code=422, detail=f"Could not parse the PDF: {str(e)}")
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


@router.post("/ask", tags=["agent"], summary="Ask the ReAct agent a question")
async def ask_question(request: AskRequest):
    """
    Sends a natural language question to the LangChain ReAct agent.
    The agent **reasons** about which tool to use:
    - `hybrid_search`: BM25 + ChromaDB vector search merged via Reciprocal Rank Fusion (RRF)
    - `structured_extract`: Pydantic schema extraction for precise field lookup

    Always returns: the answer, the tool used, source chunks, page references, and pipeline steps.
    """
    global current_pipeline_steps
    current_pipeline_steps.clear()

    print(f"\n>>> [API] Question: '{request.query}'")

    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    if not has_documents():
        raise HTTPException(
            status_code=409,
            detail="No document indexed. Please upload a PDF first.",
        )

    try:
        # Run agent in thread — LLM inference is blocking
        print(">>> [API] Running agent (Ollama in background)...")
        result = await _run(lambda: run_agent(request.query, steps=current_pipeline_steps))
        print(">>> [API] Agent done.")
        return result
    except Exception as e:
        print(f">>> [API] Agent error: {e}")
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


@router.post("/extract", tags=["extraction"], summary="Extract all 8 structured policy fields")
async def extract_data():
    """
    Runs a one-click structured extraction pipeline:
    1. Fetches top-10 most relevant chunks from ChromaDB
    2. Sends them to `llama3.1` with a strict Pydantic schema
    3. Returns all 8 fields: policy number, holder, coverage type, dates, premium, limit, exclusions

    Poll `GET /api/v1/logs` every 1-2s to see live step progress.
    """
    global current_pipeline_steps
    current_pipeline_steps.clear()

    print("\n>>> [API] Extract request received")

    if not has_documents():
        raise HTTPException(
            status_code=409,
            detail="No document indexed. Please upload a PDF first.",
        )

    current_pipeline_steps.append("Starting structured extraction pipeline")
    try:
        retriever = get_retriever(k=10)
        all_chunks = get_chunks()
        # Run extraction in thread — Ollama LLM call is blocking
        print(">>> [API] Running Pydantic extractor (Ollama in background)...")
        policy_data = await _run(
            lambda: extract_policy_data(retriever, steps=current_pipeline_steps, all_chunks=all_chunks)
        )
        print(">>> [API] Extraction complete!")
        return {
            "data": policy_data.model_dump(),
            "steps": list(current_pipeline_steps),
        }
    except Exception as e:
        print(f">>> [API] Extraction error: {e}")
        raise HTTPException(status_code=500, detail=f"Extraction error: {str(e)}")


class ChatRequest(BaseModel):
    query: str
    session_id: str | None = None


@router.post("/chat", tags=["chat"], summary="Conversational multi-agent endpoint")
async def chat(request: ChatRequest):
    """
    Conversational AI pipeline with multi-agent orchestration and session memory.

    Each call goes through three stages:
    1. **Supervisor Agent** — classifies the question and routes to the right specialist
    2. **Retrieval Agent** (hybrid_search) or **Extraction Agent** (structured_extract)
    3. Answer is saved to session memory — follow-up questions have full context

    Pass `session_id` from the previous response to continue a conversation.
    Omit it (or send null) to start a new session.
    """
    global current_pipeline_steps
    current_pipeline_steps.clear()

    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    if not has_documents():
        raise HTTPException(status_code=409, detail="No document indexed. Please upload a PDF first.")

    session_id = request.session_id or str(uuid.uuid4())

    try:
        result = await _run(
            lambda: run_orchestrator(request.query, session_id, steps=current_pipeline_steps)
        )
        return result
    except Exception as e:
        print(f">>> [API] Chat error: {e}")
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


@router.get("/chat/history/{session_id}", tags=["chat"], summary="Get conversation history")
async def get_chat_history(session_id: str):
    """Return full conversation history for a session."""
    return {"session_id": session_id, "history": get_history(session_id)}


@router.delete("/chat/sessions/{session_id}", tags=["chat"], summary="Clear a conversation session")
async def clear_chat_session(session_id: str):
    """Delete all messages for a session and start fresh."""
    clear_session(session_id)
    return {"cleared": True, "session_id": session_id}


@router.delete("/store", tags=["documents"], summary="Clear the vector store")
async def clear_document_store():
    """Deletes the ChromaDB collection and resets the in-memory BM25 index. Use this to start fresh with a new document."""
    global current_pipeline_steps, last_uploaded_hash
    current_pipeline_steps.clear()
    last_uploaded_hash = None
    try:
        clear_store()
        return {"cleared": True}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to clear document store.")
