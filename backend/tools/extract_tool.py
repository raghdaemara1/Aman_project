from langchain_core.tools import tool
from core.vectorstore import get_retriever
from core.extractor import extract_policy_data


@tool
def structured_extract(field_name: str) -> str:
    """Use this tool when the user asks for specific contract fields like contract number,
    customer name, product financed, total amount, monthly installment, loan duration,
    profit rate, or key conditions and penalties.
    Input should be the field name or a description of the specific data being requested."""

    retriever = get_retriever(k=10)
    contract = extract_policy_data(retriever)

    normalized = field_name.lower().strip()

    field_map: dict[str, str] = {
        "contract_number": contract.contract_number,
        "contract number": contract.contract_number,
        "number": contract.contract_number,
        "contract id": contract.contract_number,
        "agreement number": contract.contract_number,
        "customer_name": contract.customer_name,
        "customer name": contract.customer_name,
        "customer": contract.customer_name,
        "borrower": contract.customer_name,
        "name": contract.customer_name,
        "client": contract.customer_name,
        "product_financed": contract.product_financed,
        "product financed": contract.product_financed,
        "product": contract.product_financed,
        "item": contract.product_financed,
        "goods": contract.product_financed,
        "what was financed": contract.product_financed,
        "total_amount": contract.total_amount,
        "total amount": contract.total_amount,
        "loan amount": contract.total_amount,
        "financed amount": contract.total_amount,
        "total": contract.total_amount,
        "amount": contract.total_amount,
        "monthly_installment": contract.monthly_installment,
        "monthly installment": contract.monthly_installment,
        "installment": contract.monthly_installment,
        "monthly payment": contract.monthly_installment,
        "repayment": contract.monthly_installment,
        "duration_months": contract.duration_months,
        "duration months": contract.duration_months,
        "duration": contract.duration_months,
        "term": contract.duration_months,
        "months": contract.duration_months,
        "loan term": contract.duration_months,
        "profit_rate": contract.profit_rate,
        "profit rate": contract.profit_rate,
        "interest rate": contract.profit_rate,
        "rate": contract.profit_rate,
        "interest": contract.profit_rate,
        "profit": contract.profit_rate,
        "key_conditions": ", ".join(contract.key_conditions) if contract.key_conditions else "Not specified",
        "key conditions": ", ".join(contract.key_conditions) if contract.key_conditions else "Not specified",
        "conditions": ", ".join(contract.key_conditions) if contract.key_conditions else "Not specified",
        "penalties": ", ".join(contract.key_conditions) if contract.key_conditions else "Not specified",
        "fees": ", ".join(contract.key_conditions) if contract.key_conditions else "Not specified",
        "terms": ", ".join(contract.key_conditions) if contract.key_conditions else "Not specified",
    }

    for key, value in field_map.items():
        if key in normalized or normalized in key:
            return value or "Not specified"

    conditions_str = (
        ", ".join(contract.key_conditions) if contract.key_conditions else "Not specified"
    )
    return (
        f"Contract Number: {contract.contract_number}\n"
        f"Customer Name: {contract.customer_name}\n"
        f"Product Financed: {contract.product_financed}\n"
        f"Total Amount: {contract.total_amount}\n"
        f"Monthly Installment: {contract.monthly_installment}\n"
        f"Duration: {contract.duration_months}\n"
        f"Profit Rate: {contract.profit_rate}\n"
        f"Key Conditions: {conditions_str}"
    )
