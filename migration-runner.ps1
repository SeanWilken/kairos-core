param(
  [string]$DbHost = "localhost",
  [string]$Port = "5432",
  [string]$Database = "myai",
  [string]$Username = "myai",
  [string]$Password = "myai",
  [switch]$Baseline,
  [switch]$DryRun,
  [switch]$UpToDateCheck
)

$ErrorActionPreference = "Stop"

$conn = "Host=$DbHost;Port=$Port;Database=$Database;Username=$Username;Password=$Password"
$args = @(
  "grate",
  "--connstring", $conn,
  "--dt", "PostgreSQL",
  "--sqlfilesdirectory", ".",
  "--folders", "up=migrations",
  "--schema", "grate",
  "--noninteractive"
)

if ($Baseline) {
  $args += "--baseline"
}
if ($DryRun) {
  $args += "--dryrun"
}
if ($UpToDateCheck) {
  $args += "--isuptodate"
}

dotnet @args
