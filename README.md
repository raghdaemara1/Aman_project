# Insurance Document Intelligence Agent
## AMAN Holding — Interview Demo

### What This Demonstrates

- PDF parsing with `unstructured.io`
- Hybrid retrieval: BM25 keyword search + ChromaDB vector search merged via Reciprocal Rank Fusion (RRF)
- Agentic reasoning with LangChain ReAct agent — the agent decides WHICH tool to use
- Structured extraction with Pydantic schemas
- Fully local inference via Ollama (llama3.1 + nomic-embed-text) — no API key needed
- React + FastAPI architecture with clean separation of concerns

---

### Architecture

```
[User Browser]
     │  HTTP (axios)
     ▼
[React 18 + Vite]  ──proxy /api──►  [FastAPI + Uvicorn :8000]
                                              │
                              ┌───────────────┼───────────────┐
                              ▼               ▼               ▼
                         [parser.py]   [vectorstore.py]  [agent.py]
                         unstructured   ChromaDB + BM25   ReAct Agent
                         PDF → chunks   RRF hybrid search     │
                                                        ┌─────┴─────┐
                                                        ▼           ▼
                                                 hybrid_search  structured_extract
                                                  (BM25+RRF)    (Pydantic schema)
                                                        │           │
                                                        └─────┬─────┘
                                                              ▼
                                                    [Ollama llama3.1:latest]
```

---

### Prerequisites

- Python 3.10+
- Node.js 18+
- [Ollama](https://ollama.ai) installed and running locally
- Pull required models:
  ```bash
  ollama pull llama3.1
  ollama pull nomic-embed-text
  ```

---

### How to Run

**1. Clone and enter the project**
```bash
git clone https://github.com/raghdaemara1/Aman_project.git
cd Aman_project
```

**2. Backend setup**
```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

**3. Start the backend**
```bash
uvicorn main:app --reload --port 8000
```

**4. Frontend setup (new terminal)**
```bash
cd frontend
npm install
npm run dev
```

**5. Open the app**

Navigate to `http://localhost:5173`

Upload the sample policy from `backend/sample_docs/sample_policy.txt` (rename to `.pdf` or use any real insurance PDF).

---

### Key Design Decisions

**Why hybrid search instead of pure vector search?**
BM25 keyword search catches exact term matches (policy numbers, dates, specific clause names) that semantic embeddings sometimes miss. Reciprocal Rank Fusion (RRF, constant k=60) merges both ranked lists without needing score normalization. This mirrors production RAG best practices.

**Why two tools and not one?**
Semantic/hybrid search and structured extraction are fundamentally different operations. Search finds relevant text. Extraction pulls a specific field with a defined schema. The agent choosing between them is what makes it *agentic* — explicit reasoning about retrieval strategy.

**Why Ollama instead of OpenAI?**
This runs fully locally for the demo — zero cost, zero API key, zero rate limits. In production I would use OpenAI `gpt-4o-mini` or Snowflake Cortex for enterprise scale.

**Why ChromaDB?**
Zero infrastructure, persistent across restarts, identical LangChain API to production vector stores (Pinecone, Snowflake Cortex Search). Swapping it out is a one-line change.

---

### What I Would Add in Production

- **Snowflake Cortex Search** replacing ChromaDB for enterprise-scale retrieval
- **Neo4j knowledge graph** linking policies → claims → customers for multi-hop reasoning
- **LangSmith tracing** for agent observability and step-by-step debugging
- **Multi-document comparison** across policy versions with diff highlighting
- **FastAPI → microservice** so Maxwell or Phoenix frontends can call it as a REST service
- **Streaming responses** via Server-Sent Events for real-time agent step visibility

---

### API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/upload` | POST | Upload and index a PDF |
| `/api/v1/ask` | POST | Ask the ReAct agent a question |
| `/api/v1/extract` | POST | Run structured extraction |
| `/api/v1/store` | DELETE | Clear the vector store |

Interactive docs: `http://localhost:8000/docs`
