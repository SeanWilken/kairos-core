# Core Bootstrap Roadmap

This document defines the current bootstrap strategy for `myai-core`.

## Scope boundary

- `myai-core` is the runtime/bootstrap engine and contract host.
- `myai-studio` will handle organization/division/persona/user/workflow authoring.

## Bootstrap objective

Provide a guided setup that can:

- configure runtime connections (API provider and local model modes)
- generate deployment artifacts for multiple targets
- enforce safe secret handling (references/placeholders only)
- run connectivity checks and gate continuation
- optionally bootstrap document ingest/vectorization

## Deployment target strategy

Targets are represented as capability adapters with explicit maturity metadata.

- `docker_local`: mvp, tested
- `github_actions`: experimental, generate-only
- `k8s`: experimental, generate-only
- `terraform`: experimental, generate-only

Experimental targets are allowed for artifact generation but are not runtime-certified.

## Execution modes

- `generate_only`: produce scripts/manifests/templates
- `attempt_automated`: only available for tested targets

## Security baseline

- Raw secret values are never persisted in wizard state.
- Session state stores key names/references only.
- Generated `.env.template` files contain placeholders, not secrets.

## Validation-first plan

1. Validate one end-to-end path first: `docker_local + api_provider + pgvector`.
2. Promote additional target adapters from experimental to tested as they pass E2E validation.
3. Begin Studio implementation after one bootstrap path is certified.
