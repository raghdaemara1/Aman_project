# New Features — Conversational AI Pipeline & Multi-Agent Orchestration

---

## What Was Added

Two new capabilities were layered on top of the existing single-question agent:

1. **Conversational AI Pipeline** — the AI remembers previous messages in a session
2. **Multi-Agent Orchestration** — a Supervisor routes each question to a specialist agent

Both features are exposed through the new **Chat** tab and the `POST /api/v1/chat` endpoint.

---

## Feature 1 — Conversational AI Pipeline

### What it is

A Conversational AI Pipeline is a system where the user has a **back-and-forth conversation** with an AI that:
- Remembers every previous message in the session
- Uses that history to understand follow-up questions
- Maintains context without the user repeating themselves

### How it works technically

Every `/chat` call receives or generates a `session_id` (a UUID). The backend stores
the conversation history in `core/memory.py` — a Python dict keyed by session_id:

```
session_id → [
  { role: "human",     content: "What is the policy number?" },
  { role: "assistant", content: "US151741", agent_used: "extraction_agent" },
  { role: "human",     content: "And when does it expire?" },
  { role: "assistant", content: "August 1, 2014", agent_used: "extraction_agent" },
]
```

Before each new question is processed, the Supervisor Agent receives the full history
plus the new question. This lets it correctly classify follow-ups:

> User: "What is the policy number?"  → extraction_agent (clear field lookup)
> User: "And when does it expire?"    → extraction_agent (follow-up — needs history to classify)
> User: "What does it say about that exclusion?" → retrieval_agent (follow-up referencing earlier answer)

Without history, the second question "And when does it expire?" has no subject —
the agent would not know what "it" refers to. With history, it understands the context.

### New files

| File | Role |
|---|---|
| `backend/core/memory.py` | Session store — `get_messages()`, `add_exchange()`, `clear_session()` |

### New API endpoints

| Endpoint | What it does |
|---|---|
| `POST /api/v1/chat` | Send a message; pass `session_id` from previous response to continue the conversation |
| `GET /api/v1/chat/history/{id}` | Return full conversation history for a session |
| `DELETE /api/v1/chat/sessions/{id}` | Clear a session and start fresh |

---

## Feature 2 — Multi-Agent Orchestration

### What it is

Instead of one agent that holds all tools, the system now has **three collaborating agents**:

```
User Question
      ↓
Supervisor Agent        ← decides who should answer
      ↓
 ┌────────────┐    ┌──────────────────┐
 │  Retrieval │    │    Extraction    │
 │   Agent    │    │      Agent       │
 │            │    │                  │
 │ hybrid_    │    │ structured_      │
 │ search     │    │ extract          │
 └────────────┘    └──────────────────┘
```

This is the **Supervisor pattern** — a standard multi-agent architecture where one
coordinator delegates to specialists rather than one agent doing everything.

### How it works technically

The Supervisor uses `llm.with_structured_output(RouteDecision)` to classify the question:

```python
class RouteDecision(BaseModel):
    destination: Literal["retrieval_agent", "extraction_agent"]
    reasoning: str
```

The LLM must return a typed JSON object — not free text. The `reasoning` field is logged
in the pipeline steps so you can see exactly why the Supervisor routed the way it did.

Each specialist is a separate `create_react_agent` instance with its own focused system prompt:

- **Retrieval Agent** — only has `hybrid_search`. System prompt focused on finding passages and citing pages.
- **Extraction Agent** — only has `structured_extract`. System prompt focused on precise field values.

Neither agent can call the other's tool. This enforces clear specialisation.

If the Supervisor's structured output fails (can happen with a local LLM under load),
there is a keyword fallback that routes based on field-lookup words in the query.

### New files

| File | Role |
|---|---|
| `backend/core/orchestrator.py` | Supervisor + specialist agents + `run_orchestrator()` entry point |

---

## Why Have Both Ask and Chat? Are They the Same?

No — they look similar on the surface but serve different purposes and use different architectures.

### The short answer

| | Ask Tab | Chat Tab |
|---|---|---|
| **Memory** | None — each question is independent | Full session history |
| **Agents** | One ReAct agent | Three agents (Supervisor + 2 specialists) |
| **Tools available** | Both tools, agent picks | One tool per specialist — Supervisor decides |
| **Best for** | Quick one-off lookups | Investigation workflows, follow-up questions |
| **Speed** | Faster (one LLM call + tool) | Slower (Supervisor call + specialist call) |

### The long answer

**Ask** is a **single stateless ReAct agent**. It receives the question, reasons about
which of its two tools to call, calls it, and returns the answer. No history. Every call
starts from scratch. It is the right choice when you have one specific question and do not
need to build on previous answers.

```
User: "What is the policy number?"
  → one agent reasons: "this is a field lookup → use structured_extract"
  → calls structured_extract("policy number")
  → returns "US151741"
  → done, state forgotten
```

**Chat** is a **multi-agent pipeline with memory**. Every question goes through the Supervisor
first, which reads conversation history, then routes to the appropriate specialist. The
specialist executes its tool and the exchange is saved to memory for the next turn.

```
User: "What is the policy number?"
  → Supervisor reads history (empty) + question
  → routes to Extraction Agent
  → Extraction Agent calls structured_extract("policy number")
  → returns "US151741"  ← saved to memory

User: "And when does it expire?"       ← no explicit subject
  → Supervisor reads history + question
  → understands "it" = the policy from last turn
  → routes to Extraction Agent
  → returns "August 1, 2014"

User: "What does it say about accidents?"
  → Supervisor reads history + question
  → classifies as open question → routes to Retrieval Agent
  → Retrieval Agent calls hybrid_search("accidents coverage")
  → returns relevant passages
```

The Chat tab is what makes this system genuinely **agentic** in the modern sense — it is
not just a question answering system, it is a collaborative investigation session where
context accumulates across turns.

### Why keep Ask at all?

- It is faster — one LLM inference call fewer (no Supervisor step)
- It is simpler to explain as a standalone demo of the ReAct loop
- It shows the contrast: *this is what a single agent looks like vs a multi-agent system*
- Some users just want one quick answer without starting a session

Keeping both makes the architectural difference visible — Ask demonstrates the base ReAct
loop, Chat demonstrates orchestration and memory on top of it.

---

## Pipeline Steps You Will See in the Chat Tab

```
Session abc123… — 2 previous turn(s) in memory
Supervisor Agent: analysing question and routing to specialist...
Supervisor → extraction_agent | reason: user asked for a specific field value
Extraction Agent: running structured_extract (Pydantic schema)...
Retrieved 0 source chunk(s)
Answer generated by: extraction_agent
Done
```

The `Supervisor →` line shows exactly which agent was chosen and why.
The badge on each chat bubble (blue = Retrieval, purple = Extraction) shows who answered.
