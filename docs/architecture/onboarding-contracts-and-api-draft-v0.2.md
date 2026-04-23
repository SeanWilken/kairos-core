# Onboarding Contracts and API Draft v0.2

This draft defines the contract surface for the initial onboarding lifecycle and the next Studio-facing configuration phase.

## Scope and ownership

- `kairos-core`: bootstrap session lifecycle, runtime checks, artifact generation, ingest jobs, runtime handoff.
- `kairos-studio`: organization/persona/tool/workflow configuration and promotion workflows.
- `shared-contracts`: source of truth schemas and endpoint shape references.

## Contract set (draft)

Schemas added in `shared-contracts/schemas/interop/v0.2/`:

- `onboarding-bootstrap-session.schema.json`
- `onboarding-runtime-status.schema.json`
- `onboarding-ingest-job.schema.json`
- `bootstrap-local-env-input.schema.json`
- `studio-runtime-handoff.schema.json`
- `studio-organization-config.schema.json`
- `studio-persona-profile.schema.json`
- `studio-tool-integration.schema.json`
- `studio-workflow-definition.schema.json`
- `studio-environment-promotion.schema.json`
- `onboarding-contract-catalog.schema.json`

## Core API draft (needed next)

All responses remain wrapped in the v1 envelope (`meta`, `data`, `error`) and use tenant/org context headers.

### Bootstrap session lifecycle

- `POST /v1/bootstrap/sessions`
  - create a session from runtime/deployment/secrets/vector config
  - response `data` shape: `OnboardingBootstrapSession`
- `GET /v1/bootstrap/sessions/{session_id}`
  - read session state
  - response `data` shape: `OnboardingBootstrapSession`
- `PATCH /v1/bootstrap/sessions/{session_id}`
  - update draft sections (partial update)
  - response `data` shape: `OnboardingBootstrapSession`
- `POST /v1/bootstrap/sessions/{session_id}/preflight`
  - run static dependency/config validation
  - response `data` shape: check list + summary (compatible subset of `OnboardingRuntimeStatus`)
- `POST /v1/bootstrap/sessions/{session_id}/artifacts`
  - generate deploy artifacts for selected target
  - response `data` shape: artifact manifest + references
- `POST /v1/bootstrap/sessions/{session_id}/complete`
  - finalize setup and create Studio handoff
  - response `data` shape: `StudioRuntimeHandoff`

### Runtime verification

- `GET /v1/system/status`
  - current runtime subsystem health by check id
  - response `data` shape: `OnboardingRuntimeStatus`
- `POST /v1/system/checks/run`
  - execute active checks for current session
  - request includes `session_id` + selected check ids (optional)
  - response `data` shape: `OnboardingRuntimeStatus`

Required checks for `docker_local + pgvector` baseline:

- `core_health_endpoint`
- `postgres_reachable`
- `postgres_auth_valid`
- `postgres_database_exists`
- `pgvector_extension`
- `pgvector_version_compatible`
- `migration_permissions`
- `provider_connectivity` or `local_model_endpoint` (based on selected runtime mode)

### Document ingest

- `POST /v1/ingest/jobs`
  - enqueue ingest job after required runtime checks pass
  - request fields: `session_id`, `source_files`, `chunking_profile`, `embedding_profile`
  - response `data` shape: `OnboardingIngestJob`
- `GET /v1/ingest/jobs/{job_id}`
  - poll ingest status/results
  - response `data` shape: `OnboardingIngestJob`

### Handoff export

- `GET /v1/handoffs/{handoff_id}`
  - retrieve finalized handoff package
  - response `data` shape: `StudioRuntimeHandoff`

## Local-only generation inputs (never sent to server)

`bootstrap-local-env-input.schema.json` is intentionally client-local only. It allows collecting values needed to generate executable local scripts/env files quickly:

- database host/port/db/user/password
- existing vs new database mode
- local vs remote database location
- provider endpoint/model/api key (OpenAI and Anthropic first, custom optional)

Security requirements:

- Raw secrets (database password, API keys) stay local in memory unless user explicitly writes generated local env files.
- Raw secrets are never posted to Core API endpoints.
- Server-side contracts retain only references (for example `password_ref`) and required key names.

Generated local files should include defaults unless overridden:

- `POSTGRES_HOST=localhost`
- `POSTGRES_PORT=5432`
- `POSTGRES_DB=kairos`
- `POSTGRES_USER=kairos`
- `OPENAI_BASE_URL=https://api.openai.com/v1`
- `OPENAI_MODEL=gpt-4o-mini`

Generated bootstrap instructions should include:

- required local folder structure for generated files
- command examples for both `docker compose` and `podman compose`
- privacy disclosure for external provider usage (OpenAI/Anthropic)
- explicit RAG flow note (retrieval in Core, generation in selected provider model)

## Studio API draft (forward path)

### Organization

- `POST /v1/studio/organizations`
- `GET /v1/studio/organizations/{org_id}`
- `PATCH /v1/studio/organizations/{org_id}`
  - payload/response target: `StudioOrganizationConfig`

### Personas

- `POST /v1/studio/personas`
- `GET /v1/studio/personas/{persona_id}`
- `PATCH /v1/studio/personas/{persona_id}`
- `GET /v1/studio/personas?org_id={org_id}`
  - payload/response target: `StudioPersonaProfile`

### Tool integrations

- `POST /v1/studio/tools`
- `GET /v1/studio/tools/{tool_id}`
- `PATCH /v1/studio/tools/{tool_id}`
- `POST /v1/studio/tools/{tool_id}/validate`
  - payload/response target: `StudioToolIntegration`

### Workflows

- `POST /v1/studio/workflows`
- `GET /v1/studio/workflows/{workflow_id}`
- `PATCH /v1/studio/workflows/{workflow_id}`
- `POST /v1/studio/workflows/{workflow_id}/dry-run`
  - payload/response target: `StudioWorkflowDefinition`

### Environment promotion

- `POST /v1/studio/promotions`
- `GET /v1/studio/promotions/{promotion_id}`
- `POST /v1/studio/promotions/{promotion_id}/approve`
- `POST /v1/studio/promotions/{promotion_id}/apply`
  - payload/response target: `StudioEnvironmentPromotion`

## Do soon: realtime channel and chat unification

Add a lightweight websocket channel for runtime and collaboration signals:

- broadcast core connectivity changes (connected/disconnected/degraded)
- broadcast service health events for dependent components
- support unified chat transport so UX is cohesive across persona chat, council/meeting sessions, and colleague messaging

Studio implications:

- add onboarding/setup surfaces for chat server configuration (initially simple chat, Discord-like model later)
- include websocket/chat runtime metadata in Studio handoff and environment promotion compatibility checks

Implementation sequencing note:

- complete JWT auth/session rollout first so websocket channels can authenticate with the same access token context
- then add websocket gateway channels for:
  - system notifications (process complete, credit exhaustion, schedule events)
  - user presence/status
  - direct and persona/council chat streams
  - agent/LLM streamed interaction events

## Cross-cutting contract rules

- Include `spec_version` on every contract object.
- Use additive evolution for minor updates; breaking changes require new versioned schema files.
- Keep machine-readable `reason_code` values on all denied/failed outcomes.
- Preserve auditable fields (`tenant_id`, `org_id`, `correlation_id`, timestamps, actor ids).
- Do not persist raw secret values in contract payloads; persist references only.

## Bootstrap pipeline (implementation target)

1. Collect setup configuration and create bootstrap session.
2. Collect local-only secret/materialization inputs for env generation.
3. Generate local scripts/env templates with defaults and user overrides.
4. Start local services and run runtime checks.
5. Block ingest until all required checks pass.
6. Ingest docs with clearance/scope metadata.
7. Validate one persona chat path using RAG retrieval over approved documents.

## Implementation sequencing

1. Implement Core runtime endpoints first: `GET /v1/system/status`, `POST /v1/system/checks/run`, ingest job endpoints.
2. Add bootstrap session persistence endpoints.
3. Emit finalized `StudioRuntimeHandoff` from Core.
4. Implement Studio org/persona/tool/workflow endpoints.
5. Implement promotion endpoints with compatibility checks against handoff/runtime capabilities.
