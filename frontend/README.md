# Frontend Scaffold

This folder contains the React + TypeScript reference UI for the core training stack.

## Planned Stack

- React
- TypeScript
- Vite
- React Router
- TanStack Query

## Frontend role in the ecosystem

- Provides a baseline UX for onboarding, training configuration, and orchestration.
- Acts as reference behavior for external frontend adapters.
- Is replaceable: other UIs can integrate via shared contracts and APIs.

## Local setup

1. Install dependencies from `package.json`.
2. Start dev server.
3. Open the local Vite URL and use the core setup wizard.

## Command reference

```powershell
npm install
npm run dev
```

The current scaffold includes a bootstrap setup wizard (`src/kairos-core-setup.jsx`) for
runtime/deployment artifact generation.
