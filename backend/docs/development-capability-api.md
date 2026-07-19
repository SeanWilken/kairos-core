# Development Capability API

Core exposes a first read-only capability inventory slice for MyAIDE-aligned development workspaces and runners.

## Endpoints

- `GET /v1/development/workspaces/{workspaceId}/capabilities`
- `GET /v1/development/runners/{runnerId}/capabilities`
- `POST /v1/development/capabilities/resolve`
- `POST /v1/policy/development/check`

## Resolve example

```json
{
  "workspace_id": "ws_123",
  "required_capabilities": [
    "workspace.search",
    "language.python.lsp",
    "workspace.patch.apply",
    "repo.checkout"
  ]
}
```

Typical resolution modes returned per requested capability:

- `ready`
- `install_required`
- `proposal_only`
- `blocked`
- `missing`

## Development policy check

`POST /v1/policy/development/check` combines:

- workspace capability resolution
- workspace metadata policy rules
- path-target evaluation

This is the first contract for proposal-only vs apply decisions on development paths.

Example request:

```json
{
  "workspace_id": "ws_123",
  "session_id": "sess_123",
  "capability": "workspace.patch.apply",
  "targets": [
    {
      "kind": "path",
      "value": "infra/deploy.yaml"
    }
  ],
  "mode": "build"
}
```

Typical result reasons include:

- `POLICY_DEVELOPMENT_ALLOW`
- `POLICY_DEVELOPMENT_PROPOSAL_REQUIRED`
- `POLICY_DEVELOPMENT_PATH_DENIED`
- capability resolution reasons such as `DEVELOPMENT_CAPABILITY_INSTALL_REQUIRED`

## Purpose

These endpoints provide a governed capability inventory for development-plane clients without requiring them to infer everything from shell access or environment assumptions.

Current capability inventory is derived from:

- workspace metadata
- code-ingested knowledge entities linked to `workspace_id` and `runner_id`
- runtime tool registry

## Example capability keys

- `workspace.search`
- `workspace.patch.propose`
- `workspace.patch.apply`
- `workspace.code_index`
- `repo.status`
- `repo.diff`
- `repo.log`
- `repo.fetch`
- `repo.checkout`
- `repo.pull_latest`
- `source.profile.upsert`
- language-service capabilities such as `language.python.lsp`

## Status values

- `available`
- `installed`
- `installable`
- `unavailable`
- `blocked_by_policy`
- `degraded`

## Notes

- This is the first capability inventory slice, not the full development-plane contract.
- Language-service capabilities are currently inferred from workspace metadata and code-ingested language signals.
- Runtime-backed capabilities such as git are derived from the existing runtime registry.
- Capability resolution returns deterministic distinctions between:
  - ready now
  - install required
  - proposal only
  - blocked by policy
  - unavailable
