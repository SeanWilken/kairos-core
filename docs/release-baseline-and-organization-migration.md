# Release Baseline And Organization Migration

The executable operating procedure is `docs/sop-github-organization-and-container-publishing.md`.

## Initial application baseline

The initial MyAI suite release baseline is:

- Core API and Core frontend
- Studio frontend
- Council frontend
- MyAIDE server and frontend
- KnowLedger frontend

The suite `all` profile includes this complete baseline. Targeted profiles remain available for `core`, `suite`, `de`, and `knowledger` operations.

## Local image names

The current local image namespace remains `myaitech`:

- `myaitech/core-api`
- `myaitech/core-frontend`
- `myaitech/studio`
- `myaitech/council`
- `myaitech/aide-api`
- `myaitech/aide-frontend`
- `myaitech/knowledger`

Release images use Docker Hub under `myaitech`. GitHub source repositories use the `myAI-Tech` organization.

## Repository remote status at preparation time

- Core: personal `SeanWilken/kairos-core` origin
- Studio: personal `SeanWilken/kairos-studio` origin
- Council: no `origin`
- MyAIDE: no `origin`
- KnowLedger: no `origin`

Do not push release branches until the `myai-tech` organization repositories exist and each repository has an explicit organization remote.

## Recommended migration sequence

1. Create the five organization repositories with final names.
2. Add a new remote named `myai-tech` to each local repository.
3. Preserve existing personal remotes until organization pushes are verified.
4. Review each worktree and create focused commits without secrets, generated local state, or unrelated worktree changes.
5. Push the intended default branch to the organization remote.
6. Configure branch protection, required checks, environments, and registry credentials.
7. Build immutable release tags from reviewed commits.
8. Smoke-test the full `all` profile using only published images.
9. Promote the tested tag to the initial release tag.

## Current release blockers

- Core and MyAIDE have large uncommitted working sets that need focused review and commits.
- Organization repositories/remotes are not configured consistently.
- GitHub CLI and Docker Hub authentication are required before organization repository creation or image publication.

Resolved: `@myai-tech/myui@0.1.3-alpha.12` exposes `KnowledgeWorkspace`, the graph types, and `./knowledge.css`. KnowLedger now builds from its own repository context without a sibling worktree.

## Core security baseline

- Core exposes a public auth-state probe for bootstrap/login routing.
- Before tenancy exists, initial setup remains reachable.
- Once tenancy exists without an administrator, the frontend requires first-admin creation.
- Once an administrator exists, the frontend requires login and fails closed if auth state cannot be verified.
- Additional unauthenticated global-admin registration is rejected.
