# Work Items and Containers (v1 Draft)

This draft defines a simple, centralized model for tasks, sprints, goals, and calendar alignment.

## Design Intent

- Keep one universal unit for action: `work_item`.
- Keep one universal grouping/timebox unit: `work_container`.
- Support different industry wording in UI without changing backend contracts.

## Canonical Concepts

- `work_item`
  - A unit of work someone (or a team/agent) can execute.
  - Maps directly to existing `studio_tasks` behavior.
- `work_container`
  - A grouping construct for timebox/initiative/batch.
  - Container types are represented as metadata/facets, not separate tables per term.

## Vocabulary Mapping (UI Layer)

- Developer view
  - `work_container.type = sprint|epic|objective`
- Business/operations view
  - `work_container.type = goal|objective|job`
- Personal view
  - `work_container.type = goal|checklist`

The backend stores normalized values and apps can relabel for user-friendly wording.

## DTO Drafts

### Work Item DTO

```json
{
  "work_item_id": "task-uuid",
  "tenant_id": "tenant0",
  "org_id": "org-uuid",
  "project_id": "project-uuid",
  "title": "Implement resolver dual-read",
  "description": "Wire MyAIDE to core resolver with local fallback.",
  "status": "todo",
  "priority": "medium",
  "visibility": "team_public",
  "assignee_user_ids": ["user-uuid"],
  "tags": ["resolver", "aide", "integration"],
  "metadata": {
    "container_ids": ["container-uuid"],
    "container_type": "sprint",
    "estimate_points": 5,
    "domain": "engineering"
  },
  "related_node_ids": ["node-uuid"],
  "channel_id": "channel-uuid",
  "due_at": "2026-05-31T23:59:59Z",
  "created_at": "2026-05-13T20:00:00Z",
  "updated_at": "2026-05-13T20:00:00Z"
}
```

### Work Container DTO

```json
{
  "container_id": "container-uuid",
  "tenant_id": "tenant0",
  "org_id": "org-uuid",
  "title": "Sprint 2026-W21",
  "summary": "Resolver + ACL hardening",
  "type": "sprint",
  "status": "active",
  "owner_user_id": "user-uuid",
  "tags": ["engineering", "platform"],
  "metadata": {
    "timebox": true,
    "start_at": "2026-05-12T00:00:00Z",
    "end_at": "2026-05-26T00:00:00Z",
    "capacity_points": 30,
    "calendar_id": "meeting-series-uuid"
  },
  "created_at": "2026-05-13T20:00:00Z",
  "updated_at": "2026-05-13T20:00:00Z"
}
```

### Work Container Membership Edge (knowledge relationship)

Use existing relationship contracts:

```json
{
  "relationship_id": "rel-uuid",
  "from_entity_id": "container-entity-id",
  "to_entity_id": "work-item-entity-id",
  "relationship_type": "contains",
  "directionality": "directed",
  "visibility": {
    "scope": "team",
    "acl_policy_id": "policy-team",
    "team_id": "team-uuid"
  }
}
```

## How This Maps to Current Core APIs

- `work_item`
  - Use existing `/v1/studio/tasks` APIs.
  - Store container references in `metadata.container_ids` + `metadata.container_type`.
- `work_container`
  - Represent as federated knowledge entity (`kind = project`) with facet/metadata `type`.
  - Optional future direct CRUD route can be added when needed.
- `membership`
  - Represent as knowledge relationship (`contains`, `implements`, `blocks`).

## Calendar Integration (v1)

- Use `studio_meetings` as scheduling anchors.
- Link meetings to containers/work items through:
  - `channel_id`
  - `related_node_ids`
  - `metadata.calendar_id` and `metadata.meeting_ids`

Example: a sprint planning meeting can be linked to a sprint container and all related work items.

## Minimal Implementation Plan

1. Keep `studio_tasks` as the `work_item` backbone.
2. Start creating `work_container` as knowledge entities (`kind = project`) with `project_type` facets.
3. Link tasks to containers using relationship edges and `metadata.container_ids`.
4. Render app-specific labels in UI (Sprint/Goal/Job) based on user/app profile.

## Why This Stays Simple

- One durable task model, one grouping model.
- Works for advanced teams without confusing simple users.
- Avoids introducing many new backend tables before usage patterns stabilize.
