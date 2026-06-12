# Database Migrations with Grate

MyAI Core now uses `grate` as the migration runner and version ledger for PostgreSQL.

## Prerequisites

- .NET SDK installed
- Local tool manifest restored: `dotnet tool restore`
- PostgreSQL reachable (default local container port `5432`)

## Run migrations

From repository root:

```powershell
powershell -ExecutionPolicy Bypass -File "migration-runner.ps1"
```

Optional flags:

```powershell
# Mark existing scripts as run without executing
powershell -ExecutionPolicy Bypass -File "migration-runner.ps1" -Baseline

# Preview scripts that would run
powershell -ExecutionPolicy Bypass -File "migration-runner.ps1" -DryRun

# Check if database is up to date
powershell -ExecutionPolicy Bypass -File "migration-runner.ps1" -UpToDateCheck
```

Connection overrides:

```powershell
powershell -ExecutionPolicy Bypass -File "migration-runner.ps1" -DbHost "localhost" -Port "5432" -Database "myai" -Username "myai" -Password "myai"
```

## Notes

- Migration scripts are loaded from `migrations/` using Grate folder mapping `up=migrations`.
- Grate tracking tables are stored under schema `grate`.
- For CI/CD, run `dotnet tool restore` before invoking `migration-runner.ps1`.
