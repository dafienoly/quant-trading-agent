# Pipeline Team Stage Timeout Hotfix 测试报告

## 变更范围

验证 Team pipeline 正式阶段新增硬超时后，automation contract 与 regression 仍保持通过。

## 关联文档

- Requirement: `docs/requirements/2026-06-26-pipeline-team-stage-timeout-hotfix-requirements.md`
- Architecture: `docs/design/2026-06-26-pipeline-team-stage-timeout-hotfix-architecture.md`
- Development report: `docs/dev_reports/2026-06-26-pipeline-team-stage-timeout-hotfix-dev-report.md`

## 测试命令

```bash
bash -n scripts/run-pipeline-team-agent.sh

./.venv/bin/python -m pytest tests/test_agent_pipeline_automation.py -q --tb=short --basetemp=runtime/pytest-tmp-pipeline-timeout-hotfix

TMPDIR=/tmp/codex-pytest ./.venv/bin/python scripts/agent_pipeline_regression.py --strict
```

## 测试结果

- `bash -n`: 通过
- `pytest tests/test_agent_pipeline_automation.py`: `78 passed`
- `scripts/agent_pipeline_regression.py --strict`: `PASS`

## 覆盖说明

已覆盖：

- 正式 Team runner 包含新的 timeout 环境变量
- 正式 Team runner 包含统一 timeout 包装器
- regression 要求新的 marker
- 现有 fixed runtime / WSL bridge / preflight contract 未退化

未覆盖：

- GitHub hosted 的真实卡住 run 自动超时终止，需要在合并后通过实际 workflow 复验

## 安全确认

1. 未修改业务模块。
2. 未触碰交易敏感路径。
3. 超时失败保持 fail closed。

## 最终结论

PASS

