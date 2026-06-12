# Instruction Resolution Contract v0.1

Draft contract for resolving instruction packs from indexed fragments with policy-first enforcement.

## Scope

Used by Studio, Council, AIDE, and CLI wrappers when preparing agent or tool execution context.

## Core Objects

## SkillManifest

```json
{
  "skill_id": "string",
  "version": "string",
  "title": "string",
  "entrypoints": ["string"],
  "default_tools": ["string"],
  "tags": ["string"]
}
```

## ToolProfile

```json
{
  "tool_id": "string",
  "name": "string",
  "capabilities": ["string"],
  "risk_level": "low|medium|high",
  "input_schema_ref": "string",
  "output_schema_ref": "string",
  "enabled": true
}
```

## InstructionFragment

```json
{
  "fragment_id": "string",
  "version": "string",
  "scope_type": "global|app|persona|tool|use_case|user_segment|org_segment",
  "scope_ref": "string",
  "content": "string",
  "tags": ["string"],
  "conditions": {
    "tenant_ids": ["string"],
    "org_ids": ["string"],
    "roles": ["string"],
    "tool_ids": ["string"],
    "persona_ids": ["string"]
  },
  "priority_weight": 0,
  "token_estimate": 0,
  "effective_from": "2026-05-19T00:00:00Z",
  "effective_to": null
}
```

## OverrideRequest

```json
{
  "request_id": "string",
  "requested_by": "string",
  "reason": "string",
  "scope": "single_request|session|timeboxed",
  "expires_at": "2026-05-19T01:00:00Z",
  "target_constraints": ["string"],
  "instruction_patch": "string"
}
```

## OverrideApprovalRecord

```json
{
  "approval_id": "string",
  "request_id": "string",
  "approved_by": "string",
  "decision": "approved|rejected",
  "reason": "string",
  "scope": "single_request|session|timeboxed",
  "expires_at": "2026-05-19T01:00:00Z",
  "ticket_ref": "string"
}
```

## API Shape (candidate)

## POST `/v1/instructions/resolve`

Request:

```json
{
  "app_id": "studio",
  "tenant_id": "tenant-local",
  "org_id": "org-local",
  "persona_id": "persona-123",
  "tool_id": "email_send",
  "use_case": "customer_outreach",
  "request_instructions": "focus on concise summary",
  "override_request_id": "optional",
  "token_budget": 1800
}
```

Response:

```json
{
  "effective_instructions": "string",
  "selected_fragments": [
    {"fragment_id": "f1", "scope_type": "tool", "reason": "metadata_match"}
  ],
  "skipped_fragments": [
    {"fragment_id": "f2", "reason_code": "TOKEN_BUDGET_EXCEEDED"}
  ],
  "policy": {
    "non_overridable_applied": ["TENANT_ISOLATION"],
    "override_applied": false
  },
  "trace_id": "string"
}
```

## Precedence and Enforcement

Precedence must follow:

1. non-overridable policy constraints
2. approved override constraints (if active)
3. request-level instructions
4. user/org/persona/tool/use-case fragments
5. baseline skill instructions

Hard policy constraints must never be bypassed.

## Reason Codes (starter set)

- `POLICY_NON_OVERRIDABLE_APPLIED`
- `OVERRIDE_APPROVAL_REQUIRED`
- `OVERRIDE_APPROVAL_EXPIRED`
- `OVERRIDE_APPROVAL_REJECTED`
- `TOKEN_BUDGET_EXCEEDED`
- `FRAGMENT_CONDITION_MISMATCH`
