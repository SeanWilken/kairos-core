# Studio API Availability Matrix (Core Reference)

This document is the current handoff reference for `kairos-studio` integration against `kairos-core` backend APIs.

## Available now

### Auth (new)

- `POST /v1/auth/register` (open)
- `POST /v1/auth/login` (open)
- `POST /v1/auth/refresh` (open)
- `POST /v1/auth/logout` (open)
- `GET /v1/auth/me` (protected)

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

Behavior notes:

- Studio routes now require bearer auth and tenant/org scope from JWT claims.
- Open routes intended for installation/bootstrap: health, system status, auth, and registration.

- `POST /v1/studio/users` supports two bootstrapping paths:
  - global admin creation with no org membership required (`is_global_admin=true`)
  - org-scoped user creation with membership assignment
- `PATCH /v1/studio/memberships/{membership_id}` updates membership role/status for org assignment workflows.
- Duplicate email in the same tenant returns `409` with `reason_code=STUDIO_USER_EMAIL_EXISTS`.
- `org_id` can be provided in payload; if omitted, request `X-Org-ID` is used.
- non-global users without org context return `422` with `reason_code=STUDIO_ORG_REQUIRED_FOR_USER`.

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

- `GET /v1/bootstrap/status`
- `POST /v1/bootstrap/session` nonce challenge variant
- `POST /v1/bootstrap/global-admin`
- JWT auth endpoints (`/v1/auth/*`)

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

Migration required:

- `migrations/0002_studio_identity_foundation.sql`

## Studio integration guidance

- Use this matrix as source of truth for what can be wired immediately.
- Treat unresolved endpoints as TODOs in Studio adapters, not runtime assumptions.
- Keep all requests scoped with `X-Tenant-ID` and `X-Org-ID` until token auth rollout lands.
