# Pipeline OpenCode Runtime Docs Feature Folders 验收

## 变更范围

本次验收覆盖当前分支 `feat/pipeline-opencode-runtime-docs-feature-folders` 的 pipeline 文档目录迁移、OpenCode runtime 文案更新、stage/report gate 兼容逻辑和相关测试。

## 用户需求满足情况

| 验收项 | 结论 |
|---|---|
| 新功能默认写入 `docs/features/<feature-id>/` | 满足 |
| 旧路径仍可兼容读取 | 满足 |
| OpenCode Lead / Developer / Tester runtime 文档一致 | 满足 |
| 相关自动化测试通过 | 满足 |
| 不影响真实交易安全边界 | 满足 |

## 测试命令

- `./.venv/bin/python -m ruff check scripts/agent_pipeline_acceptance_entry.py scripts/agent_pipeline_regression.py scripts/agent_pipeline_report_viewer.py scripts/agent_runtime_profile.py scripts/validate_pr_reports.py src/product_app/agent_pipeline_automation.py src/product_app/agent_runtime/resolver.py tests/test_agent_pipeline_acceptance_entry.py tests/test_agent_pipeline_automation.py tests/test_agent_pipeline_report_viewer.py tests/test_validate_pr_reports.py`
- `./.venv/bin/python -m py_compile scripts/agent_pipeline_acceptance_entry.py scripts/agent_pipeline_regression.py scripts/agent_pipeline_report_viewer.py scripts/agent_runtime_profile.py scripts/validate_pr_reports.py src/product_app/agent_pipeline_automation.py src/product_app/agent_runtime/resolver.py`
- `./.venv/bin/python -m pytest tests/test_agent_pipeline_acceptance_entry.py tests/test_agent_pipeline_automation.py tests/test_agent_pipeline_report_viewer.py tests/test_validate_pr_reports.py -q --basetemp=runtime/pytest-tmp-pipeline-docs-feature-folders`
- `git diff --check`
- `bash -n scripts/run-pipeline-team-agent.sh`
- 当前 diff secret scan

## 测试结果

- Ruff: PASS
- Py compile: PASS
- Related pytest: PASS, 129 passed
- `git diff --check`: PASS
- `bash -n scripts/run-pipeline-team-agent.sh`: PASS
- Current diff secret scan: PASS

## 安全确认

本次变更未新增真实 order path，未暴露 `LEVEL_3_AUTO` 作为普通用户可选项，未绕过 risk、execution、stock-pool、provider contract、Tool Registry、human confirmation 或 fail-closed 行为。

## Manual merge 说明

本次改动包含 GitHub Actions workflows、scripts 和 automation code，按 `docs/pipeline/AUTO_MERGE_POLICY.md` 属于必须人工批准的类别。用户已明确要求“将当前分支修改创建 PR，并合并到 main”，可视为本次 main merge 的人工授权。

## Notes

远端 GitHub Actions 的完整端到端结果仍以 PR CI 为准；本地已完成 touched-scope 验证。

## 最终结论

ACCEPTED_WITH_NOTES
