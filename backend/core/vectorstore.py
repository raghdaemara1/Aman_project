import os
from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain.schema import Document

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
COLLECTION_NAME = "insurance_docs"
PERSIST_DIR = "./chroma_db"

# Module-level chunk cache for BM25 access without re-loading embeddings
_chunks: list[Document] = []


def _get_embeddings() -> OllamaEmbeddings:
    return OllamaEmbeddings(model="nomic-embed-text:latest", base_url=OLLAMA_BASE_URL)


def ingest_documents(documents: list[Document]) -> None:
    """Clear existing collection, embed and store new documents, cache chunks for BM25."""
    global _chunks
    clear_store()
    _chunks = list(documents)

    Chroma.from_documents(
        documents=documents,
        embedding=_get_embeddings(),
        collection_name=COLLECTION_NAME,
        persist_directory=PERSIST_DIR,
    )


def get_retriever(k: int = 4):
    """Load existing ChromaDB collection and return a retriever for top-k chunks."""
    store = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=_get_embeddings(),
        persist_directory=PERSIST_DIR,
    )
    return store.as_retriever(search_kwargs={"k": k})


def get_chunks() -> list[Document]:
    """Return cached chunk list; reloads from ChromaDB on backend restart if cache is empty."""
    global _chunks
    if not _chunks:
        try:
            store = Chroma(
                collection_name=COLLECTION_NAME,
                embedding_function=_get_embeddings(),
                persist_directory=PERSIST_DIR,
            )
            result = store.get(include=["documents", "metadatas"])
            _chunks = [
                Document(page_content=doc, metadata=meta or {})
                for doc, meta in zip(result["documents"], result["metadatas"])
            ]
        except Exception:
            _chunks = []
    return _chunks


def clear_store() -> None:
    """Delete the ChromaDB collection and clear the in-memory chunk cache."""
    global _chunks
    _chunks = []
    try:
        store = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=_get_embeddings(),
            persist_directory=PERSIST_DIR,
        )
        store.delete_collection()
    except Exception:
        pass


def has_documents() -> bool:
    """Return True if there are indexed documents available."""
    return len(get_chunks()) > 0
