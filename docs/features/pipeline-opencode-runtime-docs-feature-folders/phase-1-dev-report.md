# Phase 1 开发报告

## 需求文档

`docs/features/pipeline-opencode-runtime-docs-feature-folders/requirements.md`

## 架构文档

`docs/features/pipeline-opencode-runtime-docs-feature-folders/architecture.md`

## Roadmap 参考

`docs/roadmap/MASTER_ROADMAP.md` V16 平台基础层：AgentOps governance、Issue Pipeline、Provider Contract 前置治理。

## 变更范围

- `.github/workflows/agent-issue-bootstrap.yml`
- `.github/workflows/agent-runtime-preflight.yml`
- `.github/workflows/agent-stage-runner.yml`
- `AGENTS.md`
- `docs/pipeline/AGENT_AUTOMATION_ARCHITECTURE.md`
- `docs/pipeline/AGENT_HANDOFF_CONTRACT.md`
- `docs/pipeline/GITHUB_LABEL_POLICY.md`
- `docs/pipeline/LOCAL_AGENT_RUNTIME_SETUP.md`
- `docs/pipeline/PIPELINE_STATE_MACHINE.md`
- `docs/pipeline/TEAM_PIPELINE_V2.md`
- `docs/process/AGENT_DEVELOPMENT_PIPELINE.md`
- `docs/process/BRANCH_WORKFLOW.md`
- `docs/process/NEW_DEVELOPER_AGENT_ONBOARDING.md`
- `docs/process/NEW_TEST_ENGINEER_AGENT_ONBOARDING.md`
- `docs/process/TEST_ENGINEER_WORKFLOW.md`
- `scripts/agent_pipeline_acceptance_entry.py`
- `scripts/agent_pipeline_regression.py`
- `scripts/agent_pipeline_report_viewer.py`
- `scripts/agent_runtime_profile.py`
- `scripts/run-pipeline-team-agent.sh`
- `scripts/validate_pr_reports.py`
- `src/product_app/agent_pipeline_automation.py`
- `src/product_app/agent_runtime/resolver.py`
- `tests/test_agent_pipeline_acceptance_entry.py`
- `tests/test_agent_pipeline_automation.py`
- `tests/test_agent_pipeline_report_viewer.py`
- `tests/test_validate_pr_reports.py`

## 功能到代码映射

| 需求 | 实现 |
|---|---|
| R-001 | `build_feature_state` 默认写入 `docs/features/<feature-id>/...` |
| R-002 / R-003 | `REPORT_GLOBS_BY_STAGE`、`_glob_stage_reports` 同时支持 feature path 和 legacy path |
| R-004 | `_is_delivery_report_path`、`_is_feature_delivery_report` |
| R-005 | `render_handoff_prompt`、`scripts/run-pipeline-team-agent.sh`、workflow preflight 文案 |
| R-006 | 未触碰交易、风控、执行、provider、stock pool、signal/order 路径 |

## 新增或更新测试

- `tests/test_agent_pipeline_acceptance_entry.py`
- `tests/test_agent_pipeline_automation.py`
- `tests/test_agent_pipeline_report_viewer.py`
- `tests/test_validate_pr_reports.py`

## 自测命令和结果

| 命令 | 结果 |
|---|---|
| `./.venv/bin/python -m ruff check scripts/agent_pipeline_acceptance_entry.py scripts/agent_pipeline_regression.py scripts/agent_pipeline_report_viewer.py scripts/agent_runtime_profile.py scripts/validate_pr_reports.py src/product_app/agent_pipeline_automation.py src/product_app/agent_runtime/resolver.py tests/test_agent_pipeline_acceptance_entry.py tests/test_agent_pipeline_automation.py tests/test_agent_pipeline_report_viewer.py tests/test_validate_pr_reports.py` | PASS |
| `./.venv/bin/python -m py_compile scripts/agent_pipeline_acceptance_entry.py scripts/agent_pipeline_regression.py scripts/agent_pipeline_report_viewer.py scripts/agent_runtime_profile.py scripts/validate_pr_reports.py src/product_app/agent_pipeline_automation.py src/product_app/agent_runtime/resolver.py` | PASS |
| `./.venv/bin/python -m pytest tests/test_agent_pipeline_acceptance_entry.py tests/test_agent_pipeline_automation.py tests/test_agent_pipeline_report_viewer.py tests/test_validate_pr_reports.py -q --basetemp=runtime/pytest-tmp-pipeline-docs-feature-folders` | PASS, 129 passed |
| `git diff --check` | PASS |
| `bash -n scripts/run-pipeline-team-agent.sh` | PASS |
| `git diff | rg -n "(BEGIN|END).*PRIVATE KEY|ghp_[A-Za-z0-9_]+|github_pat_|AKIA[0-9A-Z]{16}|API_KEY=|API_SECRET=|BROKER_|ACCOUNT_|PASSWORD=|SECRET=|TOKEN=" || true` | PASS, no matches |
| `git diff --name-only | rg '(^|/)\\.env$|credentials|\\.pem$|\\.key$|cookie' || true` | PASS, no matches |

## 数据源和数据质量处理

不涉及 market data、fundamental data、provider fallback、cache freshness 或 trading signal 数据质量变更。

## API 合约影响

不新增 `/product/**` API，不改变已有 HTTP contract。

## UI 影响

不触碰 Streamlit 或 React UI entrypoint。

## Agent / LLM 边界影响

只调整 Agent pipeline 文档路径、handoff prompt 和 runtime 模型说明。LLM 仍只负责结构化阶段产物，不获得交易决策、下单、risk override 或 raw provider 越权能力。

## 未执行项

未运行全量 `pytest tests`。原因：本次变更集中于 pipeline automation、workflow、脚本和文档路径，已运行 touched-scope 测试与相关静态检查。

## 剩余风险

GitHub Actions workflow 的端到端执行仍需由远端 CI 在 PR 上验证。

## 真实交易影响

不影响真实交易能力。未绕过 risk、stock-pool filtering、human confirmation、provider contracts、Tool Registry 或 fail-closed 行为。
