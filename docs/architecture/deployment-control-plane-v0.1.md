# Deployment Control Plane v0.1

Status: initial declarative foundation

## Purpose

Core records deployable artifacts, environments, desired deployment state, and
runtime observations. It does not run Git, registry, container, Kubernetes, or
Terraform commands. Those operations belong to authenticated MyAIDE or
infrastructure runners and will require durable approvals in a later phase.

## Resources

### Registry connections

Registry connections identify Docker Hub, GHCR, cloud registries, or custom
registries. They store an opaque `credential_secret_ref`, never a password,
token, Docker auth document, or cloud access key.

Secret references must use an approved URI such as `vault://`, `op://`,
`aws-secretsmanager://`, `azure-keyvault://`, or `gcp-secretmanager://`.

Registry and environment configuration rejects credential-shaped keys. Secret
reference keys ending in `_ref` or `_reference` are permitted.

### Environments

Environments are stable organization-scoped targets such as development,
staging, or production. Configuration can identify a runner, adapter, region,
or Terraform workspace, but cannot contain credentials.

### Releases

A release is immutable metadata connecting a component and version to an
artifact reference and SHA-256 digest. Releases have no generic update route.
Corrected artifacts require a new version and release record.

Container artifact references must include the same digest recorded by the
release, for example `docker.io/myaitech/core-api@sha256:...`.

The mutable `latest` container tag is rejected. Channels such as `candidate`
and `stable` may select releases later, but deployment identity remains the
immutable digest.

Every release includes a migration plan with one of these strategies:

- `none`: no schema or data migration.
- `expand`: additive, backward-compatible schema changes.
- `migrate`: resumable mapping or backfill while old and new shapes coexist.
- `contract`: delayed cleanup after stabilization and confirmation.

Expand and migrate phases must remain backward compatible. Contract phases
must declare a prior stabilization release, backup requirement, historical
export offer, and explicit confirmation requirement.

### Deployment declarations

A deployment declaration records desired state only. It does not contact the
runtime. A new declaration for the same environment and component atomically
supersedes the prior current declaration while preserving history.

Redeclaring an older immutable release is the future rollback mechanism. It
does not reverse additive database migrations.

### Runtime observations

Runtime check runs are append-only observations supplied by an operator or a
future authenticated runner. They do not execute checks from Core. Monitoring
can use their status, individual checks, summary, source, and observation time.
User-authenticated endpoints always record an operator source. Runner sources
will require a separate authenticated runner contract.

## API Surface

The initial endpoints are under `/v1/deployment-control`:

- Registry connection create, list, get, and update.
- Environment create, list, get, and update.
- Immutable release create, list, and get.
- Deployment declaration create, list, and get.
- Runtime observation record and list.

There are intentionally no `deploy`, `execute`, `apply`, `promote`, `rollback`,
or runtime-check execution endpoints.

## Authorization

All resources are tenant and organization scoped. Reads require active
organization membership. Writes require an owner, administrator, or global
administrator. Organization membership is checked against persisted state,
not only token roles or an `X-Org-ID` header.

## Migration Safety

Migration `0027_deployment_control_plane.sql` is additive. It creates new
tables, indexes, constraints, and a nullable organization scope on audit
events. Existing audit rows remain unchanged and tenant-wide history remains
available only to global administrators. It does not rename, truncate, delete,
or rewrite existing application data. Each mutation and its audit event commit
in the same database transaction.

Future runner execution must enforce:

- Reviewed migration IDs and checksums.
- Backup and export prerequisites.
- Compatibility-window checks.
- Resumable mapper checkpoints.
- Validation queries and count/checksum evidence.
- Explicit approval before contraction.
- A later release for removal of legacy structures.

The runner procedure for image refresh and deployment invokes the same
Grate-backed migration CLI used by operators. Core should schedule the status
check and apply action through a one-time permit and persist the resulting
events as deployment steps; it must not run database tooling inside the API
process.

## Next Phase

The next phase adds a durable objective/action queue with dependencies,
approval waits, expiry, frozen arguments, and one-time runner permits. The
deployment dashboard should remain read-only until runners can report observed
state and the approval contract is complete.
