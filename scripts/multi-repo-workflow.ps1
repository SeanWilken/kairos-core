param(
  [ValidateSet("sync", "build", "refresh", "migrate", "deploy", "publish", "reset-data", "list", "pipeline")]
  [string]$Action = "list",
  [Alias("Repos")]
  [string[]]$Targets = @("all"),
  [ValidateSet("podman", "docker")]
  [string]$Engine = $(if ($env:CONTAINER_ENGINE) { $env:CONTAINER_ENGINE } else { "podman" }),
  [Alias("LocalTag")]
  [string]$SourceTag = "local",
  [Alias("PublishTag")]
  [string]$ReleaseTag = "",
  [string]$Manifest = (Join-Path $PSScriptRoot "workspace-manifest.v1.json"),
  [string]$Pipeline = "",
  [ValidateSet("apply", "baseline", "dry-run", "status")]
  [string]$MigrationAction = "apply",
  [ValidatePattern("^\d{4}$")]
  [string]$MigrationBaselineThrough = "",
  [switch]$MigrationBaselineConfirmSchema,
  [switch]$RefreshImages,
  [switch]$DestroyData,
  [switch]$SkipMigrations,
  [switch]$DryRun,
  [switch]$Json
)

$ErrorActionPreference = "Stop"

$arguments = @(
  (Join-Path $PSScriptRoot "workspace-helper.mjs"),
  "--action", $Action,
  "--targets", ($Targets -join ","),
  "--engine", $Engine,
  "--source-tag", $SourceTag,
  "--manifest", $Manifest
)

if ($ReleaseTag) { $arguments += @("--release-tag", $ReleaseTag) }
if ($Pipeline) { $arguments += @("--pipeline", $Pipeline) }
if ($MigrationAction) { $arguments += @("--migration-action", $MigrationAction) }
if ($MigrationBaselineThrough) { $arguments += @("--migration-baseline-through", $MigrationBaselineThrough) }
if ($MigrationBaselineConfirmSchema) { $arguments += "--migration-baseline-confirm-schema" }
if ($RefreshImages) { $arguments += "--refresh-images" }
if ($DestroyData) { $arguments += "--destroy-data" }
if ($SkipMigrations) { $arguments += "--skip-migrations" }
if ($DryRun) { $arguments += "--dry-run" }
if ($Json) { $arguments += "--json" }

$runtime = if (Get-Command node -ErrorAction SilentlyContinue) {
  "node"
} elseif (Get-Command bun -ErrorAction SilentlyContinue) {
  "bun"
} else {
  throw "Node.js or Bun is required to run the workspace helper."
}

& $runtime @arguments
if ($LASTEXITCODE -ne 0) {
  throw "Workspace helper failed with exit code $LASTEXITCODE."
}
