# Workflow Graph And Logic Contract v0.1

This document defines the intended contract direction for persisted workflow graphs, deterministic logic rules, and UI-aligned node/edge editing in the MyAI ecosystem.

It extends the current workflow direction from step-only definitions toward graph-first workflow persistence.

## Why this exists

Workflow generation alone is not enough.

If MyAI is going to support:

- task creation
- document drafting
- approvals
- handoffs
- deployment/troubleshooting guides
- agent and human collaboration

then workflows should become structured graphs with deterministic rules rather than prompt-only flows.

## Core objects

## WorkflowDefinition

```json
{
  "workflow_id": "string",
  "org_id": "string",
  "name": "string",
  "description": "string",
  "trigger": {
    "type": "manual|schedule|event|webhook",
    "config": {}
  },
  "nodes": [],
  "edges": [],
  "logic_rules": [],
  "policy": {
    "retry_count": 0,
    "timeout_seconds": 60,
    "failure_mode": "halt|continue|manual_review"
  },
  "created_at": "2026-06-04T00:00:00Z",
  "updated_at": "2026-06-04T00:00:00Z"
}
```

## WorkflowNode

```json
{
  "node_id": "string",
  "kind": "string",
  "label": "string",
  "description": "string",
  "ui": {
    "position": { "x": 0, "y": 0 },
    "color": "string",
    "group": "string",
    "collapsed": false
  },
  "config": {}
}
```

## WorkflowEdge

```json
{
  "edge_id": "string",
  "from_node_id": "string",
  "to_node_id": "string",
  "relationship_type": "next|success|failure|approved|rejected|true_branch|false_branch|fallback|retry|blocks|depends_on|produces_artifact",
  "label": "string",
  "condition_ref": "string"
}
```

## WorkflowLogicRule

```json
{
  "rule_id": "string",
  "scope": "node|edge|workflow",
  "trigger": "string",
  "condition": {
    "type": "string",
    "config": {}
  },
  "action": {
    "type": "allow|block|route|require_approval|emit_artifact|retry",
    "config": {}
  },
  "priority": 100
}
```

## Recommended starter node kinds

- `prompt_step`
- `knowledge_query`
- `document_draft`
- `task_create`
- `workflow_create`
- `approval_gate`
- `decision_gate`
- `condition_gate`
- `tool_call`
- `notification`
- `human_handoff`
- `agent_handoff`
- `checkpoint`
- `rollback_point`
- `artifact_emit`

## UI alignment requirements

The contract must remain easy to render using node/relationship UI from the shared package.

That means:

- stable node ids
- stable edge ids
- typed relationships
- node configuration objects
- optional UI metadata for layout/grouping
- deterministic logic references that can be configured visually

## Deterministic execution principle

The workflow graph should not rely on the LLM to decide branching logic each time.

Branching and gating should be driven by:

- typed rules
- validation
- explicit conditions
- approval states
- environment/runtime capability checks

## Artifact emission

Workflow nodes should be able to emit traceable artifacts into the knowledge plane.

Examples:

- generated markdown docs
- generated walkthroughs
- created tasks
- created bugs
- approval records
- checkpoint records

## Future direction

This contract is the bridge between:

- tool wrappers
- workflow scaffolding
- graph UX in the frontend
- deterministic logic engine
- traceable artifact model

It should eventually replace or extend the simpler step-array-only workflow shape currently used in earlier contracts.
