# PR 2 Release Notes - Core Bootstrap + Studio Runtime Foundation

## Scope

This release establishes the backend baseline needed for Studio onboarding and early runtime collaboration in single-tenant installs.

## Highlights

- Single-tenant install bootstrap and tenant policy enforcement.
- Auth lifecycle with JWT access/refresh tokens and persisted refresh sessions.
- Studio collaboration foundation: divisions, teams, memberships, channels/messages, and tasks.
- Realtime websocket transport for chat presence and chat message eventing.
- Persona-driven chat runtime foundation with OpenAI-compatible provider integration and `single_best` policy.
- Governance onboarding foundation: governance baseline read endpoint, org invites, onboarding status/complete, and org settings endpoints.

## New Migrations

Apply these in order from repo-root `migrations/`:

1. `0004_collaboration_foundation.sql`
2. `0005_persona_and_chat_runtime.sql`
3. `0006_studio_governance_foundation.sql`

## API Additions (selected)

- Install/bootstrap:
  - `GET /v1/bootstrap/tenant/status`
  - `POST /v1/bootstrap/tenant`
- Auth:
  - `POST /v1/auth/register`
  - `POST /v1/auth/login`
  - `POST /v1/auth/refresh`
  - `POST /v1/auth/logout`
  - `GET /v1/auth/me`
- Collaboration:
  - `POST/GET /v1/studio/divisions`
  - `POST/GET /v1/studio/teams`
  - `POST/GET /v1/studio/channels`
  - `POST/GET /v1/studio/channels/{channel_id}/messages`
  - `POST/GET/PATCH /v1/studio/tasks`
- Realtime:
  - `WS /v1/realtime/ws?token=<access_jwt>`
- Governance/onboarding:
  - `GET /v1/studio/governance/baseline`
  - `POST /v1/studio/invites`
  - `POST /v1/studio/invites/{invite_id}/accept`
  - `GET /v1/studio/onboarding/status`
  - `POST /v1/studio/onboarding/complete`
  - `GET/PATCH /v1/studio/settings`

## Validation Performed

- `backend\\.venv\\Scripts\\python.exe -m ruff check backend`
- `backend\\.venv\\Scripts\\python.exe -m pytest backend/tests -q`

## Notes

- In local development with persistent DB volumes, apply migrations manually; container init scripts are one-time at first DB initialization.
- This release intentionally prioritizes Studio integration velocity; governance voting/approval workflows remain a later phase.
- `PATCH /v1/studio/settings` uses merge semantics: only provided keys are updated, omitted keys are preserved.
- `POST /v1/studio/invites/{invite_id}/accept` currently uses authenticated-user email matching; invite-token redemption flow is a planned follow-up when email delivery is integrated.
