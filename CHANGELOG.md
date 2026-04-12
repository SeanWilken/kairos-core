# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog.

## [Unreleased]

- API endpoints added for: organization, auth, bootstrap and membership POC w/ tests
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
- Added bootstrap target capability schemas and a core setup wizard capability matrix with execution-mode gating and experimental target disclaimers.
- Added a Studio-aligned frontend shell and routing scaffold for Kairos Core setup flows.
- Added a modularized setup wizard architecture (`types`, `constants`, `helpers`, shared `common`, per-step components) to replace the monolithic prototype.
- Reordered setup flow to runtime -> deployment -> secrets -> vector -> preflight -> artifacts -> runtime verify + docs -> review, with required gating between phases.
- Added runtime verification checks and locked document bootstrap behind successful required runtime checks.
- Added expanded artifact generation templates for `.env.template`, `docker-compose.yml`, optional `nginx.conf`, target-specific snippets, and `bootstrap-report.json`.
- Added shell placeholders for `Backups`, `Retrain`, and `Recovery` sections plus admin utility menu entries.
- Added frontend style pipeline (`index.css`, `tailwind.css`, `theme.css`) and Vite React dedupe/alias configuration for shared UI integration.
- Fixed dropdown trigger ref warnings by replacing `DropdownMenuTrigger asChild` usage with native `button` triggers in the shell header.
- Added `lucide-react` frontend dependency and excluded legacy `src/wizard-test.tsx` from TypeScript compile inputs.
- Added Tailwind source scanning for `@kairosstack/ui` package classes in frontend styling configuration.
- Added frontend overlay style overrides for select/dropdown content layering, opacity, option spacing, and trigger-width alignment.
- Updated frontend README with current setup notes and full-step setup wizard screenshots.
- Added v0.2 draft onboarding and Studio interop schemas covering bootstrap sessions, runtime checks, ingest jobs, runtime handoff, organization config, persona profiles, tool integrations, workflow definitions, and environment promotion.
- Added an onboarding contract catalog schema to track ownership and rollout phase for each draft domain contract.
- Added architecture draft for onboarding contracts and endpoint planning across Core and Studio (`docs/architecture/onboarding-contracts-and-api-draft-v0.2.md`).
- Extended onboarding bootstrap and runtime status schemas with database configuration metadata and additional readiness checks for pgvector/local setup.
- Added `bootstrap-local-env-input` contract for local-only secret-aware env/script generation (explicitly never transmitted to server APIs).
- Updated setup wizard runtime/provider flow to prioritize OpenAI and Anthropic defaults with provider-specific endpoint/model autofill.
- Expanded artifact generation with local quickstart documentation, Docker/Podman-compatible bootstrap scripts, runtime check scripts, and in-UI artifact download actions.
- Added wizard guidance for API-provider privacy disclosure and explicit LLM+RAG execution flow context before ingest.
- Added local-only secret materialization controls in the Secrets step so users can paste values and optionally generate a populated `.env` for faster local bootstrap.
- Added PostgreSQL local override inputs (`POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`) for environment file generation without sending raw values to APIs.
- Added container engine preference (`docker` or `podman`) in deployment configuration and propagated default engine into generated local bootstrap scripts/env templates.
- Updated generated `docker-compose.yml` for local bootstrap to avoid hard failing `core_api` build contexts when a Dockerfile is not present; Core API container is now an optional commented block requiring `CORE_API_IMAGE`.
- Expanded artifact UX with `all` preview and `Download all` bundle output (`bootstrap-bundle.json`) for easier local setup handoff.
- Added explicit Core API runtime source selection (`local_source`, `bundled_image`, `custom_image`) with custom image input validation and generated env/compose behavior aligned to the selected mode.
- Added runtime wizard mode in the setup sidebar (`setup` vs `runtime`) so users can skip full environment-generation steps and go directly through deployment runtime configuration, runtime verification, and review.
- Updated runtime verify step to support explicit re-running of checks after configuration changes.
- Added repository Docker build support for both backend and frontend (`backend/Dockerfile`, `frontend/Dockerfile`) with `.dockerignore` files for local compose reference.
- Added draft initial SQL migration for bootstrap/runtime/ingest persistence (`backend/migrations/0001_initial_onboarding.sql`).
- Fixed runtime verify API flow to create/reuse a real bootstrap `session_id` and query system endpoints with that session ID instead of check names.
- Updated generated compose templates with optional `kros_core_frontend`, `kros_studio_frontend`, and `kros_council_frontend` service stubs for future plug-and-play UI images.
- Added bootstrap session resume endpoint (`GET /v1/bootstrap/sessions?latest=true`) and frontend runtime-check logic to reuse existing scoped sessions when available.
- Added generated migration helper scripts (`migrate-db.sh`, `migrate-db.ps1`) for applying initial onboarding tables to local postgres containers.
- Added initial Core onboarding endpoints for bootstrap sessions, runtime status/check execution, and ingest job lifecycle with v1 envelope responses and tenant/org scope enforcement.
- Added in-memory onboarding store and contract tests for `bootstrap`, `system`, and `ingest` endpoint flows, including ingest precondition gating on runtime checks.

## [PR 1 - Governance Baseline]

- Added simple v1 protected scope baseline with tenant/org request-context enforcement, structured access-denied error reasons, protected route contract/integration tests, compatibility notes, and updated OpenAPI snapshot.
