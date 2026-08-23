# Workspace Orchestration Helper

The workspace helper gives MyAI developers and a MyAIDE runner one structured
entry point for repository synchronization, image builds and refreshes, suite
deployment, and reusable local pipelines. Core owns the manifest and capability
contract; the runner that owns the workspace performs the host operations.

Core does not receive a container socket and does not expose arbitrary shell
execution through its API.

## Files

- `scripts/workspace-helper.mjs`: cross-platform implementation.
- `scripts/workspace-manifest.v1.json`: default MyAI workspace topology.
- `scripts/workspace-manifest.schema.json`: extension contract.
- `scripts/multi-repo-workflow.sh`: Linux compatibility wrapper.
- `scripts/multi-repo-workflow.ps1`: Windows compatibility wrapper.

The wrappers require Node.js or Bun, selecting Node.js when available and Bun
otherwise. Install one of those runtimes before using the compatibility
wrappers. Existing build, refresh, deploy, publish, reset, and list calls remain
supported after that prerequisite is met.

Canonical selection and tag parameters are `--targets`, `--source-tag`, and
`--release-tag` in Bash, with `-Targets`, `-SourceTag`, and `-ReleaseTag` in
PowerShell. The former `repos`, `local-tag`, and `publish-tag` names remain
compatibility aliases only.

## Default Layout

The default manifest resolves its workspace root to the parent of the Core
checkout and manages these repositories:

| Repository ID | Directory | Canonical remote |
| --- | --- | --- |
| `core` | `kairos-core` | `myAI-Tech/core` |
| `studio` | `kairos-studio` | `myAI-Tech/studio` |
| `council` | `kairos-council` | `myAI-Tech/council` |
| `aide` | `MyAIDE` | `myAI-Tech/aide` |
| `knowledger` | `MyAI-KnowLedger` | `myAI-Tech/knowledger` |

Repository IDs are used by `sync`. Component IDs such as `core-api`,
`studio-frontend`, and `aide-api` are used by image actions and to select the
effective Compose profile for deployment. Deployment remains profile-scoped:
one selected component deploys its profile, and components spanning profiles
deploy `all`. The helper reports that effective scope before execution.

Inspect the resolved topology before executing anything:

```bash
bash ./scripts/multi-repo-workflow.sh --action list
```

```powershell
.\scripts\multi-repo-workflow.ps1 -Action list
```

## Repository Sync

Clone all missing repositories and fast-forward existing clean checkouts:

```bash
bash ./scripts/multi-repo-workflow.sh --action sync --targets all
```

```powershell
.\scripts\multi-repo-workflow.ps1 -Action sync -Targets all
```

Select repository IDs for a partial sync:

```bash
bash ./scripts/multi-repo-workflow.sh \
  --action sync \
  --targets studio,council,knowledger
```

Sync is intentionally conservative:

- Missing repositories are cloned from the allowlisted URL and branch.
- Existing repositories must use the configured remote URL.
- Existing repositories must be on the configured branch.
- Worktrees with staged, unstaged, or untracked changes are rejected.
- Updates use fetch plus `merge --ff-only`; no rebase, reset, force, or push is
  performed.
- Paths must remain under the declared workspace root, including after symlink
  resolution.

This means a developer working on a feature branch must finish, stash, or
otherwise handle that work explicitly before synchronizing the manifest's
default branch. The helper never makes that choice for the developer.

## Development Pipeline

The default `development-redeploy` pipeline performs:

1. Safe synchronization of the four sibling repositories. It leaves the Core
   checkout running the helper untouched.
2. Local build of all seven images.
3. Profile-aware image refresh and service recreation.
4. Full suite deployment through the existing generated deployment helper.

Always inspect the plan first:

```bash
bash ./scripts/multi-repo-workflow.sh \
  --action pipeline \
  --pipeline development-redeploy \
  --dry-run
```

Run it after reviewing the plan and repository state:

```bash
bash ./scripts/multi-repo-workflow.sh \
  --action pipeline \
  --pipeline development-redeploy
```

PowerShell uses equivalent parameters:

```powershell
.\scripts\multi-repo-workflow.ps1 `
  -Action pipeline `
  -Pipeline development-redeploy `
  -DryRun
```

The default `images-redeploy` pipeline reads the effective images from Compose,
pulls non-local tags, and recreates the matching services. It does not run the
deployment helper afterward because that helper currently includes `--build`
and could replace a pulled release image with a local build.

Targeted refresh and `development-redeploy` use `--source-tag` or
`-SourceTag`. Each component declares its Compose `imageVariable`; the helper
sets process-scoped overrides so Compose resolves the exact image tag that was
built. It does not rewrite `myai-suite/.env`, and the refresh helper skips pull
attempts for `:local` tags.

The generated suite `deploy` helper currently includes `--build`. Use the
no-build release acceptance commands in
`docs/linux-development-environment.md` when proving that immutable registry
images work without local source.

Deployment and refresh require an existing generated `myai-suite` directory
with a reviewed `.env`. Repository sync can prepare the sibling checkouts, but
it does not generate bootstrap artifacts or copy secrets.

## MyAIDE Integration

Set `orchestration_manifest` in a development workspace's metadata to advertise
runner-backed orchestration through Core:

```json
{
  "runner_id": "runner_zorin_01",
  "repo_name": "myai-workspace",
  "repo_root": "/srv/ai/workspaces",
  "orchestration_manifest": "/srv/ai/workspaces/kairos-core/scripts/workspace-manifest.v1.json",
  "policy": {
    "proposal_only_capabilities": [
      "repo.sync",
      "container.images.refresh",
      "container.stack.deploy",
      "database.migrations.status",
      "database.migrations.apply",
      "workspace.pipeline.run"
    ]
  }
}
```

Core then includes these configured capabilities in workspace and runner
profiles:

- `repo.sync`
- `container.images.refresh`
- `container.stack.deploy`
- `database.migrations.status`
- `database.migrations.apply`
- `workspace.pipeline.run`

They remain `degraded` until an authenticated MyAIDE runner attests that it has
validated the manifest and can provide the corresponding local adapters. A
metadata path alone is not proof that host execution is available.

MyAIDE should resolve the required capabilities through
`POST /v1/development/capabilities/resolve`, request any required approval, and
invoke the local helper only after policy allows the operation. Proposal-only
resolution returns `allow: false`; approval must happen through the development
workflow. Core capability resolution is not itself execution authorization and
currently does not issue a durable one-time permit; keep the capabilities
proposal-only until that approval contract is implemented.

Use `--json` or `-Json` for newline-delimited events suitable for a runner log:

```bash
bash ./scripts/multi-repo-workflow.sh \
  --action pipeline \
  --pipeline development-redeploy \
  --dry-run \
  --json
```

Events distinguish pipeline, action, repository, suite, and command lifecycle
steps. Child processes are invoked with argument arrays rather than shell
interpolation, and common credential-shaped output is redacted from structured
results.

## Custom Repositories

Create another manifest conforming to
`scripts/workspace-manifest.schema.json`, then pass it explicitly:

```bash
bash ./scripts/multi-repo-workflow.sh \
  --manifest /srv/ai/workspaces/acme/workspace-manifest.json \
  --action sync \
  --targets all
```

A repository can participate only in source sync. Add a component when it also
produces a container image for the suite. Component paths are relative to their
repository, while `workspaceRoot` is relative to the manifest file.

Do not store credentials, access tokens, populated environment values, or
registry passwords in a manifest. Git and the container engine should use their
normal local credential stores.

## Custom Pipelines

Pipelines are ordered lists of typed operations:

```json
{
  "pipelines": {
    "custom-development": [
      {"action": "sync", "targets": ["core", "aide"]},
      {"action": "build", "targets": ["core-api", "aide-api"]},
      {"action": "refresh", "targets": ["core-api", "aide-api"]},
      {"action": "deploy", "targets": ["core-api", "aide-api"]}
    ]
  }
}
```

Version 1 pipelines accept only `sync`, `build`, `refresh`, and `deploy`. They
cannot embed command strings, publish images, or destroy volumes. This keeps a
custom manifest from becoming an unreviewed shell executor.

Deployment adapters are always loaded from `myai-suite` beside the trusted Core
helper. A custom manifest cannot redirect the helper to another deployment or
refresh script. Treat changes to the Core helper and generated suite scripts as
executable-code changes that require normal review.

Terraform support should be added later as explicit typed operations such as
`terraform.validate` and `terraform.plan`, with a fixed executable adapter,
workspace confinement, state/backend policy, plan artifact capture, approval,
and audit events. Do not add a generic `command` pipeline step as a shortcut.

## Database Migrations

Refresh and deploy start PostgreSQL, apply pending Grate migrations, and only
then recreate application containers. Both operations call the same versioned
migration CLI; they do not replay every SQL file through `psql`.

Run migration operations directly through the workspace wrapper:

```powershell
.\scripts\multi-repo-workflow.ps1 `
  -Action migrate `
  -MigrationAction status

.\scripts\multi-repo-workflow.ps1 `
  -Action migrate `
  -MigrationAction apply
```

Linux equivalents are:

```bash
bash ./scripts/multi-repo-workflow.sh \
  --action migrate \
  --migration-action status

bash ./scripts/multi-repo-workflow.sh \
  --action migrate \
  --migration-action apply
```

Use `--skip-migrations` or `-SkipMigrations` only for an explicitly reviewed
recovery procedure. A successful image refresh with a failed migration remains
a failed update and requires operator attention.

Legacy databases initialized before the Grate ledger require a one-time,
reviewed baseline after their schema is verified:

```powershell
.\scripts\multi-repo-workflow.ps1 `
  -Action migrate `
  -MigrationAction baseline `
  -MigrationBaselineThrough 0026 `
  -MigrationBaselineConfirmSchema
```

Do not baseline a new or partially migrated database. Baseline requires a
non-empty application schema, refuses an existing Grate ledger, and records
existing scripts only through the reviewed cutoff without executing them. Run
normal apply afterward so migrations newer than the cutoff execute.

The future Core update feature should enqueue `database.migrations.status` and
`database.migrations.apply` for an authenticated runner. It should consume the
same CLI, capture its structured events, and require release migration-plan,
backup, export, compatibility, and approval checks before issuing a permit.

## Destructive and Publishing Actions

`publish` and `reset-data` remain direct compatibility actions but are not
allowed inside manifest pipelines. `publish` requires an explicit publish tag.
`reset-data`, or deploy with `--destroy-data`, removes Compose volumes and must
not be exposed as an unattended MyAIDE action.

Production deployment requires stronger controls than this local helper:

- immutable image digests
- environment-specific approval
- database backup and migration readiness
- health checks and rollout evidence
- durable audit correlation
- rollback targets
- one-time runner-bound execution permits
