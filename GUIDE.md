# IntelliDoc — Interview Preparation Guide

> Everything you need to explain this app confidently in an interview:
> pipelines, concepts, output shapes, design decisions, and likely questions.

---

## Table of Contents

1. [What the App Does — One Paragraph](#what-the-app-does)
2. [The Full Architecture](#the-full-architecture)
3. [Pipeline 1 — Upload & Indexing](#pipeline-1--upload--indexing)
4. [Pipeline 2 — Agentic Q&A](#pipeline-2--agentic-qa)
5. [Pipeline 3 — Structured Extraction](#pipeline-3--structured-extraction)
6. [Key Concepts Explained Simply](#key-concepts-explained-simply)
7. [Actual Output Shapes (with real examples)](#actual-output-shapes)
8. [Design Decisions & Why](#design-decisions--why)
9. [Likely Interview Questions & Strong Answers](#likely-interview-questions--strong-answers)
10. [What You'd Change in Production](#what-youd-change-in-production)

---

## What the App Does

IntelliDoc is a **local, privacy-first Agentic RAG system** for insurance documents. You upload any insurance policy PDF. The system parses it, chunks it into 500-token segments, embeds every chunk using a local AI model (`nomic-embed-text`), and stores them in a vector database (ChromaDB). From that point you can:

- **Ask any question** in plain English — a LangChain ReAct agent reasons about HOW to answer, picks the right tool (semantic search vs. structured extraction), retrieves the relevant text, and generates a grounded answer with source citations.
- **Extract structured data** with one click — the LLM reads all indexed chunks and fills a strict Pydantic schema with 8 key policy fields.

Everything runs 100% locally. No API key. No cloud. No data leaves the machine.

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
   ├── llama3.1:latest        → reasoning, generation, extraction
   └── nomic-embed-text:latest → text → 768-dim vectors
```

**Data layer:**
- `ChromaDB` — persistent vector store on disk (`./chroma_db/`)
- `BM25` (rank-bm25) — keyword index built in-memory on each upload
- Both combined via **Reciprocal Rank Fusion (RRF)** for hybrid search

---

## Pipeline 1 — Upload & Indexing

**Triggered by:** `POST /api/v1/upload` with a PDF file

### Step-by-step

```
User uploads PDF
      │
      ▼
1. Validate content type = application/pdf

2. Compute MD5 hash of file bytes
   └── If same hash + documents already in ChromaDB → skip re-ingestion
       (Document Memory feature — avoids re-embedding the same file)

3. Save to temp file → parse with pypdf
   └── Loop through each page → extract raw text
   └── Skip blank pages
   └── Output: list of Document objects, one per page, with metadata:
       { page_number: int, source: str }

4. Chunk with RecursiveCharacterTextSplitter
   └── chunk_size = 500 tokens
   └── chunk_overlap = 50 tokens
   └── Why overlap? So a sentence split across a boundary
       is still fully present in at least one chunk.
   └── Output: N Document objects, each with:
       { page_number: int, source: str, chunk_index: int }

5. Embed each chunk with nomic-embed-text via Ollama
   └── Each chunk → 768-dimensional float vector
   └── These vectors capture semantic meaning, not just keywords

6. Store vectors in ChromaDB (persisted to disk)
   └── Collection name: "insurance_docs"

7. Cache all chunks in memory for BM25 (rebuilt on each upload)
```

### Real example output from the UI

```
Step 1: Received: tmp8tpsiujh.pdf (88.1 KB)
Step 2: Parsing PDF with pypdf...
Step 3: Extracted text from 10 pages (10 with content)
Step 4: Splitting into chunks (size=500 tokens, overlap=50)...
Step 5: Created 53 chunks from 10 pages
Step 6: Clearing previous document store...
Step 7: Generating embeddings with nomic-embed-text (model: nomic-embed-text:latest)...
Step 8: Stored 53 vectors in ChromaDB (collection: insurance_docs)
Step 9: BM25 keyword index built over 53 chunks
Step 10: Document ready — 53 chunks indexed and searchable
```

### API response shape

```json
{
  "chunks_indexed": 53,
  "metadata": {
    "filename": "tmp8tpsiujh.pdf",
    "pages": 10,
    "indexed_at": "2025-05-17T10:30:00Z"
  },
  "steps": [
    "Received: policy.pdf (88.1 KB)",
    "Parsing PDF with pypdf...",
    "Extracted text from 10 pages (10 with content)",
    "Splitting into chunks (size=500 tokens, overlap=50)...",
    "Created 53 chunks from 10 pages",
    "..."
  ]
}
```

---

## Pipeline 2 — Agentic Q&A

**Triggered by:** `POST /api/v1/ask` with `{ "query": "..." }`

This is the "agentic" part — the AI does not just retrieve and answer. It **reasons** about which strategy to use.

### The ReAct Loop

ReAct = **Reason + Act**. The agent loops:
```
Thought → Action → Observation → Thought → Action → ... → Final Answer
```

### The two tools

| Tool | When the agent picks it | How it works |
|------|------------------------|--------------|
| `hybrid_search` | General questions about coverage, terms, conditions, "what does this say about X" | BM25 + ChromaDB vector search merged via RRF |
| `structured_extract` | Specific field lookups: policy number, expiry date, premium, holder name, limits, exclusions | Runs full Pydantic extraction → returns the specific field |

### Hybrid Search detail (Tool 1)

```
Query: "what is covered under hospitalization?"
         │
         ├── BM25 keyword search over 53 chunks
         │   └── Tokenizes query + chunks → TF-IDF style scoring
         │   └── Great for: exact terms, policy numbers, dates
         │
         ├── ChromaDB vector search (top-4)
         │   └── Embeds query with nomic-embed-text → cosine similarity
         │   └── Great for: semantics, concepts, paraphrases
         │
         └── RRF merge (k=60)
             └── RRF score = 1/(rank + 60) for each result
             └── Sum scores from both ranked lists
             └── Re-rank by combined score → top-4 chunks returned
```

**Why RRF and not averaging scores?**
Scores from BM25 and cosine similarity are on completely different scales. RRF only uses the rank position, not the raw score, so it's scale-invariant.

### Step-by-step flow

```
POST /ask  { "query": "What is the coverage limit?" }
      │
      ▼
has_documents() check → 409 if no document uploaded yet
      │
      ▼
run_agent(query, steps=[]) called in thread pool (non-blocking)
      │
      ▼
LangGraph ReAct agent initialised:
  model = ChatOllama("llama3.1:latest", temperature=0)
  tools = [hybrid_search, structured_extract]
  system_prompt = "You are an insurance intelligence agent..."
      │
      ▼
Agent reasons:
  Thought: "coverage limit" is a specific field → use structured_extract
  Action: structured_extract("coverage limit")
  Observation: "$25,000.00"
  Final Answer: "The coverage limit is $25,000.00 per accident."
      │
      ▼
Parse messages list:
  - Last AIMessage.content → answer text
  - First AIMessage.tool_calls[0].name → tool_used
  - ToolMessage.content → source_chunks + page_refs
```

### API response shape

```json
{
  "answer": "The coverage limit is $25,000 per accident as specified in the policy declarations.",
  "tool_used": "structured_extract",
  "source_chunks": [
    "Maximum Benefit: $25,000 per accident. Coverage applies to accidental bodily injury..."
  ],
  "page_refs": [1],
  "steps": [
    "Query received: \"What is the coverage limit?\"",
    "Initializing ReAct agent (llama3.1:latest + 2 tools: hybrid_search, structured_extract)",
    "Agent reasoning — selecting tool...",
    "Tool selected: structured_extract",
    "Retrieved 1 source chunk(s)",
    "Generating final answer with llama3.1:latest...",
    "Done"
  ]
}
```

### Example Q&A pairs (what to demo)

| Question type | Example question | Tool the agent picks | Why |
|---|---|---|---|
| Specific field | "What is the policy number?" | `structured_extract` | Exact identifier lookup |
| Specific field | "When does this policy expire?" | `structured_extract` | Date field lookup |
| Specific field | "Who is the policy holder?" | `structured_extract` | Named field |
| General/conceptual | "What sports are excluded?" | `hybrid_search` | Requires reading coverage text |
| General/conceptual | "What happens if I need treatment abroad?" | `hybrid_search` | Requires understanding a clause |
| General/conceptual | "What is the claims procedure?" | `hybrid_search` | Narrative answer from document text |

---

## Pipeline 3 — Structured Extraction

**Triggered by:** `POST /api/v1/extract` (no body needed)

This pipeline does NOT go through the agent. It calls `extractor.py` directly.

### Step-by-step

```
POST /extract
      │
      ▼
has_documents() check → 409 if empty
      │
      ▼
get_chunks() → all cached Document objects
      │
      ▼
Sort all chunks by page_number (page 1 first — always)
      │
      ▼
Build full context string:
  "===== PAGE 1 =====\n[chunk text]\n[chunk text]\n
   ===== PAGE 2 =====\n[chunk text]\n..."
  └── Trimmed to 6000 chars if longer (context window limit)
      │
      ▼
Primary strategy: llm.with_structured_output(PolicyData)
  └── LangChain sends PolicyData schema as a tool definition
  └── llama3.1 MUST return a JSON matching that schema
  └── Pydantic validates it → typed Python object
      │
      ├── SUCCESS → return PolicyData
      │
      └── FAILURE (LLM refused schema) → JSON fallback:
          └── Re-prompt with format="json" (Ollama JSON mode)
          └── Parse raw JSON → construct PolicyData manually
```

### The Pydantic Schema (PolicyData)

```python
class PolicyData(BaseModel):
    policy_number:  str        # e.g. "US151741"
    policy_holder:  str        # e.g. "School District of Hillsborough County"
    coverage_type:  str        # e.g. "Accident Only Policy"
    start_date:     str        # e.g. "August 1, 2013"
    end_date:       str        # e.g. "August 1, 2014"
    premium_amount: str        # e.g. "$3.75 (Day Care), $3.50 (Summer)"
    coverage_limit: str        # e.g. "$25,000.00"
    key_exclusions: list[str]  # e.g. ["Pre-existing conditions", "Dental care"]
```

### Real output from the app (from the screenshot)

```json
{
  "data": {
    "policy_number":   "US151741",
    "policy_holder":   "School District of Hillsborough County",
    "coverage_type":   "Accident Only Policy",
    "start_date":      "August 1, 2013",
    "end_date":        "August 1, 2014",
    "premium_amount":  "$3.75 (Day Care), $3.50 (Summer), $7.50 (Community Based Training)",
    "coverage_limit":  "$25,000.00",
    "key_exclusions":  [
      "Pre-existing conditions",
      "Injuries from war or civil commotion",
      "Self-inflicted injuries",
      "Treatment not medically necessary"
    ]
  },
  "steps": [
    "Starting structured extraction pipeline",
    "Building extraction context from all indexed chunks...",
    "Using 53 cached chunks with page metadata",
    "Context built: 6015 characters (page 1 first)",
    "Sending to llama3.1 — structured output mode (tool-calling)...",
    "[OK] Extraction complete - 8/8 fields populated"
  ]
}
```

### Why page 1 is always pinned first

The declarations page (policy number, holder, effective dates) is almost always on page 1. But the chunker splits the document into 500-token pieces — it does not know which chunk contains "Policy Number:". Semantic search for "policy number" fails because the string has no semantic relationship to its value. By sorting all chunks with page 1 first, the LLM always sees the declarations page in its context window first, making it reliable.

---

## Key Concepts Explained Simply

### RAG (Retrieval-Augmented Generation)

Instead of asking the LLM a question from memory, you first **retrieve** relevant text from your document, then feed that text + question to the LLM to **generate** an answer. The LLM only answers from the provided text. This prevents hallucination and grounds the answer in the actual document.

```
Without RAG: LLM makes up an answer from training data
With RAG:    LLM reads the actual document text, then answers
```

### Agentic RAG vs. Basic RAG

| Basic RAG | Agentic RAG |
|---|---|
| Always does the same retrieval step | Agent DECIDES which retrieval strategy to use |
| One tool: vector search | Two tools: hybrid_search OR structured_extract |
| No reasoning about how to answer | ReAct loop: Thought → Action → Observation → Answer |
| Good for general Q&A | Good when different question types need different approaches |

### Vector Embeddings

`nomic-embed-text` converts each 500-token chunk into a 768-dimensional vector (an array of 768 floats). Chunks about similar topics end up with similar vectors — their cosine distance is small. When you search, your query gets embedded the same way, and ChromaDB finds the chunks whose vectors are closest.

```
"hospitalization coverage"  → [0.21, -0.04, 0.87, ...]  (768 numbers)
"inpatient admission care"  → [0.19, -0.06, 0.85, ...]  (very similar → high cosine similarity)
"policy renewal date"       → [-0.44, 0.72, -0.12, ...]  (very different)
```

### BM25

BM25 (Best Match 25) is a keyword ranking algorithm. It scores documents based on:
- **Term Frequency (TF)**: how often the search term appears in the chunk
- **Inverse Document Frequency (IDF)**: rare terms score higher than common ones
- **Document Length normalization**: penalizes very long chunks

Great for exact matches: "policy number US151741" — no vector similarity needed.

### RRF (Reciprocal Rank Fusion)

Combines two ranked lists into one. For each result:
```
RRF_score = 1 / (rank_in_bm25 + 60) + 1 / (rank_in_chroma + 60)
```
The constant 60 prevents top-ranked results from dominating. Results appearing in both lists get double contribution. This is scale-invariant — it doesn't matter that BM25 scores are 0-100 and cosine similarity is 0-1.

### ReAct (Reason + Act)

A prompting pattern where the LLM alternates between:
- **Thought**: reasoning about what to do next
- **Action**: calling a tool with an input
- **Observation**: reading the tool's output
- Repeat until confident → **Final Answer**

```
Thought: The user is asking for the policy number, a specific field.
Action: structured_extract("policy number")
Observation: "US151741"
Thought: I have the answer directly.
Final Answer: The policy number is US151741.
```

### Pydantic Schema Enforcement

When you call `llm.with_structured_output(PolicyData)`, LangChain sends the Pydantic schema as a JSON Schema to the LLM as a tool definition. The LLM must call that "tool" with arguments matching the schema. LangChain then wraps the result in a validated `PolicyData` object. If a field is missing or the wrong type, Pydantic raises a validation error — guaranteeing the output shape.

### ChromaDB

A local vector database that:
- Persists vectors to disk (SQLite + binary files in `./chroma_db/`)
- Supports cosine similarity search
- Stores document text + metadata alongside each vector
- Can be queried with a vector to return the k nearest neighbors

---

## Actual Output Shapes

### Upload response

```json
{
  "chunks_indexed": 53,
  "metadata": {
    "filename": "policy.pdf",
    "pages": 10,
    "indexed_at": "2025-05-17T10:30:00Z"
  },
  "steps": ["...array of pipeline step strings..."]
}
```

### Ask response

```json
{
  "answer": "The policy number is US151741.",
  "tool_used": "structured_extract",
  "source_chunks": ["US151741 — School District of Hillsborough County..."],
  "page_refs": [1],
  "steps": ["...array of agent reasoning steps..."]
}
```

### Extract response

```json
{
  "data": {
    "policy_number": "US151741",
    "policy_holder": "School District of Hillsborough County",
    "coverage_type": "Accident Only Policy",
    "start_date": "August 1, 2013",
    "end_date": "August 1, 2014",
    "premium_amount": "$3.75 (Day Care), $3.50 (Summer), $7.50 (Community Based Training)",
    "coverage_limit": "$25,000.00",
    "key_exclusions": ["Pre-existing conditions", "War or civil commotion", "..."]
  },
  "steps": ["...6 pipeline steps..."]
}
```

### Logs response (polled every 1s during operations)

```json
{
  "steps": [
    "Received: policy.pdf (88.1 KB)",
    "Parsing PDF with pypdf...",
    "Extracted text from 10 pages (10 with content)"
  ]
}
```

---

## Design Decisions & Why

### Why hybrid search instead of pure vector search?

Pure vector search misses exact identifiers. `"What is the policy number?"` embeds to a vector, but the policy number `US151741` has no semantic relationship to that query — it's just a string of characters. BM25 catches it perfectly via keyword match. Combining both via RRF gives the best of both worlds: concepts from vectors, exact matches from BM25.

### Why two tools instead of one?

Search and extraction are fundamentally different operations. `hybrid_search` finds **relevant text passages** — it returns the top chunks from the document. `structured_extract` **fills a schema** — it returns typed fields with validation. Mixing them in one tool means the agent loses the ability to reason about retrieval strategy. Separate tools force explicit, observable reasoning.

### Why Ollama instead of OpenAI?

Insurance documents are sensitive enterprise data. Running everything locally means zero privacy risk, zero API cost, and zero rate limits. The LangChain integration is identical — swapping `ChatOllama` for `ChatOpenAI` is a one-line change. For a production system this exact architecture could run on-premises at AMAN with no data leaving the corporate network.

### Why temperature=0?

For document Q&A and structured extraction, you want deterministic, factual answers — not creative ones. Temperature 0 means the LLM always picks the highest-probability next token, producing consistent, grounded responses. Temperature > 0 would introduce randomness that could cause the agent to hallucinate or pick wrong fields.

### Why page 1 is always pinned in extraction?

Policy declarations (number, holder, dates) are almost always on page 1, but chunking splits them across multiple chunks. Semantic search for "policy number" fails because the string has no vector relationship to its value. By sorting all chunks with page 1 first, the LLM always sees the declarations page first in its context window — making field extraction reliable.

### Why FastAPI async with a ThreadPoolExecutor?

Ollama calls (LLM inference + embeddings) are synchronous blocking operations. FastAPI is async. If you ran Ollama calls directly in an async endpoint, they would block the entire event loop, freezing all other requests. Running them in a `ThreadPoolExecutor` keeps the event loop free while the LLM processes — other API calls (like `/logs` polling) continue to respond.

---

## Likely Interview Questions & Strong Answers

**Q: What is RAG and why is it better than fine-tuning for this use case?**

> RAG retrieves relevant text at inference time and gives it to the LLM as context. Fine-tuning bakes knowledge into model weights during training. For insurance documents, RAG is better because: (1) documents change — a fine-tuned model would need retraining every time a policy updates; (2) RAG provides traceable source citations; (3) RAG works with any document without retraining. Fine-tuning makes sense for teaching the model a new task or style, not for giving it access to new documents.

**Q: What makes this "agentic"?**

> An agentic system reasons about HOW to accomplish a task, not just what to output. In IntelliDoc, the LangChain ReAct agent observes the user's question, thinks about what type of question it is, chooses between two tools based on that reasoning, executes the tool, reads the result, and decides whether it has enough to answer. A non-agentic system would just run vector search on every question regardless.

**Q: What is the difference between the two retrieval tools?**

> `hybrid_search` is for open-ended questions — it returns the most relevant text passages using BM25 + vector search merged via RRF, then the LLM generates an answer from those passages. `structured_extract` is for specific field lookups — it reads all document chunks and fills a typed Pydantic schema, guaranteeing the output has exactly the right fields in the right format. The agent picks the right tool based on whether the question is asking for a concept or a specific fact.

**Q: How does hybrid search work?**

> Two searches run in parallel: BM25 keyword search scores chunks by term frequency-inverse document frequency (good for exact matches like policy numbers), and ChromaDB vector search finds semantically similar chunks by cosine distance of embeddings (good for concepts). Both return ranked lists. Reciprocal Rank Fusion merges them by combining rank-based scores (1 / rank + 60) — scale-invariant because it uses rank position, not raw scores. The top-4 chunks by combined RRF score are returned to the agent.

**Q: Why does the extraction pipeline put page 1 first?**

> The declarations page contains the policy number, holder name, and effective dates — critical fields that appear as exact strings like "Policy Number: US151741". These have no semantic meaning a vector search can exploit. By sorting chunks so page 1 always comes first in the context, the LLM reliably sees these identifiers before any other content, making extraction accurate regardless of how chunking splits the page.

**Q: How do you prevent hallucination?**

> Three mechanisms: (1) The system prompt explicitly instructs the LLM to only answer from the provided document and to say "not found" if the answer isn't there. (2) Temperature is set to 0 for deterministic output. (3) For structured extraction, Pydantic schema enforcement means the LLM must return validated typed fields — it cannot invent fields or change their type. Source chunk citations in every answer also let the user verify the answer against the original text.

**Q: How would you scale this to production at AMAN?**

> Replace ChromaDB with Snowflake Cortex Search or Pinecone for enterprise-scale retrieval across millions of policies. Replace Ollama with a cloud LLM endpoint (OpenAI GPT-4o or Anthropic Claude) — the LangChain abstraction makes this a one-line change. Add LangSmith for full observability of every agent reasoning step. Wrap with JWT authentication for multi-user document ownership. Add a Neo4j knowledge graph to link policies → claims → customers for multi-hop reasoning ("show me all customers whose policy covers X but who have never filed a claim"). Add streaming responses via Server-Sent Events for real-time token output.

**Q: What is Reciprocal Rank Fusion?**

> RRF is a rank fusion algorithm that combines multiple ranked lists into one without needing to normalize scores. For each document in each list, its RRF contribution is 1 / (rank + k) where k=60 is a constant that prevents top ranks from having too much weight. You sum these contributions across all lists. A document that appears at rank 1 in BM25 and rank 3 in vector search will score higher than one that appears at rank 1 in only one list. The constant k=60 was empirically found to work well across many retrieval benchmarks.

**Q: Why did you use LangGraph's create_react_agent instead of LangChain's older AgentExecutor?**

> LangGraph is the modern replacement for AgentExecutor. It models the agent as a stateful graph (nodes = think/act, edges = conditions), which gives you fine-grained control over the reasoning loop, first-class support for streaming, built-in checkpointing, and cleaner tool message handling. The `create_react_agent` function from `langgraph.prebuilt` sets up the ReAct loop as a compiled graph — the same `agent.invoke({"messages": [...]})` interface works, but the internals are much more observable and extensible.

---

## What You'd Change in Production

| Current (Demo) | Production |
|---|---|
| Ollama (local llama3.1) | OpenAI GPT-4o or Anthropic Claude — swap one line in agent.py |
| ChromaDB (local disk) | Snowflake Cortex Search or Pinecone — enterprise-scale, multi-tenant |
| In-memory BM25 (lost on restart) | Elasticsearch or OpenSearch — persistent keyword index |
| No auth | JWT tokens — user sessions, document ownership |
| Single document at a time | Multi-document index — compare policy versions, portfolio view |
| Polling for logs (/logs endpoint) | Server-Sent Events (SSE) — real-time streaming without polling |
| No observability | LangSmith — trace every agent reasoning step, measure latency |
| No knowledge graph | Neo4j — link policies → claims → customers for multi-hop queries |

---

*IntelliDoc — Built with LangGraph · LangChain · FastAPI · React · ChromaDB · Ollama*
