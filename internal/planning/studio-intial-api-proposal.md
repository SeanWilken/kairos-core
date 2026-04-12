# Kairos Core API Draft (OpenAPI-First)

Scope: bootstrap + global admin/auth + org hierarchy + personas + knowledge/vector + RBAC + API keys + usage.

## API conventions

- Base path: `/v1`
- Envelope shape: `{ meta, data, error }`
- First-run bootstrap endpoints use session + nonce challenge
- Protected endpoints use bearer JWT after auth rollout
- Tenant/org scoping enforced on every request (`X-Tenant-ID`, `X-Org-ID`)

## Domain roots decision

Adopt split domain roots now to avoid later migration complexity.

- `/v1/bootstrap/*`
- `/v1/auth/*`
- `/v1/organizations/*`
- `/v1/users/*`
- `/v1/memberships/*`
- `/v1/roles/*`
- `/v1/policies/*`
- `/v1/access/*`
- `/v1/personas/*`
- `/v1/tools/*`
- `/v1/workflows/*`
- `/v1/knowledge/*`
- `/v1/api-keys/*`
- `/v1/usage/*`

`/v1/studio/*` can remain temporarily for backward compatibility during transition.

## Global admin bootstrap flow

1. `GET /v1/bootstrap/status`
   - returns `is_initialized`, `has_global_admin`, `user_count`
2. `POST /v1/bootstrap/session`
   - returns `session_id`, `nonce`, `expires_at`
3. `POST /v1/bootstrap/global-admin`
   - allowed only when `user_count == 0`
   - validates unique email and optional phone
   - atomically creates global admin and marks system initialized
4. `POST /v1/auth/login`
   - global admin logs in and receives JWT session
5. `POST /v1/organizations`
   - first organization is created after initial login

## Interim implementation note (before auth endpoints)

Current frontend implementation can bootstrap a first super user using available foundation routes:

1. `POST /v1/studio/users` with `is_global_admin=true` (no organization required)
2. `GET /v1/studio/users/{user_id}` to confirm DB persistence
3. Create organizations later via `POST /v1/studio/organizations` and memberships as needed

Then optionally create first business organization (or skip and create later).

Global-admin governance requirement (target behavior):

- Global admin is stack-wide (above organizations).
- Grant/revoke of global-admin role requires majority vote of existing global admins.

Once explicit bootstrap/auth endpoints are implemented, migrate to:

- `GET /v1/bootstrap/status`
- `POST /v1/bootstrap/session`
- `POST /v1/bootstrap/global-admin`
- `/v1/auth/*`

## Priority path set (v1)

### Bootstrap/auth

- `GET /v1/bootstrap/status`
- `POST /v1/bootstrap/session`
- `POST /v1/bootstrap/global-admin`
- `POST /v1/auth/login`
- `POST /v1/auth/refresh`
- `POST /v1/auth/logout`
- `GET /v1/auth/me`
- `POST /v1/auth/verify`

### Identity and hierarchy

- `POST /v1/organizations`
- `GET /v1/organizations`
- `GET /v1/organizations/{org_id}`
- `POST /v1/organizations/{org_id}/branches`
- `GET /v1/organizations/{org_id}/branches`
- `POST /v1/users/invite`
- `POST /v1/users/accept-invite`
- `GET /v1/users`
- `GET /v1/users/{user_id}`
- `POST /v1/memberships`
- `PATCH /v1/memberships/{membership_id}`

### RBAC/policy

- `GET /v1/roles`
- `POST /v1/roles`
- `POST /v1/policies`
- `POST /v1/assignments/roles`
- `POST /v1/assignments/policies`
- `GET /v1/access/effective`

### Personas + knowledge/vector

- `POST /v1/personas`
- `GET /v1/personas`
- `GET /v1/personas/{persona_id}`
- `PATCH /v1/personas/{persona_id}`
- `POST /v1/personas/{persona_id}/publish`
- `POST /v1/personas/{persona_id}/archive`
- `POST /v1/knowledge/documents`
- `GET /v1/knowledge/documents`
- `GET /v1/knowledge/documents/{document_id}`
- `POST /v1/knowledge/ingestion/jobs`
- `GET /v1/knowledge/ingestion/jobs/{job_id}`
- `POST /v1/knowledge/access/grants`
- `DELETE /v1/knowledge/access/grants/{grant_id}`

### API keys + usage

- `POST /v1/api-keys`
- `GET /v1/api-keys`
- `POST /v1/api-keys/{key_id}/rotate`
- `POST /v1/api-keys/{key_id}/revoke`
- `POST /v1/usage/events`
- `GET /v1/usage/summary`
- `GET /v1/usage/by-user`
- `GET /v1/usage/by-persona`
- `POST /v1/usage/budgets`

## Wizard contract typing

Wizard state should stay typed and separate from UI presentation primitives.

- Keep process state/types in core frontend (reference: `frontend/src/app/components/wizard/types.ts`)
- Keep `@kairosstack/ui` wizard components generic/presentational
- Add onboarding-specific typed state for:
  - global admin payload and result
  - organization payload and result
  - persona draft payloads
  - document upload/ingest payloads
  - persona-document grant payloads

## Dashboard health requirements

Main overview health should consume setup/runtime checks from core APIs:

- `GET /v1/health`
- `GET /v1/bootstrap/sessions?latest=true`
- `GET /v1/system/status?session_id=...`

Display at minimum:

- Core API health
- PostgreSQL reachability
- pgvector extension status
- provider connectivity status (if configured)
- app endpoint probes (studio/core/council URLs when configured)
