# Studio API Availability Matrix (Core Reference)

This document is the current handoff reference for `kairos-studio` integration against `kairos-core` backend APIs.

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
- `POST /v1/ingest/jobs`
- `GET /v1/ingest/jobs/{job_id}`

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

Behavior notes:

- Studio collaboration routes require bearer auth and tenant/org scope from JWT claims.
- Open routes intended for installation/bootstrap: health, bootstrap tenant status/create, auth register/login/refresh/logout, and system status.

- `POST /v1/studio/users` supports two bootstrapping paths:
  - global admin creation with no org membership required (`is_global_admin=true`)
  - org-scoped user creation with membership assignment
- `PATCH /v1/studio/memberships/{membership_id}` updates membership role/status for org assignment workflows.
- Duplicate email in the same tenant returns `409` with `reason_code=STUDIO_USER_EMAIL_EXISTS`.
- `org_id` is resolved from payload/JWT scope; non-global users without org context return `422` with `reason_code=STUDIO_ORG_REQUIRED_FOR_USER`.

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

Migration required:

- `migrations/0002_studio_identity_foundation.sql`
- `migrations/0004_collaboration_foundation.sql`
- `migrations/0005_persona_and_chat_runtime.sql`
- `migrations/0006_studio_governance_foundation.sql`

## Studio integration guidance

- Use this matrix as source of truth for what can be wired immediately.
- Treat unresolved endpoints as TODOs in Studio adapters, not runtime assumptions.
- Prefer JWT tenant/org scope for protected routes; headers are no longer the primary auth context.
