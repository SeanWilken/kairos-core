# Shared Contracts

This folder is the contract source-of-truth for backend, frontend, and external ecosystem repositories.

## Contract Categories

- OpenAPI specs (HTTP contracts)
- JSON Schemas (payload and artifact contracts)
- Event envelope and event type schemas
- Interop spec references and compatibility matrices

## Rules

- Treat contracts as versioned API surface.
- Backward-compatibility notes are required for breaking changes.
- Contract changes should be linked to sprint/task docs and ADRs.
- Contract updates for user-facing behavior should include safety/governance impact notes.

## Contract domains in scope

- ModelProfile
- OnboardingProfile
- KnowledgeBundle
- CapabilityContract
- RuntimeBundle
- GovernanceRecord
- TaskContract
- ArtifactOutput
- QualityGate

See `docs/ecosystem/contract-domains-v0.1.md` for details.

## Planned Structure

- `openapi/` generated or source OpenAPI docs
- `schemas/events/` event envelope + event payload schemas
- `schemas/interop/` plugin/model/profile specs
- `compatibility/` version compatibility notes
