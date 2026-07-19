# Artifact Promotion API

Core supports explicit promotion of useful outputs into the knowledge plane.

This is intended for cases where:

- a chat answer should become a durable knowledge fragment
- a workflow scaffold should become a knowledge node
- a document excerpt should be promoted with metadata and links
- a transcript fragment should be related to tasks, bugs, or guides

## Endpoint

- `POST /v1/knowledge/artifacts/promote`
- `POST /v1/knowledge/artifacts/evaluate-rules`

## Request example

```json
{
  "org_id": "org_abc",
  "artifact_kind": "knowledge_node",
  "artifact_subtype": "conversation_block",
  "title": "Useful deployment answer",
  "summary": "Promoted from chat",
  "content": "## Deployment Notes\n- refresh image\n- verify health",
  "tags": ["deployment", "chat"],
  "contexts": ["operations"],
  "relevancy": {
    "backend": {
      "score": 88,
      "confidence": 80,
      "assignedBy": "human"
    }
  },
  "validation_rules": [
    {
      "rule_id": "require-review-for-deployments",
      "condition": {"type": "tag_present", "config": {"value": "deployment"}},
      "action": {"type": "require_review", "reason": "deployment_review"},
      "priority": 10
    }
  ],
  "relationships": [
    {
      "target_entity_id": "ent-related-task",
      "relationship_type": "supports"
    }
  ]
}
```

## Response example

```json
{
  "meta": {
    "service": "myai-core-backend",
    "version": "0.1.0",
    "spec_version": "v1",
    "environment": "local",
    "timestamp": "2026-06-04T18:00:00+00:00",
    "correlation_id": "req-artifact-promote-001"
  },
  "data": {
    "artifact": {
      "entity_id": "node_123",
      "kind": "knowledge_node",
      "facets": {
        "subtype": "conversation_block"
      },
      "relevancy": {
        "backend": {
          "score": 88,
          "confidence": 80,
          "assignedBy": "human"
        }
      }
    },
    "evaluation": {
      "blocked": false,
      "review_required": true,
      "matched_rules": [
        {
          "rule_id": "require-review-for-deployments",
          "action_type": "require_review"
        }
      ]
    },
    "relationships": [
      {
        "relationship_id": "rel_001",
        "from_entity_id": "node_123",
        "to_entity_id": "ent-related-task",
        "relationship_type": "supports"
      }
    ]
  },
  "error": null
}
```

## Standalone rule evaluation

Use `POST /v1/knowledge/artifacts/evaluate-rules` to preview deterministic rule behavior without persisting anything.

This is useful for:

- client-side workflow builders
- profile/lens validation
- graph UI preview of gating behavior
- testing promotion rules before applying them

## Notes

- Promotion is explicit, not blanket persistence.
- Promoted artifacts can carry relevancy metadata immediately.
- Relationships can be attached at promotion time.
- This is a first practical step toward the traceable artifact model.
