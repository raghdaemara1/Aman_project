# Contract: POST /api/v1/extract

**Purpose**: Extract all eight structured policy fields from the indexed document in one operation. Returns a Pydantic-validated PolicyData object.

## Request

```
POST /api/v1/extract
Content-Type: application/json
```

No request body required.

## Success Response

**HTTP 200**

```json
{
  "policy_data": {
    "policy_number": "AMAN-2025-INS-004892",
    "policy_holder": "Ahmed Mohamed Hassan",
    "coverage_type": "Comprehensive Health Insurance",
    "start_date": "January 1, 2025",
    "end_date": "December 31, 2025",
    "premium_amount": "EGP 4,800 annually",
    "coverage_limit": "EGP 500,000 per year",
    "key_exclusions": [
      "Pre-existing conditions diagnosed before policy start date",
      "Cosmetic or elective procedures",
      "Dental and optical care",
      "Mental health treatment",
      "Injuries resulting from extreme sports",
      "Treatment outside Egypt unless emergency"
    ]
  }
}
```

| Field | Type | Missing value |
|-------|------|---------------|
| policy_number | string | `"Not specified"` |
| policy_holder | string | `"Not specified"` |
| coverage_type | string | `"Not specified"` |
| start_date | string | `"Not specified"` |
| end_date | string | `"Not specified"` |
| premium_amount | string | `"Not specified"` |
| coverage_limit | string | `"Not specified"` |
| key_exclusions | string[] | `[]` (empty array) |

## Error Responses

| Status | Condition | Body |
|--------|-----------|------|
| 409 | No document indexed | `{ "detail": "No document indexed. Please upload a PDF first." }` |
| 500 | LLM or parsing error | `{ "detail": "Extraction error: <reason>" }` |

## Behavior Notes

- All eight fields are always present in the response — never omitted
- String fields use `"Not specified"` when the document does not contain that information (FR-011)
- `key_exclusions` is an array of strings; frontend renders as a bullet list
- This endpoint bypasses the agent — it calls the extraction chain directly
