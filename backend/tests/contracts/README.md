# Contract Tests

Contract tests protect the public API surface.

These tests are intentionally strict about envelope shape and metadata so clients can rely on stable behavior.

## Structure

- `shared/` invariants that every API version must satisfy
- `v1/` behavior specific to v1 contracts
