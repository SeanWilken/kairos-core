# MyAI POC Quickstart

This quickstart is for external testers who want to run a local POC with sibling repos:

- `myai-core`
- `myai-studio`
- `myai-council`
- `myai-knowledger`
- `myai-de`
- `myAI`

For full details, see `docs/ecosystem/myai-poc-bootstrap.md`.

## 0) Prerequisites

- Python 3.11+
- Node 20+
- Docker or Podman
- Git

## 1) Start Core

From `myai-core/myai-stack`:

Choose frontend runtime in `.env` first:

- `FRONTEND_RUNTIME_MODE=container` for bundled frontend containers
- `FRONTEND_RUNTIME_MODE=static` to run only backend services and host frontends separately

```powershell
Copy-Item env.template .env
.\bootstrap-local.ps1
.\check-runtime.ps1
```

Expected: Core API healthy on `http://localhost:8000`.

## 2) Install backend package (recommended)

From `myai-core`:

```powershell
python -m pip install -e "backend"
```

## 3) Point Studio and Council at Core

In `myai-studio` and `myai-council`, set:

```text
VITE_MYAI_CORE_API_BASE_URL=http://localhost:8000
```

Then start each frontend dev server in its repo.

## 4) Login and smoke test

In Studio/Council, verify:

1. Login succeeds and returns access + refresh tokens
2. `GET /v1/auth/me` works
3. Realtime websocket connects
4. Chat send/receive works

## 5) Run your exercise across Studio, Council, and myAI

Suggested order:

1. Studio: create org, personas, and room/persona assignments
2. Council: validate multi-persona websocket chat behavior
3. myAI: run a repo-graph-backed coding flow using Core context/policy

## Known POC caveats

- Some environments may not have `pytest` preinstalled.
- Docker/Podman command differences can affect scripts.
- Token expiry may require refresh-and-retry behavior in clients.
- Realtime failures are often proxy/path config issues first.

## Where to report issues

When filing an issue, include:

- OS and container engine (Docker/Podman)
- which repo/app failed (Core, Studio, Council, myAI)
- failing endpoint/event (for example `POST /v1/auth/refresh`, `/v1/realtime/ws`)
- browser network or websocket close code/reason

## Next docs

- `docs/ecosystem/myai-poc-bootstrap.md`
- `docs/ecosystem/myai-poc-roadmap.md`
- `docs/ecosystem/release-and-rollback-policy-v0.1.md`
- `internal/planning/suite-priority-roadmap-v0.1.md`
