# Knowledge Document Upload (v1)

Core now supports direct document upload for federated knowledge ingestion.

## Endpoint

- `POST /v1/knowledge/documents/upload`
- Content type: `multipart/form-data`

## Form Fields

- `org_id` (required)
- `file` (required)
- `title` (optional)
- `summary` (optional)
- `tags_json` (optional JSON array string)
- `contexts_json` (optional JSON array string)
- `facets_json` (optional JSON object string)
- `visibility_json` (optional JSON object string)
- `owners_json` (optional JSON array string)
- `metadata_json` (optional JSON object string)

If `visibility_json` is omitted, defaults are applied:

- `scope = org`
- `acl_policy_id = policy-org`

## Storage Backends

Configure backend using environment variables:

- `MYAI_STORAGE_BACKEND=local|minio`
- `MYAI_STORAGE_LOCAL_ROOT=/data/storage`
- `MYAI_STORAGE_S3_ENDPOINT=http://minio:9000`
- `MYAI_STORAGE_S3_ACCESS_KEY=<key>`
- `MYAI_STORAGE_S3_SECRET_KEY=<secret>`
- `MYAI_STORAGE_S3_REGION=us-east-1`
- `MYAI_STORAGE_S3_BUCKET=myai-documents`

## Behavior

On upload, Core:

1. Stores the file in configured backend.
2. Extracts text snippet content for supported types:
   - PDF (`application/pdf` or `.pdf`)
   - Plain/code text formats (`text/*`, `.txt`, `.md`, `.json`, `.csv`, `.py`, `.ts`, `.tsx`, `.js`, `.fs`, `.cs`)
3. Creates a federated knowledge entity (`kind=document`) with pointer reference (`content_refs`) and extracted snippet.
4. Returns saved entity and storage metadata.

This enables sharing/reference across Council, Knowledger, AIDE, and other suite apps using the same ACL-governed resolver.
