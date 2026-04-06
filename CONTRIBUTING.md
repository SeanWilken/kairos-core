# Contributing

Thanks for considering a contribution.

## Before you start

- Read `README.md` for project direction.
- Read `docs/ecosystem/` and `shared-contracts/` for compatibility expectations.
- Keep API changes contract-aware. If a response shape changes, update tests and OpenAPI.
- Keep changes scoped to this repository's charter. Do not introduce implementation work for external modules in this repo.

## Local setup

### Backend

```powershell
python -m venv backend/.venv
.\backend\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".\backend[dev]"
```

### Tooling (Bun-first)

```powershell
bun install
```

`npm install` also works if Bun is not available.

Pre-commit checks are designed to work from both terminal commits and IDE commits.
If `backend/.venv` exists, checks use it automatically.

## Development workflow

1. Create a branch from `main`.
2. Keep changes small and focused.
3. Run checks before opening a PR:

```powershell
bun run check:backend
```

4. Update `CHANGELOG.md` for non-doc changes.
5. If API behavior changes, regenerate OpenAPI:

```powershell
& "backend/.venv/Scripts/python.exe" backend/scripts/export_openapi.py
```

## Commit format

This repo uses Conventional Commits. Examples:

- `feat: add v1 profile endpoint`
- `fix: map validation errors to envelope contract`
- `docs: update ecosystem interop notes`

Hooks enforce commit formatting and baseline checks.

## Governance and safety expectations

- Treat user-facing safety and prompt injection resistance as baseline requirements.
- If a change impacts policy behavior or guardrails, mention it in the PR summary and changelog.
- If a contract change affects external integrations, document migration notes in `shared-contracts/compatibility/`.

## Pull requests

Include:

- what changed
- why it changed
- how you validated it
- any contract or migration impact

If contract behavior changed, call it out clearly in the PR summary.
