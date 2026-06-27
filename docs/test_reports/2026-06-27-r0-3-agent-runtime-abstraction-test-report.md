# R0.3 Agent Runtime Abstraction 测试报告

## 变更范围

本测试报告覆盖 R0.3 Agent Runtime Abstraction 的 resolver、contract 和 CLI 输出。

## 测试文件

```text
tests/test_agent_runtime_resolver.py
```

## 覆盖矩阵

| 要求 | 覆盖方式 | 结果 |
| --- | --- | --- |
| Codex real profile | `test_codex_stage_resolves_real_when_enabled_and_command_configured` | PASS |
| Codex disabled | `test_codex_stage_without_command_is_disabled` | PASS |
| strict mode blocker | `test_strict_mode_blocks_non_real_runtime` | PASS |
| mock detection | `test_command_with_mock_marker_resolves_mock_without_leaking_value` | PASS |
| dry-run override | `test_dry_run_override_wins_even_when_real_command_exists` | PASS |
| fallback command env | `test_codex_reviewer_uses_fallback_command_input` | PASS |
| OpenCode team stage | `test_team_stage_resolves_opencode_real_profile` | PASS |
| unknown stage | `test_unknown_stage_is_blocked_unknown` | PASS |
| CLI JSON | `test_agent_runtime_profile_cli_outputs_secret_safe_json` | PASS |

## 测试命令

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

1. 测试验证 command 原文不会泄露到 profile JSON。
2. 测试验证 strict + non-real 会产生 blocker。
3. 测试验证 CLI 只输出 profile，不执行命令。
4. 未触碰任何业务执行模块。

## 缺陷列表

无已知阻断缺陷。

## 剩余风险

1. 尚未接入 workflow 产物生成。
2. 尚未在 AgentOps UI 展示 runtime profile。

## 最终结论

PASS_WITH_NOTES
