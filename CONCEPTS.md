# IntelliDoc — Concepts Explained

> You understand the pipelines. This file explains the **WHY** and **HOW** behind every tool and concept used in the app — written simply, with no assumed knowledge.

---

## Table of Contents

1. [What is a LangGraph ReAct Agent?](#1-what-is-a-langgraph-react-agent)
2. [What is a Pydantic Schema?](#2-what-is-a-pydantic-schema)
3. [What is Cosine Similarity?](#3-what-is-cosine-similarity)
4. [What is BM25 (rank-bm25)?](#4-what-is-bm25-rank-bm25)
5. [What is Hybrid Search — and why only two options?](#5-what-is-hybrid-search--and-why-only-two-options)
6. [What is RRF (Reciprocal Rank Fusion)?](#6-what-is-rrf-reciprocal-rank-fusion)
7. [What is OCR — and do we use it?](#7-what-is-ocr--and-do-we-use-it)
8. [How does structured_extract work — and is it free?](#8-how-does-structured_extract-work--and-is-it-free)
9. [Why these specific tools and not others?](#9-why-these-specific-tools-and-not-others)

---

## 1. What is a LangGraph ReAct Agent?

### Start with the problem

A normal AI chatbot receives a question and immediately generates an answer from memory. It has no ability to go look things up, run calculations, or decide between strategies. It just outputs text.

An **agent** is different. It can:
- **Use tools** (functions you give it)
- **Decide which tool to use** based on the question
- **Look at the result** and decide what to do next
- **Keep reasoning** until it has a complete answer

### What is ReAct?

ReAct is a pattern (not a library — just an idea) for how an agent thinks. The name stands for **Reason + Act**.

The agent loops through these steps:

```
Thought:      "What kind of question is this? What do I need to do?"
Action:       Call a tool with an input
Observation:  Read what the tool returned
Thought:      "Do I have enough to answer now? Or do I need another step?"
...repeat until...
Final Answer: Generate the response
```

**Real example in IntelliDoc:**

User asks: *"Can I settle this contract early?"*

```
Thought:   This is a general question about a contract clause.
           I need to find the relevant text. I'll use hybrid_search.

Action:    hybrid_search("early settlement early payment payoff")

Observation: "Page 3: The customer may settle the remaining balance in full
             at any time. An early settlement fee of 1% applies if within
             the first 12 months..."

Thought:   I found the answer. I have enough to respond.

Final Answer: "Yes, you can settle early. A 1% fee applies only in the
              first 12 months. After that, there is no fee."
```

Without ReAct, a chatbot would just try to answer from training data and might make something up. With ReAct, the answer is always grounded in the actual document text.

### What is LangGraph?

LangGraph is a Python library that implements the ReAct loop as a **graph** (nodes and edges). Think of it as:

- **Node 1:** The LLM thinks and decides what to do
- **Node 2:** A tool is called
- **Edge:** After the tool result, go back to Node 1 to think again
- **Exit edge:** When the LLM decides it has a final answer, the loop stops

```
[Start] → [LLM thinks] → [calls tool] → [LLM reads result] → [LLM thinks again]
                                                                       │
                                              ← still needs more info ←┘
                                              → has final answer → [Output]
```

`create_react_agent` from `langgraph.prebuilt` builds this graph automatically. You give it:
- A model (llama3.1)
- A list of tools (hybrid_search, structured_extract)
- A system prompt (the agent's instructions)

And it returns a compiled graph you can call with `.invoke()`.

### Why LangGraph and not the older LangChain AgentExecutor?

LangChain's old `AgentExecutor` did the same thing but was harder to debug and extend. LangGraph replaced it with a proper graph model that:
- Shows exactly what step the agent is on
- Supports streaming output (token by token)
- Supports checkpointing (saving state mid-reasoning)
- Is easier to customize

---

## 2. What is a Pydantic Schema?

### The problem it solves

When you ask an LLM to return structured data (like a JSON with specific fields), it might:
- Return the wrong field names ("contract_no" instead of "contract_number")
- Return a number as a string or a string as a list
- Include extra fields you didn't ask for
- Return invalid JSON entirely

You cannot trust a raw LLM output to be consistently shaped.

**Pydantic** is a Python library that enforces data types and structure. You define a class where each field has a name and a type. Pydantic will:
- Validate that the data has all required fields
- Validate that every field is the correct type
- Raise a clear error if anything is wrong

### The schema used in IntelliDoc

```python
from pydantic import BaseModel, Field

class ContractData(BaseModel):
    contract_number:     str        # must be a string
    customer_name:       str        # must be a string
    product_financed:    str        # must be a string
    total_amount:        str        # must be a string
    monthly_installment: str        # must be a string
    duration_months:     str        # must be a string
    profit_rate:         str        # must be a string
    key_conditions:      list[str]  # must be a list of strings
```

### How it connects to the LLM

When you call `llm.with_structured_output(ContractData)`, LangChain does something clever:
1. It converts the Pydantic class into a **JSON Schema** (a standard format describing data shapes)
2. It sends that schema to the LLM as a "tool definition"
3. The LLM is forced to call that "tool" with arguments that match the schema
4. LangChain receives the arguments and wraps them in a validated `ContractData` object

The LLM never has a chance to return a free-form string — it must call the schema tool.

### Simple analogy

Pydantic is like a customs form at an airport. The form has fixed fields (name, passport number, destination). You cannot submit it without filling every required box. The shape of the output is guaranteed.

---

## 3. What is Cosine Similarity?

### Start with vectors

When `nomic-embed-text` processes a chunk of text, it converts it into a list of 768 numbers (called a vector or embedding). These numbers capture the **meaning** of the text.

```
"monthly repayment amount"  →  [0.21, -0.04, 0.87, 0.33, ...]  (768 numbers)
"installment per month"     →  [0.19, -0.06, 0.85, 0.31, ...]  (very similar)
"contract cancellation"     →  [-0.44, 0.72, -0.12, 0.09, ...]  (very different)
```

Texts with similar meanings end up with similar vectors. The model was trained on massive amounts of text to learn this relationship.

### What is cosine similarity?

Cosine similarity measures **how similar two vectors are** by looking at the angle between them — not their length.

```
Two vectors pointing in almost the same direction → small angle → similarity close to 1.0
Two vectors pointing in opposite directions       → large angle → similarity close to -1.0
Two vectors perpendicular (unrelated)             → 90° angle  → similarity = 0.0
```

The formula is:
```
similarity = (A · B) / (|A| × |B|)
```
Where `A · B` is the dot product of the two vectors and `|A|`, `|B|` are their lengths.

You don't need to memorize the formula. The key intuition is:

> **Similar meaning = vectors point in the same direction = high cosine similarity**

### How it's used in IntelliDoc

When you type a query:
1. The query is embedded into a 768-dim vector using `nomic-embed-text`
2. ChromaDB compares that vector to every stored chunk vector using cosine similarity
3. The top-k chunks with the highest similarity scores are returned

This is why vector search finds conceptually related text even when you use different words — it's comparing meaning, not matching characters.

---

## 4. What is BM25 (rank-bm25)?

### The simple version

BM25 is a **keyword scoring algorithm**. It answers: *"How relevant is this chunk of text to this query?"* — based purely on the words present.

It scores each chunk by counting:
- How many times the query words appear in the chunk (**Term Frequency, TF**)
- How rare those words are across all chunks (**Inverse Document Frequency, IDF**)
- The length of the chunk (penalizes very long chunks)

### Why does rarity matter?

If someone asks *"What is the contract number?"*, the word "contract" appears in almost every chunk — it's not helpful for finding the right one. But the word "number" combined with a specific value like `AMAN-FIN-2025-CF-047832` is rare — that chunk is almost certainly the right one.

IDF gives rare words more weight. Common words like "the", "is", "a" get almost zero weight.

### Why use BM25 at all?

**Vector search fails at exact identifiers.**

The contract number `AMAN-FIN-2025-CF-047832` is just a random string of characters. When you embed the query "what is the contract number?", the resulting vector has no semantic relationship to a chunk containing `AMAN-FIN-2025-CF-047832`. The vector model was never trained to know that this string IS the contract number.

BM25 has no such problem. If "AMAN-FIN-2025-CF-047832" appears in the query AND in the chunk, it scores perfectly. The same applies to amounts (EGP 25,000), dates (March 1, 2025), and names.

### What is rank-bm25?

`rank-bm25` is simply a Python library that implements the BM25 algorithm. It's:
- Free and open source
- Runs entirely in memory
- No server needed — just import and use

In IntelliDoc it's rebuilt in memory every time a new document is uploaded.

---

## 5. What is Hybrid Search — and why only two options?

### Why two search methods?

No single search method is perfect for all question types:

| Question type | Best method | Why |
|---|---|---|
| "What is the contract number?" | BM25 | Exact identifier — no semantic meaning |
| "What does the contract say about late payments?" | Vector | Conceptual match |
| "Who is the customer?" | BM25 | Exact name lookup |
| "Can I cancel this contract?" | Vector | "Cancel" might appear as "terminate", "dissolve", "rescind" |

The solution: **run both and combine the results.** This is called hybrid search.

### Why only these two?

Two search paradigms cover the entire space of retrieval needs:

1. **Exact/keyword match (BM25):** Finds what you asked for literally — great for numbers, names, identifiers, legal terms
2. **Semantic/meaning match (vector):** Finds what you meant — great for concepts, paraphrases, implied topics

There is no third paradigm that does something fundamentally different. More advanced systems (like re-ranking with a cross-encoder) are a quality enhancement on top of these two, not a new category.

Adding more methods beyond these two would add complexity with diminishing returns. For a contract document, these two together cover every question type a user is likely to ask.

### How hybrid search works in IntelliDoc

```
Query arrives
      │
      ├──► BM25 search
      │    Tokenize query + all chunks
      │    Score each chunk by TF-IDF
      │    Return: [chunk_3 rank1, chunk_7 rank2, chunk_1 rank3, chunk_9 rank4]
      │
      ├──► ChromaDB vector search
      │    Embed query → cosine similarity with all chunk vectors
      │    Return: [chunk_7 rank1, chunk_2 rank2, chunk_3 rank3, chunk_5 rank4]
      │
      └──► RRF merge → [chunk_3, chunk_7, chunk_2, chunk_1] → top 4 → Agent
```

---

## 6. What is RRF (Reciprocal Rank Fusion)?

### The problem with combining scores directly

BM25 scores might be numbers like 4.2, 1.8, 0.3.
Cosine similarity scores are always between 0 and 1 (like 0.92, 0.87, 0.71).

You cannot average these directly — they're on completely different scales. A BM25 score of 4.2 doesn't mean the same thing as a cosine similarity of 4.2.

### What RRF does instead

RRF ignores the raw scores completely. It only uses the **rank position** (1st, 2nd, 3rd, etc.).

The formula for each document's RRF score:
```
RRF_score = 1/(rank_in_bm25 + 60) + 1/(rank_in_vector_search + 60)
```

The number 60 is a constant that prevents the top rank from having too much influence.

### A worked example

Say we have 5 chunks and two search results:

| Chunk | BM25 rank | Vector rank | RRF score |
|---|---|---|---|
| Chunk A | 1 | 3 | 1/(1+60) + 1/(3+60) = 0.0164 + 0.0159 = **0.0323** |
| Chunk B | 3 | 1 | 1/(3+60) + 1/(1+60) = 0.0159 + 0.0164 = **0.0323** |
| Chunk C | 2 | 5 | 1/(2+60) + 1/(5+60) = 0.0161 + 0.0154 = **0.0315** |
| Chunk D | 4 | 2 | 1/(4+60) + 1/(2+60) = 0.0156 + 0.0161 = **0.0317** |
| Chunk E | 5 | 4 | 1/(5+60) + 1/(4+60) = 0.0154 + 0.0156 = **0.0310** |

Final ranking: A = B > D > C > E

**Key insight:** A chunk that appears in **both** lists gets contributions from both, giving it a higher combined score than something that only appeared in one. This rewards chunks that are both keyword-relevant AND semantically relevant.

### Why 60?

The constant 60 was found empirically in academic research to produce the best results across many retrieval benchmarks. It smooths out the effect of position — the difference between rank 1 and rank 2 is not as dramatic as the difference between rank 1 and rank 61.

---

## 7. What is OCR — and do we use it?

### What OCR is

OCR stands for **Optical Character Recognition**. It is the process of converting an **image** of text into **actual searchable text**.

When you take a photo of a document or scan it as an image, the computer sees pixels — it does not see letters. OCR analyzes the shapes of those pixels and figures out which letter or number each shape represents.

```
[Image of the word "CONTRACT"]  →  OCR  →  "CONTRACT" (actual text string)
         (just pixels)
```

Common OCR libraries: Tesseract (free), Google Vision API, Adobe Acrobat.

### Do we use OCR in IntelliDoc?

**No — and intentionally so.**

IntelliDoc uses `pypdf` to extract text from PDFs. This only works on **digital PDFs** — PDFs that were created directly by software (Word, a contract management system, a printer driver). These PDFs contain actual text data embedded in the file.

If someone uploads a **scanned PDF** (a physical paper that was photocopied and saved as a PDF), `pypdf` would extract no text, and the ingestion would fail with zero chunks.

### Why not add OCR?

For this demo, the assumption is that Aman's contracts are **digitally generated** (they come from a contract management system, not a photocopier). This is true for almost all modern consumer finance contracts.

Adding OCR would require:
- A library like `pytesseract` or `unstructured[pdf]`
- Converting each PDF page to an image first
- Running OCR on each image (slow, ~2-5 seconds per page)
- Post-processing the text (OCR introduces spacing and character errors)

**In production**, you would add OCR as a fallback: try `pypdf` first, and if it returns no text, fall back to OCR. This handles both digital and scanned documents.

---

## 8. How does structured_extract work — and is it free?

### What it is

`structured_extract` is one of the two tools the ReAct agent can call. It is a Python function wrapped with `@tool` (a LangChain decorator that makes it callable by the agent).

When the agent calls it, it:
1. Loads all indexed chunks from ChromaDB
2. Sorts them by page number (page 1 first)
3. Builds a single text block from all chunks (up to 6,000 characters)
4. Sends that text + a system prompt to `llama3.1`
5. Forces `llama3.1` to return a `ContractData` object (via Pydantic)
6. Looks up the specific field the agent requested and returns it

### Is it free?

**Yes — completely free.**

The LLM doing the extraction is `llama3.1:latest`, running locally via **Ollama**. Ollama is a free, open-source tool that runs large language models on your own machine. There is no API key, no account, no usage fees.

The embeddings model (`nomic-embed-text`) is also free and runs locally via Ollama.

The only cost is electricity and the time it takes your CPU/GPU to run inference (typically 10-30 seconds per extraction on a normal laptop).

**Comparison if you used a cloud API:**
- OpenAI GPT-4o: ~$0.005 per extraction (very cheap but requires API key + sends data to OpenAI)
- Anthropic Claude: similar cost
- Ollama: $0.00 always, data never leaves your machine

### The two fallback strategies

The extractor tries two methods in order:

**Strategy 1 — Tool calling (preferred):**
```python
structured_llm = llm.with_structured_output(ContractData)
result = (prompt | structured_llm).invoke({"context": context})
```
LangChain converts `ContractData` to a JSON Schema and tells the LLM "you must call this tool". The LLM is forced to return matching JSON. Pydantic validates it.

**Strategy 2 — Raw JSON mode (fallback):**
```python
json_llm = ChatOllama(model="llama3.1:latest", format="json")
response = (json_prompt | json_llm).invoke({"context": context})
raw = json.loads(response.content)
result = ContractData(**raw)
```
If tool-calling fails (some local models don't support it reliably), Ollama is switched to `format="json"` mode, which forces the output to be valid JSON. Then the JSON is parsed manually and fed into the `ContractData` constructor.

### What tool does it internally call?

`structured_extract` does not call another tool. It directly:
1. Calls `get_retriever(k=10)` → retrieves from ChromaDB
2. Calls `get_chunks()` → gets cached chunk list
3. Calls `extract_policy_data(retriever, all_chunks=chunks)` → runs the LLM extraction
4. Returns the specific field from the resulting `ContractData` object

---

## 9. Why these specific tools and not others?

### Why Ollama + llama3.1?

| Option | Cost | Privacy | Speed | Setup complexity |
|---|---|---|---|---|
| Ollama + llama3.1 | Free | 100% local | Medium (10-30s) | Install Ollama, pull model |
| OpenAI GPT-4o | ~$0.005/call | Data sent to OpenAI | Fast (2-5s) | API key required |
| Anthropic Claude | ~$0.003/call | Data sent to Anthropic | Fast (2-5s) | API key required |
| Groq (free tier) | Free | Data sent to Groq | Very fast (1-2s) | API key required |

For insurance/finance documents with customer PII (national ID, bank account numbers), keeping everything local is the right default. The LangChain abstraction means switching to GPT-4o later is a one-line code change.

### Why ChromaDB and not Pinecone or Weaviate?

| Option | Cost | Where data lives | Setup |
|---|---|---|---|
| ChromaDB | Free | Local disk | No account, no server |
| Pinecone | Free tier / paid | Pinecone's cloud | API key, account |
| Weaviate | Free (self-hosted) | Local or cloud | Docker required |
| pgvector (Postgres) | Free | Local Postgres | Postgres setup |

ChromaDB is the only option that requires zero infrastructure and zero accounts while still being a real production-grade vector database. The LangChain integration is identical to Pinecone — swapping is one import change.

### Why FastAPI and not Flask or Django?

| Option | Async support | Auto docs | Performance |
|---|---|---|---|
| FastAPI | Native async | Yes (Swagger at /docs) | High |
| Flask | No (needs extensions) | No | Medium |
| Django | Partial | No | Medium |

FastAPI is specifically designed for building APIs with async support. Since Ollama calls are blocking, we run them in a `ThreadPoolExecutor` — FastAPI handles this cleanly. The auto-generated Swagger UI at `/docs` is a bonus that makes the API instantly demonstrable.

### Why React + Vite and not plain HTML or Next.js?

This is a single-page app with no server-side rendering needed. Vite gives instant hot-module replacement during development. React handles the stateful UI (live log steps, loading states, tab switching) cleanly. Next.js would be over-engineered for a local demo with one page.

### Why pypdf and not unstructured or pdfplumber?

| Option | Works on digital PDFs | Works on scanned PDFs | Setup complexity |
|---|---|---|---|
| pypdf | Yes | No | `pip install pypdf` |
| unstructured | Yes | Yes (via OCR) | Many system deps needed |
| pdfplumber | Yes | No | `pip install pdfplumber` |
| pdfminer | Yes | No | `pip install pdfminer.six` |

`pypdf` is the lightest option. `unstructured` is powerful but requires system-level dependencies (poppler, tesseract, libmagic) that are painful to install on Windows. For digital contracts, pypdf does the job perfectly.

---

## Quick Reference Glossary

| Term | One-line definition |
|---|---|
| **LLM** | Large Language Model — an AI trained on text that can generate and reason about text |
| **Embedding** | Converting text into a vector (list of numbers) that captures its meaning |
| **Vector** | An ordered list of numbers representing a point in high-dimensional space |
| **Cosine similarity** | A measure of how similar two vectors are, based on the angle between them (0 = unrelated, 1 = identical meaning) |
| **ChromaDB** | A local database that stores vectors and lets you search by similarity |
| **BM25** | A keyword ranking algorithm that scores text by word frequency and rarity |
| **Hybrid search** | Combining keyword search (BM25) and semantic search (vectors) for better results |
| **RRF** | A method for merging two ranked lists using position, not raw scores |
| **RAG** | Retrieval-Augmented Generation — find relevant text, then ask the LLM to answer from it |
| **ReAct** | A pattern where an LLM alternates between reasoning and calling tools |
| **LangGraph** | A Python library that implements the ReAct loop as a stateful graph |
| **LangChain** | A Python framework with tools for prompts, chains, tools, and LLM integrations |
| **Pydantic** | A Python library that enforces data types and structure — guarantees output shape |
| **Ollama** | A free local runtime for running LLMs on your own machine |
| **llama3.1** | An open-source LLM made by Meta, running locally via Ollama |
| **nomic-embed-text** | A free embedding model running locally via Ollama |
| **OCR** | Optical Character Recognition — reading text from images (not used in this app) |
| **Chunk** | A 500-token segment of a document, the unit of retrieval |
| **Tool (agent)** | A Python function the agent can call during its reasoning loop |
| **FastAPI** | A modern Python web framework for building APIs with async support |

---

*IntelliDoc — Aman Consumer Finance Document Intelligence Agent*
