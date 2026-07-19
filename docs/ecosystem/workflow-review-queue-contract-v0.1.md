# Workflow Review Queue Contract v0.1

This document defines the review queue semantics for workflows that pause pending explicit human approval or review.

It is intended to support graph-based workflow builders and deterministic workflow execution.

## Why this exists

Some workflow actions should not complete automatically.

Examples:

- legal or cornerstone artifact promotion
- risky deployment step
- external communication send
- generated doc that requires approval before publication
- task or workflow state transition that must be verified

These should create a review queue item and pause execution instead of relying on prompt-only instructions.

## Review queue item shape

```json
{
  "review_id": "string",
  "workflow_id": "string",
  "run_id": "string",
  "node_id": "string",
  "tenant_id": "string",
  "org_id": "string",
  "title": "string",
  "summary": "string",
  "status": "pending|approved|rejected|returned_for_edit|expired",
  "reason_code": "string",
  "requested_by": "string",
  "requested_at": "2026-06-04T00:00:00Z",
  "resolved_by": "string",
  "resolved_at": "2026-06-04T00:00:00Z",
  "context": {}
}
```

## Required behaviors

When a rule or gate requires review:

1. workflow execution pauses
2. review queue item is created
3. run status becomes `paused_review`
4. reviewer decides outcome
5. workflow resumes, reroutes, fails, or returns for edit

## Review actions

Supported actions:

- `approve`
- `reject`
- `return_for_edit`
- `expire`

## Queue surfaces

Suggested route directions:

- `GET /v1/studio/workflows/reviews`
- `GET /v1/studio/workflows/reviews/{review_id}`
- `POST /v1/studio/workflows/reviews/{review_id}/decision`

## Filtering needs

Clients should be able to filter by:

- status
- workflow id
- run id
- requested_by
- reason_code

## UI expectations

The queue should support:

- viewing all pending approvals
- drilling into node/workflow context
- seeing why review is required
- approving/rejecting inline
- linking back to graph position or related artifact

## Relationship to workflow graph

Review queue items should always link back to:

- the workflow definition
- the workflow run
- the specific node/gate that raised the review

This keeps execution explainable and reviewable.

## Relationship to artifact promotion

Artifact promotion is a common candidate for review gating.

Examples:

- promote to `cornerstone`
- promote legal-sensitive guidance
- publish FAQ/SOP from generated material

These should all be able to route through the same queue.

## Bottom line

The workflow review queue is the explicit human checkpoint layer that turns deterministic workflow rules into safe, governable behavior across graph-based workflow execution.
