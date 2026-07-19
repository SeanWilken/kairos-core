# Workflow Graph API

Core now exposes a first workflow graph persistence slice for client applications.

## Endpoints

- `POST /v1/studio/workflows`
- `GET /v1/studio/workflows?org_id=<org_id>`
- `GET /v1/studio/workflows/{workflow_id}`
- `PATCH /v1/studio/workflows/{workflow_id}`
- `POST /v1/studio/workflows/{workflow_id}/runs`
- `GET /v1/studio/workflows/{workflow_id}/runs`
- `GET /v1/studio/workflow-runs/{run_id}`
- `POST /v1/studio/workflow-runs/{run_id}/resume`
- `POST /v1/studio/workflows/{workflow_id}/dry-run`
- `GET /v1/studio/workflow-reviews?org_id=<org_id>`
- `POST /v1/studio/workflow-reviews/{review_id}/decision`

## Purpose

This is the first persistence layer for graph-based workflows with:

- nodes
- edges
- logic rules
- policy metadata
- dry-run rule evaluation against candidate artifacts

It is intended to be compatible with a future node/relationship workflow authoring UI.

## Create workflow example

```json
{
  "org_id": "org_abc",
  "name": "Deployment Workflow",
  "description": "Deployment flow with review gate",
  "trigger": {"type": "manual"},
  "nodes": [
    {"node_id": "n1", "kind": "document_draft", "label": "Draft Guide", "config": {}},
    {"node_id": "n2", "kind": "review_gate", "label": "Review", "config": {}}
  ],
  "edges": [
    {"edge_id": "e1", "from_node_id": "n1", "to_node_id": "n2", "relationship_type": "next"}
  ],
  "logic_rules": [
    {
      "rule_id": "r1",
      "scope": "workflow",
      "trigger": "after_node:n1",
      "condition": {"type": "tag_present", "config": {"value": "deployment"}},
      "action": {"type": "require_review", "reason": "deployment_review", "config": {}},
      "priority": 10
    }
  ],
  "policy": {"retry_count": 0, "timeout_seconds": 60, "failure_mode": "manual_review"},
  "metadata": {"source": "ui"},
  "spec_version": "v0.3"
}
```

## Dry-run example

```json
{
  "artifact": {
    "kind": "knowledge_node",
    "tags": ["deployment"],
    "summary": "Deployment draft",
    "visibility": {"scope": "org"},
    "facets": {},
    "kind_payload": {"content": "Deployment notes"},
    "quality": {}
  },
  "review_context": {"requested_by": "ui-test"}
}
```

Dry-run response shows:

- whether execution would block
- whether review would be required
- which rules matched
- how the artifact would be mutated by deterministic rules

## Run start behavior

`POST /v1/studio/workflows/{workflow_id}/runs` creates a persisted run record using the same deterministic rule evaluation logic as dry-run.

Current behavior:

- resolves a start node
- evaluates workflow rules against the submitted artifact
- executes supported node kinds deterministically during run start
- creates a run with status such as:
  - `completed`
  - `failed`
  - `paused_review`
- creates a workflow review queue item if review is required

Currently supported node execution:

- `document_draft`
- `task_create`
- `review_gate`

Run responses now include:

- `execution_trace`
- current review node context for resume handling

`document_draft` prefers the configured provider/model but falls back to a deterministic local markdown draft if provider execution is unavailable.

## Notes

- This is the first persistence slice, not the final execution engine.
- Review queue persistence is not yet fully active beyond the list surface and planning direction.
- The intent is to let client apps start configuring and testing graph workflows now while we continue wiring the execution and review pipeline.
