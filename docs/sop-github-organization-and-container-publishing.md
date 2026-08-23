# SOP: GitHub Organization And Container Publishing

Status: canonical release operating procedure
Audience: human maintainers and automation agents

## Purpose

Use this procedure to move a MyAI application repository into the `myAI-Tech` GitHub organization and publish its release container images under the `myaitech` Docker Hub namespace.

The steps are intentionally reusable. Substitute the repository name, local directory, image name, and release version from the canonical mapping below.

## Canonical naming

| Application | GitHub repository | Local source directory | Docker image(s) |
| --- | --- | --- | --- |
| Core | `myAI-Tech/core` | `kairos-core` | `myaitech/core-api`, `myaitech/core-frontend` |
| Studio | `myAI-Tech/studio` | `kairos-studio` | `myaitech/studio` |
| Council | `myAI-Tech/council` | `kairos-council` | `myaitech/council` |
| AIDE | `myAI-Tech/aide` | `MyAIDE` | `myaitech/aide-api`, `myaitech/aide-frontend` |
| KnowLedger | `myAI-Tech/knowledger` | `MyAI-KnowLedger` | `myaitech/knowledger` |

Repository names do not repeat `myai` because the organization already supplies that namespace. Frontend-only applications do not use a `-frontend` image suffix. Core and AIDE retain `-api` and `-frontend` because each repository publishes two independently deployed images.

## Release tag policy

- Local development image: `local`
- Release candidate: semantic prerelease such as `0.1.0-rc.1`
- Immutable release: semantic version such as `0.1.0`
- Moving promotion tag: `stable`
- Git source tag: `v<version>`, for example `v0.1.0`

Do not use `latest` as the deployment contract. Deploy immutable versions, then move `stable` only after the immutable version passes the full suite smoke test.

## Required access

- Maintainer access to the `myAI-Tech` GitHub organization
- Push access to the target organization repository
- Push access to the `myaitech` Docker Hub namespace
- GitHub CLI authenticated when using `gh`
- Docker or Podman authenticated to Docker Hub

Verify authentication:

```powershell
gh auth status
podman login docker.io
```

Use `docker login docker.io` instead when Docker is the selected container engine.

## Phase 1: Preflight the source repository

Run from the application repository:

```powershell
git status --short
git diff
git log --oneline -10
git remote -v
git branch --show-current
```

Required conditions:

- all intended changes are reviewed
- unrelated work is not included
- no `.env`, credentials, tokens, local databases, generated working directories, or private configuration are staged
- project tests and production builds pass
- the current branch is the intended organization default branch

Agents must not commit, rename branches, replace remotes, force-push, or publish images without explicit authorization.

## Phase 2: Create the GitHub organization repository

Create an empty repository without a generated README, license, or `.gitignore` so it does not introduce an unrelated root commit.

Example:

```powershell
gh repo create myAI-Tech/core --private --description "MyAI Core control plane"
```

Choose `--public` only when public visibility has been approved.

Recommended descriptions:

- Core: `MyAI Core control, policy, workflow, and knowledge plane`
- Studio: `MyAI organization and administration studio`
- Council: `MyAI multi-persona council and collaboration application`
- AIDE: `Artificial Integrated Developer Experience for MyAI`
- KnowLedger: `MyAI knowledge index and relationship workspace`

## Phase 3: Add the organization remote

Preserve an existing personal `origin` until the organization push is verified. Add a separate remote named `myai-tech`:

```powershell
git remote add myai-tech https://github.com/myAI-Tech/<repository>.git
git remote -v
```

If the remote name already exists, inspect it before changing anything:

```powershell
git remote get-url myai-tech
```

Only when the URL is known to be wrong:

```powershell
git remote set-url myai-tech https://github.com/myAI-Tech/<repository>.git
```

## Phase 4: Commit the reviewed source

Before committing:

```powershell
git status --short
git diff
git log --oneline -10
```

Stage only reviewed files. Use the repository's existing commit-message style. Do not bypass hooks or amend unless explicitly requested.

Example:

```powershell
git add <reviewed-files>
git diff --cached
git commit -m "feat: prepare initial MyAI release"
```

## Phase 5: Push the source branch

Push only the intended default branch rather than every local branch:

```powershell
$Branch = git branch --show-current
git push -u myai-tech $Branch
```

After verification, configure the organization repository default branch and protections in GitHub.

Recommended protections:

- pull request required for future changes
- required build/test checks
- prevent force pushes
- prevent branch deletion
- require resolved review conversations
- restrict release environment secrets

## Phase 6: Create Docker Hub repositories

Create the required Docker Hub repositories under `myaitech` using the canonical names.

Set for each repository:

- visibility
- short description
- overview/readme
- automated scan settings if available
- team/service-account permissions

Do not recreate deprecated placeholder names such as `myaitech/myai-core-api` or `myaitech/myai-studio-frontend`.

## Phase 7: Build local release inputs

From `kairos-core`, list the canonical build map:

```powershell
.\scripts\multi-repo-workflow.ps1 -Action list
```

Build every baseline image:

```powershell
.\scripts\multi-repo-workflow.ps1 -Action build -Targets all -Engine podman -SourceTag local
```

Build selected images:

```powershell
.\scripts\multi-repo-workflow.ps1 -Action build -Targets "core-api,core-frontend" -Engine podman -SourceTag local
```

Linux/Zorin equivalents:

```bash
bash ./scripts/multi-repo-workflow.sh --action list
bash ./scripts/multi-repo-workflow.sh --action build --targets all --engine podman --source-tag local
bash ./scripts/multi-repo-workflow.sh --action build --targets core-api,core-frontend --engine podman --source-tag local
```

The mapped IDs are:

- `core-api`
- `core-frontend`
- `studio-frontend`
- `council-frontend`
- `aide-api`
- `aide-frontend`
- `knowledger-frontend`

## Phase 8: Verify images before publishing

Inspect local images:

```powershell
podman image inspect myaitech/core-api:local --format "{{.Id}} {{.Created}}"
podman image inspect myaitech/core-frontend:local --format "{{.Id}} {{.Created}}"
```

Minimum verification:

- application tests pass
- production frontend build passes
- image build passes from a clean/reproducible context
- container health endpoint responds
- runtime configuration is generated correctly
- no build depends on an uncommitted sibling worktree

### MyUI package preflight

For applications using `@myai-tech/myui`, verify the packed package rather than only the source repository:

```powershell
bun pm view "@myai-tech/myui@<version>"
bun install --frozen-lockfile
bun run build
```

Confirm required package subpath exports and component symbols exist under `node_modules/@myai-tech/myui`. A published version number alone is not sufficient evidence that the packed artifact contains the intended exports.

Verified package: `0.1.3-alpha.12` exposes `./knowledge.css`, `KnowledgeWorkspace`, and the knowledge graph types. KnowLedger builds from its own repository context without a sibling worktree.

## Phase 9: Publish an immutable image tag

Use one version across all images participating in the same suite release.

```powershell
$Version = "0.1.0-rc.1"
.\scripts\multi-repo-workflow.ps1 -Action publish -Targets all -Engine podman -SourceTag local -ReleaseTag $Version
```

For one repository:

```powershell
.\scripts\multi-repo-workflow.ps1 -Action publish -Targets "core-api,core-frontend" -Engine podman -SourceTag local -ReleaseTag $Version
```

The publish action tags each `:local` image with the requested immutable version and pushes it to Docker Hub.

Linux/Zorin equivalent:

```bash
VERSION=0.1.0-rc.1
bash ./scripts/multi-repo-workflow.sh --action publish --targets all --engine podman --source-tag local --release-tag "$VERSION"
```

## Phase 10: Test the published suite

Set every image variable in `myai-suite/.env` to the immutable version:

```dotenv
CORE_API_IMAGE=myaitech/core-api:0.1.0-rc.1
CORE_FRONTEND_IMAGE=myaitech/core-frontend:0.1.0-rc.1
STUDIO_FRONTEND_IMAGE=myaitech/studio:0.1.0-rc.1
COUNCIL_FRONTEND_IMAGE=myaitech/council:0.1.0-rc.1
MYAI_DE_API_IMAGE=myaitech/aide-api:0.1.0-rc.1
MYAI_DE_FRONTEND_IMAGE=myaitech/aide-frontend:0.1.0-rc.1
MYAI_KNOWLEDGER_FRONTEND_IMAGE=myaitech/knowledger:0.1.0-rc.1
```

Then run from `myai-suite`:

```powershell
.\deploy.ps1 -ProfileSet all -RefreshImages
podman compose --profile all ps
```

Required smoke checks:

- Core API health
- Core first-admin/login lock
- Core frontend loading
- Studio loading and Core connectivity
- Council loading, Core connectivity, and websocket chat
- AIDE API/frontend loading and Core capability checks
- KnowLedger loading and knowledge retrieval
- database migrations complete without data loss

## Phase 11: Create source tags

After the immutable image version passes smoke tests, tag the exact source commit in each participating repository:

```powershell
git tag -a v0.1.0 -m "MyAI 0.1.0"
git push myai-tech v0.1.0
```

Do not move or recreate an immutable source tag after publishing.

## Phase 12: Promote to stable

Promote the already-tested immutable images. Do not rebuild during promotion.

Example:

```powershell
podman pull myaitech/core-api:0.1.0
podman tag myaitech/core-api:0.1.0 myaitech/core-api:stable
podman push myaitech/core-api:stable
```

Repeat for each baseline image.

## Rollback

Rollback means changing suite image variables back to the last known-good immutable version and redeploying:

```powershell
.\deploy.ps1 -ProfileSet all -RefreshImages
```

Do not overwrite or delete the previous immutable image tags during a failed release. Database rollback requires a separately reviewed migration/restore procedure.

## Release evidence checklist

Record the following for each release:

- GitHub repository and commit SHA
- Git source tag
- Docker image name and immutable tag
- image digest
- test/build commands and results
- suite smoke-test result
- migration result
- approver
- release date
- known limitations

## Agent execution checklist

An automation agent performing this SOP must:

1. inspect `git status`, `git diff`, and recent history before committing
2. stop if secrets or conflicting concurrent changes are found
3. stage only intended files
4. never replace personal remotes without explicit approval
5. never force-push
6. never publish from an unreviewed dirty worktree
7. build from the commit that will be tagged
8. publish an immutable candidate before moving `stable`
9. return repository URLs, commit SHAs, image tags/digests, and verification results
