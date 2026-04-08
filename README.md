# Kairos Core

![CI](https://github.com/SeanWilken/kairos-core/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)

Open-source core training/orchestration stack for tailoring AI assistants to a person, team, or business.

This repository is the core application layer (backend + reference frontend) for:

- onboarding and profile alignment (workstyle, domain, goals, weak areas)
- RAG + context-document driven behavior
- auditable orchestration and governance

It is designed to work as:

1. a complete reference experience
2. a modular backend/framework used by external frontends and wrappers

## Repo Intent

This repository is the Kairos core runtime. Its job is to help people:

- stand up an AI runtime locally or through an API provider,
- onboard data and preferences in a structured way,
- generate reusable outputs (knowledge bundles, runtime config, model/profile metadata),
- plug those outputs into other tools and frontends.

Current priority is coding workflows first, with extension points for other industries later.

## Vision

- Build a baseline system that helps users become more effective in their domain (coding-first initially).
- Keep architecture modular so others can build industry-specific onboarding packs (for example, carpentry or language learning).
- Define stable interop standards so separate repos can integrate cleanly.
- Support model artifact export and publishing workflows (local artifacts, Hugging Face, OpenCode-compatible flows).

## Scope (Current)

- FastAPI backend scaffold
- React + TypeScript reference frontend scaffold
- LangGraph orchestration runtime target
- PostgreSQL + pgvector target for event store and retrieval

MVP behavior target:

- RAG + context documents first
- fine-tuning/training flows introduced later behind capability gates

Model strategy support target:

- Bring your own model (local/hosted) + RAG/context
- API provider mode (OpenAI/Claude/Gemini style providers)
- Full training/fine-tuning pipelines later

## Repository Layout

- `backend/` FastAPI service scaffold and Python project config
- `frontend/` React + TypeScript reference UI scaffold
- `shared-contracts/` API and schema contracts
- `infra/` local infrastructure (Postgres + pgvector)
- `docs/` architecture, ecosystem, and standards docs

## Ecosystem Model

This repo is part of a larger open ecosystem of interoperable components.

See:

- `docs/ecosystem/repo-topology.md`
- `docs/ecosystem/interop-spec-v0.1.md`
- `docs/ecosystem/plugin-sdk-v0.1.md`
- `docs/ecosystem/model-artifact-spec-v0.1.md`

## Principles

- Tenant isolation by default
- No data sharing/selling
- Policy-governed access and delegation
- Event-sourced auditability
- Modular, fork-friendly, standards-first design
- Safety, governance, and user-facing guardrails by default

## Governance and Safety

This project treats AI governance as a first-class concern. For user-facing experiences (chatbots, assistants, support flows), baseline controls include:

- prompt injection resistance patterns
- output policy checks and refusal behavior
- citation/grounding expectations for retrieval-backed answers
- audit trails for high-risk actions and delegated decisions

See:

- `docs/architecture/ai-governance-and-safety.md`
- `SECURITY.md`

## Quick Start (Scaffold Validation)

1. Start local infrastructure from `infra/` (Podman/Docker compose compatible).
2. Create backend virtual environment and install backend dependencies.
3. Install frontend dependencies and run frontend dev server.

Repository-level hook tooling (Bun-first):

4. Install root tooling dependencies and enable Husky hooks.

```powershell
bun install
```

Fallback:

```powershell
npm install
```

See service-specific setup:

- `backend/README.md`
- `frontend/README.md`
- `infra/README.md`

## Current backend status

- Running endpoint: `GET /v1/health`
- Runtime docs: `/docs` and `/openapi.json`
- Envelope contract in place (`meta`, `data`, `error`)

## Setup wizard visuals

Frontend setup wizard screenshots for each major step are tracked in:

- `frontend/README.md`
- `docs/images/`

## OSS baseline docs

- `LICENSE`
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
- `SECURITY.md`

## Development Timeline

The roadmap is iterative and contract-first.

1. Foundation
   - establish API envelope contracts, metadata conventions, and baseline tests
   - set up CI, changelog discipline, and contributor tooling
2. Onboarding + knowledge setup
   - structured onboarding profile capture
   - document ingest, sanitization, and retrieval-ready packaging
3. Orchestration and governance
   - policy-aware runtime orchestration
   - audit traceability and risk-gated workflows
4. Extension readiness
   - stable interop contracts for external wrappers and plugin ecosystems
   - multimodal contract support for text/translation/audio/video pipelines

Internal planning and sprint execution notes are kept outside committed docs.
