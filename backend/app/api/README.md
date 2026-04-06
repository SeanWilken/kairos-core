# API Layer

The API layer is the HTTP boundary of the backend.

## Responsibilities

- Route definitions and versioning
- Input/output transport concerns
- Calling service functions and returning standardized envelopes

## What does not belong here

- Business orchestration logic
- Query construction and persistence logic
- Cross-cutting response assembly duplicated in route handlers

## Versioning

Versioned APIs live under subfolders (`v1`, `v2`, ...).
Each version has its own contract tests.
