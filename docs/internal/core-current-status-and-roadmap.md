# Core Current Status And Roadmap

Status date: 2026-07-11

## Working Now

### Chat and websocket contracts

- Structured assistant block payloads with stable block metadata
- Additive websocket events for response start, block emission, and completion
- Persona capability discovery and persona-query with resolved context

Primary docs:

- `backend/docs/chat-api-consumption.md`
- `backend/docs/chat-block-rendering-contract.md`
- `backend/docs/context-and-persona-ai-usage.md`

### Knowledge and context resolution

- ACL-aware knowledge entity and relationship upsert
- Deterministic context resolve and explain
- Explicit query signal extraction from tags, backticks, paths, and object phrases
- Structured `reference_maps` for users, projects, tasks, files, code, documents, and glossary terms
- Deterministic compaction and token-aware pruning

Primary endpoints:

- `POST /v1/context/resolve`
- `POST /v1/context/explain`
- `POST /v1/context/persona-query`
- `POST /v1/knowledge/entities/upsert`
- `POST /v1/knowledge/relationships/upsert`
- `POST /v1/graph/ingest-delta`

### Knowledge node and code-memory contracts

- Generic knowledge node list/detail retrieval
- Canonical knowledge conventions for `file`, `symbol`, `project`, `glossary_term`
- Canonical reuse relationship types
- Code ingest helper for project/file/symbol graph creation and reuse links

Primary endpoints:

- `GET /v1/knowledge/conventions`
- `POST /v1/knowledge/code-ingest`
- `GET /v1/knowledge/nodes`
- `GET /v1/knowledge/nodes/{entity_id}`

Primary docs:

- `backend/docs/knowledge-node-api.md`
- `backend/docs/knowledge-code-ingest-api.md`
- `docs/ecosystem/knowledge-entity-and-reuse-conventions-v0.1.md`

### Development capability inventory

- Workspace capability inventory
- Runner capability inventory
- Deterministic capability resolution with:
  - ready
  - install required
  - proposal only
  - blocked by policy
  - unavailable
- Development policy check for capability + path target evaluation

Primary endpoints:

- `GET /v1/development/workspaces/{workspaceId}/capabilities`
- `GET /v1/development/runners/{runnerId}/capabilities`
- `POST /v1/development/capabilities/resolve`
- `POST /v1/policy/development/check`

Primary docs:

- `backend/docs/development-capability-api.md`
- `docs/internal/myaide-tool-and-capability-core-requirements.md`

### Tool catalog and runtime discovery

- Static tool catalog
- Runtime registry for currently detectable runtime-backed tools

Primary endpoints:

- `GET /v1/tools/catalog`
- `GET /v1/tools/runtime-registry`

### Workflow graph persistence and review

- Workflow definition CRUD
- Dry-run rule evaluation
- Run start and run resume
- Deterministic execution for supported node kinds
- Review queue and review decision handling

Primary endpoints:

- `POST /v1/studio/workflows`
- `GET /v1/studio/workflows`
- `GET /v1/studio/workflows/{workflow_id}`
- `PATCH /v1/studio/workflows/{workflow_id}`
- `POST /v1/studio/workflows/{workflow_id}/dry-run`
- `POST /v1/studio/workflows/{workflow_id}/runs`
- `GET /v1/studio/workflows/{workflow_id}/runs`
- `GET /v1/studio/workflow-runs/{run_id}`
- `POST /v1/studio/workflow-runs/{run_id}/resume`
- `GET /v1/studio/workflow-reviews`
- `POST /v1/studio/workflow-reviews/{review_id}/decision`

### Voice and direct provider surfaces

- Direct provider chat
- Voice STT/TTS endpoints
- Optional transcript persistence into knowledge

## Ownership Boundary

### MyAIDE should own

- live LSP processes
- diagnostics execution
- lint and formatting execution
- editor/runtime orchestration
- websocket/session handling for development tooling

### Core should own

- capability vocabulary
- capability inventory and capability resolution
- policy and approval decisions
- durable memory and governed knowledge promotion
- workflow, audit, and event correlation

## Near-Term Upcoming

- development capability resolution refinements tied to more workspace policy inputs
- richer code-ingest/reuse-link automation from repo scans
- workflow execution expansion beyond current node kinds
- artifact lineage improvements for promoted and workflow-emitted artifacts
- broader use of profile preferences across wrappers and workflow creation

## Down The Line

- tool-pack install/uninstall/repair contracts
- optional Core-visible language-service session contracts when MyAIDE needs shared state
- diagnostics/lint/format contract surfaces where Core policy or durable records are needed
- fine-grained protected-path and proposal-only development policy APIs
- durable MyAIDE thread and execution-session contracts
- richer workspace/project memory scopes and development event taxonomy
