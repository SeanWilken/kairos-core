# CLI Wrapper and Tool Index v0.1

This document defines the first-pass architecture for a CLI-driven execution interface and a knowledge-indexed tool instruction system.

## Intent

Provide a practical path to:

- run and automate agent workflows from a lightweight CLI wrapper,
- reduce token/context cost by resolving only relevant instruction fragments,
- enforce policy constraints as first-class controls,
- support operator-visible override workflows with auditability.

## Core Principle

Policy constraints are top-level and enforced first. Instruction overrides are exceptional and only applied after explicit user intervention and approval logging.

## Runtime Layers

1. Core control plane
   - identity, policy, orchestration, audit, federated knowledge.
2. AIDE execution context
   - local workspace and repo graph context.
3. Tool knowledge index
   - tool metadata and instruction fragments with tagged scopes.
4. CLI wrapper
   - command surface for resolve, run, trace, and controlled overrides.

## Why Indexed Instructions (not one large `skills.md`)

- Lower token overhead by loading only relevant fragments.
- Better precision for persona/tool/use-case/user context combinations.
- Better governance with independent versioning and audit trace per fragment.
- Better maintainability for teams and forks.

## Instruction Resolution Order

From highest to lowest precedence:

1. hard policy constraints (non-bypassable)
2. approved override constraints (time-bounded)
3. request-level explicit instructions
4. user or org contextual instructions
5. persona instructions
6. tool-specific instructions
7. use-case templates
8. default skill baseline

## CLI Wrapper (planned)

Representative command groups:

- `myai skill list|inspect|publish`
- `myai tool list|inspect|status`
- `myai instruction resolve`
- `myai run` (mode-aware)
- `myai trace` (selected fragments, skips, policy decisions, overrides)
- `myai override request|approve|revoke` (gated)

Goal scopes should support `user`, `workspace`, `thread`, and `organization` so local and team-level planning can share one contract surface.

The CLI is an operator and developer interface and must not bypass policy.

## Tool Knowledge Index Model

The index stores compact, queryable records:

- tool profiles (id, capabilities, risk class, schema refs)
- instruction fragments (scope, tags, conditions, priority)
- use-case profiles (task categories and recommended instruction packs)
- user segment or org variants (role-sensitive instructions)

Resolver should pre-filter by metadata and conditions, then rank and trim by token budget.

## Override Workflow (single approval, no dual-auth yet)

1. client submits override request with reason and scope.
2. user intervention/approval is required before use.
3. approval record is stored with actor identity and expiry.
4. resolution trace must include override metadata.
5. expired or revoked overrides are ignored.

Required audit attributes:

- `approved_by`
- `requested_by`
- `reason`
- `scope`
- `expires_at`
- `ticket_ref` (optional but recommended)

## Near-Term Build Targets

1. Define schema contracts for instruction resolution and override records.
2. Add resolver endpoint in Core (`/v1/instructions/resolve` candidate).
3. Wire Studio tools page to real tool registry and approval queues.
4. Integrate resolver into Council and AIDE agent/tool calls.
5. Add compatibility tests for precedence and policy enforcement.

## Compatibility Expectations

This architecture should remain compatible with:

- repo-local `skills.md` manifests,
- registry-managed skill metadata,
- existing Core persona and orchestration endpoints.
