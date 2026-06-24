param(
  [Parameter(Mandatory=$true)]
  [ValidateSet(
    "claude_lead_plan",
    "claude_developer",
    "claude_tester",
    "claude_lead_review",
    "bugfix",
    "postmortem"
  )]
  [string]$Stage,

  [switch]$PreflightOnly
)

$ErrorActionPreference = "Stop"

if ($env:GITHUB_WORKSPACE -and (Test-Path (Join-Path $env:GITHUB_WORKSPACE "scripts\run-pipeline-team-agent.sh"))) {
  $repoRoot = $env:GITHUB_WORKSPACE
} else {
  $repoRoot = (Get-Location).Path
  if (-not (Test-Path (Join-Path $repoRoot "scripts\run-pipeline-team-agent.sh"))) {
    Write-Error "Cannot locate repo root with scripts/run-pipeline-team-agent.sh"
    exit 2
  }
}

if ($repoRoot -match '^([A-Za-z]):') {
  $drive = $Matches[1].ToLowerInvariant()
  $wslRoot = "/mnt/$drive" + ($repoRoot.Substring(2) -replace '\\', '/')
} else {
  Write-Error "Cannot convert path to WSL: $repoRoot"
  exit 2
}

$scriptPath = "$wslRoot/scripts/run-pipeline-team-agent.sh"
Write-Host "WSL script path: $scriptPath"

$metadataPath = $null
if ($PreflightOnly) {
  $preflightRole = switch ($Stage) {
    "claude_lead_plan" { "lead" }
    "claude_lead_review" { "lead" }
    "postmortem" { "lead" }
    "claude_tester" { "tester" }
    "claude_developer" { "developer" }
    "bugfix" { "developer" }
  }
  $metadataPath = Join-Path $repoRoot ".agent\tmp\runtime-preflight-$preflightRole.execution.json"
  Remove-Item -Force -ErrorAction SilentlyContinue $metadataPath
}

$wslArgs = @()
if ($env:AGENT_WSL_DISTRO) {
  $wslArgs += @("-d", $env:AGENT_WSL_DISTRO)
}
$wslArgs += @("--cd", $wslRoot, "--", "bash", "-i", "scripts/run-pipeline-team-agent.sh", $Stage)
if ($PreflightOnly) {
  $wslArgs += "--preflight-only"
}

& wsl.exe @wslArgs

$runnerExitCode = $LASTEXITCODE
if ($runnerExitCode -ne 0) {
  Write-Error "Team pipeline runner exited with code $runnerExitCode" -ErrorAction Continue
  exit $runnerExitCode
}

if ($PreflightOnly) {
  if (-not (Test-Path $metadataPath)) {
    Write-Error "Runtime preflight returned without required metadata: $metadataPath"
    exit 2
  }
  Write-Host "Runtime preflight metadata: $metadataPath"
}
