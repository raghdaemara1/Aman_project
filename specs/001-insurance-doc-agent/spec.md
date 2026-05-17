# Feature Specification: Insurance Document Intelligence Agent

**Feature Branch**: `001-insurance-doc-agent`

**Created**: 2026-05-17

**Status**: Draft

**Input**: User description: "Insurance Document Intelligence Agent — React.js frontend + FastAPI backend + LangChain ReAct agent with two tools (semantic_search, structured_extract) + ChromaDB vector store + Pydantic structured output. Users upload insurance policy PDFs, ask natural language questions, and extract structured policy data. The agent reasons about which retrieval tool to use and always shows the source chunk and tool used."

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Upload a Policy Document (Priority: P1)

A user (insurance analyst or customer service agent) opens the application and uploads an insurance policy PDF. The system parses the document, splits it into searchable chunks, and confirms the document is ready for querying. The user can see how many chunks were indexed and basic document metadata.

**Why this priority**: Nothing else in the system works without a document loaded. This is the entry point for every other user journey.

**Independent Test**: Upload the sample policy file → system reports chunk count and metadata → user can proceed to ask a question or extract data. Delivers a fully usable ingestion pipeline.

**Acceptance Scenarios**:

1. **Given** a valid insurance policy PDF, **When** the user uploads it, **Then** the system confirms indexing success and displays the number of chunks indexed and document metadata (estimated title, page count).
2. **Given** a previously indexed document, **When** the user uploads a new PDF, **Then** the old document is cleared and replaced with the new one.
3. **Given** an unsupported file type (e.g., `.docx`, `.jpg`), **When** the user tries to upload it, **Then** the system rejects the file with a clear error message explaining that only PDF files are accepted.

---

### User Story 2 — Ask Natural Language Questions (Priority: P2)

After uploading a policy, the user types a natural language question about the document (e.g., "What procedures are excluded from coverage?", "Is maternity care included?"). The agent reasons about the best retrieval strategy, fetches relevant content, and returns a concise answer. The user always sees which tool was used and the exact source text behind the answer.

**Why this priority**: This is the core intelligence feature — the agentic Q&A — and the primary value proposition of the demo.

**Independent Test**: With a document indexed, submit a question → receive an answer with a tool badge (semantic search or structured extract) and a source chunk with page reference. Fully functional as a standalone use case.

**Acceptance Scenarios**:

1. **Given** an indexed policy, **When** the user asks an open-ended question about coverage, **Then** the agent uses the hybrid search tool, returns a relevant answer, displays a "Hybrid Search" badge, and shows the source text chunk with page number.
2. **Given** an indexed policy, **When** the user asks for a specific data field (e.g., "What is the policy number?", "When does this policy expire?"), **Then** the agent uses the structured extraction tool, returns the exact field value, and displays a "Structured Extraction" badge with the relevant source chunk.
3. **Given** a question whose answer does not exist in the document, **When** the agent cannot find relevant content, **Then** it clearly states it cannot find the answer — it does not guess or hallucinate.
4. **Given** any answered question, **When** the answer is displayed, **Then** the source chunk is viewable in a collapsible section showing the exact document text used.

---

### User Story 3 — Extract Structured Policy Data (Priority: P3)

The user clicks "Extract Structured Data" to automatically pull all key policy fields from the document in one operation. The system returns a clean, structured table with fields such as policy number, holder name, coverage type, dates, premium, coverage limit, and exclusions — without the user having to ask individual questions.

**Why this priority**: A high-value secondary feature that demonstrates structured extraction capability independently of conversational Q&A.

**Independent Test**: With a document indexed, click extract → receive a populated table of all eight policy fields. Fully usable and demonstrable independently.

**Acceptance Scenarios**:

1. **Given** an indexed policy, **When** the user triggers structured extraction, **Then** the system returns all eight fields: Policy Number, Policy Holder, Coverage Type, Start Date, End Date, Premium Amount, Coverage Limit, and Key Exclusions.
2. **Given** a field that is not present in the document, **When** extraction runs, **Then** that field displays "Not specified" — never blank or an error.
3. **Given** the extracted data table, **When** the user views it, **Then** the list field (Key Exclusions) is displayed as a readable bullet list, not a raw array.

---

### Edge Cases

- What happens when the user submits a question before uploading a document? → System must display a clear prompt to upload a document first.
- What happens when the uploaded PDF is password-protected or corrupt? → System must return a user-friendly error, not a stack trace.
- What happens when the PDF has no extractable text (scanned image only)? → System must inform the user that the document could not be parsed.
- What happens when the user asks an ambiguous question that could match both tools? → The agent uses its reasoning to select the most appropriate tool; the choice is always visible to the user.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST accept PDF file uploads through the browser interface.
- **FR-002**: The system MUST parse uploaded PDFs into text chunks and index them for retrieval.
- **FR-003**: The system MUST clear the previous document index when a new document is uploaded.
- **FR-004**: The system MUST display the number of chunks indexed and document metadata after a successful upload.
- **FR-005**: The system MUST allow users to type natural language questions about the uploaded document.
- **FR-006**: The system MUST use an AI agent that reasons about which retrieval strategy to apply (hybrid search vs. specific field lookup) for each question.
- **FR-007**: Every agent answer MUST identify which tool was used (hybrid search or structured extraction) via a visible label.
- **FR-008**: Every agent answer MUST include the source text chunk(s) and page reference used to generate the response.
- **FR-009**: The agent MUST explicitly state when it cannot find an answer — it MUST NOT hallucinate or guess.
- **FR-010**: The system MUST provide a one-click structured extraction operation that returns all eight policy fields simultaneously.
- **FR-011**: Structured extraction MUST return "Not specified" for any field not found in the document.
- **FR-012**: The system MUST run entirely on a local machine without cloud infrastructure (except the LLM API call).
- **FR-013**: The system MUST reject non-PDF file uploads with a clear error message.

### Key Entities

- **Document**: An uploaded insurance policy PDF. Has a source filename, page count, and produces a set of Chunks on ingestion.
- **Chunk**: A text segment from the document. Has content, page number, and chunk index. Stored in the vector index.
- **Question**: A natural language query submitted by the user. Triggers agent reasoning.
- **AgentResponse**: The output of an agent run. Contains the answer text, the tool used, the source chunks, and page references.
- **PolicyData**: A structured representation of key policy fields extracted from the document. Eight fixed fields with string values.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can upload a policy document and receive confirmation of successful indexing within 30 seconds.
- **SC-002**: A user can ask a natural language question and receive a sourced answer within 15 seconds.
- **SC-003**: 100% of agent responses display which tool was used and include at least one source chunk.
- **SC-004**: The structured extraction operation returns all eight policy fields in a single interaction.
- **SC-005**: The system correctly returns "Not specified" for missing fields — zero hallucinated values in extraction output.
- **SC-006**: The full application starts on a new machine in under 5 minutes following the setup instructions.
- **SC-007**: The agent correctly selects the hybrid search tool for open-ended questions and the structured extraction tool for specific field lookups — verifiable against a set of 10 representative test questions.

---

## Assumptions

- Users have Ollama running locally with the required models (`llama3.1` and `nomic-embed-text`).
- The primary test document is the provided sample insurance policy; real PDFs from users are a secondary scenario.
- A single document is active at a time — multi-document comparison is out of scope for v1.
- Mobile browser support is out of scope; the application targets desktop browsers.
- User authentication and access control are out of scope — the demo runs for a single local user.
- The document vector index persists to local disk and reloads automatically on page refresh — users do not need to re-upload between sessions. Conversation history (Q&A pairs) is not persisted; only the index is.
- PDF files are assumed to contain extractable text; OCR for scanned-image-only PDFs is out of scope for v1.

---

## Clarifications

### Session 2026-05-17

- Q: When the user refreshes the browser, is the previously indexed document still available, or must they re-upload? → A: Index persists across refreshes — user resumes without re-uploading (ChromaDB disk persistence reloaded on startup).
