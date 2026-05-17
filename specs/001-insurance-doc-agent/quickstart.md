# Quickstart: Insurance Document Intelligence Agent

## Prerequisites

| Requirement | Version | Check |
|-------------|---------|-------|
| Python | 3.10+ | `python --version` |
| Node.js | 18+ | `node --version` |
| Ollama | latest | `ollama --version` |
| Ollama models | llama3.1 + nomic-embed-text | `ollama list` |

Pull required models if not already installed:
```bash
ollama pull llama3.1
ollama pull nomic-embed-text
```

---

## Backend Setup

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env        # edit if Ollama is not on default port
uvicorn main:app --reload   # runs on http://localhost:8000
```

Verify backend is running:
```
GET http://localhost:8000/docs   → FastAPI Swagger UI
```

---

## Frontend Setup

```bash
cd frontend
npm install
npm run dev                     # runs on http://localhost:5173
```

Open `http://localhost:5173` in your browser.

---

## Demo Flow (Golden Path)

1. **Upload** — click "Choose File" or drag-drop `backend/sample_docs/sample_policy.txt` (rename to `.pdf` for the file picker, or use a real PDF)
2. **Confirm** — system shows "42 chunks indexed" with document metadata
3. **Ask (semantic)** — type: `"What services are covered under this policy?"`
   - Expect: Blue "Semantic Search" badge + answer + source chunk from the coverage section
4. **Ask (structured)** — type: `"What is the policy expiry date?"`
   - Expect: Green "Structured Extraction" badge + exact date + source chunk
5. **Extract** — click "Extract Structured Data" tab → click "Extract"
   - Expect: Table with all 8 fields populated; Key Exclusions as a bullet list

---

## Validation Checklist

- [ ] Backend starts without errors
- [ ] Frontend loads at localhost:5173
- [ ] PDF upload succeeds and reports chunk count
- [ ] Open-ended question returns semantic_search tool
- [ ] Field-specific question returns structured_extract tool
- [ ] Every answer shows a source chunk with page number
- [ ] Extract tab returns all 8 fields; missing fields show "Not specified"
- [ ] Uploading a second PDF clears the first document
- [ ] Page refresh retains the indexed document (ChromaDB persistence)
- [ ] Non-PDF upload shows error message

---

## Environment Variables

| Variable | Default | Notes |
|----------|---------|-------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Change if Ollama runs on a different port |

---

## Common Issues

**"Connection refused" on /api/v1/upload**
→ Backend not running. Run `uvicorn main:app --reload` in `backend/`.

**"model not found: llama3.1"**
→ Run `ollama pull llama3.1`.

**Empty source chunks in response**
→ ChromaDB collection may be empty. Re-upload the document.

**CORS error in browser**
→ Ensure Vite proxy is configured (`vite.config.ts`) and backend is on port 8000.
