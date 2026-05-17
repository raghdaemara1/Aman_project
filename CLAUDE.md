# IntelliDoc Demo — AMAN Interview Project

## Project Goal
Build a small, local, working demo called **"Insurance Document Intelligence Agent"** that demonstrates agentic RAG skills for an Agentic AI Lead interview at AMAN Holding in Egypt.

The demo must be simple enough to run locally, impressive enough to show real architectural thinking, and specific enough to AMAN's business domain (insurance, policies, claims).

---

## What the App Does

1. User uploads an insurance policy PDF
2. App parses and indexes it automatically
3. User can ask natural language questions about the document
4. An agent decides HOW to answer — semantic search OR structured extraction
5. App shows the answer + the source chunk + which tool the agent used

This demonstrates: PDF parsing → chunking → vector indexing → agent reasoning → retrieval → structured extraction — the full IntelliDoc pipeline locally.

---

## Tech Stack — Do Not Change This

```
Python 3.10+
├── streamlit              → UI
├── langchain              → agent + chains + tools
├── langchain-community    → document loaders, vectorstores
├── chromadb               → local vector store (no cloud needed)
├── openai                 → LLM + embeddings (gpt-4o-mini to keep cost low)
├── unstructured[pdf]      → PDF parsing
├── pydantic               → structured output schemas
└── python-dotenv          → environment variables
```

---

## Project Structure

```
aman-demo/
├── CLAUDE.md               ← this file
├── README.md               ← how to run the app
├── requirements.txt        ← all dependencies pinned
├── .env.example            ← OPENAI_API_KEY=your-key-here
├── app.py                  ← main Streamlit entry point
├── core/
│   ├── __init__.py
│   ├── parser.py           ← PDF parsing with unstructured
│   ├── vectorstore.py      ← ChromaDB setup + ingestion
│   ├── agent.py            ← LangChain agent with two tools
│   └── extractor.py        ← structured extraction chain
├── tools/
│   ├── __init__.py
│   ├── search_tool.py      ← semantic search tool for agent
│   └── extract_tool.py     ← structured extraction tool for agent
└── sample_docs/
    └── sample_policy.txt   ← a fake insurance policy for testing
```

---

## File-by-File Instructions

### app.py — Main Streamlit UI

Build a clean multi-section Streamlit app with:

**Sidebar:**
- App title: "IntelliDoc — Insurance Document Agent"
- File uploader accepting PDF files
- On upload: show a spinner "Parsing and indexing document..." then call `parser.py` → `vectorstore.py`
- Show success message with number of chunks indexed
- Show document metadata extracted: title guess, number of pages, language

**Main area — two tabs:**

Tab 1: "Ask a Question"
- Text input: "Ask anything about this policy..."
- On submit: call the agent from `agent.py`
- Show response in three sections:
  - Answer (large text)
  - Tool used badge: either "Semantic Search" (blue) or "Structured Extraction" (green)
  - Source chunk expander: show the exact text chunk used + page reference

Tab 2: "Extract Policy Data"
- Button: "Extract Structured Data"
- On click: call `extractor.py` directly (no agent, direct structured extraction)
- Show results as a clean table with these fields:
  - Policy Number
  - Policy Holder Name
  - Coverage Type
  - Start Date
  - End Date / Expiry
  - Premium Amount
  - Key Exclusions (list)
  - Coverage Limit

Style notes:
- Use `st.set_page_config(layout="wide")`
- Use columns for layout
- Keep it clean — no excessive colors
- Show a "How this works" expander at the bottom explaining the pipeline

---

### core/parser.py — PDF Parser

```python
# Use unstructured library to parse PDF
# Return: list of Document objects with page_content and metadata
# Metadata must include: page_number, source filename, chunk_index
# Chunk size: 500 tokens, overlap: 50 tokens
# Use RecursiveCharacterTextSplitter from langchain
```

Function signature:
```python
def parse_and_chunk(file_path: str) -> list[Document]:
    """
    Parse PDF using unstructured, split into chunks.
    Returns list of LangChain Document objects.
    """
```

---

### core/vectorstore.py — ChromaDB Vector Store

```python
# Use ChromaDB as local persistent vector store
# Use OpenAI text-embedding-3-small for embeddings (cheap + good)
# Collection name: "insurance_docs"
# Persist to: ./chroma_db/ directory
```

Functions needed:
```python
def ingest_documents(documents: list[Document]) -> Chroma:
    """Embed and store documents in ChromaDB. Return retriever."""

def get_retriever(k: int = 4) -> VectorStoreRetriever:
    """Load existing ChromaDB and return retriever for top-k chunks."""

def clear_store():
    """Delete all documents — called when new PDF is uploaded."""
```

---

### core/extractor.py — Structured Extraction Chain

Use LangChain with Pydantic output parser and gpt-4o-mini.

Define this Pydantic schema:
```python
class PolicyData(BaseModel):
    policy_number: str = Field(description="The unique policy identifier")
    policy_holder: str = Field(description="Full name of the policy holder")
    coverage_type: str = Field(description="Type of insurance coverage")
    start_date: str = Field(description="Policy start date")
    end_date: str = Field(description="Policy expiry or end date")
    premium_amount: str = Field(description="Monthly or annual premium amount")
    coverage_limit: str = Field(description="Maximum coverage amount")
    key_exclusions: list[str] = Field(description="List of things NOT covered")
```

Function:
```python
def extract_policy_data(retriever) -> PolicyData:
    """
    Retrieve all chunks, pass to LLM with structured output prompt.
    Return PolicyData object.
    """
```

System prompt to use:
```
You are an insurance document analyst. Extract the structured policy 
information from the provided document chunks. If a field is not found, 
return "Not specified". Be precise and factual — only extract what is 
explicitly stated in the document.
```

---

### core/agent.py — LangChain Agent

Build a LangChain agent with TWO tools:

**Tool 1: semantic_search**
- Description: "Use this tool when the user asks a general question, wants to know about coverage, asks 'what does this policy say about X', or asks any open-ended question about the document."
- Action: runs vector similarity search, returns top 4 chunks with page numbers

**Tool 2: structured_extract**  
- Description: "Use this tool when the user asks for specific policy fields like policy number, expiry date, premium amount, holder name, coverage limit, or exclusions."
- Action: calls extractor.py and returns the specific field requested

Use: `create_react_agent` from langchain with gpt-4o-mini

System prompt:
```
You are an insurance document intelligence agent for AMAN Holding.
You have access to two tools:
1. semantic_search — for open questions about policy content
2. structured_extract — for specific policy field lookups

Always cite which page or section your answer comes from.
Be concise, factual, and professional.
If you cannot find the answer in the document, say so clearly.
Do not hallucinate or guess.
```

Function:
```python
def run_agent(query: str, retriever) -> dict:
    """
    Run agent on user query.
    Return: {
        "answer": str,
        "tool_used": str,  # "semantic_search" or "structured_extract"
        "source_chunks": list[str],
        "page_references": list[int]
    }
    """
```

---

### tools/search_tool.py

```python
# Wrap the ChromaDB retriever as a LangChain Tool
# Input: query string
# Output: formatted string of top chunks with page numbers
# Format: "Page {n}: {chunk_content}\n---\n"
```

---

### tools/extract_tool.py

```python
# Wrap the extractor as a LangChain Tool
# Input: field name (e.g. "expiry date", "exclusions")  
# Output: extracted value as string
# Internally calls extractor.py PolicyData and returns the right field
```

---

### sample_docs/sample_policy.txt

Create a realistic fake insurance policy document with these details so the app works without needing a real PDF:

```
Policy Number: AMAN-2025-INS-004892
Policy Holder: Ahmed Mohamed Hassan
Coverage Type: Comprehensive Health Insurance
Issue Date: January 1, 2025
Expiry Date: December 31, 2025
Premium: EGP 4,800 annually
Coverage Limit: EGP 500,000 per year

Covered Services:
- Hospitalization (up to 90 days per year)
- Emergency surgery
- Outpatient consultations (up to 20 visits)
- Laboratory tests and diagnostics
- Prescription medications (up to EGP 2,000/year)
- Maternity coverage (after 12 months waiting period)

Exclusions:
- Pre-existing conditions diagnosed before policy start date
- Cosmetic or elective procedures
- Dental and optical care
- Mental health treatment
- Injuries resulting from extreme sports
- Treatment outside Egypt unless emergency

Network: All accredited hospitals in Cairo, Alexandria, and Giza
Emergency hotline: 19795
```

---

### requirements.txt

```
streamlit==1.32.0
langchain==0.1.20
langchain-community==0.0.38
langchain-openai==0.1.6
chromadb==0.4.24
openai==1.25.0
unstructured[pdf]==0.13.0
pydantic==2.7.0
python-dotenv==1.0.1
tiktoken==0.7.0
```

---

### README.md

Write a clean README with:

```markdown
# Insurance Document Intelligence Agent
## AMAN Holding — Interview Demo

### What This Demonstrates
- PDF parsing with unstructured.io
- Vector indexing with ChromaDB + OpenAI embeddings  
- Agentic reasoning with LangChain ReAct agent
- Two retrieval modes: semantic search + structured extraction
- Full local deployment — no cloud infrastructure needed

### Architecture
[draw simple text diagram of the pipeline]

### How to Run
1. Clone the repo
2. pip install -r requirements.txt
3. cp .env.example .env → add your OpenAI key
4. streamlit run app.py
5. Upload the sample policy from sample_docs/

### Key Design Decisions
- ChromaDB chosen for zero-infrastructure local deployment
- Two-tool agent forces explicit reasoning about retrieval strategy
- Structured extraction uses Pydantic for type-safe outputs
- Chunk size 500 tokens with 50 overlap balances context vs precision

### What I Would Add in Production
- Snowflake Cortex Search replacing ChromaDB for enterprise scale
- Neo4j knowledge graph linking policies → claims → customers
- LangSmith tracing for agent observability
- Multi-document comparison across policy versions
```

---

## Things to Know Before the Interview

### Why ChromaDB and not Pinecone?
"This runs fully locally for the demo. In production at O3Sigma I used Snowflake Cortex Search. ChromaDB is the right choice for a local demo — zero infrastructure, persistent, and the LangChain integration is identical to production vector stores."

### Why two tools and not one?
"Semantic search and structured extraction are fundamentally different operations. Search finds the most relevant text. Extraction pulls a specific field with a defined schema. Mixing them in one tool loses the type safety and explainability. The agent choosing between them is what makes it agentic."

### Why gpt-4o-mini and not gpt-4o?
"Cost-accuracy tradeoff. For document Q&A on a focused domain, gpt-4o-mini performs comparably to gpt-4o at 10x lower cost. In production I'd benchmark both but for a demo this is the right call."

### What would you change for AMAN production?
"Replace ChromaDB with Snowflake Cortex Search, add Neo4j to link policies to customers and claims, add LangSmith for agent tracing and observability, and wrap everything in a FastAPI backend so Maxwell or Phoenix apps can call it as a service — exactly what IntelliDoc is building."

---

## How to Run Claude Code

In your terminal, navigate to your project folder and run:

```bash
claude
```

Then paste this message:

```
Please read CLAUDE.md fully before writing any code. 
Build the complete project exactly as specified. 
Create all files and folders in the structure defined. 
After building, run the app and confirm it starts without errors.
Start with requirements.txt, then core/ files, then tools/, then app.py last.
```

---

<!-- SPECKIT START -->
## Active Implementation Plan

Feature: **Insurance Document Intelligence Agent**
Branch: `001-insurance-doc-agent`
Plan: [`specs/001-insurance-doc-agent/plan.md`](specs/001-insurance-doc-agent/plan.md)
Spec: [`specs/001-insurance-doc-agent/spec.md`](specs/001-insurance-doc-agent/spec.md)
<!-- SPECKIT END -->
