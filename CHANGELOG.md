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

## [PR 1 - Governance Baseline]

- Added simple v1 protected scope baseline with tenant/org request-context enforcement, structured access-denied error reasons, protected route contract/integration tests, compatibility notes, and updated OpenAPI snapshot.
