# myAI POC Bootstrap Guide

This guide helps contributors run a local MyAI Core installation and connect it to a sibling `../myAI` repository for early proof-of-concept workflows.

Status: POC-level setup. Expect gaps, rough edges, and manual recovery steps.

## Scope

This setup is intended to validate the current top-priority path:

1. Studio for configuration and governance
2. Council for persona collaboration and realtime WebSocket behavior
3. AIDE IDE flow backed by Core + AIDE server graph context

## Recommended Local Topology

Use sibling folders so local app repos can reference the same Core endpoint.

```text
Projects/
  myai-core/
  myai-studio/
  myai-council/
  myAI/
```

## Prerequisites

- Git
- Python 3.11+
- Node 20+
- Docker or Podman (Podman is supported in current team workflows)

Optional but useful:

- `bun` for root tooling/scripts
- PowerShell 5.1+ (Windows)

## 1) Start Core stack

From `myai-core/myai-stack`:

1. Copy `env.template` to `.env` and fill required values.
2. Choose frontend mode in `.env`:
   - `FRONTEND_RUNTIME_MODE=container` and `FRONTEND_CONTAINER_SET=core_only|suite`, or
   - `FRONTEND_RUNTIME_MODE=static` for backend-only bootstrap.
3. Run bootstrap:

```powershell
.\bootstrap-local.ps1
```

4. Run runtime checks:

```powershell
.\check-runtime.ps1
```

Expected result:

- Core API healthy on `http://localhost:8000`
- Runtime checks report pass/warn with actionable output

Reference: `myai-stack/README-quickstart.md`

## 2) Install backend dependencies (local dev path)

From `myai-core`:

```powershell
python -m pip install -e "backend"
```

Optional validation:

```powershell
python backend/scripts/export_openapi.py
```

If this fails with missing modules, re-run the editable install command.

## 3) Configure Studio/Council against local Core

In sibling app repos (`myai-studio`, `myai-council`), set:

- `VITE_MYAI_CORE_API_BASE_URL=http://localhost:8000`

For local dev proxy mode, apps may route through `/api` and rewrite to Core. Ensure each Vite config includes websocket proxy support when testing realtime features.

## 4) Validate auth and realtime quickly

Minimum checks before connecting `../myAI`:

1. Login works and returns `access_token` + `refresh_token`
2. `GET /v1/auth/me` succeeds
3. `POST /v1/auth/refresh` rotates token pair
4. WebSocket connects to `/v1/realtime/ws?token=...`
5. Studio/Council can send and receive chat events

## 5) Connect `../myAI` to Core

In `../myAI`, configure Core endpoint and tenant/org context (naming may differ by repo implementation):

- Core API base URL: `http://localhost:8000`
- Tenant ID and org ID for the active workspace
- Access/refresh token handling for long-lived sessions

POC expectation:

- AIDE-side repo graph and workspace metadata remain local-first
- Core receives normalized context references and policy-governed requests
- Persona/task orchestration is traceable back to Core run and audit records

## 6) Suggested first end-to-end POC flow

1. Use Studio to create org/personas and assign room personas.
2. Use Council realtime room to validate persona orchestration behavior.
3. In `../myAI`, index a small repo/workspace graph.
4. Trigger an agent coding task that references Core policy/context.
5. Confirm outcome and traceability across:
   - orchestration mode resolution
   - context inputs
   - persona selection
   - audit/timeline events

## Operational Caveats (Current)

- Test runner availability may vary by environment (`pytest` may not be present).
- Container CLI availability differs by machine (Docker vs Podman).
- Realtime failures are often proxy/path issues before backend handler issues.
- Token expiry can cause idle-tab unauthorized errors if clients do not auto-refresh and retry.

## Publish Notes for External POC Users

When publishing POC instructions publicly, clearly call out:

- This is an active build with breaking changes possible.
- Core contracts are stabilizing and may version quickly.
- Some modules are partial and intentionally behind priority gates.
- Recommended usage is local/dev evaluation, not production deployment.

## Related Docs

- `README.md`
- `myai-stack/README-quickstart.md`
- `docs/ecosystem/release-and-rollback-policy-v0.1.md`
- `internal/planning/suite-priority-roadmap-v0.1.md`
- `docs/ecosystem/interop-spec-v0.1.md`
