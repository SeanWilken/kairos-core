# Core Infrastructure

Core contains cross-cutting backend infrastructure used by all API versions.

## Files

- `config.py` runtime settings from environment
- `schemas.py` envelope and metadata models
- `response.py` helper builders for success/error responses
- `middleware.py` request correlation ID propagation
- `errors.py` exception-to-contract mapping

## Why this exists

Putting shared behavior in one place keeps endpoint code smaller and prevents contract drift.
If we need to update metadata or error conventions later, we do it in one location.
