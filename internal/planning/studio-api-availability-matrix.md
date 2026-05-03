# Studio API Availability Matrix (Core Reference)

This document is the current handoff reference for `kairos-studio` integration against `kairos-core` backend APIs.

## Integration concerns + immediate next steps (Studio handoff)

These are current concerns found while wiring Studio against latest OpenAPI/runtime behavior.

### Contract concerns to address in Core

- Many endpoints still return generic `object` schemas with `additionalProperties=true`; Studio can integrate, but typed client generation and strict validation remain limited.
- Governance + collaboration endpoints in OpenAPI often enumerate only `200` and `422`, while runtime emits richer statuses (`401/403/404/409/410`) with reason codes.
- Websocket runtime contract is implemented and stable in code, but not represented in OpenAPI; event/action schema drift risk is increasing as chat orchestration evolves.
- Invite workflow currently models server-side invite records and acceptance, but email delivery/link-token setup contract still needs explicit first-class API shape.

### Immediate next steps recommended for Core

1. Add typed envelope response schemas for high-traffic endpoints:
   - `POST /v1/persona-config/import`
   - `GET/POST /v1/reviews/packs*`
   - `POST /v1/studio/channels/{channel_id}/chat`
   - governance endpoints (`/v1/studio/governance/*`, `/v1/studio/invites*`, `/v1/studio/onboarding/*`, `/v1/studio/settings`)
2. Expand OpenAPI error responses to match runtime behavior, including explicit reason-code examples for 4xx outcomes.
3. Publish websocket contract docs (or AsyncAPI) for:
   - connect/auth
   - incoming actions (`subscribe`, `publish`, `chat.typing`, `chat.send`)
   - emitted events (`system.connected`, `chat.message.user.created`, `chat.response.*`, `council.*`, `system.error`)
4. Finalize invite-email contract additions:
   - invite delivery metadata
   - invite link/code redemption semantics
   - expiry/retry/resend/cancel behavior
5. Add encrypted-at-rest support for AI-only private profile context fields by default (planned for user profile builder integration).

### Studio implementation assumptions until above lands

- Studio will continue defensive parsing of response `data` for mutable endpoints.
- Studio websocket tester uses the runtime route shape: `WS /v1/realtime/ws?token=<access_jwt>`.
- Studio persona + profile builder will treat private guidance fields as encrypted-at-rest required data classes.

## Available now

### Auth (new)

- `POST /v1/auth/register` (open)
- `POST /v1/auth/login` (open)
- `POST /v1/auth/refresh` (open)
- `POST /v1/auth/logout` (open)
- `GET /v1/auth/me` (protected)

### Install bootstrap (single-tenant profile)

- `GET /v1/bootstrap/tenant/status` (open)
- `POST /v1/bootstrap/tenant` (open, one-time in single-tenant mode)

### Bootstrap + runtime + ingest

- `POST /v1/bootstrap/sessions`
- `GET /v1/bootstrap/sessions`
- `GET /v1/bootstrap/sessions/{session_id}`
- `PATCH /v1/bootstrap/sessions/{session_id}`
- `GET /v1/system/status?session_id=...`
- `POST /v1/system/checks/run`
- `GET /v1/system/ai/providers`
- `GET /v1/system/ai/providers/{provider_id}/models`
- `GET /v1/system/audit/events`
- `POST /v1/ingest/jobs`
- `GET /v1/ingest/jobs/{job_id}`

### Knowledge index hub foundation (new)

- `POST /v1/knowledge/domains`
- `GET /v1/knowledge/domains`
- `POST /v1/knowledge/nodes`
- `GET /v1/knowledge/nodes`
- `POST /v1/knowledge/edges`
- `GET /v1/knowledge/edges`

### Studio foundation (new)

- `POST /v1/studio/organizations`
- `GET /v1/studio/organizations`
- `GET /v1/studio/organizations/{org_id}`
- `POST /v1/studio/users`
- `GET /v1/studio/users`
- `GET /v1/studio/users/{user_id}`
- `POST /v1/studio/memberships`
- `PATCH /v1/studio/memberships/{membership_id}`

### Collaboration foundation (new)

- `POST /v1/studio/divisions`
- `GET /v1/studio/divisions`
- `POST /v1/studio/teams`
- `GET /v1/studio/teams`
- `POST /v1/studio/teams/{team_id}/memberships`
- `GET /v1/studio/teams/{team_id}/memberships`
- `PATCH /v1/studio/team-memberships/{team_membership_id}`
- `POST /v1/studio/channels`
- `GET /v1/studio/channels`
- `POST /v1/studio/channels/{channel_id}/messages`
- `GET /v1/studio/channels/{channel_id}/messages`
- `POST /v1/studio/tasks`
- `GET /v1/studio/tasks`
- `GET /v1/studio/tasks/{task_id}`
- `PATCH /v1/studio/tasks/{task_id}`
- `POST /v1/studio/tasks/{task_id}/assignments`

### Realtime transport (new)

- `WS /v1/realtime/ws?token=<access_jwt>`

### Governance foundation (new)

- `GET /v1/studio/governance/baseline`
- `POST /v1/studio/invites`
- `POST /v1/studio/invites/{invite_id}/accept`
- `GET /v1/studio/onboarding/status`
- `POST /v1/studio/onboarding/complete`
- `GET /v1/studio/settings`
- `PATCH /v1/studio/settings`

### Persona catalog governance (new)

- `POST /v1/studio/personas/{persona_id}/approval`
- `GET /v1/studio/personas/{persona_id}/versions`
- `GET /v1/studio/personas/{persona_id}/versions/{version_id}`
- `POST /v1/studio/personas/{persona_id}/rollback/{version_id}`
- `GET /v1/studio/channels/{channel_id}/council-config`
- `PATCH /v1/studio/channels/{channel_id}/council-config`
- `PUT /v1/studio/channels/{channel_id}/personas`
- `GET /v1/studio/users/{user_id}/persona-contexts`
- `GET /v1/studio/users/{user_id}/persona-contexts/{persona_id}`
- `PUT /v1/studio/users/{user_id}/persona-contexts/{persona_id}`
- `GET /v1/persona-config/templates/categories`
- `GET /v1/persona-config/templates/options/{category_name}`
- `GET /v1/persona-config/prefabs`
- `GET /v1/persona-config/export`
- `POST /v1/persona-config/import`

### Pack review workflow (new)

- `GET /v1/reviews/packs`
- `GET /v1/reviews/packs/{queue_id}`
- `POST /v1/reviews/packs/{queue_id}/conversation`
- `POST /v1/reviews/packs/{queue_id}/decision`
- `POST /v1/reviews/packs/{queue_id}/approve`
- `POST /v1/reviews/packs/{queue_id}/reject`
- `POST /v1/reviews/packs/{queue_id}/request-changes`
- `POST /v1/reviews/packs/{queue_id}/install`

Behavior notes:

- Studio collaboration routes require bearer auth and tenant/org scope from JWT claims.
- Open routes intended for installation/bootstrap: health, bootstrap tenant status/create, auth register/login/refresh/logout, and system status.

- `POST /v1/studio/users` supports two bootstrapping paths:
  - global admin creation with no org membership required (`is_global_admin=true`)
  - org-scoped user creation with membership assignment
- `PATCH /v1/studio/memberships/{membership_id}` updates membership role/status for org assignment workflows.
- Duplicate email in the same tenant returns `409` with `reason_code=STUDIO_USER_EMAIL_EXISTS`.
- `org_id` is resolved from payload/JWT scope; non-global users without org context return `422` with `reason_code=STUDIO_ORG_REQUIRED_FOR_USER`.

### Persona-config import compatibility + Studio consumption rules

- `POST /v1/persona-config/import` now accepts three payload shapes:
  - V2 nested: `manifest + catalog.{categories,options,prefabs,...}`
  - V2 flat: `manifest + categories/options/prefabs/...`
  - V1 legacy: `pack_metadata + template_categories/template_options/prefab_segments/...`
- Unknown or ambiguous payloads are rejected with `reason_code=PACK_SCHEMA_UNKNOWN`.
- V1 imports are accepted but return deprecation warning entries (`PACK_SCHEMA_V1_DEPRECATED`) in response `data.warnings`.
- Import response now includes `data.detected_schema` for client telemetry and rollout validation.
- Import validation failures return `reason_code=PACK_IMPORT_VALIDATION_FAILED` with structured `details.errors`.
- Option/category normalization resolves category references across ID/name/display-name forms; unresolved references surface as `PACK_OPTION_CATEGORY_UNRESOLVED`.

### Pack install lifecycle for Studio UI

- Import should use `dry_run=true` first, show `warnings`, then submit final import.
- Queue entries remain non-installed after approval; installation is explicit via `POST /v1/reviews/packs/{queue_id}/install`.
- Approve/install guards:
  - required conversation tests must pass before approve (`PACK_REVIEW_REQUIRED_CASES_INCOMPLETE`)
  - install requires extracted `config.org_id` (`PACK_CONFIG_ORG_ID_REQUIRED`)
- Suggested Studio state machine:
  - `pending_review` -> `conversation_required` -> `approved` -> `installed`
  - `rejected` and `changes_requested` are terminal for that queue item (new import needed).

### Resume-builder alignment (pack + user profile)

- Studio should persist and surface optional payload sections:
  - `quick_config` (persona resume prefill)
  - `user_profile_template` (strengths/weaknesses/interests prefill)
- If missing, backend returns non-blocking warnings:
  - `PACK_QUICK_CONFIG_MISSING`
  - `PACK_USER_PROFILE_TEMPLATE_MISSING`
- `config.org_id` missing is also warning at import time (`PACK_INSTALL_ORG_ID_MISSING`) but blocks install later.

### Wrapper chat integration path (ready now)

- Use `POST /v1/studio/channels/{channel_id}/chat` for wrapper-backed channel chat.
- Create channel with persona binding (`default_persona_id`) via `POST /v1/studio/channels`.
- Chat route enforces persona approval policy for org modes (`approval_required`, `allowlist_only`).

### Interim global-admin bootstrap path (current implementation)

Until dedicated bootstrap/auth endpoints land, the frontend can create the initial super user with current foundation endpoints:

1. Ensure control organization exists (currently `global-control-plane`) via `POST /v1/studio/organizations` when needed
2. `POST /v1/studio/users` with:
   - `is_global_admin=true`
   - `role=owner`
   - `org_id=<control organization id>`
3. `GET /v1/studio/users/{user_id}` to verify persistence

Optional after global admin creation:

- Create first business organization now or skip and create multiple organizations later.

This is temporary and should be replaced by the explicit first-run flow once available:
- `GET /v1/bootstrap/status`
- `POST /v1/bootstrap/session`
- `POST /v1/bootstrap/global-admin`
- `/v1/auth/*`

## Gaps still open

### Bootstrap/auth lifecycle

- `GET /v1/bootstrap/status` (still open)
- `POST /v1/bootstrap/session` nonce challenge variant
- `POST /v1/bootstrap/global-admin`

### Membership + access controls

- remaining membership endpoints (`GET /v1/studio/memberships`, `GET /v1/studio/memberships/{membership_id}`, delete/deactivate)
- role catalog/assignment endpoints
- policy definition/assignment endpoints
- effective access resolution endpoint

### Domain roots (decided direction)

Use split domain roots now (instead of adding more `/v1/studio/*`) to avoid later migration complexity:

- personas under `/v1/personas/*`
- tools under `/v1/tools/*`
- workflows under `/v1/workflows/*`
- knowledge under `/v1/knowledge/*`
- api keys under `/v1/api-keys/*`
- usage under `/v1/usage/*`
- auth under `/v1/auth/*`
- memberships under `/v1/memberships/*`

`/v1/studio/*` remains as current foundation endpoints until parity endpoints exist in split roots.

### Studio config domains

- personas endpoints under `/v1/personas/*`
- tools endpoints under `/v1/tools/*`
- workflows endpoints under `/v1/workflows/*`
- promotion endpoints under `/v1/promotions/*`

### Collaboration + realtime extensions

- channel moderation and per-channel policy endpoints
- websocket presence and durable notification feed endpoints
- team metrics snapshot endpoints

### Knowledge + API keys + usage

- knowledge document endpoints (`/v1/knowledge/*`)
- API key lifecycle endpoints (`/v1/api-keys/*`)
- usage/budget/limits endpoints (`/v1/usage/*`)

## Next implementation sequence (recommended)

1. Bootstrap + global admin lifecycle
   - `GET /v1/bootstrap/status`
   - `POST /v1/bootstrap/session` (nonce challenge variant)
   - `POST /v1/bootstrap/global-admin`
2. Auth lifecycle
   - `POST /v1/auth/login`
   - `POST /v1/auth/refresh`
   - `POST /v1/auth/logout`
   - `GET /v1/auth/me`
   - `POST /v1/auth/verify`
3. Membership + RBAC baseline
   - `POST /v1/memberships`
   - `PATCH /v1/memberships/{membership_id}`
   - role/policy assignment and effective access endpoint
4. Studio onboarding domains
   - `POST /v1/personas`
   - `POST /v1/knowledge/documents`
   - `POST /v1/knowledge/ingestion/jobs`
   - `POST /v1/knowledge/access/grants`
5. App integration + governance controls
   - `/v1/api-keys/*`
   - `/v1/usage/*`

## Data model foundation currently in DB

- `studio_users`
- `studio_organizations`
- `studio_org_memberships`
- `studio_divisions`
- `studio_teams`
- `studio_team_memberships`
- `studio_channels`
- `studio_channel_participants`
- `studio_channel_messages`
- `studio_personas`
- `studio_tasks`
- `studio_task_assignments`
- `studio_org_invites`
- `studio_org_settings`
- `studio_org_onboarding`
- `persona_template_categories`
- `persona_template_options`
- `prompt_prefabs`
- `prompt_catalog_bundles`
- `persona_versions`
- `persona_version_history`
- `user_persona_contexts`
- `room_council_config`
- `room_personas`
- `pack_import_queue`
- `pack_review_conversations`

Migration required:

- `migrations/0002_studio_identity_foundation.sql`
- `migrations/0004_collaboration_foundation.sql`
- `migrations/0005_persona_and_chat_runtime.sql`
- `migrations/0006_studio_governance_foundation.sql`
- `migrations/0007_persona_template_options.sql`
- `migrations/0008_persona_versioning.sql`
- `migrations/0009_prompt_prefabs.sql`
- `migrations/0010_user_persona_context.sql`
- `migrations/0011_room_council_config.sql`
- `migrations/0012_prompt_catalog_governance.sql`
- `migrations/0013_pack_review_workflow.sql`
- `migrations/0014_orchestration_runs_and_event_outbox.sql`
- `migrations/0015_audit_events.sql`
- `migrations/0016_knowledge_index_foundation.sql`

## Studio integration guidance

- Use this matrix as source of truth for what can be wired immediately.
- Treat unresolved endpoints as TODOs in Studio adapters, not runtime assumptions.
- Prefer JWT tenant/org scope for protected routes; headers are no longer the primary auth context.
