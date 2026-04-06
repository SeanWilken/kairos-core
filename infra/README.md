# Infrastructure

Local infrastructure for development and proof-of-concept testing.

## Included services

- PostgreSQL (with pgvector image)

## Why this setup

- one local database for app state, event store experiments, and vector retrieval
- simple enough for contributors to run quickly
- close to the production database path we expect to use first

## Runtime compatibility

- Podman Compose
- Docker Compose

## Start services

```powershell
podman compose up -d
```

or

```powershell
docker compose up -d
```

## Notes

- Port `5432` is exposed to the host.
- `infra/postgres/init/` scripts run on first initialization.
- If you need to re-run init scripts, remove the volume and recreate the container.
