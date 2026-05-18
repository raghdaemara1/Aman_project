# IntelliDoc — Pipeline Visual Guide

---

## PIPELINE A — Upload  (always the same, no agent involved)

```
You click "Upload PDF"
         │
         ▼
┌─────────────────────────────────┐
│  routes.py  /upload             │
│  reads the file bytes           │
│  computes MD5 hash              │
│  same file? → skip              │
└────────────┬────────────────────┘
             │ new file
             ▼
┌─────────────────────────────────┐
│  parser.py                      │
│                                 │
│  pypdf reads every page         │
│  Page 1 → text string           │
│  Page 2 → text string           │
│  Page 3 → text string  ...      │
│                                 │
│  Splitter cuts each page into   │
│  500-character chunks           │
│  with 50-char overlap           │
│                                 │
│  OUTPUT: list of ~50 chunks     │
│  each chunk has page_number     │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  vectorstore.py                 │
│                                 │
│  For EACH chunk:                │
│    nomic-embed-text reads it    │
│    converts to 768 numbers      │
│    e.g. [0.12, -0.34, 0.91...] │
│                                 │
│  Saves vectors → ChromaDB disk  │
│  Saves chunks  → _chunks memory │
│                                 │
│  OUTPUT: nothing returned,      │
│  data is now stored in 2 places │
│  ① ./chroma_db/ (disk)         │
│  ② _chunks[]   (memory)        │
└─────────────────────────────────┘
```

After upload, you have:
- `_chunks[]` in memory = plain text, used by BM25
- `chroma_db/` on disk  = vectors,     used by semantic search

---

## PIPELINE B — Ask a Question  (/ask → AGENT DECIDES)

This is the one with LangGraph. Read it carefully.

```
You type: "What is the policy number?"
and click Ask
         │
         ▼
┌─────────────────────────────────┐
│  routes.py  /ask                │
│  passes question to agent.py    │
└────────────┬────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────┐
│  agent.py — LangGraph ReAct Agent starts                   │
│                                                            │
│  create_react_agent gives llama3.1 this context:           │
│                                                            │
│  "You have 2 tools:                                        │
│   - hybrid_search   → for open/general questions          │
│   - structured_extract → for specific field lookups"       │
│                                                            │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  STEP 1 — THINK                                     │  │
│  │                                                     │  │
│  │  llama3.1 reads: "What is the policy number?"       │  │
│  │  llama3.1 reads tool descriptions                   │  │
│  │                                                     │  │
│  │  llama3.1 output (JSON, not text):                  │  │
│  │  {                                                  │  │
│  │    "tool": "structured_extract",                    │  │
│  │    "arguments": {"field_name": "policy number"}     │  │
│  │  }                                                  │  │
│  │                                                     │  │
│  │  ← LLM did NOT write an answer yet                 │  │
│  │  ← LLM just said which tool it wants to call       │  │
│  └──────────────────────┬──────────────────────────────┘  │
│                          │                                 │
│  ┌───────────────────────▼─────────────────────────────┐  │
│  │  STEP 2 — ACT                                       │  │
│  │                                                     │  │
│  │  LangGraph (not the LLM) runs the Python function:  │  │
│  │                                                     │  │
│  │  structured_extract("policy number")                │  │
│  │           │                                         │  │
│  │           ▼                                         │  │
│  │  extract_tool.py calls extract_policy_data()        │  │
│  │           │                                         │  │
│  │           ▼                                         │  │
│  │  extractor.py:                                      │  │
│  │    takes ALL _chunks from memory                    │  │
│  │    sends to llama3.1 with PolicyData schema         │  │
│  │    llama3.1 fills the form                          │  │
│  │    Pydantic validates it                            │  │
│  │    returns PolicyData object                        │  │
│  │           │                                         │  │
│  │           ▼                                         │  │
│  │  field_map matches "policy number"                  │  │
│  │  returns: "US151741"                                │  │
│  └──────────────────────┬──────────────────────────────┘  │
│                          │                                 │
│  ┌───────────────────────▼─────────────────────────────┐  │
│  │  STEP 3 — OBSERVE                                   │  │
│  │                                                     │  │
│  │  LangGraph adds the tool result to the conversation │  │
│  │                                                     │  │
│  │  The conversation now looks like:                   │  │
│  │                                                     │  │
│  │  Human:  "What is the policy number?"               │  │
│  │  Agent:  [called structured_extract]                │  │
│  │  Tool:   "US151741"          ← this is the observe  │  │
│  │                                                     │  │
│  │  llama3.1 reads ALL of the above again              │  │
│  └──────────────────────┬──────────────────────────────┘  │
│                          │                                 │
│  ┌───────────────────────▼─────────────────────────────┐  │
│  │  STEP 4 — THINK AGAIN                               │  │
│  │                                                     │  │
│  │  llama3.1 reads the tool result "US151741"          │  │
│  │  decides: "I have enough to answer. Stop."          │  │
│  │                                                     │  │
│  │  llama3.1 output (plain text this time, not JSON):  │  │
│  │  "The policy number is US151741, as shown           │  │
│  │   on page 1 of the document."                       │  │
│  │                                                     │  │
│  │  ← plain text = no tool call = STOP the loop       │  │
│  └──────────────────────┬──────────────────────────────┘  │
│                          │                                 │
└──────────────────────────┼─────────────────────────────────┘
                           │
                           ▼
              Answer shown in the UI
```

---

## What if the answer needs more than one tool call?

Example: "Compare the policy number and tell me if sickness is covered."

```
THINK  → calls structured_extract("policy number")
OBSERVE → "US151741"
THINK  → "I have the number but still need sickness coverage info"
ACT    → calls hybrid_search("sickness coverage")
OBSERVE → "Page 1: BENEFITS ARE NOT PAYABLE FOR LOSS DUE TO SICKNESS"
THINK  → "Now I have both. I can answer."
ANSWER → "Policy US151741 does NOT cover sickness losses,
           as stated on page 1."
```

The loop runs as many times as needed. It only stops when the LLM
outputs plain text instead of a tool call JSON.

---

## PIPELINE B — Same question, different tool chosen

```
You type: "What does it say about sickness?"
         │
         ▼
  THINK: "This is a general question about content
          → use hybrid_search"
         │
         ▼
  ACT: hybrid_search("sickness coverage")
         │
         │   search_tool.py runs TWO searches:
         │
         ├──► BM25 (keyword search)
         │      reads _chunks[] from memory
         │      tokenizes every chunk into words
         │      scores each chunk by word overlap with query
         │      ranks: chunk 12 > chunk 3 > chunk 7 > chunk 21
         │
         └──► ChromaDB (vector/semantic search)
                converts query to 768-dim vector
                finds 4 closest vectors on disk
                ranks: chunk 12 > chunk 7 > chunk 3 > chunk 5
                │
                ▼
         RRF merges both ranked lists
         chunk 12 was #1 in both → highest score → kept
         chunk 3  was #2 in BM25, #3 in vector → kept
         picks top 4 chunks
         │
         ▼
  OBSERVE: LangGraph adds to conversation:
  "Page 1: BENEFITS ARE NOT PAYABLE FOR LOSS DUE TO SICKNESS.
   THIS POLICY PAYS BENEFITS FOR SPECIFIC LOSSES FROM ACCIDENT ONLY."
         │
         ▼
  THINK: "I have the relevant text. I can write the answer."
         │
         ▼
  ANSWER: "According to page 1, benefits are not payable
           for loss due to sickness. This is an accident-only policy."
```

---

## PIPELINE C — Extract Tab  (/extract → NO AGENT, NO LOOP)

```
You click "Extract Policy Data"
         │
         ▼
┌─────────────────────────────────┐
│  routes.py  /extract            │
│  no agent, goes straight to:    │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  extractor.py                   │
│                                 │
│  takes ALL _chunks from memory  │
│  sorts by page number           │
│  builds one big text block      │
│  trims to 6,000 characters      │
│                                 │
│  sends to llama3.1:             │
│  "Fill this exact JSON form     │
│   from the document text:       │
│   {                             │
│     policy_number: ...,         │
│     policy_holder: ...,         │
│     coverage_type: ...,         │
│     start_date: ...,            │
│     end_date: ...,              │
│     premium_amount: ...,        │
│     coverage_limit: ...,        │
│     key_exclusions: [...]       │
│   }"                            │
│                                 │
│  Pydantic validates the JSON    │
│  returns PolicyData object      │
└────────────┬────────────────────┘
             │
             ▼
     Structured table in UI
     all 8 fields shown
```

No loop. No tool choice. No agent.
It always does the same thing.

---

## Side-by-side summary

```
                /ask                          /extract
                ────                          ────────
Entry point     routes.py /ask                routes.py /extract
Agent?          YES — LangGraph ReAct          NO — direct function call
Loop?           YES — Think→Act→Observe        NO — runs once
Tool choice?    YES — LLM decides              NO — always structured extract
BM25+ChromaDB?  YES — if hybrid_search picked  NO
Pydantic?       YES — if structured_extract    YES — always
                      picked
Output          Natural language answer         8-field structured table
```

---

## The LangGraph graph — what create_react_agent builds

```
create_react_agent builds this state machine:

  ┌─────────┐
  │  START  │
  └────┬────┘
       │  question comes in
       ▼
  ┌────────────┐   plain text answer    ┌─────────┐
  │ agent node │ ──────────────────────►│   END   │
  │ (llama3.1) │                        └─────────┘
  └─────┬──────┘
        │ tool call JSON
        ▼
  ┌────────────┐
  │  tool node │  runs the Python function
  │ (LangGraph)│  structured_extract() or hybrid_search()
  └─────┬──────┘
        │ tool result added to messages
        └──────────────────────────────► back to agent node
                                         (observe + think again)
```

The loop between agent node and tool node is what makes it "agentic".
It runs until the agent node outputs plain text (no tool call).
