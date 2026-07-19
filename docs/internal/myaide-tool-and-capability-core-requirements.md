# MyAIDE Tool And Capability Core Requirements

Status: proposed internal contract draft
Audience: Core API, policy, workflow, memory, knowledge, and integration-plane implementers

## Purpose

This document turns MyAIDE's development-plane needs into a Core-facing contract proposal.

The goal is to align on what Core should govern, expose, and persist so MyAIDE can deliver:

- first-class agent tooling
- durable chat and thread workflows
- installable language and developer tooling
- runner-aware capability discovery
- directory-scoped execution and write permissions
- workflow, approval, memory, and audit alignment

This is not meant to force a single implementation shape. It is meant to define the minimum contract surfaces Core should support so MyAIDE and Core can evolve together without ad hoc coupling.

## Product Framing

MyAIDE is the operational development surface.

Core is the canonical control plane for:

- policy
- approval
- durable memory
- workflow orchestration
- capability vocabulary
- audit and event contracts

MyAIDE should not have to invent its own incompatible capability model for tools, permissions, sessions, and memory.

## Design Principles

### 1. Capability-first, not shell-first

Core should understand named capabilities such as `repo.status` or `language.server.start`, not just broad "run a command" access.

### 2. Runner-aware, not image-assumed

The API image should not be assumed to contain every SDK, formatter, linter, or language server.

Capabilities should be discoverable from the bound runner, dev container, or remote execution target.

### Ownership boundary

MyAIDE should own live development tooling execution such as:

- language server processes
- diagnostics collection
- lint execution
- formatting execution
- editor/runtime orchestration

Core should own the canonical contract and governance layer around those capabilities, including:

- capability vocabulary
- capability inventory and resolution
- policy and approval decisions
- durable memory and knowledge promotion
- workflow, audit, and event correlation

Core does not need to host or run every LSP, formatter, linter, or diagnostics process itself.

### 3. Scoped permissions, not repo-wide trust

Permissions should support:

- read/write/execute separation
- directory-prefix constraints
- glob-based constraints
- proposal-only protected areas
- environment-specific restrictions

### 4. Durable contracts, not session-only prompt behavior

Threads, tool inventory, memory, approvals, and workflow actions should be first-class persisted resources where appropriate.

### 5. Auditability and rollback

Tool execution, approvals, installs, writes, and protected-path proposals should produce durable event/audit records.

## Core Requirement Areas

Core should support the following requirement areas for MyAIDE.

1. workspace and runner capability inventory
2. tool catalog and tool installation contracts
3. durable chat thread and execution session contracts
4. language server and diagnostics contracts
5. fine-grained policy and protected-path contracts
6. workflow and approval integration
7. durable memory integration
8. event and audit correlation

## 1. Workspace And Runner Capability Inventory

MyAIDE needs Core to understand what a workspace can actually do based on the currently bound runner.

### Proposed resources

- `WorkspaceCapabilityProfile`
- `RunnerCapabilityProfile`
- `CapabilityGrant`
- `ToolInstallationRecord`

### Proposed `WorkspaceCapabilityProfile`

```json
{
  "workspaceId": "ws_123",
  "runnerId": "runner_local_01",
  "snapshotAt": "2026-07-11T18:00:00Z",
  "capabilities": [
    {
      "key": "repo.status",
      "status": "available",
      "source": "native"
    },
    {
      "key": "language.fsharp.lsp",
      "status": "installable",
      "source": "tool-pack",
      "toolPackId": "fsharp-core-pack"
    },
    {
      "key": "format.prettier",
      "status": "installed",
      "source": "tool-pack",
      "version": "3.6.0"
    }
  ]
}
```

### Capability status values

- `available`
- `installed`
- `installable`
- `unavailable`
- `blocked_by_policy`
- `degraded`

### Core requirements

Core should support:

- listing capability inventory for a workspace
- listing capability inventory for a runner
- resolving capability requirements for a requested action
- returning policy-blocked vs missing-tool distinctions
- attaching provenance for capability detection

### Suggested endpoints

- `GET /v1/development/workspaces/{workspaceId}/capabilities`
- `GET /v1/development/runners/{runnerId}/capabilities`
- `POST /v1/development/capabilities/resolve`

## 2. Tool Catalog And Installation Contracts

MyAIDE needs one-click install and verification support for developer tools.

These tools should be modeled as installable packs or managed units, not just random terminal setup instructions.

### Examples

- FsAutoComplete
- TypeScript language server
- ESLint
- Prettier
- Tailwind language server
- Pyright
- markdownlint
- Dockerfile tooling

### Proposed resources

- `ToolPack`
- `ToolPackVersion`
- `ToolInstallRequest`
- `ToolInstallOperation`
- `ToolHealthReport`

### Proposed `ToolPack`

```json
{
  "toolPackId": "fsharp-core-pack",
  "name": "F# Core Pack",
  "provides": [
    "language.fsharp.lsp",
    "dotnet-fsi"
  ],
  "supportedTargets": ["local-runner", "container-runner"],
  "installModes": ["ui", "cli", "policy-approved-auto"],
  "defaultVersion": "1.0.0"
}
```

### Core requirements

Core should support:

- listing tool packs available for a runner type
- listing installed tool packs for a workspace or runner
- requesting install/uninstall/repair
- verifying installed tool health
- surfacing operation progress and failures
- linking installed tools to resulting capabilities

### Suggested endpoints

- `GET /v1/development/tool-packs`
- `GET /v1/development/runners/{runnerId}/tool-packs`
- `POST /v1/development/runners/{runnerId}/tool-installs`
- `POST /v1/development/runners/{runnerId}/tool-uninstalls`
- `POST /v1/development/runners/{runnerId}/tool-verifications`
- `GET /v1/development/tool-operations/{operationId}`

### Suggested operation statuses

- `queued`
- `running`
- `succeeded`
- `failed`
- `cancelled`
- `blocked_by_policy`

## 3. Durable Chat Thread And Execution Session Contracts

MyAIDE already has a working chat transport, but Core should define the durable contract for threads and assisted execution sessions.

### Why this matters

MyAIDE needs more than transient chat messages. It needs:

- thread list views
- project/task-linked conversations
- distinction between planning and execution sessions
- review/approval context per thread
- durable recovery after restart

### Proposed resources

- `Thread`
- `ThreadMessage`
- `ExecutionSession`
- `SessionToolAction`
- `ThreadAssociation`

### Proposed thread types

- `plan`
- `pair`
- `execution`
- `review`
- `walkthrough`
- `triage`

### Proposed `Thread`

```json
{
  "threadId": "thr_123",
  "workspaceId": "ws_123",
  "type": "execution",
  "title": "Stabilize shell extraction",
  "status": "active",
  "linkedTaskIds": ["task_42"],
  "linkedRepoIds": ["repo_myaide"],
  "sessionMode": "build",
  "createdBy": "user_1",
  "createdAt": "2026-07-11T18:00:00Z"
}
```

### Proposed `ExecutionSession`

```json
{
  "sessionId": "sess_123",
  "threadId": "thr_123",
  "workspaceId": "ws_123",
  "mode": "build",
  "runnerId": "runner_local_01",
  "approvalMode": "explicit_permissions",
  "rollbackPolicy": "checkpoint_before_write",
  "status": "active"
}
```

### Core requirements

Core should support:

- creating and listing threads by workspace/project/task
- persisting messages and structured tool actions
- distinguishing planning-only vs tool-enabled execution sessions
- storing session policy mode and approval requirements
- linking thread/session records to workflow and audit events

### Suggested endpoints

- `GET /v1/threads?workspaceId={workspaceId}`
- `POST /v1/threads`
- `GET /v1/threads/{threadId}`
- `POST /v1/threads/{threadId}/messages`
- `POST /v1/threads/{threadId}/sessions`
- `GET /v1/sessions/{sessionId}`
- `POST /v1/sessions/{sessionId}/tool-actions`

## 4. Language Server And Diagnostics Contracts

MyAIDE needs Core-aligned contracts for browser-hosted editor intelligence.

This should be modeled around language-service capabilities, not around direct VS Code extension assumptions.

### Execution ownership clarification

These contracts do not require Core to host the underlying language-service runtime.

Preferred operating model:

- MyAIDE server owns live language-service, diagnostics, lint, and formatting execution.
- Core exposes the durable contract surfaces, capability status, policy checks, artifact promotion paths, and audit linkage that MyAIDE depends on.

This keeps MyAIDE as the operational development plane while Core remains the canonical control plane.

### Proposed resources

- `LanguageServiceRegistration`
- `LanguageServiceSession`
- `DiagnosticReport`
- `FormattingRequest`
- `LintRequest`

### Proposed capability keys

- `language.fsharp.lsp`
- `language.typescript.lsp`
- `language.python.lsp`
- `diagnostics.list`
- `lint.eslint`
- `format.prettier`
- `format.dotnet`

### Core requirements

Core should support:

- listing language services available to a workspace
- optionally tracking or brokering language-service session lifecycle for a workspace when MyAIDE wants Core-visible session state
- querying service health and version
- persisting diagnostics snapshots where useful
- exposing explicit lint and format operations as governed actions when those operations need Core policy, workflow, or memory linkage

### Suggested endpoints

- `GET /v1/development/workspaces/{workspaceId}/language-services`
- `POST /v1/development/workspaces/{workspaceId}/language-services/{serviceKey}/sessions` if Core-visible session state is needed
- `DELETE /v1/development/language-service-sessions/{sessionId}` if Core-visible session state is needed
- `GET /v1/development/language-service-sessions/{sessionId}` if Core-visible session state is needed
- `POST /v1/development/workspaces/{workspaceId}/diagnostics`
- `POST /v1/development/workspaces/{workspaceId}/lint`
- `POST /v1/development/workspaces/{workspaceId}/format`

### Suggested realtime event families

- `language_service.session.started`
- `language_service.session.failed`
- `diagnostics.updated`
- `lint.completed`
- `format.completed`

## 5. Fine-Grained Policy And Protected Path Contracts

This is one of the most important Core requirements.

MyAIDE needs more than coarse workspace-level allow/deny behavior.

### Proposed resources

- `WorkspacePolicyProfile`
- `CapabilityRule`
- `PathRule`
- `ApprovalRequirement`
- `ProtectedArea`

### Proposed `PathRule`

```json
{
  "pathRuleId": "rule_123",
  "workspaceId": "ws_123",
  "matchType": "glob",
  "pattern": "src/MyFeature/**",
  "read": "allow",
  "write": "allow",
  "execute": "deny",
  "proposal": "allow"
}
```

### Required policy behaviors

Core should be able to express:

- allow read but deny write
- allow proposal but deny apply
- allow write only inside specific directory prefixes
- require approval for command execution matching risk classes
- block tool installs on protected runners
- apply different rules by workspace, repo, mode, persona, environment, or task state

### Example protected areas

- deployment manifests
- production environment config
- auth policy files
- billing logic
- secrets-bearing paths

### Suggested policy-check endpoint

- `POST /v1/policy/development/check`

Suggested request shape:

```json
{
  "workspaceId": "ws_123",
  "sessionId": "sess_123",
  "capability": "fs.write",
  "targets": [
    {
      "kind": "path",
      "value": "src/MyFeature/NewModule.fs"
    }
  ],
  "mode": "build"
}
```

Suggested response shape:

```json
{
  "decision": "allow",
  "approvalRequired": false,
  "matchedRules": ["rule_123"],
  "obligations": ["create_checkpoint_before_write"]
}
```

## 6. Workflow And Approval Integration

MyAIDE needs session actions and outputs to connect cleanly to Core workflow entities.

### Proposed resources

- `WorkflowAssociation`
- `ApprovalRequest`
- `ApprovalDecision`
- `ArtifactLink`
- `ExecutionCheckpoint`

### Core requirements

Core should support:

- linking a thread/session to a task, milestone, incident, or initiative
- requesting approval for protected actions
- attaching artifacts such as patches, reports, diagnostics bundles, or screenshots
- recording checkpoints before risky operations
- recording approval rationale and reviewer identity

### Suggested endpoints

- `POST /v1/workflow/associations`
- `POST /v1/approvals`
- `POST /v1/approvals/{approvalId}/decisions`
- `POST /v1/artifacts/links`
- `POST /v1/checkpoints`

### Suggested approval trigger examples

- apply patch in protected path
- install tool pack on shared runner
- execute external-network command
- run DB-affecting command
- write durable memory outside allowed category

## 7. Durable Memory Integration

MyAIDE needs a governed way to persist user, project, and workspace constraints that should survive sessions.

### Proposed memory categories

- user preference
- project convention
- hard requirement
- compliance constraint
- environment warning
- workflow note

### Core requirements

Core should support:

- scoped memory reads by tenant/project/workspace/thread/session
- durable memory writes with policy enforcement
- superseding or revoking outdated memory
- provenance and author tracking
- optional requirement strength or confidence metadata

### Suggested endpoints

- `GET /v1/memory?workspaceId={workspaceId}`
- `POST /v1/memory`
- `POST /v1/memory/{memoryId}/supersede`
- `POST /v1/memory/{memoryId}/revoke`

## 8. Event And Audit Correlation

Core should be the canonical event and audit plane for assisted development activity.

### Required correlation fields

- `workspaceId`
- `threadId`
- `sessionId`
- `runnerId`
- `taskId`
- `approvalId`
- `correlationId`
- `actorType`
- `actorId`

### Recommended event families

- `thread.created`
- `thread.message.created`
- `session.started`
- `session.completed`
- `tool.action.requested`
- `tool.action.completed`
- `tool.install.requested`
- `tool.install.completed`
- `policy.check.performed`
- `approval.requested`
- `approval.decided`
- `checkpoint.created`
- `memory.written`
- `memory.revoked`
- `diagnostics.updated`

### Audit expectations

Core should retain enough information to answer:

- what the assistant tried to do
- what policy was checked
- what approval was required or bypassed
- what tool version/environment was involved
- what files/paths/targets were affected
- what checkpoint or rollback surface existed before action

## 9. Suggested Capability Vocabulary

Core should standardize a capability vocabulary that MyAIDE can depend on.

### File and workspace

- `fs.read`
- `fs.write`
- `fs.move`
- `fs.delete`
- `workspace.search`
- `workspace.snapshot.create`
- `workspace.snapshot.restore`
- `workspace.patch.propose`
- `workspace.patch.apply`

### Runtime and shell

- `runtime.command`
- `runtime.terminal.start`
- `runtime.terminal.input`
- `runtime.terminal.stop`
- `runtime.job.inspect`
- `runtime.logs.read`
- `runtime.process.inspect`

### Repo and source

- `repo.status`
- `repo.diff`
- `repo.log`
- `repo.pull_latest`
- `repo.fetch`
- `repo.checkout`
- `source.profile.upsert`
- `source.sync`

### Language and tooling

- `language.server.start`
- `language.server.stop`
- `language.server.query`
- `diagnostics.list`
- `lint.run`
- `format.run`
- `tool.install`
- `tool.verify`

### Workflow and memory

- `workflow.plan.create`
- `workflow.task.update`
- `workflow.approval.request`
- `workflow.handoff.create`
- `memory.read`
- `memory.write`
- `memory.revoke`

## 10. Recommended MVP Order

To keep this practical, Core and MyAIDE should align on implementation order.

### MVP 1

- capability vocabulary
- workspace/runner capability inventory
- policy check contract for tool/path actions
- durable threads and session metadata

### MVP 2

- tool pack catalog and install operations
- language-service registration/session contracts
- approval + checkpoint linking

### MVP 3

- durable memory authoring/revocation
- richer workflow associations
- advanced protected-path/proposal-only semantics
- broader event and audit reporting

## 11. Open Alignment Questions For Core

Core and MyAIDE should explicitly decide:

1. Should threads live in a general cross-product conversation model or a development-specific thread model?
2. Should policy checks be synchronous request/response only, or also support long-running approval escalation flows?
3. Should tool installs be modeled as workflow operations, tool operations, or both?
4. Does Core want one shared capability vocabulary across all products, or a development-plane extension namespace?
5. Which event bus or audit substrate is the source of truth for development-plane actions?
6. How much of runner capability discovery is owned by Core vs reported by MyAIDE/runtime adapters?

## 12. Bottom Line

For MyAIDE to become a serious human+AI development environment, Core needs to expose more than generic chat and broad permission flags.

The minimum strategic contract is:

- durable threads and execution sessions
- named capability inventory
- managed tool installation and verification
- language-service and diagnostics contracts
- fine-grained path/capability policy checks
- workflow/approval/checkpoint integration
- durable memory and audit correlation

If Core provides those surfaces, MyAIDE can build the operational UX without hardcoding policy, memory, or tool governance into the IDE itself.
