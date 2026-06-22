# V15.4 PR 报告门禁功能说明

## 变更范围

新增 `scripts/validate_pr_reports.py` PR 报告门禁校验脚本，接入 PR validation workflow，确保每个非纯文档 PR 必须附带中文功能说明和验收报告。

### 新增文件

- `scripts/validate_pr_reports.py` — 独立 CLI 校验脚本
- `tests/test_validate_pr_reports.py` — 10 个测试用例
- `docs/requirements/2026-06-22-v15-4-pr-report-governance-requirements.md` — 需求文档
- `docs/design/2026-06-22-v15-4-pr-report-governance-architecture.md` — 架构文档
- `docs/dev_reports/2026-06-22-v15-4-pr-report-governance-dev-report.md` — 本报告
- `docs/test_reports/...` — 测试报告
- `docs/review/...` — 架构审查
- `docs/acceptance/...` — 验收报告

### 修改文件

- `.github/workflows/agent-pr-validation.yml` — 接入报告门禁步骤

## 测试命令

```
./.venv/bin/python -m pytest tests/test_validate_pr_reports.py -q
./.venv/bin/python scripts/agent_pipeline_regression.py --strict
./.venv/bin/python -m pytest tests/test_agent_pipeline_automation.py tests/test_agent_pipeline_regression.py -q
ruff check scripts/validate_pr_reports.py tests/test_validate_pr_reports.py
git diff --check
```

## 测试结果

- 10 个门禁测试全部通过
- Pipeline 回归 Status: PASS
- 自动化测试 85 全部通过
- ruff lint: 2 个 unused import 已修复
- `git diff --check`: PASS

## 安全确认

- 不修改交易敏感模块
- 不修改 Merge Gate
- 不修改 Claude/Codex 执行逻辑
- 不自动合并 main
- 不变更 V14.1 fail-closed 策略

## 最终结论

PR 报告门禁校验通过，可提交 PR 审阅。
