param(
  [ValidateSet("apply", "baseline", "dry-run", "status")]
  [string]$Action = "apply",
  [string]$SuitePath = (Join-Path $PSScriptRoot "myai-suite"),
  [string]$MigrationsPath = (Join-Path $PSScriptRoot "migrations"),
  [string]$DbHost = "",
  [string]$Port = "",
  [string]$Database = "",
  [string]$Username = "",
  [ValidateRange(0, 600)]
  [int]$WaitSeconds = 60,
  [ValidatePattern("^\d{4}$")]
  [string]$BaselineThrough = "",
  [switch]$BaselineConfirmSchema,
  [switch]$Baseline,
  [switch]$DryRun,
  [switch]$UpToDateCheck,
  [switch]$RestoreTools,
  [switch]$Json
)

$ErrorActionPreference = "Stop"

if ($Baseline) { $Action = "baseline" }
if ($DryRun) { $Action = "dry-run" }
if ($UpToDateCheck) { $Action = "status" }
if ($DbHost) { $env:POSTGRES_HOST = $DbHost }
if ($Port) { $env:POSTGRES_PORT = $Port }
if ($Database) { $env:POSTGRES_DB = $Database }
if ($Username) { $env:POSTGRES_USER = $Username }

$runtime = if (Get-Command node -ErrorAction SilentlyContinue) {
  "node"
} elseif (Get-Command bun -ErrorAction SilentlyContinue) {
  "bun"
} else {
  throw "Node.js or Bun is required to run migrations."
}

$arguments = @(
  (Join-Path $PSScriptRoot "scripts\migration-helper.mjs"),
  "--action", $Action,
  "--suite-path", $SuitePath,
  "--migrations-path", $MigrationsPath,
  "--wait-seconds", $WaitSeconds
)
if ($RestoreTools) { $arguments += "--restore-tools" }
if ($BaselineThrough) { $arguments += @("--baseline-through", $BaselineThrough) }
if ($BaselineConfirmSchema) { $arguments += "--baseline-confirm-schema" }
if ($Json) { $arguments += "--json" }

& $runtime @arguments
if ($LASTEXITCODE -ne 0) {
  throw "Migration helper failed with exit code $LASTEXITCODE."
}
