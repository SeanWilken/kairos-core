param(
  [ValidateSet("build", "refresh", "deploy", "publish", "reset-data", "list")]
  [string]$Action = "list",
  [string[]]$Repos = @("all"),
  [ValidateSet("podman", "docker")]
  [string]$Engine = $(if ($env:CONTAINER_ENGINE) { $env:CONTAINER_ENGINE } else { "podman" }),
  [string]$LocalTag = "local",
  [string]$PublishTag = "",
  [switch]$RefreshImages,
  [switch]$DestroyData
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$projectsRoot = Split-Path $root -Parent
$suitePath = Join-Path $root "myai-suite"

$repoMap = @(
  [pscustomobject]@{ Id = "core-api"; Label = "Core API"; Path = Join-Path $root "backend"; Context = Join-Path $root "backend"; Dockerfile = Join-Path $root "backend\Dockerfile"; Image = "myaitech/core-api"; Profile = "core" },
  [pscustomobject]@{ Id = "core-frontend"; Label = "Core Frontend"; Path = Join-Path $root "frontend"; Context = Join-Path $root "frontend"; Dockerfile = Join-Path $root "frontend\Dockerfile"; Image = "myaitech/core-frontend"; Profile = "core" },
  [pscustomobject]@{ Id = "studio-frontend"; Label = "Studio Frontend"; Path = Join-Path $projectsRoot "kairos-studio"; Context = Join-Path $projectsRoot "kairos-studio"; Dockerfile = Join-Path $projectsRoot "kairos-studio\Dockerfile"; Image = "myaitech/studio"; Profile = "suite" },
  [pscustomobject]@{ Id = "council-frontend"; Label = "Council Frontend"; Path = Join-Path $projectsRoot "kairos-council"; Context = Join-Path $projectsRoot "kairos-council"; Dockerfile = Join-Path $projectsRoot "kairos-council\Dockerfile"; Image = "myaitech/council"; Profile = "suite" },
  [pscustomobject]@{ Id = "aide-api"; Label = "MyAIDE API"; Path = Join-Path $projectsRoot "MyAIDE\src\MyAIDE.Api"; Context = Join-Path $projectsRoot "MyAIDE"; Dockerfile = Join-Path $projectsRoot "MyAIDE\src\MyAIDE.Api\Dockerfile"; Image = "myaitech/aide-api"; Profile = "de" },
  [pscustomobject]@{ Id = "aide-frontend"; Label = "MyAIDE Frontend"; Path = Join-Path $projectsRoot "MyAIDE\src\MyAIDE.Web"; Context = Join-Path $projectsRoot "MyAIDE"; Dockerfile = Join-Path $projectsRoot "MyAIDE\src\MyAIDE.Web\Dockerfile"; Image = "myaitech/aide-frontend"; Profile = "de" },
  [pscustomobject]@{ Id = "knowledger-frontend"; Label = "KnowLedger Frontend"; Path = Join-Path $projectsRoot "MyAI-KnowLedger"; Context = Join-Path $projectsRoot "MyAI-KnowLedger"; Dockerfile = Join-Path $projectsRoot "MyAI-KnowLedger\Dockerfile"; Image = "myaitech/knowledger"; Profile = "knowledger" }
)

function Resolve-Targets {
  param([string[]]$Requested)

  $normalizedRequested = @()
  foreach ($item in $Requested) {
    if (-not $item) { continue }
    $normalizedRequested += ($item -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ })
  }

  if ($normalizedRequested.Count -eq 1 -and $normalizedRequested[0] -eq "all") {
    return $repoMap
  }

  $selected = @()
  foreach ($repo in $normalizedRequested) {
    $match = $repoMap | Where-Object { $_.Id -eq $repo }
    if (-not $match) {
      throw "Unknown repo id: $repo"
    }
    $selected += $match
  }
  return $selected
}

function Assert-PathExists {
  param([string]$PathValue, [string]$Label)
  if (-not (Test-Path $PathValue)) {
    throw "$Label path not found: $PathValue"
  }
}

function Invoke-Build {
  param($Target)
  Assert-PathExists -PathValue $Target.Context -Label $Target.Label
  Assert-PathExists -PathValue $Target.Dockerfile -Label "$($Target.Label) Dockerfile"
  $tag = "$($Target.Image):$LocalTag"
  "[$($Target.Id)] building $tag from $($Target.Context)"
  & $Engine build -f $Target.Dockerfile -t $tag $Target.Context
  if ($LASTEXITCODE -ne 0) {
    throw "Container build failed for $($Target.Id) with exit code $LASTEXITCODE."
  }
}

function Invoke-SuiteRefresh {
  param([array]$Targets)
  Assert-PathExists -PathValue $suitePath -Label "myai-suite"
  $byProfile = $Targets | Group-Object Profile
  foreach ($group in $byProfile) {
    $profile = [string]$group.Name
    $imagesCsv = ($group.Group | ForEach-Object { "$($_.Image):$LocalTag" }) -join ","
    "[suite:$profile] refreshing images $imagesCsv"
    & ".\refresh-images.ps1" -ImagesCsv $imagesCsv -ProfileSet $profile
  }
}

function Invoke-SuiteDeploy {
  param([array]$Targets)
  Assert-PathExists -PathValue $suitePath -Label "myai-suite"
  $profiles = $Targets | Select-Object -ExpandProperty Profile -Unique
  $profileSet = if ($profiles.Count -gt 1) { "all" } else { [string]$profiles[0] }
  if ($DestroyData) {
    "[suite:$profileSet] destroying volumes and containers"
    & $Engine compose --profile $profileSet down -v
  }
  if ($RefreshImages) {
    & ".\deploy.ps1" -ProfileSet $profileSet -RefreshImages
  } else {
    & ".\deploy.ps1" -ProfileSet $profileSet
  }
}

function Invoke-Publish {
  param($Target)
  if (-not $PublishTag) {
    throw "PublishTag is required for publish action."
  }
  $source = "$($Target.Image):$LocalTag"
  $dest = "$($Target.Image):$PublishTag"
  "[$($Target.Id)] tagging $source -> $dest"
  & $Engine tag $source $dest
  if ($LASTEXITCODE -ne 0) {
    throw "Container tag failed for $($Target.Id) with exit code $LASTEXITCODE."
  }
  "[$($Target.Id)] pushing $dest"
  & $Engine push $dest
  if ($LASTEXITCODE -ne 0) {
    throw "Container push failed for $($Target.Id) with exit code $LASTEXITCODE."
  }
}

$targets = Resolve-Targets -Requested $Repos

switch ($Action) {
  "list" {
    $repoMap | Select-Object Id, Label, Path, Image, Profile | Format-Table -AutoSize
  }
  "build" {
    foreach ($target in $targets) { Invoke-Build -Target $target }
  }
  "refresh" {
    Push-Location $suitePath
    try {
      Invoke-SuiteRefresh -Targets $targets
    }
    finally {
      Pop-Location
    }
  }
  "deploy" {
    Push-Location $suitePath
    try {
      Invoke-SuiteDeploy -Targets $targets
    }
    finally {
      Pop-Location
    }
  }
  "reset-data" {
    $DestroyData = $true
    Push-Location $suitePath
    try {
      Invoke-SuiteDeploy -Targets $targets
    }
    finally {
      Pop-Location
    }
  }
  "publish" {
    foreach ($target in $targets) { Invoke-Publish -Target $target }
  }
}
