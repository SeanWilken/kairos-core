# API v1

This folder holds the first public API contract.

## v1 contract baseline

- All responses use a consistent envelope shape:
  - `meta`
  - `data`
  - `error`
- `meta` includes service/version/environment/timestamp/correlation_id.
- Success responses return `data` and `error = null`.
- Error responses return `error` and `data = null`.

## Evolution policy

- Additive changes are preferred.
- Breaking changes require a new version (`v2`).
- Contract tests under `backend/tests/contracts/v1/` are the source of truth for compatibility.
