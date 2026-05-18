# IntelliDoc — Code Walkthrough

This file explains the entire app by following two user actions:
1. **Uploading a PDF** — what happens step by step
2. **Asking a question** — how the agent picks a tool and answers

---

## The folder structure — what is "core" vs "tools" vs "api"?

```
backend/
├── main.py              ← starts the FastAPI server
├── api/
│   └── routes.py        ← HTTP endpoints: /upload, /ask, /extract, /store
├── core/                ← the "brain" — pure Python logic, no HTTP
│   ├── parser.py        ← reads PDF, splits into chunks
│   ├── vectorstore.py   ← stores and retrieves chunks (ChromaDB + cache)
│   ├── extractor.py     ← structured field extraction (Pydantic schema)
│   └── agent.py         ← LangGraph ReAct agent, decides which tool to use
└── tools/               ← wrappers that the agent can call
    ├── search_tool.py   ← hybrid_search tool (BM25 + vector)
    └── extract_tool.py  ← structured_extract tool (field lookup)
```

**Core** = reusable business logic. No HTTP, no agent — just plain functions.
**Tools** = thin wrappers around core functions that are decorated with `@tool`
so the LangGraph agent can call them.
**API** = the HTTP layer. Calls core functions and returns JSON to the frontend.

---

## PART 1 — Upload Pipeline

When you click "Upload" in the UI, this chain fires:

```
Browser  →  POST /api/v1/upload  →  parser.py  →  vectorstore.py
```

### Step 1 — api/routes.py receives the file

```python
# FILE: backend/api/routes.py  (line 41)

@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    content = await file.read()                      # read raw bytes
    file_hash = hashlib.md5(content).hexdigest()     # MD5 fingerprint

    # DEDUPLICATION: skip if same file already indexed
    if last_uploaded_hash == file_hash and has_documents():
        return {"chunks_indexed": ..., "steps": [...]}

    # Write to a temp file so pypdf can open it
    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        tmp.write(content)
        chunks = await _run(lambda: parse_and_chunk(tmp_path, steps=...))

    await _run(lambda: ingest_documents(chunks, steps=...))
```

Key point: `await _run(...)` runs the slow functions (pypdf, Ollama embeddings)
in a thread pool so FastAPI does not freeze.

---

### Step 2 — core/parser.py reads and splits the PDF

```python
# FILE: backend/core/parser.py  (line 7)

def parse_and_chunk(file_path: str) -> list[Document]:
    reader = PdfReader(file_path)

    # Read each page → one Document per page
    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text()   # digital PDF only, no OCR
        raw_docs.append(Document(
            page_content=text,
            metadata={"page_number": page_num, "source": filename}
        ))

    # Split long pages into smaller chunks
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(raw_docs)
    return chunks
```

**Why split into chunks?**
A 21-page PDF has too much text to fit in one LLM prompt.
Splitting into 500-character chunks means you can find the exact
relevant piece later instead of sending the whole document every time.

**Why overlap=50?**
If a sentence is cut at the boundary of chunk 3 / chunk 4,
the 50-character overlap makes sure neither chunk loses the context.

**Why pypdf and not OCR?**
pypdf reads the text layer that is already inside a digital PDF.
OCR (like Tesseract) is only needed for scanned images. This policy PDF
is digital, so pypdf is faster, free, and accurate.

After this step you have something like:

```
chunks = [
    Document(page_content="UNITED STATES FIRE INSURANCE...", metadata={"page_number": 1}),
    Document(page_content="This Policy is issued in the state...", metadata={"page_number": 1}),
    Document(page_content="BLANKET ACCIDENT BENEFITS SCHEDULE...", metadata={"page_number": 2}),
    ...  # ~30-80 chunks depending on PDF size
]
```

---

### Step 3 — core/vectorstore.py embeds and stores the chunks

```python
# FILE: backend/core/vectorstore.py  (line 17)

def ingest_documents(documents: list[Document]) -> None:
    global _chunks
    _chunks = list(documents)   # cache in memory for BM25 later

    # Convert each chunk's text into a 768-number vector using Ollama
    Chroma.from_documents(
        documents=documents,
        embedding=OllamaEmbeddings(model="nomic-embed-text:latest"),
        collection_name="insurance_docs",
        persist_directory="./chroma_db",   # saved to disk
    )
```

**What is an embedding / vector?**
`nomic-embed-text` reads a chunk like "Policy Number: US151741"
and converts it into a list of 768 numbers, e.g. [0.12, -0.34, 0.91, ...].
Similar meaning → similar numbers. This is how semantic search works.

**What is ChromaDB?**
A local database that stores those 768-number vectors on disk.
When you search later, it finds the vectors closest to your query vector.
No cloud, no API key, runs entirely on your machine.

**What is the in-memory `_chunks` cache?**
ChromaDB stores vectors but not in a Python list.
BM25 (keyword search) needs a plain Python list.
So we keep `_chunks` in memory as a fast shortcut.

After upload, the data lives in two places:
- `./chroma_db/` — vectors on disk (survives restart)
- `_chunks` in memory — plain text (rebuilt from ChromaDB on restart)

---

## PART 2 — The Two Tools

When you ask a question, the agent must choose between two tools.

### Tool 1 — hybrid_search  (for open questions)

```python
# FILE: backend/tools/search_tool.py  (line 6)

@tool
def hybrid_search(query: str) -> str:
    """Use this when the user asks an open-ended question about the document."""

    chunks = get_chunks()   # all chunks in memory

    # --- BM25: keyword search ---
    # Tokenize every chunk into words, score them against the query words
    tokenized = [doc.page_content.lower().split() for doc in chunks]
    bm25 = BM25Okapi(tokenized)
    bm25_scores = bm25.get_scores(query.lower().split())
    bm25_ranked = sorted(range(len(chunks)), key=lambda i: bm25_scores[i], reverse=True)[:4]
    # Result: indices of the 4 chunks with the most keyword overlap

    # --- ChromaDB: vector / semantic search ---
    retriever = get_retriever(k=4)
    vector_docs = retriever.invoke(query)
    # Result: 4 chunks whose meaning is closest to the query meaning

    # --- RRF: merge the two ranked lists ---
    # Each chunk gets a score = 1/(rank + 60) from each list
    # A chunk ranked #1 in both lists gets the highest combined score
    rrf_scores = {}
    for rank, idx in enumerate(bm25_ranked):
        rrf_scores[idx] = rrf_scores.get(idx, 0) + 1.0 / (rank + 60)
    for rank, idx in enumerate(vector_ranked):
        rrf_scores[idx] = rrf_scores.get(idx, 0) + 1.0 / (rank + 60)

    top_chunks = [chunks[i] for i in sorted(rrf_scores, key=..., reverse=True)[:4]]

    # Return formatted text for the agent to read
    return "Page 1: UNITED STATES FIRE INSURANCE...\n---\nPage 2: ..."
```

**Why two search methods and not one?**

| | BM25 keyword | ChromaDB vector |
|---|---|---|
| Good at | Exact terms: "US151741", "deductible" | Synonyms: "what is excluded" = "not covered" |
| Bad at | Synonyms, paraphrasing | Rare exact strings like policy numbers |
| Speed | Fast (in-memory) | Slower (disk read) |

By merging both, you get the best of both worlds.

**What is RRF (Reciprocal Rank Fusion)?**
Instead of averaging scores (which breaks when BM25 uses raw counts
and ChromaDB uses cosine similarity — completely different scales),
RRF uses only the **rank position**: 1st place, 2nd place, etc.
Formula: `score = 1 / (rank + 60)`. The constant 60 prevents
the top rank from dominating too much.

---

### Tool 2 — structured_extract  (for specific field lookups)

```python
# FILE: backend/tools/extract_tool.py  (line 6)

@tool
def structured_extract(field_name: str) -> str:
    """Use this when the user asks for a specific field: policy number, holder, dates, etc."""

    policy = extract_policy_data(retriever)   # calls extractor.py

    # Map natural language to the right field
    field_map = {
        "policy number": policy.policy_number,   # "US151741"
        "number":        policy.policy_number,
        "policy no":     policy.policy_number,
        "holder":        policy.policy_holder,   # "School District..."
        "expiry":        policy.end_date,        # "August 1, 2014"
        "exclusions":    ", ".join(policy.key_exclusions),
        ...
    }

    for key, value in field_map.items():
        if key in normalized or normalized in key:
            return value
```

**What does extract_policy_data() do internally?**

```python
# FILE: backend/core/extractor.py  (line 49)

def extract_policy_data(retriever) -> PolicyData:
    # 1. Get all chunks with page metadata
    context = build_full_context(all_chunks)

    # 2. Send to llama3.1 with a strict Pydantic schema
    structured_llm = llm.with_structured_output(PolicyData)
    result = (prompt | structured_llm).invoke({"context": context})
    # llama3.1 MUST return JSON matching PolicyData — no free text allowed

    return result  # PolicyData object with all 8 fields populated
```

**What is Pydantic?**
Pydantic is a Python library that defines a schema with types.
When you use `llm.with_structured_output(PolicyData)`, LangChain
tells the LLM: "you must return JSON with exactly these keys and types."
If the LLM tries to return something else, Pydantic raises an error.

```python
class PolicyData(BaseModel):
    policy_number: str        # must be a string
    key_exclusions: list[str] # must be a list of strings
    ...
```

This is why structured_extract is reliable for field lookups —
the output format is guaranteed.

---

### The difference between the two tools

| | hybrid_search | structured_extract |
|---|---|---|
| **Question type** | Open-ended | Specific field |
| **Example query** | "What does this policy say about accidents?" | "What is the policy number?" |
| **Output** | Raw text chunks the LLM reads to form an answer | A single typed value from a guaranteed schema |
| **LLM role** | Read chunks and write a natural answer | Fill a JSON form |
| **Use when** | You need explanation or context | You need an exact value |

---

## PART 3 — How the LangGraph ReAct Agent Works

```python
# FILE: backend/core/agent.py  (line 34)

llm = ChatOllama(model="llama3.1:latest", temperature=0)
tools = [hybrid_search, structured_extract]

agent = create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)

result = agent.invoke({"messages": [HumanMessage(content=query)]})
```

### What is a ReAct agent?

ReAct = **Re**ason + **Act**. The agent runs a loop:

```
LOOP:
  1. THINK  — LLM reads the question and decides what to do
  2. ACT    — LLM calls one tool with arguments
  3. OBSERVE — LLM reads the tool's output
  4. THINK  — is the answer complete? if yes, stop. if no, go back to step 2.
```

For the question "what is the policy number?":

```
THINK:  "The user wants a specific field. I should use structured_extract."
ACT:    structured_extract(field_name="policy number")
OBSERVE: "US151741"
THINK:  "I have the answer. I can stop."
ANSWER: "The policy number is US151741."
```

For the question "what does this policy say about sickness?":

```
THINK:  "This is an open question about content. I should use hybrid_search."
ACT:    hybrid_search(query="sickness coverage")
OBSERVE: "Page 1: BENEFITS ARE NOT PAYABLE FOR LOSS DUE TO SICKNESS..."
THINK:  "I found the relevant section. I can stop."
ANSWER: "According to Page 1, benefits are not payable for loss due to sickness..."
```

### What is create_react_agent?

`create_react_agent` is a function from the `langgraph` library.
It builds a state machine (a graph) with these nodes:

```
START → [agent node] → [tool node] → [agent node] → END
                  ↑__________________________|
                  (loop until agent says stop)
```

- **agent node**: runs the LLM to decide what to do next
- **tool node**: runs whichever tool the LLM chose
- The loop continues until the LLM produces a final answer (no tool call)

### How to build it yourself (minimal version)

```python
from langgraph.prebuilt import create_react_agent
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage

# 1. Define your LLM
llm = ChatOllama(model="llama3.1:latest", temperature=0)

# 2. Define tools with @tool decorator
@tool
def my_tool(input: str) -> str:
    """Describe when to use this tool so the LLM knows to pick it."""
    return "result from tool"

# 3. Create the agent (just one line)
agent = create_react_agent(llm, [my_tool], prompt="You are a helpful assistant.")

# 4. Run it
result = agent.invoke({"messages": [HumanMessage(content="your question")]})
print(result["messages"][-1].content)
```

The `@tool` decorator does two things:
- Wraps your function so LangGraph can call it
- Uses the docstring as the description the LLM reads to decide whether to use it

**The docstring is critical.** The LLM reads it to decide which tool to pick.
A vague docstring = wrong tool choice = wrong answer.

---

## Full flow diagram

```
User uploads PDF
       │
       ▼
routes.py /upload
       │
       ├─► parser.py          → reads PDF pages → splits into ~50 chunks
       │
       └─► vectorstore.py     → embeds with nomic-embed-text → saves to ChromaDB
                                 also caches chunks in _chunks[] for BM25

User asks "what is the policy number?"
       │
       ▼
routes.py /ask
       │
       └─► agent.py           → create_react_agent runs the ReAct loop
                  │
                  ├─ THINK: "specific field → use structured_extract"
                  │
                  └─► extract_tool.py → extract_policy_data()
                                │
                                └─► extractor.py → sends all chunks to llama3.1
                                                   with Pydantic schema
                                                   → returns PolicyData object
                                                   → returns "US151741"

User asks "what does it say about sickness?"
       │
       ▼
routes.py /ask
       │
       └─► agent.py           → create_react_agent runs the ReAct loop
                  │
                  ├─ THINK: "open question → use hybrid_search"
                  │
                  └─► search_tool.py
                          │
                          ├─ BM25 keyword search over _chunks[]
                          ├─ ChromaDB vector search via get_retriever()
                          └─ RRF merge → top 4 chunks → returned as text
                                                         LLM reads and answers
```

---

## Files to open during the interview demo

| What you want to show | File to open |
|---|---|
| How PDF is parsed | [core/parser.py](backend/core/parser.py) |
| How vectors are stored | [core/vectorstore.py](backend/core/vectorstore.py) |
| How the agent is built | [core/agent.py](backend/core/agent.py) |
| The hybrid search logic | [tools/search_tool.py](backend/tools/search_tool.py) |
| The structured extraction | [tools/extract_tool.py](backend/tools/extract_tool.py) |
| The Pydantic schema | [core/extractor.py](backend/core/extractor.py) |
| The API endpoints | [api/routes.py](backend/api/routes.py) |
