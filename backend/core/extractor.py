import os
import json
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from pydantic import BaseModel, Field

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

SYSTEM_PROMPT = """\
You are an expert consumer finance contract analyst at Aman Fintech Egypt.
You are given raw text extracted directly from an installment purchase contract or loan agreement.

Your task is to extract EXACTLY 8 fields from the text below. Read every line carefully.

IMPORTANT INSTRUCTIONS:
- Look for labels like: "Contract Number:", "Customer Name:", "Product:", "Total Amount:", "Monthly Installment:", "Duration:", "Profit Rate:", "Conditions:"
- These labels are followed directly by the value on the same line or the next line
- Copy the value EXACTLY as it appears in the document
- Only return "Not specified" if the field is truly absent from the document
- For key_conditions: list any penalties, fees, or obligations explicitly stated
"""


class ContractData(BaseModel):
    contract_number: str = Field(description="The unique contract/agreement identifier exactly as shown")
    customer_name: str = Field(description="Full name of the customer/borrower exactly as shown")
    product_financed: str = Field(description="The product or service being financed e.g. Samsung TV, Toyota Car, Furniture Set")
    total_amount: str = Field(description="Total financed/loan amount with currency symbol e.g. EGP 25,000")
    monthly_installment: str = Field(description="Monthly repayment installment amount with currency e.g. EGP 1,200/month")
    duration_months: str = Field(description="Loan/contract duration in months e.g. 24 months")
    profit_rate: str = Field(description="Annual or monthly profit/interest rate as stated e.g. 2.5% per month flat")
    key_conditions: list[str] = Field(description="List of key contract conditions, penalties, fees, or obligations")


def _build_full_context(all_chunks: list[Document]) -> str:
    sorted_chunks = sorted(all_chunks, key=lambda c: c.metadata.get("page_number", 99))
    parts = []
    current_page = None
    for chunk in sorted_chunks:
        page = chunk.metadata.get("page_number", "?")
        if page != current_page:
            parts.append(f"\n\n===== PAGE {page} =====")
            current_page = page
        parts.append(chunk.page_content)
    return "\n".join(parts)


def extract_policy_data(
    retriever,
    steps: list[str] | None = None,
    all_chunks: list[Document] | None = None,
) -> ContractData:
    """Extract contract fields using full document text with page 1 always first."""

    def log(msg: str) -> None:
        print(f"[extractor] {msg}", flush=True)
        if steps is not None:
            steps.append(msg)

    log("Building extraction context from all indexed chunks...")

    if all_chunks:
        log(f"Using {len(all_chunks)} cached chunks with page metadata")
        context = _build_full_context(all_chunks)
        if len(context) > 6000:
            context = context[:6000] + "\n...[truncated]"
        log(f"Context built: {len(context)} characters (page 1 first)")
    else:
        log("No cached chunks available — falling back to semantic retrieval")
        docs = retriever.invoke(
            "contract number customer name product financed total amount monthly installment duration profit rate conditions"
        )
        log(f"Retrieved {len(docs)} chunks via semantic search")
        context = "\n\n".join(
            f"[PAGE {d.metadata.get('page_number', '?')}]\n{d.page_content}"
            for d in docs
        )

    llm = ChatOllama(model="llama3.1:latest", temperature=0, base_url=OLLAMA_BASE_URL)

    log("Sending to llama3.1 — structured output mode (tool-calling)...")
    try:
        structured_llm = llm.with_structured_output(ContractData)
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", (
                "Here is the full consumer finance contract text. "
                "PAGE 1 (the contract header) is shown first — "
                "it contains the contract number, customer name, and key financial terms.\n\n"
                "{context}\n\n"
                "Extract all 8 fields exactly as they appear in the text above."
            )),
        ])
        result = (prompt | structured_llm).invoke({"context": context})
        populated = len([
            v for v in result.model_dump().values()
            if v and v not in ("Not specified", [])
        ])
        log(f"[OK] Extraction complete - {populated}/8 fields populated")
        return result
    except Exception as e:
        log(f"Structured output failed: {e} - trying JSON fallback")

    try:
        json_llm = ChatOllama(
            model="llama3.1:latest", temperature=0, format="json", base_url=OLLAMA_BASE_URL
        )
        json_prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT + (
                '\n\nReturn ONLY a JSON object with exactly these keys: '
                'contract_number, customer_name, product_financed, total_amount, '
                'monthly_installment, duration_months, profit_rate, '
                'key_conditions (an array of strings). '
                'Use "Not specified" only if the field is truly absent.'
            )),
            ("human", (
                "Full contract text (page 1 is first):\n\n{context}\n\n"
                "Return the JSON object now:"
            )),
        ])
        response = (json_prompt | json_llm).invoke({"context": context})
        raw = json.loads(response.content)
        conditions = raw.get("key_conditions", [])
        if isinstance(conditions, str):
            conditions = [conditions]
        result = ContractData(
            contract_number=raw.get("contract_number", "Not specified"),
            customer_name=raw.get("customer_name", "Not specified"),
            product_financed=raw.get("product_financed", "Not specified"),
            total_amount=raw.get("total_amount", "Not specified"),
            monthly_installment=raw.get("monthly_installment", "Not specified"),
            duration_months=raw.get("duration_months", "Not specified"),
            profit_rate=raw.get("profit_rate", "Not specified"),
            key_conditions=conditions,
        )
        populated = len([
            v for v in result.model_dump().values()
            if v and v not in ("Not specified", [])
        ])
        log(f"[OK] JSON fallback complete - {populated}/8 fields populated")
        return result
    except Exception as e:
        log(f"[ERROR] Both extraction methods failed: {e}")
        return ContractData(
            contract_number="Not specified",
            customer_name="Not specified",
            product_financed="Not specified",
            total_amount="Not specified",
            monthly_installment="Not specified",
            duration_months="Not specified",
            profit_rate="Not specified",
            key_conditions=[],
        )
