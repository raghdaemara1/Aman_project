import os
import tempfile
import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from core.parser import parse_and_chunk
from core.vectorstore import ingest_documents, has_documents, clear_store, get_retriever
from core.agent import run_agent
from core.extractor import extract_policy_data

router = APIRouter()


class AskRequest(BaseModel):
    query: str


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=415, detail="Only PDF files are accepted.")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        chunks = parse_and_chunk(tmp_path)
        if not chunks:
            raise HTTPException(
                status_code=422,
                detail="Could not parse the PDF. The file may be corrupt or password-protected.",
            )

        ingest_documents(chunks)

        page_numbers = [c.metadata.get("page_number", 1) for c in chunks]
        page_count = max(page_numbers) if page_numbers else 1

        return {
            "chunks_indexed": len(chunks),
            "metadata": {
                "filename": file.filename,
                "page_count": page_count,
                "indexed_at": datetime.datetime.utcnow().isoformat() + "Z",
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not parse the PDF: {str(e)}")
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


@router.post("/ask")
async def ask_question(request: AskRequest):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    if not has_documents():
        raise HTTPException(
            status_code=409,
            detail="No document indexed. Please upload a PDF first.",
        )

    try:
        return run_agent(request.query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


@router.post("/extract")
async def extract_data():
    if not has_documents():
        raise HTTPException(
            status_code=409,
            detail="No document indexed. Please upload a PDF first.",
        )

    try:
        retriever = get_retriever(k=10)
        policy_data = extract_policy_data(retriever)
        return {"policy_data": policy_data.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction error: {str(e)}")


@router.delete("/store")
async def clear_document_store():
    try:
        clear_store()
        return {"cleared": True}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to clear document store.")
