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

$repoCandidates = @(
  $env:GITHUB_WORKSPACE,
  (Get-Location).Path
) | Where-Object { $_ -and (Test-Path (Join-Path $_ "scripts\run-pipeline-team-agent.sh")) }

if (-not $repoCandidates -or $repoCandidates.Count -eq 0) {
  Write-Error "无法定位包含 Team Pipeline runner 的仓库工作区。"
  exit 2
}

$repo = $repoCandidates[0]
if ($repo -match '^([A-Za-z]):\\(.*)$') {
  $drive = $Matches[1].ToLowerInvariant()
  $rest = $Matches[2] -replace '\\', '/'
} else {
  Write-Error "当前 GitHub self-hosted runner 工作区不是可转换的 Windows 路径：$repo"
  exit 2
}

$singleQuote = [char]0x27
if ($repo.Contains($singleQuote)) {
  Write-Error "仓库路径包含不受支持的单引号字符。"
  exit 2
}

$wslRepo = "/mnt/$drive/$rest"
$command = "cd `"$wslRepo`" && bash scripts/run-pipeline-team-agent.sh `"$Stage`""

$wslArgs = @()
if ($env:AGENT_WSL_DISTRO) {
  $wslArgs += @("-d", $env:AGENT_WSL_DISTRO)
}
$wslArgs += @("--", "bash", "-lc", $command)

Write-Host "使用仓库内 Team Pipeline runner 执行 stage=$Stage"
& wsl.exe @wslArgs
if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}
