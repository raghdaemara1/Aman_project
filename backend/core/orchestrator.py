"""
Multi-agent orchestrator using LangGraph StateGraph.

Architecture:
  User query + session history
        ↓
  SupervisorAgent (llama3.1, structured output)
        ↓ routes to
  ┌─────────────────────────────┐
  │  RetrievalAgent             │  ExtractionAgent
  │  tool: hybrid_search        │  tool: structured_extract
  │  open questions             │  field lookups
  └─────────────────────────────┘
        ↓
  Answer + source chunks + agent_used
        ↓
  Saved to session memory
"""

import os
from typing import TypedDict, Annotated, Literal
import operator

from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_ollama import ChatOllama
from pydantic import BaseModel

from tools.search_tool import hybrid_search
from tools.extract_tool import structured_extract
from core.memory import get_messages, add_exchange

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

SUPERVISOR_SYSTEM = (
    "You are an orchestrator for an insurance document AI system. "
    "Route the user question to the correct specialist agent:\n"
    "- extraction_agent: specific field lookups — policy number, policyholder, dates, "
    "premium, coverage limit, exclusions, coverage type\n"
    "- retrieval_agent: open questions — what does the policy say about X, explain coverage, "
    "what is covered, summarise a section, any general inquiry\n"
    "Use conversation context to classify follow-up questions."
)

RETRIEVAL_SYSTEM = (
    "You are a Retrieval Specialist for insurance documents. "
    "Use hybrid_search to find relevant passages and answer the user's question. "
    "Cite the page number when possible. Be concise and factual. "
    "Do not hallucinate — if the answer is not in the document, say so."
)

EXTRACTION_SYSTEM = (
    "You are an Extraction Specialist for insurance documents. "
    "Use structured_extract to look up specific policy fields. "
    "The policy number is the value next to 'Policy Number:' — NOT the GAP form code. "
    "Return the exact extracted value. Be precise."
)


class RouteDecision(BaseModel):
    destination: Literal["retrieval_agent", "extraction_agent"]
    reasoning: str


class OrchestratorState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]
    session_id: str
    agent_used: str
    steps: list[str]
    source_chunks: list[str]
    page_refs: list[int]


def _parse_tool_output(messages: list[BaseMessage]) -> tuple[list[str], list[int]]:
    """Extract source chunks and page refs from ToolMessage observations."""
    source_chunks: list[str] = []
    page_refs: list[int] = []
    for msg in messages:
        if isinstance(msg, ToolMessage) and isinstance(msg.content, str):
            current_lines: list[str] = []
            current_page: int | None = None
            for line in msg.content.split("\n"):
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
            break
    return source_chunks, page_refs


def run_orchestrator(query: str, session_id: str, steps: list[str] | None = None) -> dict:
    """
    Run the multi-agent orchestrator.
    1. Supervisor classifies the question.
    2. Routes to RetrievalAgent (hybrid_search) or ExtractionAgent (structured_extract).
    3. Saves exchange to session memory.
    Returns answer, agent_used, source_chunks, page_refs, steps, session_id.
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

    # Supervisor: classify the question
    log("Supervisor Agent: analysing question and routing to specialist...")
    routing_messages = [SystemMessage(content=SUPERVISOR_SYSTEM)] + history + [HumanMessage(content=query)]
    try:
        route: RouteDecision = llm.with_structured_output(RouteDecision).invoke(routing_messages)
        destination = route.destination
        log(f"Supervisor → {destination} | reason: {route.reasoning}")
    except Exception as exc:
        print(f"[orchestrator] Supervisor structured output failed: {exc}", flush=True)
        # Keyword fallback
        field_keywords = ["number", "holder", "date", "premium", "limit", "exclusion", "type", "who"]
        destination = (
            "extraction_agent"
            if any(k in query.lower() for k in field_keywords)
            else "retrieval_agent"
        )
        log(f"Supervisor fallback (keyword) → {destination}")

    # Build history context string for sub-agent system prompt
    history_context = ""
    if history:
        recent = history[-4:]  # last 2 exchanges
        history_context = "\n\nPrevious conversation context:\n"
        for msg in recent:
            role = "User" if isinstance(msg, HumanMessage) else "Assistant"
            history_context += f"{role}: {msg.content}\n"

    # Run the specialist agent
    if destination == "retrieval_agent":
        log("Retrieval Agent: running hybrid_search (BM25 + ChromaDB + RRF)...")
        system = RETRIEVAL_SYSTEM + history_context
        agent = create_react_agent(llm, [hybrid_search], prompt=system)
    else:
        log("Extraction Agent: running structured_extract (Pydantic schema)...")
        system = EXTRACTION_SYSTEM + history_context
        agent = create_react_agent(llm, [structured_extract], prompt=system)

    agent_result = agent.invoke({"messages": [HumanMessage(content=query)]})
    agent_messages: list[BaseMessage] = agent_result.get("messages", [])

    # Extract final answer
    answer = "I could not find an answer in the document."
    for msg in reversed(agent_messages):
        if isinstance(msg, AIMessage) and msg.content:
            answer = msg.content
            break

    source_chunks, page_refs = _parse_tool_output(agent_messages)
    log(f"Retrieved {len(source_chunks)} source chunk(s)")
    log(f"Answer generated by: {destination}")
    log("Done")

    # Persist to session memory
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
