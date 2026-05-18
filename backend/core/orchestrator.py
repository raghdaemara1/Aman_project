"""
Multi-agent orchestrator.

Architecture:
  User query + session history
        ↓
  Supervisor Agent (llama3.1, structured output → RouteDecision)
        ↓ routes to
  ┌──────────────────────┬──────────────────────┐
  │   Retrieval Agent    │   Extraction Agent   │
  │   hybrid_search      │   structured_extract │
  │   open questions     │   field lookups      │
  └──────────────────────┴──────────────────────┘
        ↓
  Answer + source chunks + agent_used
        ↓
  Saved to session memory

Specialist agents call their tool directly (guaranteed execution) then
pass the tool result to the LLM to generate a natural language answer.
The Supervisor is the "agentic" layer — it reads conversation history
and decides which specialist should handle the question.
"""

import os
from typing import Literal

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_ollama import ChatOllama
from pydantic import BaseModel

from tools.search_tool import hybrid_search  # type: ignore[attr-defined]
from tools.extract_tool import structured_extract  # type: ignore[attr-defined]
from core.memory import get_messages, add_exchange

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

SUPERVISOR_SYSTEM = (
    "You are an orchestrator for an insurance document AI system. "
    "Route the user question to the correct specialist agent.\n\n"
    "Use extraction_agent for ANY question asking for a specific data field, including:\n"
    "  - policy number / policy id\n"
    "  - policyholder / insured name / who is covered\n"
    "  - effective date / start date / when does it start\n"
    "  - expiration date / expiry date / end date / when does it expire / when does it end\n"
    "  - premium / cost / price / how much does it cost\n"
    "  - coverage limit / maximum benefit / how much is covered\n"
    "  - coverage type / type of insurance\n"
    "  - exclusions / what is not covered / conditions\n\n"
    "Use retrieval_agent for open questions such as:\n"
    "  - what does the policy say about X\n"
    "  - explain the coverage for accidents\n"
    "  - summarise the policy\n"
    "  - any general inquiry not asking for a single specific field value\n\n"
    "When the question is a follow-up (e.g. 'and when does it expire?', 'what about the premium?'), "
    "classify based on what the follow-up is asking for — not that it is a follow-up."
)

RETRIEVAL_ANSWER_SYSTEM = (
    "You are a Retrieval Specialist for insurance documents. "
    "You have been given relevant passages retrieved from the document. "
    "Answer the user's question using only those passages. "
    "Cite the page number when possible. Be concise and factual."
)

EXTRACTION_ANSWER_SYSTEM = (
    "You are an Extraction Specialist for insurance documents. "
    "You have been given data extracted directly from the policy. "
    "Answer the user's question using only that extracted data. "
    "The policy number is next to the 'Policy Number:' label — NOT the GAP form code. "
    "Be precise and direct."
)


class RouteDecision(BaseModel):
    destination: Literal["retrieval_agent", "extraction_agent"]
    reasoning: str


def _parse_tool_result(tool_output: str) -> tuple[list[str], list[int]]:
    """Extract source chunks and page refs from tool output text."""
    source_chunks: list[str] = []
    page_refs: list[int] = []
    current_lines: list[str] = []
    current_page: int | None = None

    for line in tool_output.split("\n"):
        if line.startswith("Page ") and ":" in line:
            if current_lines and current_page is not None:
                source_chunks.append("\n".join(current_lines).strip())
                page_refs.append(current_page)
            try:
                current_page = int(line.split(":")[0].replace("Page ", "").strip())
                current_lines = [":".join(line.split(":")[1:]).strip()]
            except ValueError:
                current_page = 1
                current_lines = [line]
        elif line.strip() == "---":
            if current_lines and current_page is not None:
                source_chunks.append("\n".join(current_lines).strip())
                page_refs.append(current_page)
            current_lines = []
            current_page = None
        else:
            current_lines.append(line)

    if current_lines and current_page is not None:
        source_chunks.append("\n".join(current_lines).strip())
        page_refs.append(current_page)

    return source_chunks, page_refs


def run_orchestrator(query: str, session_id: str, steps: list[str] | None = None) -> dict:
    """
    Run the multi-agent orchestrator:
    1. Supervisor Agent classifies the question (structured output).
    2. Specialist Agent calls its tool directly, then LLM generates the answer.
    3. Exchange saved to session memory for conversation continuity.
    """
    def log(msg: str) -> None:
        print(f"[orchestrator] {msg}", flush=True)
        if steps is not None:
            steps.append(msg)

    llm = ChatOllama(model="llama3.1:latest", temperature=0, base_url=OLLAMA_BASE_URL)

    # Load session history
    history = get_messages(session_id)
    turn_count = len(history) // 2
    log(f"Session {session_id[:8]}… — {turn_count} previous turn(s) in memory")

    # --- Supervisor Agent ---
    log("Supervisor Agent: analysing question and routing to specialist...")
    routing_messages = [SystemMessage(content=SUPERVISOR_SYSTEM)] + history + [HumanMessage(content=query)]
    try:
        route: RouteDecision = llm.with_structured_output(RouteDecision).invoke(routing_messages)
        destination = route.destination
        log(f"Supervisor → {destination} | reason: {route.reasoning}")
    except Exception as exc:
        print(f"[orchestrator] Supervisor structured output failed: {exc}", flush=True)
        field_keywords = [
            "number", "holder", "date", "premium", "limit", "exclusion", "type", "who",
            "expire", "expir", "expiry", "start", "end", "when", "cost", "price",
            "coverage type", "policyholder", "policy number", "benefit", "maximum",
        ]
        destination = (
            "extraction_agent"
            if any(k in query.lower() for k in field_keywords)
            else "retrieval_agent"
        )
        log(f"Supervisor fallback (keyword) → {destination}")

    # Correction: override to extraction_agent if query clearly asks for a specific field
    # (Supervisor sometimes misclassifies short follow-up questions)
    _field_triggers = [
        "expire", "expir", "expiry", "end date", "start date", "effective date",
        "policy number", "policy no", "policyholder", "who is insured", "who is covered",
        "premium", "how much", "coverage limit", "maximum benefit", "what type",
        "coverage type", "what exclusion", "key exclusion",
    ]
    if destination == "retrieval_agent" and any(k in query.lower() for k in _field_triggers):
        destination = "extraction_agent"
        log("Supervisor correction: field keyword detected → overriding to extraction_agent")

    # Build conversation context for the answer step
    history_context = ""
    if history:
        recent = history[-4:]
        history_context = "\n\nConversation context:\n"
        for msg in recent:
            role = "User" if isinstance(msg, HumanMessage) else "Assistant"
            history_context += f"{role}: {msg.content}\n"

    # --- Specialist Agent: call tool directly, then generate answer ---
    if destination == "retrieval_agent":
        log("Retrieval Agent: calling hybrid_search (BM25 + ChromaDB + RRF)...")
        tool_result = hybrid_search.invoke({"query": query})
        answer_system = RETRIEVAL_ANSWER_SYSTEM + history_context
        log("Retrieval Agent: generating answer from retrieved passages...")
    else:
        log("Extraction Agent: calling structured_extract (Pydantic schema)...")
        tool_result = structured_extract.invoke({"field_name": query})
        answer_system = EXTRACTION_ANSWER_SYSTEM + history_context
        log("Extraction Agent: generating answer from extracted data...")

    # LLM reads the tool result and writes the final answer
    answer_messages: list[BaseMessage] = [
        SystemMessage(content=answer_system),
        HumanMessage(content=f"Question: {query}\n\nData from document:\n{tool_result}\n\nAnswer the question above.")
    ]
    response = llm.invoke(answer_messages)
    answer = response.content if isinstance(response, AIMessage) else str(response.content)

    source_chunks, page_refs = _parse_tool_result(tool_result)
    log(f"Retrieved {len(source_chunks)} source chunk(s)")
    log(f"Answer generated by: {destination}")
    log("Done")

    add_exchange(session_id, query, answer, destination)

    if not source_chunks:
        source_chunks = ["Source content retrieved from document index."]
        page_refs = [1]

    return {
        "answer": answer,
        "agent_used": destination,
        "source_chunks": source_chunks,
        "page_refs": page_refs,
        "steps": steps if steps is not None else [],
        "session_id": session_id,
    }
