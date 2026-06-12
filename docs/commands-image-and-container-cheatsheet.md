# Image And Container Cheatsheet

This is a practical command reference for local image development, container refresh/deploy loops, inspection, and Docker Hub publishing for the MyAI suite.

## Assumptions

- Workspace root contains `myai-suite/` for generated local deployment files.
- Local frontend/backend images are often built with `:local` tags during development.
- `CONTAINER_ENGINE` in `.env` should match the engine used to build the images.

Examples:

- If you build with Podman: `CONTAINER_ENGINE=podman`
- If you build with Docker Desktop: `CONTAINER_ENGINE=docker`

## Common local image tags

- `myaitech/myai-core-api:local`
- `myaitech/myai-core-frontend:local`
- `myaitech/myai-studio-frontend:local`
- `myaitech/myai-council-frontend:local`
- `myaitech/myai-de-api:local`
- `myaitech/myai-de-frontend:local`

## Build local images

### Core frontend

From repo root:

```powershell
podman build -t myaitech/myai-core-frontend:local ./frontend
```

### Core API

From repo root:

```powershell
podman build -t myaitech/myai-core-api:local ./backend
```

### Studio frontend

From `../kairos-studio`:

```powershell
podman build -t myaitech/myai-studio-frontend:local .
```

### Council frontend

From the council repo:

```powershell
podman build -t myaitech/myai-council-frontend:local .
```

### myAIDE API / frontend

From their respective repos:

```powershell
podman build -t myaitech/myai-de-api:local .
podman build -t myaitech/myai-de-frontend:local .
```

## Local deploy flow (preserve data)

From `myai-suite/`:

### Deploy all active stack services

```powershell
.\deploy.ps1 -ProfileSet all
```

### Deploy and pull non-local images first

```powershell
.\deploy.ps1 -ProfileSet all -RefreshImages
```

Behavior:

- preserves Postgres volume/data
- force-recreates app containers
- rebuilds local buildable services
- applies SQL migrations after successful deploy

## Refresh containers after rebuilding local images

### Refresh just Studio

```powershell
.\refresh-images.ps1 -ImagesCsv "myaitech/myai-studio-frontend:local" -ProfileSet suite
```

### Refresh just Core frontend

```powershell
.\refresh-images.ps1 -ImagesCsv "myaitech/myai-core-frontend:local" -ProfileSet core
```

### Refresh whole active stack

```powershell
.\refresh-images.ps1 -ProfileSet all
```

Behavior:

- skips pull for `:local` tags
- pulls only non-local tags when doing profile-wide refresh
- force-recreates matching services

## Manual targeted recreate commands

### Recreate one service without touching dependencies

```powershell
podman compose --profile suite up -d --no-deps --force-recreate myai_studio_frontend
```

### Remove one container and let compose recreate it

```powershell
podman rm -f myai-studio-frontend
podman compose --profile suite up -d --no-deps --force-recreate myai_studio_frontend
```

This does not remove Postgres data.

## Inspect images and containers

### Show local image ID

```powershell
podman image inspect myaitech/myai-studio-frontend:local --format "{{.Id}} {{.Created}}"
```

### Show running container image

```powershell
podman inspect myai-studio-frontend --format "{{.ImageName}} {{.Image}}"
```

### Show running containers

```powershell
podman ps
```

### Show compose services and state

From `myai-suite/`:

```powershell
podman compose ps
```

### Tail logs

```powershell
podman logs -f myai-studio-frontend
podman logs -f myai-core-frontend
podman logs -f <container-name>
```

## Tag images for release

When a local image is ready for release, tag it with a non-local tag.

Example:

```powershell
podman tag myaitech/myai-studio-frontend:local myaitech/myai-studio-frontend:0.1.0
```

You can also use:

- `stable`
- date tags like `2026-06-04`
- semver tags like `0.1.0`

## Push images to Docker Hub

### Log in

```powershell
podman login docker.io
```

### Push tagged image

```powershell
podman push myaitech/myai-studio-frontend:0.1.0
```

Example release pushes:

```powershell
podman push myaitech/myai-core-api:0.1.0
podman push myaitech/myai-core-frontend:0.1.0
podman push myaitech/myai-studio-frontend:0.1.0
podman push myaitech/myai-council-frontend:0.1.0
podman push myaitech/myai-de-api:0.1.0
podman push myaitech/myai-de-frontend:0.1.0
```

## Helpful Git commands during release prep

### See working tree

```powershell
git status --short
```

### See staged files

```powershell
git diff --cached --name-only
```

### See recent commits

```powershell
git log --oneline -10
```

## Common pitfalls

### 1. Built image not used by compose

Cause:

- built with Podman, but suite is running with Docker
- or vice versa

Fix:

- make `CONTAINER_ENGINE` in `myai-suite/.env` match the engine used to build

### 2. Refresh tries to pull `:local`

Expected behavior now:

- refresh scripts skip pulling `:local` tags

If you still see pull attempts, make sure you are using the updated scripts from `myai-suite/`.

### 3. Deploy runs migrations even when app deploy fails

Expected behavior now:

- updated deploy scripts fail fast on compose deploy failure
- migrations only run after successful container deployment

### 4. Knowledger image missing

Current behavior:

- `all` does not include Knowledger right now
- use `knowledger` profile only when that image exists

## Recommended local release loop

1. Build local image in its source repo.
2. Refresh or recreate only the affected service.
3. Verify UI/runtime behavior.
4. Repeat until satisfied.
5. Tag local image with release tag.
6. Push release tag to Docker Hub.
7. Update deployment env/compose to use release tag if needed.
