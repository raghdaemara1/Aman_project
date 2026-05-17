# Contract: DELETE /api/v1/store

**Purpose**: Clear the current document index from ChromaDB. Called internally before each new upload; can also be called manually to reset state.

## Request

```
DELETE /api/v1/store
```

No request body.

## Success Response

**HTTP 200**

```json
{
  "cleared": true
}
```

## Error Responses

| Status | Condition | Body |
|--------|-----------|------|
| 500 | ChromaDB deletion failed | `{ "detail": "Failed to clear document store." }` |

## Behavior Notes

- Safe to call when no document is indexed (returns `{ "cleared": true }` with no error)
- After this call, `/api/v1/ask` and `/api/v1/extract` will return HTTP 409 until a new document is uploaded
- The `POST /api/v1/upload` endpoint calls this automatically before ingesting a new document
