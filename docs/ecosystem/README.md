# Ecosystem Documentation

This folder defines how the core stack interoperates with external repositories and custom frontends.

## Documents

- `repo-topology.md` - recommended multi-repo structure
- `interop-spec-v0.1.md` - baseline interop contracts
- `contract-domains-v0.1.md` - concrete contract objects and lifecycle
- `plugin-sdk-v0.1.md` - plugin extension model
- `model-artifact-spec-v0.1.md` - model package/export contract
- `myai-poc-bootstrap.md` - local install and bootstrap flow for sibling `../myAI` usage
- `myai-poc-roadmap.md` - POC caveats, goals, and short-term roadmap
- `release-and-rollback-policy-v0.1.md` - release channels, compatibility gates, and rollback standards
- `cli-wrapper-and-tool-index-v0.1.md` - CLI wrapper model and indexed instruction strategy
- `document-manager-contract-v0.1.md` - document upload and knowledge-note UX/API contract

## Intent

Enable:

- standalone use of training core
- pluggable onboarding/evaluation/domain packs
- alternate frontends and IDE integrations
- open-source community extensions without lock-in

The ecosystem model is intentionally contract-first so teams can build wrappers and integrations without coupling to one UI.
