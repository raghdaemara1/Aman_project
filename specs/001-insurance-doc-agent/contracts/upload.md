# Contract: POST /api/v1/upload

**Purpose**: Upload an insurance policy PDF, parse it into chunks, and index it in ChromaDB. Replaces any previously indexed document.

## Request

```
POST /api/v1/upload
Content-Type: multipart/form-data
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| file | File (PDF) | Yes | Must be `application/pdf`; max size unconstrained for v1 |

## Success Response

**HTTP 200**

```json
{
  "chunks_indexed": 42,
  "metadata": {
    "filename": "policy_document.pdf",
    "page_count": 5,
    "indexed_at": "2026-05-17T10:30:00Z"
  }
}
```

## Error Responses

| Status | Condition | Body |
|--------|-----------|------|
| 415 | Non-PDF file uploaded | `{ "detail": "Only PDF files are accepted." }` |
| 422 | PDF is corrupt or unreadable | `{ "detail": "Could not parse the PDF. The file may be corrupt or password-protected." }` |
| 500 | Unexpected server error | `{ "detail": "Internal server error." }` |

## Behavior Notes

- Previous document index is cleared before ingesting the new document (FR-003)
- Chunks are split at 500 tokens with 50-token overlap
- On success, subsequent calls to `/api/v1/ask` and `/api/v1/extract` operate on this document
