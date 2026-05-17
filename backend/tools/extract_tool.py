from langchain.tools import tool
from core.vectorstore import get_retriever
from core.extractor import extract_policy_data


@tool
def structured_extract(field_name: str) -> str:
    """Use this tool when the user asks for specific policy fields like policy number,
    expiry date, premium amount, holder name, coverage limit, or exclusions.
    Input should be the field name or a description of the specific data being requested."""

    retriever = get_retriever(k=10)
    policy = extract_policy_data(retriever)

    normalized = field_name.lower().strip()

    field_map: dict[str, str] = {
        "policy_number": policy.policy_number,
        "policy number": policy.policy_number,
        "number": policy.policy_number,
        "policy_holder": policy.policy_holder,
        "policy holder": policy.policy_holder,
        "holder": policy.policy_holder,
        "name": policy.policy_holder,
        "insured": policy.policy_holder,
        "coverage_type": policy.coverage_type,
        "coverage type": policy.coverage_type,
        "type": policy.coverage_type,
        "start_date": policy.start_date,
        "start date": policy.start_date,
        "start": policy.start_date,
        "issue date": policy.start_date,
        "end_date": policy.end_date,
        "end date": policy.end_date,
        "expiry": policy.end_date,
        "expiry date": policy.end_date,
        "expiration": policy.end_date,
        "expires": policy.end_date,
        "premium_amount": policy.premium_amount,
        "premium amount": policy.premium_amount,
        "premium": policy.premium_amount,
        "cost": policy.premium_amount,
        "coverage_limit": policy.coverage_limit,
        "coverage limit": policy.coverage_limit,
        "limit": policy.coverage_limit,
        "maximum": policy.coverage_limit,
        "key_exclusions": ", ".join(policy.key_exclusions) if policy.key_exclusions else "Not specified",
        "key exclusions": ", ".join(policy.key_exclusions) if policy.key_exclusions else "Not specified",
        "exclusions": ", ".join(policy.key_exclusions) if policy.key_exclusions else "Not specified",
        "excluded": ", ".join(policy.key_exclusions) if policy.key_exclusions else "Not specified",
        "not covered": ", ".join(policy.key_exclusions) if policy.key_exclusions else "Not specified",
    }

    for key, value in field_map.items():
        if key in normalized or normalized in key:
            return value or "Not specified"

    # Return all fields if no specific match found
    exclusions_str = (
        ", ".join(policy.key_exclusions) if policy.key_exclusions else "Not specified"
    )
    return (
        f"Policy Number: {policy.policy_number}\n"
        f"Policy Holder: {policy.policy_holder}\n"
        f"Coverage Type: {policy.coverage_type}\n"
        f"Start Date: {policy.start_date}\n"
        f"End Date: {policy.end_date}\n"
        f"Premium Amount: {policy.premium_amount}\n"
        f"Coverage Limit: {policy.coverage_limit}\n"
        f"Key Exclusions: {exclusions_str}"
    )
