# Contract: POST /api/v1/ask

**Purpose**: Submit a natural language question about the indexed document. The ReAct agent selects a tool, retrieves relevant content, and returns a sourced answer.

## Request

```
POST /api/v1/ask
Content-Type: application/json
```

```json
{
  "query": "What procedures are excluded from coverage?"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| query | string | Yes | Non-empty natural language question |

## Success Response

**HTTP 200**

```json
{
  "answer": "The policy excludes cosmetic procedures, dental and optical care, mental health treatment, and injuries from extreme sports.",
  "tool_used": "hybrid_search",
  "source_chunks": [
    "Exclusions: Pre-existing conditions diagnosed before policy start date. Cosmetic or elective procedures. Dental and optical care..."
  ],
  "page_refs": [2]
}
```

| Field | Type | Notes |
|-------|------|-------|
| answer | string | Final agent answer; states "I cannot find this information" if not found |
| tool_used | `"hybrid_search"` \| `"structured_extract"` | Which tool the agent selected |
| source_chunks | string[] | Raw text of chunks used; parallel with `page_refs` |
| page_refs | integer[] | Page numbers for each source chunk; parallel with `source_chunks` |

## Error Responses

| Status | Condition | Body |
|--------|-----------|------|
| 400 | Empty query string | `{ "detail": "Query cannot be empty." }` |
| 409 | No document indexed yet | `{ "detail": "No document indexed. Please upload a PDF first." }` |
| 500 | LLM or agent error | `{ "detail": "Agent error: <reason>" }` |

## Behavior Notes

- Agent uses `hybrid_search` for open-ended questions about policy content (combines BM25 keyword matching + ChromaDB vector similarity, merged via Reciprocal Rank Fusion)
- Agent uses `structured_extract` for specific field lookups (policy number, expiry date, etc.)
- `source_chunks` and `page_refs` are always non-empty arrays on HTTP 200
- Agent MUST NOT hallucinate; if uncertain, answer field explains this explicitly
