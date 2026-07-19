# Context and Persona AI Usage (v1)

This document summarizes Core endpoints for federated context resolution and persona-driven AI responses.

## Context Profiles

- `GET /v1/context/channels`
- Returns default channel profiles (development, architecture, operations) with retrieval budgets and lens defaults.

## Relevancy Profiles

- `GET /v1/context/profiles`
- `GET /v1/context/profiles/{profile_id}`

Returns built-in retrieval presets such as:

- frontend engineer
- backend engineer
- help desk agent
- generalist
- knowledge librarian
- relations manager
- document drafter
- project manager
- scrum master

Profiles expose:

- `relevancy_focus`
- preferred node kinds
- preferred relationship types
- preferred tools / outputs
- `preferred_tool_policies`
- `provider_preferences`
- voice defaults for later persona-facing interaction layers

## Identity Federation

- `GET /v1/context/identity`
- Optional query param: `org_id`

Returns cacheable runtime identity context for app interoperability:

- org scope
- team memberships
- role ids
- app/capability grants (`app_access`)

## Policy Decision API

- `POST /v1/policy/decision`

Request pattern:

- `subject`
- `resource`
- `action`
- `context` (including `app_id`, `org_id`)

Response includes machine-readable `reason_code` and boolean `allow`.

Each decision evaluation is also recorded as an audit event (`policy.decision.evaluate`) for traceability.

## Canonical Event Ingest and Query

- `POST /v1/events/ingest`
- `GET /v1/events`
- `GET /v1/events/stream` (SSE)

Events can be filtered by:

- `app_id`
- `workspace_id`
- `correlation_id`

## Daily Summary

- `GET /v1/context/daily-summary`
- Optional query params:
  - `date=YYYY-MM-DD`
  - `org_id=<org_id>`

Returns short highlights and sectioned bullets for the day based on tracked activity (tasks, meetings, uploads, and audit activity).

Daily summary generation is persisted as a journal snapshot.

- `GET /v1/context/daily-summary/journal`
- Optional query params:
  - `org_id=<org_id>`
  - `start_date=YYYY-MM-DD`
  - `end_date=YYYY-MM-DD`
  - `limit=1..120`

This returns stored summary entries so users can review activity in journal-like history form.

## Federated Context

- `POST /v1/context/resolve`
  - Non-debug context retrieval with concise explain fields.
- `POST /v1/context/explain`
  - Debug retrieval with exclusion report and deeper trace data.

## Persona Capability Discovery

- `GET /v1/context/personas/capabilities`
  - Lists accessible personas in current org with runtime/model/tool capabilities.
- `GET /v1/context/personas/{persona_id}/capability`
  - Returns capability details for one persona if accessible.

Persona capability payloads also include a `voice` object if the persona has voice metadata configured.

## Persona Query with Federated Context

- `POST /v1/context/persona-query`

Request body:

```json
{
  "persona_id": "<persona_id>",
  "question": "How should we implement scoped knowledge retrieval for IDE context?",
  "anchor": { "entity_id": "<optional_entity_id>", "text": "resolver policy" },
  "lens": {
    "channel_profile_id": "development-default",
    "profile_id": "backend-engineer",
    "include_node_kinds": ["project", "task", "file", "document", "policy"],
    "include_relationship_types": ["contains", "depends_on", "imports", "governed_by"],
    "relevancy_focus": {"backend": 1.0, "security": 0.4}
  },
  "budget": { "max_nodes": 40, "max_edges": 80, "max_snippets": 20, "max_tokens": 8000 },
  "options": { "include_exclusion_report": false }
}
```

Response includes:

- persona identity/runtime used
- generated answer
- model usage metadata
- context bundle summary (bundle id, graph version, selected sources)
- deterministic query signals extracted from the request (`query_signals`)
- structured reference maps for agents (`reference_maps`) across projects, tasks, files, code, documents, and glossary terms
- compaction metadata (`compaction`) describing token-aware pruning and duplicate collapse
- context quality summary:
  - `quality` (`high|medium|low`)
  - `selected_nodes`, `average_score`, `coverage_ratio`
  - `follow_up_recommended` and `follow_up_reasons`

Resolver safety checks:

- Core validates `selection_reason_code` values from resolver output against allowed enum values.
- Invalid reason codes fail with `KNOWLEDGE_SELECTION_REASON_CODE_INVALID`.
- Conflict precedence is deterministic; lower-ranked duplicates are excluded as `conflict_lost`.
- Budget pruning is deterministic; pruned items are surfaced as `budget_exceeded` in explain mode.
- Explicit references from tags, backticks, file paths, and common object phrases can surface as `explicit_reference` selections.
- Duplicate context entries are compacted deterministically and surfaced as `compacted_duplicate` in explain mode.

## Access Behavior

- Persona access is org-scoped and visibility-aware.
- Admin-only personas are restricted to owner/admin/global-admin contexts.
- Context source visibility is enforced via knowledge ACL and edge-aware traversal rules.
