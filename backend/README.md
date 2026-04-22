# Backend

FastAPI backend for the core training/orchestration engine.

## What lives here

- API transport and versioning (`/v1`)
- shared response envelope and metadata conventions
- middleware and error mapping
- core service entry points for future orchestration, policy, and event workflows

## Tech stack

- FastAPI + Pydantic
- SQLAlchemy + Alembic (planned schema/migration workflow)
- PostgreSQL + pgvector
- LangGraph integration target

## Local setup (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
copy .env.example .env
```

Run API:

```powershell
uvicorn app.main:app --reload --port 8000
```

Docker build/run:

```powershell
docker build -t kairos/core-api:local -f Dockerfile .
docker run --rm -p 8000:8000 --env-file .env kairos/core-api:local
```

Apply SQL migrations (repo-root `migrations/` is source of truth):

```powershell
$migrationDir = "..\migrations"
Get-ChildItem "$migrationDir\*.sql" |
  Sort-Object Name |
  ForEach-Object { psql "$env:DATABASE_URL" -v ON_ERROR_STOP=1 -f $_.FullName }
```

Current migration set includes:

- `0001_initial_onboarding.sql`
- `0002_studio_identity_foundation.sql`
- `0003_auth_sessions_and_credentials.sql`
- `0004_collaboration_foundation.sql`
- `0005_persona_and_chat_runtime.sql`

Run tests:

```powershell
python -m pytest
```

Run repo checks from root:

```powershell
bun run check:backend
```

## API contract baseline

Responses are wrapped in a shared envelope:

- `meta`
- `data`
- `error`

This makes frontend integration and versioned compatibility checks predictable.

## OpenAPI

Runtime:

- `/docs`
- `/openapi.json`

Version snapshots should be stored under `../shared-contracts/openapi/`.
