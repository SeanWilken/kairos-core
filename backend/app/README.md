# App Package

This folder is the backend runtime package.

The structure is intentionally layered so contributors can find things quickly and keep responsibilities separated.

## Layout

- `api/` HTTP transport layer (versioned routers, request/response entry points)
- `core/` cross-cutting infrastructure (config, response envelope, middleware, error mapping)
- `main.py` FastAPI application bootstrap

As features land, we will continue this layout with:

- `services/` use-case orchestration and business workflows
- `repositories/` persistence and data access
- `domain/` domain entities and rules

## Design conventions

- Keep route handlers thin and focused on transport concerns.
- Build response metadata and envelopes through core helpers, not per-route custom code.
- Keep version boundaries explicit (`/v1`, future `/v2`).
