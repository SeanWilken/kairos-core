# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog.

## [Unreleased]

- Scaffolded backend response envelope conventions and v1 health endpoint.
- Added contract/unit/integration test layout and baseline tests.
- Added ecosystem and architecture documentation for modular repo strategy.
- Added OSS project baseline files (`LICENSE`, `CONTRIBUTING`, `CODE_OF_CONDUCT`, `SECURITY`).
- Added Bun-first repo tooling with npm fallback for local workflows and git hooks.
- Added GitHub CI workflow, issue/PR templates, and OpenAPI snapshot verification checks.
- Added changelog enforcement checks for local pre-commit and pull request workflows.
- Added charter and governance documentation to align repo intent with modular ecosystem goals.
- Expanded interop and contract docs with concrete domain contract objects.
- Added AI safety and prompt-injection posture notes for user-facing integrations.
- Rebranded project naming to Kairos Core across backend/frontend/tooling and ecosystem docs.
- Fixed CI OpenAPI export execution by resolving backend module path and running export with backend virtual environment Python.
- .gitattributes added for json eol=lf 

## [PR 1 - Governance Baseline]

- Added simple v1 protected scope baseline with tenant/org request-context enforcement, structured access-denied error reasons, protected route contract/integration tests, compatibility notes, and updated OpenAPI snapshot.