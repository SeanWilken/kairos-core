# OpenAPI Contracts

This folder stores committed OpenAPI snapshots by API version.

## Why we commit snapshots

- easier review of contract changes in pull requests
- better compatibility tracking for external clients
- stable integration target for ecosystem repos

## Suggested layout

```text
shared-contracts/openapi/
  v1/
    openapi.json
```

## Workflow

1. update API code
2. generate/update `openapi.json`
3. run contract tests
4. commit the spec change with the related code change
