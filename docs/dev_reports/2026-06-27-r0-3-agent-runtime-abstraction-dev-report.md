# R0.3 Agent Runtime Abstraction 开发报告

## 变更范围

本次变更新增只读 Agent Runtime Abstraction，用于解析和审计 Agent stage 的 runtime profile，但不执行任何外部命令。

变更文件：

| 文件 | 说明 |
| --- | --- |
| `src/product_app/agent_runtime/__init__.py` | 新增 package entrypoint |
| `src/product_app/agent_runtime/contracts.py` | 新增 runtime contract models |
| `src/product_app/agent_runtime/resolver.py` | 新增 runtime resolver |
| `scripts/agent_runtime_profile.py` | 新增 CLI JSON 输出 |
| `tests/test_agent_runtime_resolver.py` | 新增 resolver / CLI 测试 |
| `docs/requirements/...` | R0.3 需求文档 |
| `docs/design/...` | R0.3 架构文档 |

## 实现说明

1. 新增 `RuntimeMode`：`real`、`dry_run`、`mock`、`disabled`、`unknown`。
2. 新增 `RuntimeProvider`：`codex`、`opencode`、`team_stage_runner`、`generic_command`、`unknown`。
3. `resolve_agent_runtime(stage, env, dry_run)` 可解析指定 stage 的 runtime profile。
4. command 原文不会出现在 profile 中，只返回 `command_env_var`、`command_configured` 和 `command_fingerprint`。
5. 对 legacy `claude_*` stage 明确标注实际 provider 为 OpenCode。
6. 新增 CLI：`python scripts/agent_runtime_profile.py --stage <stage>`。

## 测试命令

建议执行：

```bash
python -m py_compile src/product_app/agent_runtime/__init__.py src/product_app/agent_runtime/contracts.py src/product_app/agent_runtime/resolver.py scripts/agent_runtime_profile.py tests/test_agent_runtime_resolver.py
python -m pytest tests/test_agent_runtime_resolver.py -q
python scripts/agent_runtime_profile.py --stage runtime_preflight --dry-run
python scripts/validate_pr_reports.py --base origin/main --head HEAD --strict --json
git diff --check
```

## 测试结果

预期结果：

```text
py_compile: passed
pytest focused: passed
agent_runtime_profile.py CLI: outputs secret-safe JSON
validate_pr_reports.py --strict: passed
git diff --check: passed
```

PR 打开后以 GitHub 轻量验证结果为最终 CI 凭据。

## 安全确认

1. resolver 不执行命令。
2. CLI 不执行命令，只输出 JSON profile。
3. 不输出 command 原文或 secret 值。
4. 不修改 workflow。
5. 不新增 HTTP API。
6. 不修改行情、策略、风控、执行、账户、券商接入等运行时业务模块。

## 剩余风险

1. R0.3 目前尚未把 runtime profile 写入 `.agent/tmp`。
2. AgentOps UI 尚未展示 runtime profile。
3. 后续可在 R0.5 或 AgentOps follow-up 中把 CLI 接入 workflow diagnostics。

## 最终结论

PASS_WITH_NOTES
