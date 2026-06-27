# R0.3 Agent Runtime Abstraction 架构

## 架构目标

新增一个只读 Agent Runtime Abstraction，用统一 contract 描述 pipeline stage 的 runtime 状态，让 AgentOps 和后续 gate 能审计执行模式，但不直接执行命令。

## 模块结构

```text
src/product_app/agent_runtime/
├── __init__.py
├── contracts.py
└── resolver.py

scripts/agent_runtime_profile.py
```

## 核心契约

### RuntimeMode

```text
real
dry_run
mock
disabled
unknown
```

### RuntimeProvider

```text
codex
opencode
team_stage_runner
generic_command
unknown
```

### AgentRuntimeProfile

```text
contract_version
stage
provider
mode
command_env_var
fallback_command_env_vars
command_configured
command_fingerprint
real_flag_env_var
real_enabled
strict_flag_env_var
strict_enabled
timeout_env_var
timeout_seconds
model
variant
source
audit
safety
```

## 安全设计

1. resolver 不执行命令。
2. resolver 不返回 command 原文。
3. command fingerprint 只使用 SHA-256 前 12 位，便于审计 drift，但不能还原 secret。
4. `RuntimeSafety.executes_command` 固定为 false。
5. strict mode 只有在 real profile 下才允许 `safe_to_execute=true`。

## Stage 映射

Codex stages：

```text
codex_pm -> CODEX_A_PM_AGENT_COMMAND
codex_architect -> CODEX_B_ARCHITECT_AGENT_COMMAND
codex_reviewer -> CODEX_B_REVIEW_AGENT_COMMAND or REVIEW_AGENT_COMMAND
codex_acceptance -> CODEX_A_ACCEPTANCE_AGENT_COMMAND or ACCEPTANCE_AGENT_COMMAND
```

Team stages：

```text
claude_lead_plan -> OpenCode lead model
claude_lead_review -> OpenCode lead model
claude_developer -> OpenCode developer model
claude_tester -> OpenCode tester model
bugfix -> OpenCode developer model
postmortem -> OpenCode lead model
runtime_preflight -> OpenCode preflight
```

`claude_*` 名称保留为历史 stage ID，实际 provider 在本架构中标记为 `opencode`。

## CLI

```bash
python scripts/agent_runtime_profile.py --stage codex_pm
python scripts/agent_runtime_profile.py --stage claude_developer
python scripts/agent_runtime_profile.py --stage runtime_preflight --dry-run
```

## 测试策略

`tests/test_agent_runtime_resolver.py` 覆盖：

1. Codex real。
2. Codex disabled。
3. strict mode blocker。
4. mock command detection。
5. dry-run override。
6. fallback command env。
7. OpenCode team stage。
8. unknown stage。
9. CLI JSON 输出。

## 后续扩展

后续可以在 AgentOps 中展示 runtime profile，也可以在 workflow 中调用 CLI 生成 `.agent/tmp/<stage>.runtime-profile.json`。本 PR 不修改 workflow，降低 R0.3 风险。

## 安全确认

本架构不新增执行器、不调用 Agent、不读取 secret、不写入业务数据、不触碰交易相关模块。