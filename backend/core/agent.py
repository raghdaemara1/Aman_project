import os
from langchain_ollama import ChatOllama
from langchain.agents import create_react_agent, AgentExecutor
from langchain.prompts import PromptTemplate
from tools.search_tool import hybrid_search
from tools.extract_tool import structured_extract

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

REACT_PROMPT = PromptTemplate.from_template(
    """You are an insurance document intelligence agent for AMAN Holding.
You have access to the following tools:

{tools}

Use the following format EXACTLY:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Rules:
- Use hybrid_search for open questions about policy content, coverage details, or general inquiries
- Use structured_extract for specific field lookups: policy number, expiry date, premium, holder name, exclusions, coverage limit
- Always cite which page your answer comes from when possible
- Be concise, factual, and professional
- If you cannot find the answer in the document, state that clearly in the Final Answer
- Do NOT hallucinate or guess information not present in the document

Begin!

Question: {input}
Thought:{agent_scratchpad}"""
)


def run_agent(query: str) -> dict:
    """Run the ReAct agent on the user query.

    Returns:
        answer: str, tool_used: str, source_chunks: list[str], page_refs: list[int]
    """
    llm = ChatOllama(model="llama3.1:latest", temperature=0, base_url=OLLAMA_BASE_URL)
    tools = [hybrid_search, structured_extract]

    agent = create_react_agent(llm, tools, REACT_PROMPT)
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        return_intermediate_steps=True,
        handle_parsing_errors=True,
        max_iterations=6,
    )

    result = executor.invoke({"input": query})

    answer = result.get("output", "I could not find an answer in the document.")
    intermediate_steps = result.get("intermediate_steps", [])

    tool_used = "hybrid_search"
    source_chunks: list[str] = []
    page_refs: list[int] = []

    if intermediate_steps:
        action, observation = intermediate_steps[0]
        tool_used = action.tool

        if observation and isinstance(observation, str):
            current_lines: list[str] = []
            current_page: int | None = None

            for line in observation.split("\n"):
                if line.startswith("Page ") and ":" in line:
                    # Save previous chunk
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

    if not source_chunks:
        source_chunks = ["Source content retrieved from document index."]
        page_refs = [1]

    return {
        "answer": answer,
        "tool_used": tool_used,
        "source_chunks": source_chunks,
        "page_refs": page_refs,
    }
