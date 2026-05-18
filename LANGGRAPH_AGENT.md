# LangGraph ReAct Agent — Full Explanation

---

## What is a ReAct Agent?

ReAct = **Re**ason + **Act**

Instead of the LLM answering directly, it runs a loop:

```
THINK → ACT → OBSERVE → THINK → ACT → OBSERVE → ... → ANSWER
```

The LLM never calls Python directly.
It outputs JSON saying "I want to call this tool."
LangGraph intercepts that, runs the real Python function,
feeds the result back, and the LLM reads it and decides what to do next.

---

## The Full Code — agent.py

```python
# STEP 1 — Import what you need
from langchain_ollama import ChatOllama           # the LLM
from langgraph.prebuilt import create_react_agent  # builds the graph
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from tools.search_tool import hybrid_search        # Tool 1
from tools.extract_tool import structured_extract  # Tool 2
```

```python
# STEP 2 — Write the system prompt
# This is the ONLY routing logic. No if/else in code.
# The LLM reads these descriptions and decides which tool to call.

SYSTEM_PROMPT = (
    "You are an insurance document intelligence agent. "
    "You have access to two tools:\n"
    "1. hybrid_search — use for open questions about policy terms, coverage, "
       "what the policy says about a specific topic.\n"
    "2. structured_extract — use for specific field lookups: policy number, "
       "policyholder name, coverage type, dates, premium, limit, exclusions.\n\n"
    "Be concise, factual, and professional."
)
```

```python
# STEP 3 — Build the agent (one line)
llm   = ChatOllama(model="llama3.1:latest", temperature=0)
tools = [hybrid_search, structured_extract]

agent = create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)

# create_react_agent builds this state machine internally:
#
#  [START]
#     │
#     ▼
#  [agent node] ◄─────────────────────────────────┐
#     │                                            │
#     │  LLM outputs tool call JSON?               │
#     ├── YES ──► [tool node]                      │
#     │               runs Python function         │
#     │               adds ToolMessage to list ────┘
#     │
#     └── NO (plain text) ──► [END]
#                              returns all messages
```

```python
# STEP 4 — Run the loop
result = agent.invoke({"messages": [HumanMessage(content=query)]})

# agent.invoke() runs the full loop internally.
# You get back a dict with "messages" — the complete conversation history.
```

```python
# STEP 5 — Extract the final answer
messages = result.get("messages", [])

answer = "I could not find an answer."
for msg in reversed(messages):         # walk backwards through messages
    if isinstance(msg, AIMessage) and msg.content:
        answer = msg.content           # last AIMessage with text = final answer
        break

# Why reversed? Because the last AIMessage is always the final answer.
# Earlier AIMessages only contain tool_calls JSON, not readable text.
```

```python
# STEP 6 — Find which tool was used (for the UI badge)
tool_used = "hybrid_search"
for msg in messages:                   # walk forwards through messages
    if isinstance(msg, AIMessage) and msg.tool_calls:
        tool_used = msg.tool_calls[0].get("name", "hybrid_search")
        break
```

---

## Pipeline 2 — Full Loop for "what is the policy number?"

```
agent.invoke({"messages": [HumanMessage("what is the policy number?")]})
│
│
├── TURN 1 ── agent node
│
│   llama3.1 receives:
│   ┌────────────────────────────────────────────────────────┐
│   │ SYSTEM: You are an insurance agent. You have 2 tools:  │
│   │   1. hybrid_search — for open questions               │
│   │   2. structured_extract — for specific fields         │
│   │                                                        │
│   │ HUMAN: "what is the policy number?"                    │
│   └────────────────────────────────────────────────────────┘
│
│   llama3.1 output (JSON, not readable text):
│   {
│     "tool_calls": [{
│       "name": "structured_extract",
│       "args": {"field_name": "policy number"}
│     }]
│   }
│
│   ← LLM has NOT written an answer yet
│   ← LLM chose structured_extract because the description said
│     "use for specific field lookups: policy number..."
│
│   messages so far:
│   [0] HumanMessage  "what is the policy number?"
│   [1] AIMessage     tool_calls=[structured_extract("policy number")]
│
│
├── TURN 1 ── tool node
│
│   LangGraph (not the LLM) runs:
│   structured_extract("policy number")
│        │
│        ▼
│   extract_tool.py:
│     all_chunks = get_chunks()           ← all 53 chunks
│     policy = extract_policy_data(retriever, all_chunks=all_chunks)
│        │
│        ▼
│     extractor.py:
│       builds context from all chunks (page 1 first)
│       sends to llama3.1 with PolicyData schema
│       llama3.1 fills the form → PolicyData(policy_number="US151741", ...)
│       _regex_override() confirms: "Policy Number: US151741" found in text
│       returns PolicyData
│        │
│        ▼
│     field_map["policy number"] = "US151741"
│     returns "US151741"
│
│   LangGraph adds ToolMessage("US151741") to messages
│
│   messages so far:
│   [0] HumanMessage  "what is the policy number?"
│   [1] AIMessage     tool_calls=[structured_extract("policy number")]
│   [2] ToolMessage   "US151741"                  ← OBSERVE step
│
│   → loop back to agent node
│
│
├── TURN 2 ── agent node
│
│   llama3.1 receives ALL messages:
│   ┌────────────────────────────────────────────────────────┐
│   │ SYSTEM: You are an insurance agent...                  │
│   │                                                        │
│   │ HUMAN:  "what is the policy number?"                   │
│   │ AI:     [called structured_extract]                    │
│   │ TOOL:   "US151741"                                     │
│   └────────────────────────────────────────────────────────┘
│
│   llama3.1 output (plain text this time):
│   "The policy number is US151741."
│
│   ← plain text = no tool_calls = STOP the loop
│
│   messages so far:
│   [0] HumanMessage  "what is the policy number?"
│   [1] AIMessage     tool_calls=[structured_extract("policy number")]
│   [2] ToolMessage   "US151741"
│   [3] AIMessage     "The policy number is US151741."   ← FINAL ANSWER
│
│
└── agent.invoke() returns result["messages"] = all 4 messages above
```

**Back in run_agent():**
```python
# reversed loop finds messages[3] = "The policy number is US151741."
answer = "The policy number is US151741."

# forward loop finds messages[1] has tool_calls
tool_used = "structured_extract"
```

---

## Pipeline 2 — Full Loop for "what does it say about sickness?"

```
agent.invoke({"messages": [HumanMessage("what does it say about sickness?")]})
│
│
├── TURN 1 ── agent node
│
│   llama3.1 sees the question + tool descriptions
│   decides: "open question about policy content → hybrid_search"
│
│   output:
│   {
│     "tool_calls": [{
│       "name": "hybrid_search",
│       "args": {"query": "sickness coverage"}
│     }]
│   }
│
│
├── TURN 1 ── tool node
│
│   LangGraph runs: hybrid_search("sickness coverage")
│        │
│        ▼
│   search_tool.py:
│     chunks = get_chunks()         ← all 53 chunks from memory
│
│     BM25 search:
│       tokenizes every chunk into words
│       scores chunks by word overlap with "sickness coverage"
│       top 4: chunk[2], chunk[0], chunk[11], chunk[5]
│
│     ChromaDB vector search:
│       converts "sickness coverage" → 768-dim vector
│       finds 4 closest vectors in chroma_db/
│       top 4: chunk[2], chunk[11], chunk[0], chunk[7]
│
│     RRF merge:
│       chunk[2]  ranked #1 in BM25, #1 in vector → score = 1/61 + 1/61 = highest
│       chunk[0]  ranked #2 in BM25, #3 in vector → score = 1/62 + 1/63
│       chunk[11] ranked #4 in BM25, #2 in vector → score = 1/64 + 1/62
│       ...
│       picks top 4 by combined score
│
│     returns:
│     "Page 1: BENEFITS ARE NOT PAYABLE FOR LOSS DUE TO SICKNESS.
│      THIS POLICY PAYS BENEFITS FOR SPECIFIC LOSSES FROM ACCIDENT ONLY.
│      ---
│      Page 5: "Sickness" means illness or disease which first manifests...
│      ---"
│
│   LangGraph adds ToolMessage(above text) to messages
│
│
├── TURN 2 ── agent node
│
│   llama3.1 reads the tool output
│   output (plain text):
│   "According to page 1, benefits are NOT payable for loss due to
│    sickness. This is an accident-only policy — sickness is explicitly
│    excluded. The definition of Sickness (page 5) includes illness,
│    disease, and complications of pregnancy."
│
│   ← plain text = STOP
│
│
└── agent.invoke() returns
```

**Back in run_agent():**
```python
answer   = "According to page 1, benefits are NOT payable..."
tool_used = "hybrid_search"

# source_chunks parsed from ToolMessage:
# "Page 1: BENEFITS ARE NOT PAYABLE..." → chunk 1, page_ref = 1
# "Page 5: Sickness means illness..."   → chunk 2, page_ref = 5
```

---

## The @tool decorator — how tools register themselves

```python
# FILE: tools/search_tool.py

@tool                           # ← this decorator does 3 things:
def hybrid_search(query: str) -> str:
    """Use this tool when the user asks a general question..."""
    #   ↑ docstring → sent to LLM as the tool description
    #                  LLM reads this to decide whether to call it

    # actual Python code runs here when LangGraph calls it
    ...
```

The three things `@tool` does:
1. Registers the function so LangGraph can call it by name
2. Sends the function signature (`query: str`) to the LLM so it knows what argument to pass
3. Sends the docstring to the LLM as the description of when to use it

**The docstring is the only routing logic.**
If you write a bad docstring, the LLM picks the wrong tool.

---

## How to build your own ReAct agent from scratch

```python
from langgraph.prebuilt import create_react_agent
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage

# 1. Define the LLM
llm = ChatOllama(model="llama3.1:latest", temperature=0)

# 2. Define tools
@tool
def search_docs(query: str) -> str:
    """Use this for general questions about the document."""
    return "some relevant text found in the document"

@tool
def get_field(field_name: str) -> str:
    """Use this for specific field lookups like name, date, number."""
    return "the specific field value"

# 3. Build the agent
agent = create_react_agent(llm, [search_docs, get_field], prompt="You are a helpful agent.")

# 4. Run it
result = agent.invoke({"messages": [HumanMessage(content="what is the policy number?")]})

# 5. Get the answer
print(result["messages"][-1].content)
```

That's it. `create_react_agent` handles the entire Think → Act → Observe loop.
You only need to define: the LLM, the tools, and the system prompt.

---

## Summary — what each part does

```
create_react_agent(llm, tools, prompt)
        │
        │  builds a graph with 2 nodes:
        │
        ├── agent node: runs llm.invoke(messages)
        │               if output has tool_calls → route to tool node
        │               if output is plain text  → route to END
        │
        └── tool node:  finds the function by tool name
                        calls it with the args the LLM provided
                        wraps result in ToolMessage
                        routes back to agent node
```

```
messages list grows each turn:
  HumanMessage   ← user question
  AIMessage      ← LLM tool call decision   (tool_calls=[...])
  ToolMessage    ← tool result              (the OBSERVE step)
  AIMessage      ← LLM final answer         (plain text, no tool_calls)
```

```
run_agent() after the loop:
  reversed(messages) → find last AIMessage with text  → answer
  forward(messages)  → find first AIMessage with tool_calls → tool_used
  ToolMessage content → parse "Page N: ..." lines → source_chunks + page_refs
```
