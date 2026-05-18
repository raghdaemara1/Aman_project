import os
import re
import json
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from pydantic import BaseModel, Field

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

SYSTEM_PROMPT = """\
You are an expert insurance document analyst.
You are given raw text extracted directly from an insurance policy document.

Your task is to extract EXACTLY 8 fields from the text below. Read every line carefully.

IMPORTANT INSTRUCTIONS:
- Look for labels like: "Policy Number:", "Policyholder:", "Policy Holder:", "Coverage Type:", "Effective Date:", "Expiration Date:", "Premium:", "Coverage Limit:", "Exclusions:"
- These labels are followed directly by the value on the same line or the next line
- Copy the value EXACTLY as it appears in the document
- Only return "Not specified" if the field is truly absent from the document
- For key_exclusions: list any conditions, losses, or situations explicitly NOT covered

CRITICAL RULES:
- policy_number: find the line that starts with "Policy Number:" and copy ONLY its value.
  Do NOT use form numbers, document codes, or GAP numbers printed at the bottom of the page.
  Form/document numbers (e.g. "GAP 26932-FL") are NOT the policy number.
- policy_holder: find the line that starts with "Policyholder:" or "Policy Holder:" — this is the insured person or organization name, NOT the insurance company name.
"""


class PolicyData(BaseModel):
    policy_number: str = Field(description="Value on the line labelled 'Policy Number:' only — e.g. US151741. Never use GAP numbers or form codes.")
    policy_holder: str = Field(description="Full name of the policyholder or insured entity exactly as shown — NOT the insurance company name")
    coverage_type: str = Field(description="Type of insurance coverage e.g. Accident Only, Health, Comprehensive")
    start_date: str = Field(description="Policy effective/start date e.g. August 1, 2013")
    end_date: str = Field(description="Policy expiration/end date e.g. August 1, 2014")
    premium_amount: str = Field(description="Premium amount as stated in the document")
    coverage_limit: str = Field(description="Maximum coverage or benefit amount as stated")
    key_exclusions: list[str] = Field(description="List of things NOT covered or key conditions and limitations")


def _scan_label(text: str, labels: list[str]) -> str | None:
    """Scan text for 'Label: value' pattern and return the value if found."""
    for label in labels:
        match = re.search(rf"{re.escape(label)}\s*:?\s*([^\n]+)", text, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            if value:
                return value
    return None


def _regex_override(result: "PolicyData", context: str) -> "PolicyData":
    """Override LLM-extracted fields with regex results where labels are clearly present."""
    overrides: dict = {}

    v = _scan_label(context, ["Policy Number", "Policy No", "Policy #"])
    if v:
        overrides["policy_number"] = v

    # Do NOT include generic "Insured" — it appears in definition text with wrong meaning
    v = _scan_label(context, ["Policyholder", "Policy Holder", "Named Insured"])
    if v:
        overrides["policy_holder"] = v

    v = _scan_label(context, ["Policy Effective Date", "Effective Date", "Issue Date"])
    if v:
        overrides["start_date"] = v

    v = _scan_label(context, ["Policy Expiration Date", "Expiration Date", "Expiry Date"])
    if v:
        overrides["end_date"] = v

    v = _scan_label(context, ["MAXIMUM BENEFIT AMOUNT", "Maximum Benefit Amount", "Coverage Limit", "Benefit Limit"])
    if v:
        overrides["coverage_limit"] = v

    v = _scan_label(context, ["PREMIUM", "Premium Amount", "Annual Premium", "Monthly Premium"])
    if v:
        overrides["premium_amount"] = v

    if overrides:
        return result.model_copy(update=overrides)
    return result


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
) -> PolicyData:
    """Extract policy fields using full document text with page 1 always first."""

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
            "policy number policyholder coverage type effective date expiration date premium coverage limit exclusions"
        )
        log(f"Retrieved {len(docs)} chunks via semantic search")
        context = "\n\n".join(
            f"[PAGE {d.metadata.get('page_number', '?')}]\n{d.page_content}"
            for d in docs
        )

    llm = ChatOllama(model="llama3.1:latest", temperature=0, base_url=OLLAMA_BASE_URL)

    log("Sending to llama3.1 — structured output mode (tool-calling)...")
    try:
        structured_llm = llm.with_structured_output(PolicyData)
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", (
                "Here is the full insurance policy document text. "
                "PAGE 1 (the policy header) is shown first — "
                "it contains the policy number, policyholder, and key policy terms.\n\n"
                "{context}\n\n"
                "Extract all 8 fields exactly as they appear in the text above."
            )),
        ])
        result = (prompt | structured_llm).invoke({"context": context})
        result = _regex_override(result, context)
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
                'policy_number, policy_holder, coverage_type, start_date, '
                'end_date, premium_amount, coverage_limit, '
                'key_exclusions (an array of strings). '
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
        result = _regex_override(result, context)
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
