import os
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


def parse_and_chunk(file_path: str, steps: list[str] | None = None) -> list[Document]:
    """Parse PDF using pypdf, split into chunks."""
    def log(msg: str) -> None:
        print(f"[parser] {msg}", flush=True)
        if steps is not None:
            steps.append(msg)

    source_name = os.path.basename(file_path)
    size_kb = round(os.path.getsize(file_path) / 1024, 1)
    log(f"Received: {source_name} ({size_kb} KB)")
    log("Parsing PDF with pypdf...")

    raw_docs: list[Document] = []
    reader = PdfReader(file_path)
    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            raw_docs.append(Document(
                page_content=text,
                metadata={"page_number": page_num, "source": source_name},
            ))

    log(f"Extracted text from {len(reader.pages)} pages ({len(raw_docs)} with content)")
    log("Splitting into chunks (size=500 tokens, overlap=50)...")

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(raw_docs)

    for i, chunk in enumerate(chunks):
        chunk.metadata.setdefault("page_number", 1)
        chunk.metadata["chunk_index"] = i
        chunk.metadata["source"] = source_name

    log(f"Created {len(chunks)} chunks from {len(raw_docs)} pages")
    return chunks
