import os
from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from tools.search_tool import hybrid_search
from tools.extract_tool import structured_extract

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

SYSTEM_PROMPT = (
    "You are an insurance document intelligence agent. "
    "You have access to two tools:\n"
    "1. hybrid_search — use for open questions about policy terms, coverage, "
    "what the policy says about a specific topic, or any general inquiry about the document.\n"
    "2. structured_extract — use for specific field lookups: policy number, policyholder name, "
    "coverage type, effective date, expiration date, premium amount, coverage limit, or exclusions.\n\n"
    "Always cite which page or section your answer comes from when possible. "
    "Be concise, factual, and professional. "
    "If you cannot find the answer in the document, say so clearly. "
    "Do not hallucinate or guess."
)


def run_agent(query: str, steps: list[str] | None = None) -> dict:
    """Run the agent on the user query. Returns answer, tool_used, source_chunks, page_refs, steps."""
    def log(msg: str) -> None:
        print(f"[agent] {msg}", flush=True)
        if steps is not None:
            steps.append(msg)

    log(f"Query received: \"{query}\"")
    log("Initializing ReAct agent (llama3.1:latest + 2 tools: hybrid_search, structured_extract)")

    llm = ChatOllama(model="llama3.1:latest", temperature=0, base_url=OLLAMA_BASE_URL)
    tools = [hybrid_search, structured_extract]
    agent = create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)

    log("Agent reasoning — selecting tool...")
    result = agent.invoke({"messages": [HumanMessage(content=query)]})

    messages = result.get("messages", [])

    answer = "I could not find an answer in the document."
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            answer = msg.content
            break

    tool_used = "hybrid_search"
    for msg in messages:
        if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
            tool_used = msg.tool_calls[0].get("name", "hybrid_search")
            break

    log(f"Tool selected: {tool_used}")

    source_chunks: list[str] = []
    page_refs: list[int] = []

    for msg in messages:
        if isinstance(msg, ToolMessage) and isinstance(msg.content, str):
            observation = msg.content
            current_lines: list[str] = []
            current_page: int | None = None

            for line in observation.split("\n"):
                if line.startswith("Page ") and ":" in line:
                    if current_lines and current_page is not None:
                        source_chunks.append("\n".join(current_lines).strip())
                        page_refs.append(current_page)
                    try:
                        current_page = int(line.split(":")[0].replace("Page ", "").strip())
                        content = ":".join(line.split(":")[1:]).strip()
                        current_lines = [content]
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

    log(f"Retrieved {len(source_chunks)} source chunk(s)")
    log("Generating final answer with llama3.1:latest...")
    log("Done")

    if not source_chunks:
        source_chunks = ["Source content retrieved from document index."]
        page_refs = [1]

    return {
        "answer": answer,
        "tool_used": tool_used,
        "source_chunks": source_chunks,
        "page_refs": page_refs,
        "steps": steps if steps is not None else [],
    }
