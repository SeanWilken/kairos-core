# Development Plane Capability Matrix

Status: living internal handoff artifact
Audience: Core API, policy, knowledge, workflow, and integration-plane implementers

## Purpose

This document captures the current and anticipated capability model for MyAIDE's development plane so Core can expose the correct integration contracts across:

- policy and permissioning
- knowledge retrieval and relationship indexing
- workflow and approval access
- runtime tool exposure
- rollback and recovery
- memory / persistent constraint handling

The goal is to let AI participate as a first-class development collaborator without treating raw shell or unconstrained machine access as the primary integration primitive.

## Core Framing

The AI should not be granted arbitrary host access by default.

Instead, AI should receive scoped access to a governed development plane composed of:

- workspace and file-system surfaces
- runtime/build/inspection tools
- source control and source-sync tools
- knowledge-plane retrieval and relationship creation
- workflow/task/approval interfaces
- memory-writing interfaces
- rollback-aware execution and snapshot controls

Mode selection determines:

- which tools are visible
- whether execution is permitted
- whether approval is required
- whether rollback checkpoints are mandatory
- whether memory writes are allowed

## Plane Model

- Experience plane:
  - IDE, chat, pair-programming, review, operator UX
- Control plane:
  - Core identity, policy, orchestration, events, audit, approvals
- Development plane:
  - workspaces, runners, sandboxes, terminals, builds, runtime inspections
- Knowledge plane:
  - docs, repo context, relationship graph, memory, provenance
- Workflow plane:
  - tasks, approvals, handoffs, statuses, artifact transitions

## Session Modes

Current proposed modes and their intent:

### Plan

- No execution
- Reasoning, planning, dependency mapping, architecture relationships
- Knowledge-plane heavy
- Can propose plans, relationships, and future actions

### Build

- Produces real artifacts through the development plane
- Code, docs, images, videos, generated assets, patches, reports
- Can execute runner-bound commands where allowed

### Walkthrough

- No execution
- Generates deeper guides, procedural help, migration notes, runbooks, and explanations

### Explicit Permissions

- Execution allowed, but sensitive actions require granular approval
- Best for guarded or high-trust repos and environments

### Auto

- Broad autonomous execution within policy bounds
- Requires stronger audit, rollback, and kill-switch semantics

### Memory

- Writes persistent requirements, preferences, conventions, constraints, and context anchors
- Must be treated as governed durable state, not informal prompt hacks

## Capability Domains

The following capability domains should be modeled explicitly.

### 1. Workspace and File Capabilities

- read file
- open file
- list tree
- create file
- create directory
- write file
- move/rename file
- delete file or directory
- patch/apply diff
- create scratch artifact
- create or restore snapshot

### 2. Runtime and Command Capabilities

- run build/test command
- run shell command
- start interactive terminal session
- inspect job output/stdout/stderr
- inspect process/runtime health
- inspect running application behavior
- attach to remote runner or build server
- capability discovery for current runner
- install toolchain or dependency in sandbox

### 3. Source Control and Source Sync Capabilities

- inspect git status/diff/log
- validate source mirror/remote health
- sync source profile
- rotate source credential
- replay queued source actions
- create patch proposal against repo state
- branch-aware diff preparation

### 4. Knowledge Plane Capabilities

- retrieve related docs
- resolve context bundle for workspace/scope
- create or update relationships
- tag source provenance
- retrieve project conventions and decisions
- retrieve task-linked context
- attach docs to workspace or project scope
- capture references discovered during planning/build

### 5. Workflow Plane Capabilities

- read task/work item state
- create plan/work item
- update workflow status
- request approval
- attach artifact to workflow
- link runtime result to task
- create handoff note
- emit review status or escalation

### 6. Memory Capabilities

- write user preference memory
- write project convention memory
- write hard requirement memory
- write compliance or policy constraint memory
- read prior memory scoped to tenant/project/workspace/session
- revoke or supersede memory entries

### 7. Environment and Integration Capabilities

- inspect DB connection health
- run DB-safe introspection command
- inspect API/service health endpoints
- inspect logs from running instance
- inspect deployment/runtime metadata
- connect to external service by policy
- read environment profile metadata
- inspect runner capability inventory

### 8. Host and Infrastructure Capabilities

- inspect host hardware metadata
- inspect CPU, memory, disk, and network state
- inspect mounted filesystems
- inspect service/process inventory
- inspect container runtime state
- inspect remote machine facts through agent client
- run infrastructure-scoped commands through approved adapters
- capture diagnostics bundles for support or incident review

## Capability Matrix by Mode

Legend:

- allow: permitted without additional approval in that mode
- approve: permitted only with explicit approval or policy escalation
- deny: not available in that mode
- checkpoint: snapshot/rollback checkpoint required before action

| Capability Domain | Plan | Walkthrough | Build | Explicit Permissions | Auto | Memory |
|---|---|---|---|---|---|---|
| Read files/tree | allow | allow | allow | allow | allow | allow |
| Write/create/move files | deny | deny | checkpoint | approve + checkpoint | checkpoint | deny |
| Run shell/build commands | deny | deny | checkpoint | approve + checkpoint | checkpoint | deny |
| Interactive terminal | deny | deny | checkpoint | approve + checkpoint | checkpoint | deny |
| Runtime inspection/log read | allow | allow | allow | allow | allow | allow |
| Source sync/credential ops | deny | deny | approve | approve | approve | deny |
| Relationship creation in knowledge plane | allow | allow | allow | allow | allow | allow |
| Knowledge retrieval | allow | allow | allow | allow | allow | allow |
| Workflow read | allow | allow | allow | allow | allow | allow |
| Workflow write/status update | deny | deny | allow | approve | allow | deny |
| Approval request creation | deny | deny | allow | allow | allow | deny |
| Memory write | deny | deny | approve | approve | approve | allow |
| Snapshot create/restore | allow create only | allow create only | checkpoint required | approve + checkpoint | checkpoint | deny |
| External network action | deny | deny | approve | approve | approve | deny |
| DB introspection | deny | deny | approve | approve | approve | deny |
| Host/hardware inspection | deny | deny | approve | approve | approve | deny |

## Rollback and Recovery Requirements

Rollback should be a first-class concept in development-plane operations.

### Required rollback surfaces

- workspace snapshots
- patch proposal/apply history
- source diff audit trail
- runtime command log and correlation trail
- approval-linked restore checkpoints

### Recommended rollback checkpoints

- before multi-file agent write
- before dependency install
- before migration or DB-affecting command
- before broad autonomous task execution
- before source sync with writeback/replay semantics

### Core-facing rollback events

- snapshot.created
- snapshot.restored
- patch.proposed
- patch.applied
- command.started
- command.completed
- rollback.requested
- rollback.completed
- rollback.failed

## Policy and Permission Requirements for Core

Core should be able to decide access based on:

- tenant
- org
- team/persona
- user vs agent actor
- app id
- workspace id
- runner id
- capability requested
- resource target
- mode
- environment risk tier

Core should return machine-readable reason codes for:

- allow
- deny
- allow_with_approval
- allow_with_checkpoint
- runner_capability_missing
- resource_scope_invalid
- memory_write_disallowed

## Knowledge Plane Requirements for Core

To support the intended hybrid coding experience, Core or the knowledge plane should expose:

- workspace-scoped context retrieval
- file and code-unit relationship retrieval
- architecture decision lookup
- requirement and convention lookup
- relationship write/update interfaces
- provenance and citation metadata
- memory retrieval/write interfaces with policy scopes

## Workflow Plane Requirements for Core

Core should support AI-facing workflow interfaces for:

- plan creation
- task read/update
- approval request lifecycle
- artifact linking
- handoff note creation
- review status signaling
- checkpoint association with workflow states

## Runner and Sandbox Expectations

The development plane should not assume MyAIDE itself contains every SDK.

Instead, Core should expect MyAIDE to bind workspaces to runners/sandboxes that declare capabilities such as:

- git
- dotnet
- dotnet-sdk
- dotnet-fsi
- bun
- node
- python
- docker
- db-client capabilities

This enables:

- local process runners
- local containers
- remote build servers
- ephemeral agent sandboxes

## Cross-System Interaction Model

Core and the development plane should assume that:

- Core runs in a different container or service boundary than the development runtime.
- MyAIDE may run separately from the execution target.
- build servers, support nodes, utility machines, and remote hosts may all need to expose governed capabilities.

Because of that separation, the platform should not rely on implicit local process access between systems.

Instead, it should use a stable cross-system interaction model made of:

- a transport-neutral command DSL
- a thin execution client/agent that can be installed on machines
- Core-issued scoped action requests
- machine-reported capability inventories and telemetry

## Thin Client / Remote Execution Agent

A separate thin client should be considered a first-class integration target for the development plane.

This client could be installed on:

- developer workstations
- remote build servers
- utility nodes
- support machines
- sandbox hosts
- hardware-adjacent environments

The thin client would:

- register itself with Core or a designated control-plane endpoint
- advertise capability inventory
- receive scoped tool/action requests
- execute them within local policy and environment rules
- stream results, logs, facts, and errors back to the control plane

This keeps MyAIDE and Core extensible to other platforms instead of tightly coupling all execution into one container image.

## Command DSL Requirements

The cross-system interaction layer should use a durable DSL or action envelope rather than raw shell strings as the primary interop contract.

The DSL should support:

- action type
- capability class
- target scope
- actor and mode
- policy and approval metadata
- rollback/checkpoint requirements
- correlation id
- structured arguments
- structured outputs and artifacts

Example action families:

- file.read
- file.write
- file.move
- workspace.search
- runtime.command
- runtime.terminal.start
- runtime.terminal.send
- runtime.terminal.stop
- source.sync
- source.status
- workflow.plan.create
- workflow.approval.request
- knowledge.query
- memory.write
- host.inspect
- host.command
- service.logs.read
- db.inspect

The DSL should be extensible so other projects and platforms can implement compatible clients without inheriting MyAIDE-specific UI assumptions.

## Remote Machine and Hardware Insight

If the thin client is installed on other machines, the AI should be able to help with real operational and hardware-aware tasks, subject to policy.

Useful examples:

- explain current host resource pressure
- inspect disk usage and likely causes
- summarize service failures from logs
- describe mounted volumes and filesystem layout
- compare runner capability inventories across machines
- diagnose why a build server cannot execute a required tool
- guide an operator through recovery using live machine facts

This should still flow through the same governed development-plane model rather than bypassing Core policy.

## Suggested Project Boundary

The DSL and thin client should likely be treated as a reusable integration project or subsystem, not a one-off MyAIDE implementation detail.

That subsystem should be designed to support:

- MyAIDE development workflows
- Core-governed cross-app execution
- future platform integrations beyond MyAIDE
- remote machine introspection and utility operations

## Suggested Core Contract Additions

## Suggested Core Contract Additions

The following contract areas should be formalized or expanded in Core.

### Mode contract

- mode name
- allowed capability classes
- approval policy
- checkpoint policy
- memory write policy
- network/DB/source restrictions

### Runner contract

- runner id
- runner type
- capability inventory
- health state
- environment profile
- workspace binding rules

### Thin client contract

- client id
- client type
- host identity
- platform/os metadata
- capability inventory
- registration/auth model
- heartbeat/health model
- log and artifact streaming model
- policy scope and revocation model

### DSL action contract

- action schema version
- action family
- capability requirement
- target resource or machine scope
- structured arguments
- approval status
- checkpoint requirement
- expected artifact/result types
- timeout and cancellation semantics
- machine-readable failure codes

### Development action contract

- actor
- mode
- workspace id
- runner id
- action type
- resource target
- approval requirement
- checkpoint requirement
- correlation id

### Host and environment contract

- host facts
- hardware summary
- filesystem summary
- process/service inventory summary
- runtime/container inventory summary
- diagnostic bundle reference

### Memory contract

- memory type
- scope
- author
- provenance
- approval status
- supersession/revocation model

## Proposed Near-Term Priority Tools

These are the most useful first-class tools to prioritize for hybrid coding.

- file read/write/create/move
- workspace search
- runtime command execution
- terminal session start/send/stop
- job output inspection
- snapshot create/restore
- source sync/status
- context bundle retrieval
- knowledge lookup
- workflow plan/request approval
- memory read/write with scoped governance
- runner capability discovery
- host inspect and diagnostics retrieval

## Living Document Maintenance

This document should be updated as:

- new session modes are added
- new tool classes become first-class
- policy semantics are refined
- knowledge/workflow contracts become more concrete
- runner/sandbox model becomes implementation-backed

Append new sections rather than rewriting prior requirements unless the contract is intentionally changed.
