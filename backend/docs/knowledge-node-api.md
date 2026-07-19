# Knowledge Node API

Core exposes a generic knowledge node retrieval surface in addition to document-specific routes.

## Endpoints

- `GET /v1/knowledge/conventions`
- `POST /v1/knowledge/code-ingest`
- `GET /v1/knowledge/nodes?org_id=<org_id>&kind=<kind>&subtype=<subtype>&tag=<tag>&query=<text>&limit=<n>&cursor=<cursor>`
- `GET /v1/knowledge/nodes/{entity_id}`

Optional relevancy-aware filters:

- `relevancy_dimension`
- `relevancy_min`
- `relevancy_max`

## Purpose

Use this surface for non-document knowledge items such as:

- notes
- note collections
- voice transcripts
- generic knowledge nodes
- future code/tool/SOP memory entities

`GET /v1/knowledge/conventions` returns the current canonical conventions for first-class knowledge entities and reuse relationship types. This is intended to keep ingest tools, indexers, and agent subsystems aligned on the same object model.

`POST /v1/knowledge/code-ingest` is the canonical helper for promoting repo/workspace code scan results into `project`, `file`, and `symbol` knowledge entities plus deterministic reuse links.

Current first-class conventions include:

- `file`
- `symbol`
- `project`
- `glossary_term`

Current cross-project reuse relationship types include:

- `similar_to`
- `duplicate_of`
- `extracted_from`
- `should_be_shared`

## List response example

```json
{
  "meta": {
    "service": "myai-core-backend",
    "version": "0.1.0",
    "spec_version": "v1",
    "environment": "local",
    "timestamp": "2026-06-04T17:00:00+00:00",
    "correlation_id": "req-knowledge-nodes-001"
  },
  "data": {
    "items": [
      {
        "entity_id": "node-voice-001",
        "kind": "knowledge_node",
        "subtype": "voice_transcript",
        "title": "Voice Transcript Note",
        "summary": "Transcript summary",
        "tags": ["voice", "notes"],
        "contexts": [],
        "facets": {
          "subtype": "voice_transcript"
        },
        "relevancy": {
          "backend": {
            "score": 91,
            "confidence": 85,
            "assignedBy": "human"
          }
        },
        "visibility": {
          "scope": "org",
          "acl_policy_id": "policy-org"
        },
        "visibility_scope": "org",
        "source": {
          "source_system": "voice_stt",
          "source_id": "meeting-1",
          "external_ref": "local://tenant-local/org_abc/meeting.wav",
          "source_of_truth": true,
          "dedupe_key": "meeting-1"
        },
        "confidence": 0.9,
        "verification_state": "derived",
        "lifecycle_status": "active",
        "updated_at": "2026-06-04T17:00:00+00:00",
        "created_at": "2026-06-04T17:00:00+00:00"
      }
    ],
    "next_cursor": null
  },
  "error": null
}
```

## Detail response example

```json
{
  "meta": {
    "service": "myai-core-backend",
    "version": "0.1.0",
    "spec_version": "v1",
    "environment": "local",
    "timestamp": "2026-06-04T17:01:00+00:00",
    "correlation_id": "req-knowledge-node-001"
  },
  "data": {
    "entity": {
      "entity_id": "node-voice-001",
      "kind": "knowledge_node",
      "title": "Voice Transcript Note",
      "summary": "Transcript summary",
      "kind_payload": {
        "subtype": "voice_transcript",
        "transcript": "meeting notes transcript"
      }
    },
    "summary": {
      "entity_id": "node-voice-001",
      "kind": "knowledge_node",
      "subtype": "voice_transcript",
      "title": "Voice Transcript Note",
      "summary": "Transcript summary",
      "tags": ["voice", "notes"],
      "contexts": [],
      "facets": {
        "subtype": "voice_transcript"
      },
      "visibility": {
        "scope": "org",
        "acl_policy_id": "policy-org"
      },
      "visibility_scope": "org",
      "source": {
        "source_system": "voice_stt",
        "source_id": "meeting-1",
        "external_ref": "local://tenant-local/org_abc/meeting.wav",
        "source_of_truth": true,
        "dedupe_key": "meeting-1"
      },
      "confidence": 0.9,
      "verification_state": "derived",
      "lifecycle_status": "active",
      "updated_at": "2026-06-04T17:00:00+00:00",
      "created_at": "2026-06-04T17:00:00+00:00"
    }
  },
  "error": null
}
```

## Notes

- The node list is ACL-aware and org-scoped.
- This surface is intended to be the canonical retrieval path for non-document knowledge fragments.
- Documents should continue using the dedicated document routes when file/content retrieval is needed.
- Node summaries now include `convention_id` and `convention` when a canonical convention applies.
