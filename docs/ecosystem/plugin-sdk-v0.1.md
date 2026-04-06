# Plugin SDK Spec v0.1

## Goal

Allow external contributors to extend onboarding, evaluation, and domain behavior safely.

## Plugin types (initial)

- onboarding packs
- evaluator packs
- retrieval adapters
- export/publish adapters
- UI extension packs

## Manifest (minimum)

- plugin name
- plugin version
- compatible core versions
- requested permissions/scopes
- hook registrations

## Hook examples

- `on_profile_created`
- `on_context_attached`
- `on_eval_run`
- `on_artifact_export`

## Security requirements

- least-privilege permissions
- explicit tenant boundary adherence
- plugin actions must emit auditable events
- deterministic failure behavior for denied permissions

## User-facing safety requirements

Plugins that can influence user-facing output must support:

- prompt injection-safe handling of untrusted content
- separation of policy instructions from user-controlled context
- explicit fallback behavior when policy checks fail
- output filtering hooks for restricted domains
