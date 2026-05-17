# Data Model: Insurance Document Intelligence Agent

**Phase 1 Output** | Branch: `001-insurance-doc-agent` | Date: 2026-05-17

---

## Entities

### Document (runtime state, not persisted as a record)

Represents the currently active insurance policy PDF.

| Field | Type | Notes |
|-------|------|-------|
| filename | str | Original uploaded filename |
| page_count | int | Number of pages extracted by unstructured |
| chunk_count | int | Number of chunks stored in ChromaDB after splitting |
| indexed_at | datetime | Timestamp of successful ingestion |

**Lifecycle**: Created on upload → replaces any previous document → survives backend restarts (via ChromaDB persistence) · Cleared when a new upload arrives.

**Stored where**: Chunk data in ChromaDB. Document-level metadata (filename, page_count, chunk_count) returned from `/api/v1/upload`; not persisted separately.

---

### Chunk (persisted in ChromaDB)

One text segment from the document after splitting.

| Field | Type | Notes |
|-------|------|-------|
| content | str | Raw text of the chunk (≤ 500 tokens) |
| page_number | int | Source page from unstructured element metadata |
| chunk_index | int | Sequential index within the document (0-based) |
| source | str | Original filename |

**Identity**: ChromaDB assigns a UUID per chunk. No application-level ID needed.

**Embedding**: `nomic-embed-text:latest` via Ollama, stored in ChromaDB alongside the chunk.

---

### PolicyData (Pydantic v2 schema, returned by `/api/v1/extract`)

The structured extraction output. All fields are `str`; missing values use `"Not specified"`.

```python
class PolicyData(BaseModel):
    policy_number:   str = Field(description="Unique policy identifier")
    policy_holder:   str = Field(description="Full name of the policy holder")
    coverage_type:   str = Field(description="Type of insurance coverage")
    start_date:      str = Field(description="Policy start date")
    end_date:        str = Field(description="Policy expiry or end date")
    premium_amount:  str = Field(description="Monthly or annual premium amount")
    coverage_limit:  str = Field(description="Maximum coverage amount")
    key_exclusions:  list[str] = Field(description="Things NOT covered by this policy")
```

**Validation rule**: LLM MUST return `"Not specified"` (exact string) for any field not found in the document — never `null`, never an empty string, never a hallucinated value.

---

### AgentResponse (API response shape, not persisted)

Returned by `/api/v1/ask`.

| Field | Type | Notes |
|-------|------|-------|
| answer | str | Final agent answer text |
| tool_used | Literal["hybrid_search", "structured_extract"] | Which tool the agent invoked |
| source_chunks | list[str] | Raw text of chunks used to generate the answer |
| page_refs | list[int] | Corresponding page numbers for each source chunk |

**Constraint**: `source_chunks` and `page_refs` MUST be parallel arrays of equal length. If the agent used `structured_extract`, `source_chunks` contains the retrieved context passed to the extractor.

---

## State Transitions

```
App startup
  └─ ChromaDB exists on disk?
       ├─ Yes → load existing collection → UI shows "Document ready"
       └─ No  → empty state → UI prompts "Upload a document"

User uploads PDF
  └─ clear_store() → parse_and_chunk() → ingest_documents()
       └─ Success → return { chunks_indexed, metadata } → UI updates state
       └─ Failure (corrupt/not PDF) → HTTP 422/415 → UI shows error

User asks question
  └─ agent selects tool
       ├─ semantic_search → ChromaDB similarity search → format chunks → LLM answer
       └─ structured_extract → retrieve all chunks → LLM JSON extraction → PolicyData field
  └─ return AgentResponse → UI renders AnswerCard

User clicks Extract
  └─ retrieve all chunks → LLM structured extraction → PolicyData
  └─ return { policy_data: PolicyData } → UI renders ExtractTable
```

---

## Relationships

```
Document 1 ──── * Chunk          (one document produces many chunks)
Chunk    * ────── AgentResponse  (one or more chunks cited in each response)
PolicyData 1 ─── 8 fields        (fixed schema, always all 8 returned)
```
