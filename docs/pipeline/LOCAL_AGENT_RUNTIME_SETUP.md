# Local Agent Runtime Setup

## 中文说明

这份文档说明如何把 GitHub workflow、Windows 下的 Codex、本地 WSL
中的 Claude Code Agent，以及 Codex API 接入到 Team Pipeline V2。

你的 `Claude Code -> ccswitch -> opencode-go -> DeepSeek` 接入方式是可
以兼容的。Pipeline 只要求“Claude 阶段命令”满足输入输出契约：

1. 读取 `.agent/handoff/<stage>.md`。
2. 在正确的 git 分支或 worktree 中执行。
3. 输出对应的 `docs/dev_reports/`、`docs/test_reports/` 或 `docs/review/`
   文件。
4. 如果失败，返回非 0 exit code。
5. 不把 API Key、Cookie、Token 写入仓库或日志。

也就是说，`ccswitch` 和 `opencode-go` 只影响下面
`CLAUDE_*_AGENT_COMMAND` 的具体命令写法，不影响 GitHub label、阶段门禁、
Codex Review、PM 验收和 Merge Gate 的规则。

This guide explains how to connect the Team Pipeline V2 GitHub workflows with a
local Windows Codex installation, WSL VS Code Claude Code Agent, and Codex API
access.

## Recommended Topology

```text
GitHub Issue / PR labels
  -> GitHub Actions workflow
  -> self-hosted runner on user's machine
  -> Windows Codex command for Codex A/B stages
  -> WSL Claude Code command for Claude A/B/C stages
  -> repository reports and gate files
```

GitHub-hosted runners cannot directly control local Windows or WSL tools. Use a
self-hosted runner for full local automation, or run workflows in dry-run mode
and execute the generated `.agent/handoff/*.md` prompts manually.

## Required GitHub Variables or Secrets

Configure these in GitHub repository settings:

| Name | Example owner | Purpose |
|---|---|---|
| `CODEX_A_PM_AGENT_COMMAND` | Windows Codex or Codex API wrapper | Generates requirements |
| `CODEX_B_ARCHITECT_AGENT_COMMAND` | Windows Codex or Codex API wrapper | Generates architecture |
| `CLAUDE_LEAD_AGENT_COMMAND` | WSL Claude Code | Creates team plan, lead review, postmortem |
| `CLAUDE_DEVELOPER_AGENT_COMMAND` | WSL Claude Code | Implements each phase |
| `CLAUDE_TESTER_AGENT_COMMAND` | WSL Claude Code | Tests each phase |
| `BUGFIX_AGENT_COMMAND` | WSL Claude Code or BugFix service | Fix loop |
| `CODEX_B_REVIEW_AGENT_COMMAND` | Windows Codex or Codex API wrapper | Final architecture review |
| `CODEX_A_ACCEPTANCE_AGENT_COMMAND` | Windows Codex or Codex API wrapper | PM acceptance |

Use GitHub **Secrets** for commands that include tokens. Use GitHub
**Variables** only when the command contains no secret material.

## Windows Codex Wrapper

Create a local wrapper script outside the repository if it contains secrets. A
safe repository-side command should reference environment variables only:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\agent-runners\run-codex-stage.ps1 -Stage codex_pm
```

The wrapper should:

1. read `.agent/handoff/<stage>.md`;
2. call the local Codex CLI or Codex API using environment variables;
3. write the required report under `docs/`;
4. return non-zero on missing report, model error, or policy failure.

## WSL Claude Code Wrapper

Use `wsl.exe` from a Windows self-hosted runner:

```powershell
wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/repo/work/signalGPTV2/quant-trading-agent && ./scripts/run_claude_stage.sh claude_developer'
```

If Claude Code is routed through `ccswitch` to `opencode-go` and a DeepSeek
model, keep that logic inside `scripts/run_claude_stage.sh` or another local
wrapper. The workflow should still call one stable command per stage.

Example wrapper shape:

```bash
#!/usr/bin/env bash
set -euo pipefail

stage="${1:?stage is required}"
handoff=".agent/handoff/${stage}.md"
test -f "$handoff"

# Example only. Replace this with the exact ccswitch/opencode-go command that
# works in your WSL environment. Keep secrets in environment variables.
ccswitch run -- opencode run \
  --model "${DEEPSEEK_MODEL:-deepseek-v4-flash}" \
  --input "$handoff"
```

The exact `ccswitch` command may differ on your machine. The required behavior
is stable: read the handoff, run the Agent, write the report, and return a
correct exit code.

The WSL wrapper should:

1. activate the project virtual environment when Python checks are needed;
2. read `.agent/handoff/<stage>.md`;
3. run Claude Code in the repository checkout;
4. write the required phase report;
5. update `.agent/state.json` after phase testing:

```json
{
  "team_pipeline": {
    "current_phase": 2,
    "all_phases_tested": false
  }
}
```

Set `all_phases_tested=true` only after every phase in
`docs/dev_plans/*team-plan.md` has a passing test report.

## Parallel Local Workspace Layout

When multiple Claude teams run in parallel, do not let them share one working
directory. Use git worktrees or separate clones.

Recommended layout:

```text
/mnt/d/repo/work/signalGPTV2/quant-trading-agent/                 # control workspace
/mnt/d/repo/work/signalGPTV2/worktrees/team-a/<feature>/           # team A integration
/mnt/d/repo/work/signalGPTV2/worktrees/team-a/<feature>/phase-1/   # Claude B phase 1
/mnt/d/repo/work/signalGPTV2/worktrees/team-a/<feature>/test-1/    # Claude C phase 1
/mnt/d/repo/work/signalGPTV2/worktrees/team-b/<feature>/           # team B integration
```

Create worktrees from the same repository:

```bash
git fetch origin
git worktree add /mnt/d/repo/work/signalGPTV2/worktrees/team-a/my-feature origin/epic/my-feature
git worktree add /mnt/d/repo/work/signalGPTV2/worktrees/team-a/my-feature-phase-1 -b feat/my-feature/phase-1 origin/epic/my-feature
```

Each active Agent terminal should use one worktree:

- `Claude Code A`: team integration worktree.
- `Claude Code B`: current phase development worktree.
- `Claude Code C`: temporary test worktree.
- `Codex A/B`: control workspace or epic worktree.

Do not run two writing Agents in the same worktree at the same time.

## Dry-Run Bootstrap

Generate pipeline state and handoff prompts without calling external agents:

```bash
python scripts/agent_pipeline.py init-feature \
  --title "Agent Team Pipeline V2" \
  --feature-id agent-team-pipeline-v2 \
  --risk-level docs-only \
  --handoff-stage codex_pm \
  --handoff-stage codex_architect \
  --handoff-stage claude_lead_plan
```

Generate a specific handoff:

```bash
python scripts/agent_pipeline.py write-handoff --stage claude_developer
python scripts/agent_pipeline.py write-handoff --stage claude_tester
python scripts/agent_pipeline.py write-handoff --stage codex_reviewer
```

## Local Verification Commands

Use WSL/Linux paths when testing inside WSL:

```bash
git status --short --branch
./.venv/bin/python -m pytest tests/test_agent_pipeline_automation.py -q --basetemp=runtime/pytest-tmp-agent-team-pipeline-v2
./.venv/bin/python -m ruff check src/product_app/agent_pipeline_automation.py scripts/agent_pipeline.py tests/test_agent_pipeline_automation.py
git diff --check
```

Use Windows paths only when the active workspace is Windows-only:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_agent_pipeline_automation.py -q --basetemp=runtime/pytest-tmp-agent-team-pipeline-v2
.\.venv\Scripts\python.exe -m ruff check src/product_app/agent_pipeline_automation.py scripts/agent_pipeline.py tests/test_agent_pipeline_automation.py
```

## Security Rules

- Never store Codex API keys or Claude credentials in this repository.
- Use environment variables or GitHub Secrets only.
- Do not echo secrets in workflow logs.
- Sensitive changed paths still require manual approval even if every Agent
  stage passes.
