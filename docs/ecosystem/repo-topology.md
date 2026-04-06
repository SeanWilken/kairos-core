# Repository Topology (Proposed)

## Core philosophy

Keep this repository as the core training/orchestration reference implementation.
Allow external repositories to consume stable interop contracts.

## Recommended repos

1. `kairos-core` (this repo)
   - backend + reference frontend + infra + contracts
2. `kairos-sdk`
   - SDKs, plugin manifest validators, sample plugins
3. `kairos-ui-adapters`
   - alternate frontends (web variants, IDE extensions)
4. `kairos-integrations`
   - embeddings into existing products (chatbot/FAQ adapters, enterprise connectors)
5. `kairos-artifact-publish`
   - Hugging Face export/publish and local artifact tooling

Note: this repository currently focuses on the core only. External repos are design targets and are intentionally not implemented here yet.

## Integration contract boundaries

- UI adapters integrate through OpenAPI + contract schemas.
- Plugins integrate through manifest + hook contracts.
- Artifact tools integrate through model artifact spec.
- All integrations must carry tenant/org scoping metadata.

## Governance

- semver for contracts
- compatibility matrix maintained in `shared-contracts`
- deprecation windows for breaking API/spec changes
