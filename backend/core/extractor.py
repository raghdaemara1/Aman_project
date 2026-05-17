import os
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

SYSTEM_PROMPT = (
    "You are an insurance document analyst. Extract the structured policy "
    "information from the provided document chunks. If a field is not found, "
    'return "Not specified". Be precise and factual — only extract what is '
    "explicitly stated in the document."
)


class PolicyData(BaseModel):
    policy_number: str = Field(description="The unique policy identifier")
    policy_holder: str = Field(description="Full name of the policy holder")
    coverage_type: str = Field(description="Type of insurance coverage")
    start_date: str = Field(description="Policy start date")
    end_date: str = Field(description="Policy expiry or end date")
    premium_amount: str = Field(description="Monthly or annual premium amount")
    coverage_limit: str = Field(description="Maximum coverage amount")
    key_exclusions: list[str] = Field(description="List of things NOT covered by this policy")


def extract_policy_data(retriever, steps: list[str] | None = None) -> PolicyData:
    """Retrieve chunks, send to LLM with Pydantic schema, return structured PolicyData."""
    def log(msg: str) -> None:
        print(f"[extractor] {msg}", flush=True)
        if steps is not None:
            steps.append(msg)

    log("Retrieving top-10 chunks from ChromaDB...")
    docs = retriever.invoke(
        "policy number holder name coverage type start date expiry date premium exclusions"
    )
    log(f"Retrieved {len(docs)} chunks ({sum(len(d.page_content) for d in docs)} chars of context)")

    context = "\n\n".join(doc.page_content for doc in docs)

    llm = ChatOllama(model="llama3.1:latest", temperature=0, base_url=OLLAMA_BASE_URL)
    parser = PydanticOutputParser(pydantic_object=PolicyData)

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT + "\n\n{format_instructions}"),
        ("human", "Document content:\n\n{context}\n\nExtract the policy data:"),
    ])

    chain = prompt | llm | parser

    log("Sending to llama3.1:latest with Pydantic schema (8 fields)...")
    try:
        result = chain.invoke({
            "context": context,
            "format_instructions": parser.get_format_instructions(),
        })
        log("Pydantic parser: structured output parsed successfully")
        log(f"Extraction complete — {len([f for f in result.model_dump().values() if f and f != 'Not specified'])} / 8 fields populated")
        return result
    except Exception:
        log("Pydantic parser failed — falling back to with_structured_output mode")
        structured_llm = llm.with_structured_output(PolicyData)
        fallback_prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", "Document content:\n\n{context}\n\nExtract the policy data:"),
        ])
        result = (fallback_prompt | structured_llm).invoke({"context": context})
        log("Fallback extraction complete")
        return result
