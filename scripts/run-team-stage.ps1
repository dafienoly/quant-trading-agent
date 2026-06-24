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
  [string]$Stage
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

$wslArgs = @()
if ($env:AGENT_WSL_DISTRO) {
  $wslArgs += @("-d", $env:AGENT_WSL_DISTRO)
}
$wslArgs += @("--", "bash", "-c", "cd `"$wslRoot`" && bash scripts/run-pipeline-team-agent.sh `"$Stage`"")

& wsl.exe @wslArgs

if ($LASTEXITCODE -ne 0) {
  Write-Error "Team pipeline runner exited with code $LASTEXITCODE"
  exit $LASTEXITCODE
}
