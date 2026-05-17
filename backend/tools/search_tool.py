from langchain_core.tools import tool
from rank_bm25 import BM25Okapi
from core.vectorstore import get_retriever, get_chunks


@tool
def hybrid_search(query: str) -> str:
    """Use this tool when the user asks a general question, wants to know about coverage,
    asks 'what does this policy say about X', or asks any open-ended question about the document.
    Uses both BM25 keyword matching and semantic vector similarity for comprehensive retrieval."""

    chunks = get_chunks()
    if not chunks:
        return "No document indexed. Please upload a PDF first."

    k = 4

    # BM25 keyword search over stored chunk texts
    tokenized = [doc.page_content.lower().split() for doc in chunks]
    bm25 = BM25Okapi(tokenized)
    bm25_scores = bm25.get_scores(query.lower().split())
    bm25_ranked = sorted(range(len(chunks)), key=lambda i: bm25_scores[i], reverse=True)[:k]

    # Vector similarity search via ChromaDB
    vector_ranked: list[int] = []
    try:
        retriever = get_retriever(k=k)
        vector_docs = retriever.invoke(query)
        for vdoc in vector_docs:
            for i, chunk in enumerate(chunks):
                if chunk.page_content == vdoc.page_content:
                    vector_ranked.append(i)
                    break
    except Exception:
        pass

    # Reciprocal Rank Fusion (RRF) — standard constant k=60
    rrf_scores: dict[int, float] = {}
    for rank, idx in enumerate(bm25_ranked):
        rrf_scores[idx] = rrf_scores.get(idx, 0.0) + 1.0 / (rank + 60)
    for rank, idx in enumerate(vector_ranked):
        rrf_scores[idx] = rrf_scores.get(idx, 0.0) + 1.0 / (rank + 60)

    top_indices = sorted(rrf_scores, key=lambda i: rrf_scores[i], reverse=True)[:k]
    top_chunks = [chunks[i] for i in top_indices]

    if not top_chunks:
        return "No relevant content found in the document."

    result = ""
    for chunk in top_chunks:
        page = chunk.metadata.get("page_number", 1)
        result += f"Page {page}: {chunk.page_content}\n---\n"

    return result
