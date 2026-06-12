# Release and Rollback Policy v0.1

This policy defines how MyAI Core and suite frontends are released and rolled back during the current POC-to-working-release phase.

## Goals

- Keep Studio, Council, and AIDE workflows stable while shipping quickly.
- Allow independent frontend release cadence without breaking Core contracts.
- Make rollback fast, safe, and operationally predictable.

## Release Model

## Backend services (Core and related servers)

- Release as container images with immutable tags and a promoted stable tag.
- Database migrations must be forward-safe and tracked (Grate workflow).
- Working release requires contract checks to pass for auth, realtime, and core orchestration endpoints.

## Frontends (Core UI, Studio, Council, others)

- Preferred production posture: static web app artifacts.
- Optional operational posture: containerized static serving (Nginx or equivalent).
- Each frontend may release independently as long as shared contract compatibility is maintained.

## Channels

- `stable`: default channel for POC users and working releases.
- `preview`: faster channel for integration testing and validation.

## Compatibility Rules

Before promoting to `stable`, release candidates must satisfy:

1. API compatibility against current shared contracts.
2. Auth/session checks (login, me, refresh, context switch).
3. Realtime checks for websocket connection and chat flow.
4. Tenant/org scope checks for protected calls.

## Rollback Policy

## Frontend rollback

- Static deployments: roll back by repointing to prior artifact version.
- Container deployments: roll back by deploying prior image tag.
- Do not require backend rollback for frontend-only regressions unless contract coupling demands it.

## Backend rollback

- Roll back image to previous stable tag.
- If migrations are non-reversible, apply forward fix rather than destructive schema rollback.
- Restore from backup only for data integrity events or explicit incident response decision.

## Incident Response Sequence

1. Detect regression and identify blast radius (which app/workflow).
2. Apply fastest safe rollback path (frontend-first when possible).
3. Confirm health/auth/realtime baseline.
4. Open remediation issue and schedule corrective release.
5. Publish short incident note in release log.

## Working Release Gate for Suite Priority Apps

Working release is considered valid when all pass:

- Studio governance flow smoke tests
- Council websocket and persona orchestration smoke tests
- AIDE integration reference flow smoke tests

## Required Metadata Per Release

Each release should record:

- image/artifact version
- target channel (`preview` or `stable`)
- compatibility contract version
- migration set applied
- known caveats and rollback instruction

## Implementation Notes for Current Bootstrap

- `FRONTEND_RUNTIME_MODE=container|static` controls whether frontend containers start.
- `FRONTEND_CONTAINER_SET=core_only|suite` controls which frontend containers are started in container mode.
- For static mode, frontends must point to Core API URL and follow websocket proxy/URL requirements.
