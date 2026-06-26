# Pipeline Team Stage Timeout Hotfix 开发报告

## 变更范围

本次修复为 pipeline infrastructure hotfix，用于解决 Team stage 正式执行缺少 timeout 导致 workflow 可能无限挂起的问题。

涉及文件：

- `scripts/run-pipeline-team-agent.sh`
- `tests/test_agent_pipeline_automation.py`
- `scripts/agent_pipeline_regression.py`
- `docs/requirements/2026-06-26-pipeline-team-stage-timeout-hotfix-requirements.md`
- `docs/design/2026-06-26-pipeline-team-stage-timeout-hotfix-architecture.md`
- `docs/test_reports/2026-06-26-pipeline-team-stage-timeout-hotfix-test-report.md`
- `docs/acceptance/2026-06-26-pipeline-team-stage-timeout-hotfix-acceptance.md`

## 对应文档

- Requirement: `docs/requirements/2026-06-26-pipeline-team-stage-timeout-hotfix-requirements.md`
- Architecture: `docs/design/2026-06-26-pipeline-team-stage-timeout-hotfix-architecture.md`

## 实现说明

1. 为正式 Team stage 新增：
   - `AGENT_LEAD_STAGE_TIMEOUT_SECONDS`
   - `AGENT_TESTER_STAGE_TIMEOUT_SECONDS`
   - `AGENT_DEVELOPER_STAGE_TIMEOUT_SECONDS`
2. 抽出 `require_positive_integer()` 统一校验 timeout 配置。
3. 抽出 `run_stage_with_timeout()`，统一包装正式 `opencode run`。
4. 超时时输出 `OpenCode stage '<stage>' timed out after <n>s.`。
5. automation test 与 regression marker 同步更新。

## 测试命令

```bash
bash -n scripts/run-pipeline-team-agent.sh

./.venv/bin/python -m pytest tests/test_agent_pipeline_automation.py -q --tb=short --basetemp=runtime/pytest-tmp-pipeline-timeout-hotfix

TMPDIR=/tmp/codex-pytest ./.venv/bin/python scripts/agent_pipeline_regression.py --strict
```

## 测试结果

- `bash -n`: 通过
- `tests/test_agent_pipeline_automation.py`: `78 passed`
- `scripts/agent_pipeline_regression.py --strict`: `PASS`

## 安全确认

1. 未触碰交易敏感模块。
2. 未改变真实交易、风控或行情业务逻辑。
3. 未绕过 gate，超时仍 fail closed。
4. 未提交 `.agent/tmp/**`、`.agent/reports/**`、`runtime/**`、`feedback/index.json`。

## 剩余风险

1. 当前卡住的 `#91` bootstrap run 仍使用旧版 runner，无法被本次未合并 hotfix 立即修复。
2. hotfix 合并后，需要取消并重触发 `#91` pipeline，才能真正验证修复效果。

## 最终结论

PASS

