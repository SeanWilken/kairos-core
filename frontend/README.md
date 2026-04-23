# Frontend

This folder contains the React + TypeScript reference UI for Kairos Core bootstrap/setup.

## Stack

- React + React Router
- TypeScript + Vite
- Tailwind CSS v4
- `@kairosstack/ui` shared component library

## Frontend role in the ecosystem

- Provides the Core bootstrap flow (runtime/deployment/secrets/vector/preflight/artifacts/runtime verify/docs/review).
- Demonstrates shell/layout patterns aligned with Studio while preserving Core-specific responsibilities.
- Acts as reference behavior for external frontend adapters that consume shared contracts.

## Local setup

```powershell
npm install
npm run dev
```

Open the local Vite URL and run through the setup wizard.

## Tailwind + Shared UI package

Tailwind source scanning includes both local app files and `@kairosstack/ui` package files.

- `src/styles/tailwind.css`

If shared component styles appear missing (for example, transparent or compressed dropdowns), restart the dev server after dependency/style changes.

## Wizard screenshots

### Runtime Configuration

![Runtime Configuration](../docs/images/core-runtime-config.png)

### Deployment Target

![Deployment Target](../docs/images/core-deployment-target.png)

### Secrets Strategy

![Secrets Strategy](../docs/images/core-secrets-strategy.png)

### Vector Store

![Vector Store](../docs/images/core-vector-store.png)

### RAG Option

![RAG Option](../docs/images/core-rag-option.jpeg)

### Preflight Validation

![Preflight](../docs/images/core-preflight.png)

### Artifact Generation

![Artifact Generation](../docs/images/core-artifact-generation.png)

### Runtime Verify (Failure State)

![Runtime Verify Failure](../docs/images/core-runtime-verify-failure.png)
