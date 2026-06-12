# Document Manager Contract v0.1

This document defines the first-pass API and UI contract for a real document manager experience across Studio, Council, AIDE, and future CLI workflows.

## Goals

- Separate file upload workflows from manual note-style knowledge entry.
- Expose binary storage, extraction, indexing, and failure states clearly.
- Keep one canonical contract so all apps present consistent behavior.
- Support DXL and CLI document-aware context resolution.

## Creation Paths

Two explicit creation modes are required:

1. Upload document file
2. Create knowledge note

Both produce a `kind=document` federated knowledge entity, but differ by source type and processing behavior.

## API Endpoints

## 1) Upload document file

- `POST /v1/knowledge/documents/upload`
- Content type: `multipart/form-data`

Request fields:

- required: `org_id`, `file`
- optional: `title`, `summary`
- optional JSON-string fields: `tags_json`, `contexts_json`, `facets_json`, `visibility_json`, `owners_json`, `metadata_json`

Response fields (required shape for UI parity):

- `document_id`
- `entity`
- `upload`
  - `filename`
  - `content_type`
  - `size_bytes`
  - `storage_backend`
  - `storage_uri`
- `processing`
  - `status`
  - `extracted_text_length`
  - `warnings[]`
  - `errors[]`
  - `job_id` (optional for async indexing)

## 2) Create knowledge note

- `POST /v1/knowledge/documents/note`

Request fields:

- required: `org_id`, `title`, `content`
- optional metadata fields consistent with upload path

Response shape mirrors upload response, with:

- `source_type = note`
- processing status path suitable for note indexing

## 3) List documents

- `GET /v1/knowledge/documents`

Query fields:

- `org_id` (required)
- optional filters: `status`, `source_type`, `visibility_scope`, `query`, `limit`, `cursor`

List item fields:

- `document_id`
- `title`
- `source_type`
- `filename`
- `content_type`
- `size_bytes`
- `processing_status`
- `visibility_scope`
- `created_at`, `updated_at`
- `created_by`
- `storage_backend`

## 4) Document details

- `GET /v1/knowledge/documents/{document_id}`

Returns canonical entity payload plus processing details and extraction summary.

## 5) Reprocess/retry

- `POST /v1/knowledge/documents/{document_id}/reprocess`

Used for extraction or indexing retry after failure.

## Lifecycle and Enums

## `processing_status`

- `uploaded`
- `extracting`
- `extracted`
- `indexing`
- `indexed`
- `failed`
- `archived`

## `source_type`

- `file`
- `note`
- `url`
- `generated`

## `failure_reason_code` starter set

- `DOCUMENT_EMPTY_FILE`
- `DOCUMENT_UNSUPPORTED_TYPE`
- `DOCUMENT_EXTRACTION_FAILED`
- `DOCUMENT_INDEXING_FAILED`
- `DOCUMENT_STORAGE_FAILED`

## UI Contract

Required page sections:

1. `Upload Files`
2. `Create Note`
3. `Documents`

## Upload Files requirements

- drag and drop plus file picker
- metadata fields
- upload queue with progress and status chips
- row actions: view, retry, archive/delete

## Create Note requirements

- markdown/text editor
- metadata fields
- save as document entity

## Documents table minimum columns

- Name/Title
- Source type
- File type
- Size
- Status
- Visibility
- Modified
- Actions

## Details panel requirements

- metadata block
- extraction preview
- processing timeline
- related entity links (tasks/threads/workflows)

## DXL and CLI Alignment

CLI commands to keep in parity:

- `myai doc upload <file> ...`
- `myai doc note create ...`
- `myai doc list --status indexed`
- `myai doc show <id>`
- `myai doc reprocess <id>`

DXL resolvers should treat documents by status and source type, avoiding stale or failed content when composing context packs.

## Implementation Priorities

1. Freeze endpoint and enum contract.
2. Extend upload response with processing shape.
3. Add list/detail/reprocess endpoints.
4. Update Studio and Council to split upload and note workflows.
5. Add CLI parity commands.
6. Add contract and integration tests for status transitions and failure paths.
