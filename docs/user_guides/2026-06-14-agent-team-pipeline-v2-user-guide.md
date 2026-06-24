# Agent Team Pipeline V2 User Guide

## 中文速览

Team Pipeline V2 的目标是让用户只需要在 GitHub Issue 里提出需求，
系统自动把需求交给不同 Agent 处理：

1. `Codex A` 负责产品经理工作，输出需求和最终功能验收。
2. `Codex B` 负责架构师工作，输出架构设计和最终代码 Review。
3. `OpenCode Lead` 使用 GLM 5.2 拆分阶段并做组内总 Review。
4. `Claude Code Developer` 使用 ultracode-xhigh 按阶段开发。
5. `OpenCode Test Engineer` 使用 DeepSeek V4 Pro max 按阶段测试。
6. 所有阶段测试通过后，才交给 `OpenCode Lead` 总 Review，再交给
   `Codex B` 做最终 Review。

关键规则：`OpenCode Test Engineer` 测试某个阶段通过后，不会直接交给
`Codex B`，而是回到 `Claude Code Developer` 继续下一阶段。只有所有阶段
都测试通过后，才进入 `OpenCode Lead` 总 Review。

## What This Feature Does

Team Pipeline V2 lets you start a feature from a GitHub Issue and route it
through:

1. Codex A as Product Manager.
2. Codex B as Architect.
3. OpenCode Lead, Claude Code Developer, and OpenCode Test Engineer as the development team.
4. Codex B as final Architect Reviewer.
5. Codex A as PM Acceptance.
6. Merge Gate for automatic or manual merge.

The purpose is to reduce Codex usage cost while keeping Codex in the final
quality and safety control positions.

## Start a New Feature

1. Open a GitHub Issue with the `Agent Feature Request` template.
2. Keep the default `agent:pipeline` and `stage:pm-pending` labels.
3. Choose the risk level.
4. Submit the Issue.

提交前建议先确认最近一次 `Agent Runtime Preflight` 的 `role=all` 运行成功。
如果 preflight 失败，不要创建正式功能 Issue；先修复 self-hosted runner 的
WSL PATH、CLI、模型认证或插件配置。

The bootstrap workflow creates:

- `.agent/state.json`
- `.agent/current_task.yaml`
- `.agent/handoff/codex_pm.md`
- an `epic/<date-feature>` branch
- a PR from the epic branch to `main`

## Recommended Local Setup

For full local automation, install a GitHub self-hosted runner on the machine
that can access:

- Windows Codex;
- WSL OpenCode and Claude Code;
- the repository checkout;
- environment variables for Codex API keys.

Use `docs/pipeline/LOCAL_AGENT_RUNTIME_SETUP.md` and
`.agent/config/local_agent_commands.example.env` as the setup reference.

中文说明：如果你要完全自动化，推荐在本机安装 GitHub self-hosted runner。
这样 GitHub label 触发 workflow 后，可以调用你本地 Windows 下的 Codex，
也可以通过 `wsl.exe` 调用 WSL 里的 Claude Code / ccswitch / opencode-go。
如果不安装 self-hosted runner，也可以用 dry-run 只生成 handoff 文件，再
手动把提示词发给对应 Agent。

## Stage Labels

The pipeline advances by PR labels:

| Label | Meaning |
|---|---|
| `stage:team-plan-pending` | OpenCode GLM 5.2 writes the phase plan |
| `stage:team-dev-pending` | Claude Code ultracode-xhigh develops the current phase |
| `stage:team-test-pending` | OpenCode DeepSeek V4 Pro max tests the current phase |
| `stage:claude-lead-review-pending` | OpenCode GLM 5.2 reviews all completed phases |
| `stage:codex-review-pending` | Codex B performs final architecture review |
| `stage:pm-acceptance-pending` | Codex A performs PM acceptance |
| `stage:merge-ready` | Merge Gate decides auto or manual merge |

OpenCode testing never jumps directly to Codex B. It returns to Claude Code
Developer until all planned phases pass.

## Manual Dry Run

You can generate handoffs locally without calling any external agent:

```powershell
.\.venv\Scripts\python.exe scripts\agent_pipeline.py init-feature `
  --title "My Feature" `
  --feature-id my-feature `
  --risk-level docs-only `
  --handoff-stage codex_pm `
  --handoff-stage codex_architect `
  --handoff-stage claude_lead_plan
```

Generate later-stage handoffs:

```powershell
.\.venv\Scripts\python.exe scripts\agent_pipeline.py write-handoff --stage claude_developer
.\.venv\Scripts\python.exe scripts\agent_pipeline.py write-handoff --stage claude_tester
.\.venv\Scripts\python.exe scripts\agent_pipeline.py write-handoff --stage codex_reviewer
```

## Runtime Preflight

Pipeline runner 或本机 Agent 环境变更后，运行：

```bash
gh workflow run agent-runtime-preflight.yml --ref main -f role=all
```

该 workflow 会真实验证 OpenCode Lead、OpenCode Test Engineer 和 Claude
Code Developer，但不会创建报告、提交代码、推进 stage 或合并 main。

## Parallel Local Workspaces

中文说明：多个开发小组并行时，不建议所有 Agent 共用同一个工作目录。
每个 Agent 小组、每个阶段开发分支、每个测试验证分支，都应该使用独立
`git worktree` 或独立 clone。否则多个 Agent 同时修改同一目录，容易互相
覆盖、打乱 `.agent/state.json`、污染测试临时文件。

Recommended local layout:

```text
D:/repo/work/signalGPTV2/quant-trading-agent/                 # main control workspace
D:/repo/work/signalGPTV2/worktrees/team-a/<feature>/           # hybrid team integration worktree
D:/repo/work/signalGPTV2/worktrees/team-a/<feature>/phase-1/   # Claude Code dev worktree
D:/repo/work/signalGPTV2/worktrees/team-a/<feature>/test-1/    # OpenCode test worktree
D:/repo/work/signalGPTV2/worktrees/team-b/<feature>/           # another team worktree
```

In practice, parallel execution usually means multiple local terminals:

- one terminal or runner job for `OpenCode Lead`;
- one terminal or runner job for `Claude Code Developer`;
- one terminal or runner job for `OpenCode Test Engineer`;
- optional Windows terminal for Codex A/B stages.

If you only have one local terminal, run stages sequentially. The workflow still
works; it just will not be parallel.

## Merge Behavior

The merge gate never merges `main` automatically. All changes require manual
review and manual merge. Sensitive changes require additional scrutiny,
including:

- GitHub workflows;
- scripts;
- API or UI entrypoints;
- data providers;
- risk, execution, broker, account, order, or live trading modules;
- credentials or `.env` files.

## When Codex B Rejects Work

Codex B review failures return structured feedback to OpenCode Lead. After
three failed Codex B reviews on the same feature, the pipeline enters
`stage:postmortem-pending` and waits for a postmortem and user decision before
continuing.
