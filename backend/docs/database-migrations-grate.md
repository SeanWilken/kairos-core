# Database Migrations with Grate

MyAI Core uses `grate` as the migration runner and version ledger for
PostgreSQL. Refresh, deploy, direct CLI usage, and future authenticated runners
share the same migration procedure.

## Prerequisites

- .NET SDK installed
- Local tool manifest restored: `dotnet tool restore`
- PostgreSQL reachable (default local container port `5432`)

## Run migrations

From the repository root on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File "migration-runner.ps1" -Action apply
```

On Linux:

```bash
bash ./migration-runner.sh --action apply
```

Status and preview operations:

```powershell
powershell -ExecutionPolicy Bypass -File "migration-runner.ps1" -Action status
powershell -ExecutionPolicy Bypass -File "migration-runner.ps1" -Action dry-run
```

Connection overrides:

```powershell
$env:POSTGRES_HOST = "localhost"
$env:POSTGRES_PORT = "5432"
$env:POSTGRES_DB = "myai"
$env:POSTGRES_USER = "myai"
$env:POSTGRES_PASSWORD = '<retrieve-from-secret-store>'
powershell -ExecutionPolicy Bypass -File "migration-runner.ps1" -Action status
```

## Notes

- Migration scripts are loaded from `migrations/` using Grate folder mapping `up=migrations`.
- Grate tracking tables are stored under schema `grate`.
- For CI/CD, run `dotnet tool restore` before invoking `migration-runner.ps1`.
- The CLI reads connection defaults from `myai-suite/.env` without printing the
  password. Process environment values take precedence.
- `refresh-images` and `deploy` apply pending migrations automatically.
- Use `-SkipMigrations` or `--skip-migrations` only in a reviewed recovery flow.

## Legacy baseline

Databases created by the former direct SQL replay procedure may not have a
Grate ledger. Verify the complete schema and backup/export state, then baseline
exactly once:

```powershell
powershell -ExecutionPolicy Bypass -File "migration-runner.ps1" `
  -Action baseline `
  -BaselineThrough 0026 `
  -BaselineConfirmSchema
```

Baseline refuses an existing Grate ledger or an empty application schema, then
marks scripts through the reviewed cutoff as applied without executing them.
Run normal apply afterward so newer migrations execute. Never baseline a new
database or use baseline to bypass a failed migration.
