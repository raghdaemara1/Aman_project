import os
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


def parse_and_chunk(file_path: str) -> list[Document]:
    """Parse PDF using pypdf, split into chunks.
    Returns list of LangChain Document objects with page_number and chunk_index metadata.
    """
    source_name = os.path.basename(file_path)
    raw_docs: list[Document] = []

    reader = PdfReader(file_path)
    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            raw_docs.append(Document(
                page_content=text,
                metadata={"page_number": page_num, "source": source_name},
            ))

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(raw_docs)

    for i, chunk in enumerate(chunks):
        chunk.metadata.setdefault("page_number", 1)
        chunk.metadata["chunk_index"] = i
        chunk.metadata["source"] = source_name

    return chunks
