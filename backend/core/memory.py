from collections import defaultdict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

# session_id → list of serialisable dicts so the frontend can read history
_sessions: dict[str, list[dict]] = defaultdict(list)


def get_history(session_id: str) -> list[dict]:
    return list(_sessions[session_id])


def get_messages(session_id: str) -> list[BaseMessage]:
    """Return conversation history as LangChain message objects."""
    result: list[BaseMessage] = []
    for entry in _sessions[session_id]:
        if entry["role"] == "human":
            result.append(HumanMessage(content=entry["content"]))
        else:
            result.append(AIMessage(content=entry["content"]))
    return result


def add_exchange(session_id: str, human: str, assistant: str, agent_used: str) -> None:
    _sessions[session_id].append({"role": "human", "content": human})
    _sessions[session_id].append({"role": "assistant", "content": assistant, "agent_used": agent_used})


def clear_session(session_id: str) -> None:
    _sessions.pop(session_id, None)
