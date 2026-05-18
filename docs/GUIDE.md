# IntelliDoc — Interview Preparation Guide

> Everything you need to explain this app confidently at the Aman interview:
> pipelines, concepts, output shapes, design decisions, and likely questions.
> All examples use Aman's real business domain: consumer finance contracts.

---

## Table of Contents

1. [What the App Does — One Paragraph](#what-the-app-does)
2. [Why This Is Relevant to Aman](#why-this-is-relevant-to-aman)
3. [The Full Architecture](#the-full-architecture)
4. [Pipeline 1 — Upload & Indexing](#pipeline-1--upload--indexing)
5. [Pipeline 2 — Agentic Q&A](#pipeline-2--agentic-qa)
6. [Pipeline 3 — Structured Extraction](#pipeline-3--structured-extraction)
7. [Key Concepts Explained Simply](#key-concepts-explained-simply)
8. [Actual Output Shapes (with real examples)](#actual-output-shapes)
9. [Design Decisions & Why](#design-decisions--why)
10. [Likely Interview Questions & Strong Answers](#likely-interview-questions--strong-answers)
11. [What You'd Change in Production at Aman](#what-youd-change-in-production)

---

## What the App Does

IntelliDoc is a **local, privacy-first Agentic RAG system** for consumer finance documents. You upload any Aman installment contract PDF. The system parses every page, splits it into 500-token chunks, embeds each chunk using a local AI model (`nomic-embed-text`), and stores them in ChromaDB. From there you can:

- **Ask any question** in plain English — a LangGraph ReAct agent reasons about HOW to answer, picks the right tool (semantic search vs. structured extraction), retrieves the relevant text, and generates a grounded answer with source citations.
- **Extract structured data** with one click — the LLM reads all indexed chunks and fills a strict Pydantic schema with 8 key contract fields.

Everything runs 100% locally. No API key. No cloud. No customer data leaves the machine.

---

## Why This Is Relevant to Aman

Aman issues consumer finance installment contracts for electronics, furniture, cars, and tourism packages through its stores, e-commerce platform, and Super App. Each contract contains:

- Customer identity and financial terms
- Monthly installment amounts and profit rates
- Repayment schedules and maturity dates
- Late payment fees, early settlement conditions
- Takaful (Islamic insurance) coverage details

**The problem IntelliDoc solves:** A branch agent or operations analyst needs to quickly answer a customer's question about their contract — "Can I settle early?", "What is my monthly payment?", "What happens if I miss a payment?" — without reading the full document. IntelliDoc turns any contract PDF into a queryable, structured knowledge base in under 30 seconds.

---

## The Full Architecture

```
Browser (React 18 + TypeScript + Vite)
        │
        │  HTTP REST API
        ▼
FastAPI Backend (Python, port 8000)
   ├── POST /api/v1/upload   → parser.py → vectorstore.py
   ├── POST /api/v1/ask      → agent.py  → search_tool / extract_tool
   ├── POST /api/v1/extract  → extractor.py
   ├── GET  /api/v1/logs     → live pipeline step polling
   └── DELETE /api/v1/store  → clear ChromaDB
        │
        │  Local HTTP (port 11434)
        ▼
Ollama (local AI runtime)
   ├── llama3.1:latest        → reasoning, generation, structured extraction
   └── nomic-embed-text:latest → text → 768-dim vectors
```

**Data layer:**
- `ChromaDB` — persistent vector store on disk (`./chroma_db/`)
- `BM25` (rank-bm25) — keyword index rebuilt in-memory on each upload
- Both combined via **RRF (Reciprocal Rank Fusion)** for hybrid search

---

## Pipeline 1 — Upload & Indexing

**Triggered by:** `POST /api/v1/upload` with a PDF file

### Step-by-step

```
1. Validate content type = application/pdf

2. Compute MD5 hash of file bytes
   └── Same hash + documents already in ChromaDB → skip re-ingestion
       ("Document Memory" — avoids re-embedding the same contract)

3. Save to temp file → parse with pypdf
   └── Extract raw text from each page
   └── Output: one Document object per page with metadata:
       { page_number: int, source: str }

4. Chunk with RecursiveCharacterTextSplitter
   └── chunk_size = 500 tokens, chunk_overlap = 50 tokens
   └── Overlap: a sentence split across a boundary is still fully
       present in at least one chunk — no context is ever lost
   └── Each chunk gets: { page_number, source, chunk_index }

5. Embed each chunk with nomic-embed-text
   └── Each chunk → 768-dimensional float vector
   └── Vectors capture semantic meaning (not just keywords)

6. Store in ChromaDB (persisted to ./chroma_db/)

7. Cache all chunks in memory for BM25 (rebuilt on each upload)
```

### Real example log output

```
Step 1:  Received: aman_contract_047832.pdf (92.4 KB)
Step 2:  Parsing PDF with pypdf...
Step 3:  Extracted text from 6 pages (6 with content)
Step 4:  Splitting into chunks (size=500 tokens, overlap=50)...
Step 5:  Created 38 chunks from 6 pages
Step 6:  Clearing previous document store...
Step 7:  Generating embeddings with nomic-embed-text...
Step 8:  Stored 38 vectors in ChromaDB (collection: insurance_docs)
Step 9:  BM25 keyword index built over 38 chunks
Step 10: Document ready — 38 chunks indexed and searchable
```

### API response shape

```json
{
  "chunks_indexed": 38,
  "metadata": {
    "filename": "aman_contract_047832.pdf",
    "pages": 6,
    "indexed_at": "2025-05-17T10:30:00Z"
  },
  "steps": ["Received: aman_contract_047832.pdf (92.4 KB)", "..."]
}
```

---

## Pipeline 2 — Agentic Q&A

**Triggered by:** `POST /api/v1/ask` with `{ "query": "..." }`

### The ReAct Loop

ReAct = **Reason + Act**. The agent loops:
```
Thought → Action → Observation → Thought → Action → ... → Final Answer
```

The agent does NOT just run a search on every question. It reasons about which strategy fits the question, then acts accordingly.

### The Two Tools

| Tool | When agent picks it | How it works |
|---|---|---|
| `hybrid_search` | General questions about terms, conditions, processes, "what does the contract say about X" | BM25 + ChromaDB merged via RRF → top-4 chunks → LLM generates answer |
| `structured_extract` | Specific field lookups: contract number, customer name, amount, installment, rate, duration, conditions | Fills ContractData Pydantic schema → returns the specific field |

### Hybrid Search Detail (Tool 1)

```
Query: "what happens if I miss a payment?"
         │
         ├── BM25 keyword search over all chunks
         │   Tokenizes + scores by TF-IDF
         │   Good for: "late payment", "missed installment", "penalty"
         │
         ├── ChromaDB vector search (top-4)
         │   Embeds query → cosine similarity search
         │   Good for: concepts, paraphrases, "consequences of non-payment"
         │
         └── RRF merge (k=60)
             Score = 1/(rank + 60) from each list
             Sum scores → re-rank → top-4 chunks returned to agent
```

### Example Agent Reasoning (ReAct trace)

**Question: "What is the monthly installment?"**
```
Thought: The user is asking for a specific field — the monthly installment amount.
         This is a precise value, not a general question. I should use structured_extract.
Action:  structured_extract("monthly installment")
Observation: "EGP 1,458.33 / month"
Thought: I have the exact value.
Final Answer: The monthly installment is EGP 1,458.33.
```

**Question: "Can I pay off the contract early?"**
```
Thought: This is a general question about early settlement terms.
         I need to find the relevant contract clause. I should use hybrid_search.
Action:  hybrid_search("early settlement early payment payoff")
Observation: Page 3: "The customer may settle the remaining balance in full at any time.
             An early settlement fee of 1% of the outstanding principal applies
             if settlement occurs within the first 12 months..."
Thought: I found the relevant clause.
Final Answer: Yes, you can settle early. A 1% fee applies if you do so within
              the first 12 months. No fee after 12 months.
```

### API Response Shape

```json
{
  "answer": "The monthly installment is EGP 1,458.33 per month.",
  "tool_used": "structured_extract",
  "source_chunks": [
    "Monthly Installment: EGP 1,458.33 / month\nTotal Repayment Amount: EGP 35,000..."
  ],
  "page_refs": [1],
  "steps": [
    "Query received: \"What is the monthly installment?\"",
    "Initializing ReAct agent (llama3.1:latest + 2 tools)",
    "Agent reasoning — selecting tool...",
    "Tool selected: structured_extract",
    "Retrieved 1 source chunk(s)",
    "Generating final answer with llama3.1:latest...",
    "Done"
  ]
}
```

### Question-to-Tool Mapping (Demo Examples)

| Question | Tool | Why |
|---|---|---|
| "What is the contract number?" | `structured_extract` | Exact identifier |
| "What is the monthly installment?" | `structured_extract` | Specific numeric field |
| "Who is the customer?" | `structured_extract` | Named field |
| "What is the profit rate?" | `structured_extract` | Specific rate field |
| "What are the late payment penalties?" | `hybrid_search` | Clause content |
| "Can I settle this contract early?" | `hybrid_search` | Process/condition question |
| "What is covered by Takaful?" | `hybrid_search` | Coverage clause |
| "What happens if I miss 3 payments?" | `hybrid_search` | Consequence clause |

---

## Pipeline 3 — Structured Extraction

**Triggered by:** `POST /api/v1/extract`

### Step-by-step

```
1. Load all cached Document objects from memory (or reload from ChromaDB)

2. Sort by page_number — page 1 ALWAYS first
   (contract header: number, customer, financial terms are on page 1)

3. Build full context string:
   "===== PAGE 1 =====\n[chunk]\n[chunk]\n
    ===== PAGE 2 =====\n[chunk]..."
   Trim to 6,000 characters

4. Primary: llm.with_structured_output(ContractData)
   LangChain sends ContractData schema as a JSON tool definition
   llama3.1 must call the tool with matching JSON
   Pydantic validates all 8 fields and types

5. Fallback (if tool-calling fails):
   Re-prompt with format="json" (Ollama JSON mode)
   Parse raw JSON response → construct ContractData manually
```

### The Pydantic Schema (ContractData)

```python
class ContractData(BaseModel):
    contract_number:    str        # "AMAN-FIN-2025-CF-047832"
    customer_name:      str        # "Sara Ahmed Mahmoud"
    product_financed:   str        # "Samsung QLED 65-inch Smart TV"
    total_amount:       str        # "EGP 25,000"
    monthly_installment:str        # "EGP 1,458.33 / month"
    duration_months:    str        # "24 months"
    profit_rate:        str        # "2.5% per month (flat rate)"
    key_conditions:     list[str]  # ["Late fee EGP 75/month", "Early settlement 1%..."]
```

### Real Output Shape

```json
{
  "data": {
    "contract_number":     "AMAN-FIN-2025-CF-047832",
    "customer_name":       "Sara Ahmed Mahmoud",
    "product_financed":    "Samsung QLED 65-inch Smart TV (Model: QN65Q80C)",
    "total_amount":        "EGP 25,000",
    "monthly_installment": "EGP 1,458.33 / month",
    "duration_months":     "24 months",
    "profit_rate":         "2.5% per month (flat rate)",
    "key_conditions": [
      "Late payment fee: EGP 75/month after 7 days grace period",
      "3 missed payments: full balance declared immediately due",
      "Bounced direct debit fee: EGP 150 per occurrence",
      "Early settlement fee: 1% of outstanding principal (first 12 months only)",
      "Ownership transfers to customer upon full repayment"
    ]
  },
  "steps": [
    "Starting structured extraction pipeline",
    "Building extraction context from all indexed chunks...",
    "Using 38 cached chunks with page metadata",
    "Context built: 5,842 characters (page 1 first)",
    "Sending to llama3.1 — structured output mode (tool-calling)...",
    "[OK] Extraction complete - 8/8 fields populated"
  ]
}
```

---

## Key Concepts Explained Simply

### RAG (Retrieval-Augmented Generation)

Instead of asking the LLM a question from memory (where it could hallucinate), you first **retrieve** relevant text from your document, then feed that text + question to the LLM to **generate** a grounded answer.

```
Without RAG:  LLM guesses from training data → may hallucinate
With RAG:     LLM reads actual contract text → grounded, citable answer
```

### Agentic RAG vs. Basic RAG

| Basic RAG | Agentic RAG (IntelliDoc) |
|---|---|
| Always runs vector search | Agent DECIDES which retrieval to use |
| One strategy fits all questions | Two tools: search OR structured extract |
| No reasoning step | ReAct: Thought → Action → Observation → Answer |

### Vector Embeddings

`nomic-embed-text` converts each chunk into 768 floats. Similar text → similar vectors → small cosine distance. Used for semantic search.

```
"monthly repayment amount"   → [0.21, -0.04, ...]  (768 numbers)
"installment per month"      → [0.19, -0.06, ...]  (very similar → high cosine similarity)
"contract cancellation"      → [-0.44, 0.72, ...]  (very different)
```

### BM25

Keyword ranking by Term Frequency × Inverse Document Frequency. Great for exact strings like `AMAN-FIN-2025-CF-047832` — no vector relationship exists between a contract number and the query "what is the contract number?", but BM25 finds it perfectly.

### RRF (Reciprocal Rank Fusion)

Merges BM25 and vector search ranked lists:
```
RRF_score(doc) = 1/(bm25_rank + 60) + 1/(vector_rank + 60)
```
Scale-invariant — uses rank position, not raw scores. Documents in both lists get double contribution.

### ReAct (Reason + Act)

LLM alternates between Thought (what should I do?) and Action (call a tool) until it has enough to answer. The key insight: the agent sees the tool output and can reason further before answering, instead of blindly returning whatever the tool returns.

### Pydantic Schema Enforcement

`llm.with_structured_output(ContractData)` sends the Pydantic schema as a JSON Schema tool definition. The LLM must call that tool with arguments matching the schema. Pydantic validates the result. If `monthly_installment` is missing or the wrong type, it raises — guaranteeing the output shape every time.

### ChromaDB

Local vector database. Persists to disk (`./chroma_db/` as SQLite + binary files). Supports cosine similarity search. Stores document text + metadata alongside each vector.

---

## Design Decisions & Why

**Why Hybrid Search instead of pure vector search?**
Contract identifiers like `AMAN-FIN-2025-CF-047832` have no semantic relationship to the query "what is the contract number?" — vector search fails. BM25 catches it exactly. Combining both via RRF handles both exact lookups and conceptual questions in one step.

**Why two separate tools?**
Search finds relevant text passages. Extraction fills a typed schema with validation. Keeping them separate forces the agent to reason explicitly about retrieval strategy. That reasoning step is what makes this "agentic" — without it, it's just basic RAG.

**Why Ollama instead of OpenAI?**
Consumer finance contracts contain sensitive customer PII (national ID, bank account, name). Running everything locally means zero privacy risk for Aman customers — no data ever leaves the corporate machine. The LangChain abstraction makes switching to GPT-4o a one-line change if needed.

**Why page 1 is always pinned first?**
Contract headers (number, customer name, financial terms) are always on page 1, but chunking splits them into multiple pieces. Semantic search for "contract number" fails because the string has no vector relationship to its value. Sorting all chunks with page 1 first ensures the LLM always sees the key identifiers before anything else.

**Why FastAPI with ThreadPoolExecutor?**
Ollama calls are synchronous and blocking. Running them directly in async endpoints would freeze the entire event loop, making the `/logs` polling endpoint unresponsive during inference. The thread pool keeps the event loop free — the frontend can keep polling for progress updates while the LLM processes.

**Why temperature=0?**
For contract Q&A and structured extraction, you need deterministic, factual answers. Temperature 0 means the model always picks the highest-probability token — consistent, grounded, no randomness that could cause hallucination or wrong fields.

---

## Likely Interview Questions & Strong Answers

**Q: What is RAG and why is it better than fine-tuning for this use case?**

> RAG retrieves relevant text from the document at inference time and gives it to the LLM as context. Fine-tuning bakes knowledge into model weights during training. For Aman's contracts, RAG is the right choice for three reasons: (1) contracts change — a new contract is immediately queryable after upload, with no retraining; (2) RAG gives traceable source citations so staff can verify answers; (3) RAG handles any document without any training. Fine-tuning makes sense for teaching the model a new reasoning style or task domain, not for giving it access to new documents.

**Q: What makes this "agentic"?**

> An agentic system reasons about HOW to accomplish a task, not just what to output. In IntelliDoc, the LangGraph ReAct agent observes the user's question, thinks about what type of question it is, chooses between two tools based on that reasoning, executes the tool, reads the result, and decides whether it has enough to answer. A non-agentic system would run the same vector search on every single question regardless. The agent's reasoning step is what separates this from basic RAG.

**Q: How does hybrid search work?**

> Two searches run in parallel: BM25 scores chunks by term frequency-inverse document frequency — great for exact matches like contract numbers, amounts, and dates. ChromaDB vector search finds semantically similar chunks by cosine distance of 768-dim embeddings — great for concepts like "early settlement" or "late payment consequences". Both return ranked lists. Reciprocal Rank Fusion merges them using rank position (1 / rank + 60) — scale-invariant because it doesn't care that BM25 scores are 0-100 and cosine similarity is 0-1. The top-4 results by combined RRF score go to the agent.

**Q: What is the difference between your two tools?**

> `hybrid_search` is for open-ended questions — it retrieves the most relevant text passages and the LLM synthesizes an answer. `structured_extract` is for specific field lookups — it reads all chunks and fills a Pydantic schema, returning typed, validated fields. A question like "what is the profit rate?" goes to `structured_extract` — I want the exact value. A question like "what are all the conditions if I miss a payment?" goes to `hybrid_search` — I need to read a clause and synthesize it. Mixing both in one tool loses that distinction and the type safety.

**Q: How do you prevent the LLM from hallucinating?**

> Three mechanisms: (1) The system prompt explicitly instructs the agent to only answer from the provided document text and to say "not found" if the answer isn't there. (2) Temperature is 0 — deterministic output, no randomness that could generate invented values. (3) Pydantic schema enforcement — for structured extraction, the LLM must return validated typed fields and cannot invent fields or change their type. Every answer also shows the source chunk it came from, so users can verify against the original document.

**Q: How would you scale this for Aman in production?**

> Replace ChromaDB with Snowflake Cortex Search or Pinecone for millions of contracts across all branches. Replace Ollama with GPT-4o or Anthropic Claude — one line change in agent.py. Add LangSmith for full observability: trace every agent reasoning step, measure latency per tool, catch failures. Add JWT authentication so each branch agent only sees their contracts. Add a Neo4j knowledge graph to link contracts → customers → payment history for multi-hop queries like "show me all customers with active contracts who have missed payments in the last 3 months". Add streaming via SSE instead of polling. All of this is a matter of swapping components — the core architecture (parse → chunk → embed → agent → hybrid search + structured extract) scales unchanged.

**Q: Why use LangGraph instead of LangChain's older AgentExecutor?**

> LangGraph is the modern standard for building stateful agent loops. It models the agent as a compiled graph — nodes for reasoning and acting, edges for conditions — giving you fine-grained control over the loop, first-class streaming support, built-in checkpointing, and cleaner message handling. `create_react_agent` from `langgraph.prebuilt` sets this up with sensible defaults. AgentExecutor was the older approach; it's being deprecated in favor of LangGraph because the graph model is more transparent, more extensible, and easier to debug.

**Q: Why did you choose ChromaDB over Pinecone or Weaviate?**

> For a local demo, ChromaDB is the right choice: zero infrastructure, persists to disk, and the LangChain integration is identical to any cloud vector store. The abstraction is the same — if I swap to Pinecone tomorrow, I change one import and the rest of the code is untouched. ChromaDB proves the architecture without requiring cloud accounts, API keys, or network dependencies. For Aman at production scale, I'd move to Snowflake Cortex Search which they may already have in their data infrastructure, or Pinecone for a managed vector service.

---

## What You'd Change in Production

| Current (Demo) | Production at Aman Scale |
|---|---|
| Ollama local llama3.1 | OpenAI GPT-4o or Anthropic Claude — one-line swap |
| ChromaDB local disk | Snowflake Cortex Search — enterprise-scale, multi-tenant |
| In-memory BM25 | Elasticsearch — persistent, scalable keyword index |
| No authentication | JWT — branch staff login, contract ownership per user |
| Single contract at a time | Multi-contract index — full portfolio per customer |
| Polling `/logs` | SSE (Server-Sent Events) — real-time streaming without polling |
| No tracing | LangSmith — every agent step traced, latency measured, errors caught |
| No knowledge graph | Neo4j — contracts → customers → payments → delinquency patterns |
| Local PDF only | Direct integration with Aman's document management system |

---

*IntelliDoc — Built with LangGraph · LangChain · FastAPI · React · ChromaDB · Ollama*
*Domain: Aman Consumer Finance — installment contracts, Murabaha financing, fintech Egypt*
