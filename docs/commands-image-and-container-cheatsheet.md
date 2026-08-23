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

- `myaitech/core-api:local`
- `myaitech/core-frontend:local`
- `myaitech/studio:local`
- `myaitech/council:local`
- `myaitech/aide-api:local`
- `myaitech/aide-frontend:local`
- `myaitech/knowledger:local`

## Build local images

### Multi-repo helper (recommended)

From `kairos-core/`:

```powershell
.\scripts\multi-repo-workflow.ps1 -Action list
```

Build all mapped repos:

```powershell
.\scripts\multi-repo-workflow.ps1 -Action build -Targets all -Engine podman
```

Build specific repos:

```powershell
.\scripts\multi-repo-workflow.ps1 -Action build -Targets core-api,core-frontend,studio-frontend -Engine podman
```

Linux/Zorin:

```bash
bash ./scripts/multi-repo-workflow.sh --action list
bash ./scripts/multi-repo-workflow.sh --action build --targets all --engine podman
bash ./scripts/multi-repo-workflow.sh --action build --targets core-api,core-frontend,studio-frontend --engine podman
```

### Core frontend

From repo root:

```powershell
podman build -t myaitech/core-frontend:local ./frontend
```

### Core API

From repo root:

```powershell
podman build -t myaitech/core-api:local ./backend
```

### Studio frontend

From `../kairos-studio`:

```powershell
podman build -t myaitech/studio:local .
```

### Council frontend

From the council repo:

```powershell
podman build -t myaitech/council:local .
```

### myAIDE API / frontend

From their respective repos:

```powershell
podman build -t myaitech/aide-api:local .
podman build -t myaitech/aide-frontend:local .
```

## Local deploy flow (preserve data)

From `myai-suite/`:

Orchestrated from `kairos-core/`:

```powershell
.\scripts\multi-repo-workflow.ps1 -Action deploy -Targets all -Engine podman
```

```bash
bash ./scripts/multi-repo-workflow.sh --action deploy --targets all --engine podman
```

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

### Multi-repo helper (recommended)

Refresh all mapped repos into the suite:

```powershell
.\scripts\multi-repo-workflow.ps1 -Action refresh -Targets all -Engine podman
```

```bash
bash ./scripts/multi-repo-workflow.sh --action refresh --targets all --engine podman
```

Refresh only Studio and Council:

```powershell
.\scripts\multi-repo-workflow.ps1 -Action refresh -Targets studio-frontend,council-frontend -Engine podman
```

### Refresh just Studio

```powershell
.\refresh-images.ps1 -ImagesCsv "myaitech/studio:local" -ProfileSet suite
```

### Refresh just Core frontend

```powershell
.\refresh-images.ps1 -ImagesCsv "myaitech/core-frontend:local" -ProfileSet core
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
podman image inspect myaitech/studio:local --format "{{.Id}} {{.Created}}"
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
podman tag myaitech/studio:local myaitech/studio:0.1.0
```

You can also use:

- `stable`
- date tags like `2026-06-04`
- semver tags like `0.1.0`

## Push images to Docker Hub

### Multi-repo helper (recommended)

Publish all mapped repos with a shared release tag:

```powershell
.\scripts\multi-repo-workflow.ps1 -Action publish -Targets all -Engine podman -ReleaseTag 0.1.0
```

Publish only selected repos:

```powershell
.\scripts\multi-repo-workflow.ps1 -Action publish -Targets core-api,core-frontend,studio-frontend -Engine podman -ReleaseTag 0.1.0
```

### Log in

```powershell
podman login docker.io
```

### Push tagged image

```powershell
podman push myaitech/studio:0.1.0
```

Example release pushes:

```powershell
podman push myaitech/core-api:0.1.0
podman push myaitech/core-frontend:0.1.0
podman push myaitech/studio:0.1.0
podman push myaitech/council:0.1.0
podman push myaitech/aide-api:0.1.0
podman push myaitech/aide-frontend:0.1.0
podman push myaitech/knowledger:0.1.0
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

### 4. KnowLedger local build dependency

Current behavior:

- `all` includes KnowLedger as part of the release baseline
- `@myai-tech/myui@0.1.3-alpha.12` provides the required knowledge UI exports and stylesheet
- KnowLedger builds from its own repository context with no sibling-worktree dependency

### 5. Multi-repo script only covers known mapped repos

Current mapped repo IDs:

- `core-api`
- `core-frontend`
- `studio-frontend`
- `council-frontend`
- `aide-api`
- `aide-frontend`
- `knowledger-frontend`

If a repo is not mapped yet, build/publish it manually or extend `scripts/multi-repo-workflow.ps1`.

### 6. Preserve vs destroy data

- preserve existing data:
  - `.\scripts\multi-repo-workflow.ps1 -Action deploy -Targets all -Engine podman`
- destroy volumes and reset data:
  - `.\scripts\multi-repo-workflow.ps1 -Action reset-data -Targets all -Engine podman`

The reset-data action removes named volumes for the selected profile set before redeploying.

## Recommended local release loop

1. Build local image in its source repo.
2. Refresh or recreate only the affected service.
3. Verify UI/runtime behavior.
4. Repeat until satisfied.
5. Tag local image with release tag.
6. Push release tag to Docker Hub.
7. Update deployment env/compose to use release tag if needed.
