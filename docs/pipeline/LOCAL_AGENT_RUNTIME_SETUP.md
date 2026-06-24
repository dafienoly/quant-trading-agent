# Local Agent Runtime Setup

## 中文说明

这份文档说明如何把 GitHub workflow、Windows 下的 Codex、本地 WSL
中的 OpenCode 与 Claude Code 接入 Team Pipeline V2。

Team stages 由仓库内 runner 固定执行：

1. OpenCode Lead：`opencode-go/glm-5.2`。
2. Claude Code Developer/BugFix：`ultracode-xhigh`、`effort=xhigh`、
   `feature-dev` workflow、`superpowers`。
3. OpenCode Test Engineer：`opencode-go/deepseek-v4-pro`、
   `variant=max`、`superpowers`。

GitHub Variables/Secrets 不再决定 Team stages 的模型。模型或插件不可用时
runner fail closed，不允许 fallback 到其他执行器。

This guide explains how to connect the Team Pipeline V2 GitHub workflows with a
local Windows Codex installation, WSL VS Code Claude Code Agent, and Codex API
access.

## Recommended Topology

```text
GitHub Issue / PR labels
  -> GitHub Actions workflow
  -> self-hosted runner on user's machine
  -> Windows Codex command for Codex A/B stages
  -> scripts/run-team-stage.ps1
  -> WSL scripts/run-pipeline-team-agent.sh
  -> OpenCode Lead / Claude Developer / OpenCode Tester
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
| `CODEX_B_REVIEW_AGENT_COMMAND` | Windows Codex or Codex API wrapper | Final architecture review |
| `CODEX_A_ACCEPTANCE_AGENT_COMMAND` | Windows Codex or Codex API wrapper | PM acceptance |

Use GitHub **Secrets** for commands that include tokens. Use GitHub
**Variables** only when the command contains no secret material.

Team stages only need an optional runner environment variable:

| Name | Purpose |
|---|---|
| `AGENT_WSL_DISTRO` | Optional WSL distribution name, for example `Ubuntu` |

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

## WSL Team Runner

GitHub workflow directly calls:

```powershell
.\scripts\run-team-stage.ps1 -Stage claude_developer
```

The PowerShell bridge converts the current checkout path to WSL and executes:

```bash
bash scripts/run-pipeline-team-agent.sh claude_developer
```

Runner 会检查 CLI、固定模型、superpowers/feature-dev，并写入
`.agent/tmp/<stage>.execution.json`。阶段报告仍由现有 gate 校验。

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

- `OpenCode Lead`: team integration worktree.
- `Claude Code Developer`: current phase development worktree.
- `OpenCode Test Engineer`: temporary test worktree.
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
