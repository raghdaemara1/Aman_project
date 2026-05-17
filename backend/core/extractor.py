import os
from langchain_ollama import ChatOllama
from langchain.prompts import ChatPromptTemplate
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


def extract_policy_data(retriever) -> PolicyData:
    """Retrieve all chunks, pass to LLM with structured output prompt, return PolicyData."""
    docs = retriever.get_relevant_documents(
        "policy number holder name coverage type start date expiry date premium exclusions"
    )
    context = "\n\n".join(doc.page_content for doc in docs)

    llm = ChatOllama(model="llama3.1:latest", temperature=0, base_url=OLLAMA_BASE_URL)
    parser = PydanticOutputParser(pydantic_object=PolicyData)

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT + "\n\n{format_instructions}"),
        ("human", "Document content:\n\n{context}\n\nExtract the policy data:"),
    ])

    chain = prompt | llm | parser

    try:
        return chain.invoke({
            "context": context,
            "format_instructions": parser.get_format_instructions(),
        })
    except Exception:
        # Fallback: with_structured_output JSON mode
        structured_llm = llm.with_structured_output(PolicyData)
        fallback_prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", "Document content:\n\n{context}\n\nExtract the policy data:"),
        ])
        return (fallback_prompt | structured_llm).invoke({"context": context})
