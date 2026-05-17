import os
import json
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from pydantic import BaseModel, Field

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

SYSTEM_PROMPT = """\
You are an expert insurance document analyst. You are given raw text extracted directly from an insurance policy PDF.

Your task is to extract EXACTLY 8 fields from the text below. Read every line carefully.

IMPORTANT INSTRUCTIONS:
- Look for labels like: "Policy Number:", "Policyholder:", "Policy Effective Date:", "Policy Expiration Date:", "Named Insured:", "Insured:"
- These labels are followed directly by the value on the same line or the next line
- Copy the value EXACTLY as it appears in the document
- Only return "Not specified" if the field is truly absent from the document
- For key_exclusions: list any conditions, events, or categories explicitly NOT covered
"""


class PolicyData(BaseModel):
    policy_number: str = Field(description="The unique policy identifier/number exactly as shown, e.g. US151741")
    policy_holder: str = Field(description="Full name of the insured / policyholder / named insured exactly as shown")
    coverage_type: str = Field(description="Type of insurance coverage e.g. Accident Only Policy, Homeowners HO-3")
    start_date: str = Field(description="Policy effective / start date exactly as written e.g. August 1, 2013")
    end_date: str = Field(description="Policy expiration / end date exactly as written e.g. August 1, 2014")
    premium_amount: str = Field(description="Monthly or annual premium amount with currency symbol")
    coverage_limit: str = Field(description="Maximum benefit or coverage amount with currency symbol")
    key_exclusions: list[str] = Field(description="List of things explicitly NOT covered by this policy")


def _build_full_context(all_chunks: list[Document]) -> str:
    """
    Build context by sorting chunks by page number and concatenating.
    Page 1 (declarations) is ALWAYS first.
    """
    # Sort by page number so page 1 is first
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
) -> PolicyData:
    """Extract policy fields using full document text with page 1 always first."""

    def log(msg: str) -> None:
        print(f"[extractor] {msg}", flush=True)
        if steps is not None:
            steps.append(msg)

    log("Building extraction context from all indexed chunks...")

    # Strategy A: Use all_chunks directly (best — preserves page metadata)
    if all_chunks:
        log(f"Using {len(all_chunks)} cached chunks with page metadata")
        context = _build_full_context(all_chunks)
        # Trim to ~6000 chars to avoid overloading the context window
        if len(context) > 6000:
            context = context[:6000] + "\n...[truncated]"
        log(f"Context built: {len(context)} characters (page 1 first)")
    else:
        # Strategy B: Fallback — semantic retrieval (less reliable)
        log("No cached chunks available — falling back to semantic retrieval")
        docs = retriever.invoke(
            "policy number policyholder insured name coverage type effective date expiration date premium exclusions"
        )
        log(f"Retrieved {len(docs)} chunks via semantic search")
        context = "\n\n".join(
            f"[PAGE {d.metadata.get('page_number', '?')}]\n{d.page_content}"
            for d in docs
        )

    llm = ChatOllama(model="llama3.1:latest", temperature=0, base_url=OLLAMA_BASE_URL)

    # Primary: structured output via tool-calling (most reliable)
    log("Sending to llama3.1 — structured output mode (tool-calling)...")
    try:
        structured_llm = llm.with_structured_output(PolicyData)
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", (
                "Here is the full insurance policy document text. "
                "PAGE 1 (the declarations page) is shown first — "
                "it contains the policy number, policyholder name, and dates.\n\n"
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

    # Fallback: force raw JSON output
    try:
        json_llm = ChatOllama(
            model="llama3.1:latest", temperature=0, format="json", base_url=OLLAMA_BASE_URL
        )
        json_prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT + (
                '\n\nReturn ONLY a JSON object with exactly these keys: '
                'policy_number, policy_holder, coverage_type, start_date, end_date, '
                'premium_amount, coverage_limit, key_exclusions (an array of strings). '
                'Use "Not specified" only if the field is truly absent.'
            )),
            ("human", (
                "Full policy text (page 1 is first):\n\n{context}\n\n"
                "Return the JSON object now:"
            )),
        ])
        response = (json_prompt | json_llm).invoke({"context": context})
        raw = json.loads(response.content)
        exclusions = raw.get("key_exclusions", [])
        if isinstance(exclusions, str):
            exclusions = [exclusions]
        result = PolicyData(
            policy_number=raw.get("policy_number", "Not specified"),
            policy_holder=raw.get("policy_holder", "Not specified"),
            coverage_type=raw.get("coverage_type", "Not specified"),
            start_date=raw.get("start_date", "Not specified"),
            end_date=raw.get("end_date", "Not specified"),
            premium_amount=raw.get("premium_amount", "Not specified"),
            coverage_limit=raw.get("coverage_limit", "Not specified"),
            key_exclusions=exclusions,
        )
        populated = len([
            v for v in result.model_dump().values()
            if v and v not in ("Not specified", [])
        ])
        log(f"[OK] JSON fallback complete - {populated}/8 fields populated")
        return result
    except Exception as e:
        log(f"[ERROR] Both extraction methods failed: {e}")
        return PolicyData(
            policy_number="Not specified",
            policy_holder="Not specified",
            coverage_type="Not specified",
            start_date="Not specified",
            end_date="Not specified",
            premium_amount="Not specified",
            coverage_limit="Not specified",
            key_exclusions=[],
        )
