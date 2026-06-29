# Phase 1 测试报告

## 文档路径

- Requirement: `docs/features/pipeline-opencode-runtime-docs-feature-folders/requirements.md`
- Architecture: `docs/features/pipeline-opencode-runtime-docs-feature-folders/architecture.md`
- Development report: `docs/features/pipeline-opencode-runtime-docs-feature-folders/phase-1-dev-report.md`

## 测试环境

- OS: WSL / Linux
- Python: `.venv/bin/python`
- 日期: 2026-06-29

## 测试范围

覆盖 pipeline feature-folder 文档路径、legacy fallback、acceptance entry、report validation、runner shell syntax、static checks、diff hygiene 和当前 diff secret scan。

## 不在范围

不测试真实交易、market provider、broker、risk engine、execution engine、UI 浏览器 smoke。

## Requirement Coverage Matrix

| Requirement | 测试证据 | 结果 |
|---|---|---|
| R-001 | `tests/test_agent_pipeline_automation.py::test_feature_state_contains_team_pipeline_defaults` | PASS |
| R-002 | report gate 相关测试保留 legacy fallback | PASS |
| R-003 | `test_required_report_gate_finds_feature_reports` | PASS |
| R-004 | `test_developer_delivery_accepts_explicit_docs_only_phase` | PASS |
| R-005 | runtime contract 测试和 shell syntax smoke | PASS |
| R-006 | 当前 diff secret scan、未触碰交易模块确认 | PASS |

## 命令和结果

| 命令 | 结果 |
|---|---|
| `./.venv/bin/python -m ruff check ...` | PASS |
| `./.venv/bin/python -m py_compile ...` | PASS |
| `./.venv/bin/python -m pytest tests/test_agent_pipeline_acceptance_entry.py tests/test_agent_pipeline_automation.py tests/test_agent_pipeline_report_viewer.py tests/test_validate_pr_reports.py -q --basetemp=runtime/pytest-tmp-pipeline-docs-feature-folders` | PASS, 129 passed |
| `git diff --check` | PASS |
| `bash -n scripts/run-pipeline-team-agent.sh` | PASS |
| 当前 diff secret scan | PASS, no matches |

## Data-quality 和 fail-closed 证据

本次不处理行情或基本面数据。Pipeline gate 对缺失报告继续 fail closed；旧路径兼容只扩展读取来源，不把缺失 artifact 标记为通过。

## 缺陷列表

未发现阻断缺陷。

## Feedback bug 文件

未生成 `feedback/bugs/open/BUG_*.md` 或 `.json`，原因是未发现可复现阻断缺陷。

## 剩余风险

远端 GitHub Actions 端到端运行结果需要 PR CI 进一步确认。

## 最终结果

PASS
