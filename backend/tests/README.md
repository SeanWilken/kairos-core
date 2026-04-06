# Backend Tests

The backend test suite is organized by intent, not by framework type.

## Folders

- `contracts/` API compatibility tests
- `unit/` focused tests for helper functions and modules
- `integration/` end-to-end request path tests inside the backend process

## Why this split

Contract tests protect public behavior.
Unit tests keep feedback fast while building helpers.
Integration tests catch wiring mistakes (middleware, exception handlers, routers).

## Running tests

From `backend/`:

```powershell
python -m pytest
```
