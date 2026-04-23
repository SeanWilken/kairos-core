# Kairos Operating Model (v0.1)

This document defines how all Kairos repos work together: architecture boundaries, contracts, testing, documentation, quality gates, and PR workflow.

## 1) Purpose

We optimize for:
- contract-first development
- safe and auditable AI behavior
- modular repos with clear ownership boundaries
- small, reviewable units of value

## 2) Repo Boundaries (Source of Truth)

- `kairos-core`: runtime engine, API contracts, bootstrap/deployment orchestration, ingest/vectorization pipeline.
- `kairos-studio`: administrative/control-plane UX (org/division/persona/users/tools/workflows).
- `kairos-council`: multi-agent collaboration UX and orchestration interaction.
- `kairos-agent`: end-user/internal assistant surfaces.
- `kairos-sdk`: typed clients + contract bindings for apps/integrators.
- `kairos-ui`: shared UI primitives/composites; contract-agnostic.
- Other repos: adapters/plugins/extensions must consume published contracts.

Rule:
- Domain/runtime truth lives in Core contracts.
- UI libraries must not import Core domain contracts directly.
- Product apps map contracts to view-models at the app edge.

## 3) Contract-First Standards

Before implementation:
1. Define/modify machine-readable schemas/OpenAPI.
2. Add/adjust contract tests.
3. Document compatibility impact.
4. Then implement code.

Contract locations:
- OpenAPI snapshots: `shared-contracts/openapi/<version>/openapi.json`
- Interop schemas: `shared-contracts/schemas/interop/<version>/...`
- Event schemas: `shared-contracts/schemas/events/<version>/...`
- Compatibility notes: `shared-contracts/compatibility/<api-version>.md`

Versioning:
- Additive changes allowed within same major API version.
- Breaking changes require a new API version and migration notes.

## 4) AI Governance and Safety Baseline

All user-facing AI flows must support:
- tenant/org boundary enforcement
- machine-readable denial/error reasons
- correlation IDs on requests/responses
- auditable decision/event records for high-risk actions
- risk-gated tool access and escalation paths

Defaults:
- safe mode by default
- explicit user confirmation for risky actions
- no silent destructive operations

## 5) Testing Standard

Minimum test layers:
- Contract tests: external API behavior and schema invariants
- Unit tests: business logic/transformations/validators
- Integration tests: real request path and component wiring

Required for merge:
- tests pass locally and in CI
- changed contracts are covered by contract tests
- OpenAPI snapshot updated when API behavior changes

## 6) Tooling, Hooks, and CI

Tooling policy:
- Bun-first for repo-level scripts
- npm fallback where needed
- Python virtual env for backend runtime checks

Hooks:
- Husky enabled
- commitlint enforces Conventional Commits
- changelog check enforced for non-doc changes

CI must verify:
- lint + test
- contract checks
- OpenAPI snapshot consistency
- changelog policy
- security checks where configured

## 7) Commit and PR Workflow

Commits:
- small, logical, reversible
- Conventional Commit format:
  - `feat: ...`
  - `fix: ...`
  - `chore: ...`
  - `docs: ...`
  - `test: ...`
  - `ci: ...`

PRs:
- 1 coherent unit of value per PR
- 1–5 commits per PR preferred
- include tests/docs/contracts with implementation
- include compatibility and rollout notes when relevant

Do not merge if:
- boundaries are violated (wrong repo ownership)
- contracts changed without snapshot/tests/docs updates
- safety/governance regression is introduced

## 8) Changelog and Release Discipline

- Update `CHANGELOG.md` for all non-doc behavior/config changes.
- Entries describe user-visible impact, not internal minutiae.
- Follow semver and release notes by repo.

## 9) Documentation Standard

Every non-trivial feature must include:
- what/why
- contract impact
- test coverage expectations
- operational notes (env/deploy/checks)
- handoff notes for dependent repos

Preferred docs:
- architecture decisions in `docs/architecture/`
- ecosystem contracts in `docs/ecosystem/`
- repo-specific setup in `README.md`

## 10) Cross-Repo Synchronization

When Core contracts change:
1. update schemas/OpenAPI/compat notes
2. release/update `kairos-sdk` types/clients
3. adapt app edge mappers (`studio`, `council`, etc.)
4. update integration tests in consuming repos

Cadence:
- weekly contract sync across core/sdk/ui/app owners
- monthly compatibility review

## 11) Definition of Done (Global)

A change is done when:
- contracts are correct and versioned
- tests (contract/unit/integration) pass
- docs/changelog updated
- CI passes
- safety/governance expectations remain intact
- downstream repo impact is identified and tracked

## 12) Non-Negotiables

- No secrets in source control.
- No destructive git operations in normal workflow.
- No bypassing hooks without explicit approval.
- No hidden runtime behavior outside documented contracts.