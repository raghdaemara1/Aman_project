import os
from langchain_community.document_loaders import UnstructuredFileLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document


def parse_and_chunk(file_path: str) -> list[Document]:
    """Parse PDF using unstructured, split into chunks.
    Returns list of LangChain Document objects with page_number and chunk_index metadata.
    """
    loader = UnstructuredFileLoader(file_path, mode="elements")
    raw_docs = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
    )
    chunks = splitter.split_documents(raw_docs)

    source_name = os.path.basename(file_path)
    for i, chunk in enumerate(chunks):
        if "page_number" not in chunk.metadata or chunk.metadata["page_number"] is None:
            chunk.metadata["page_number"] = 1
        chunk.metadata["chunk_index"] = i
        chunk.metadata["source"] = source_name

    return chunks
