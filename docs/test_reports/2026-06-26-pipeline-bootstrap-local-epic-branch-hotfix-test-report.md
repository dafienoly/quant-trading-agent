# Pipeline Bootstrap 本地 Epic 分支残留 Hotfix 测试报告

## 变更范围

验证 bootstrap 对 self-hosted runner 残留同名本地 epic 分支的幂等性修复。

## 关联文档

- Requirement: `docs/requirements/2026-06-26-pipeline-bootstrap-local-epic-branch-hotfix-requirements.md`
- Architecture: `docs/design/2026-06-26-pipeline-bootstrap-local-epic-branch-hotfix-architecture.md`
- Development report: `docs/dev_reports/2026-06-26-pipeline-bootstrap-local-epic-branch-hotfix-dev-report.md`

## 测试命令

```bash
./.venv/bin/python -m pytest tests/test_agent_pipeline_automation.py -q --tb=short --basetemp=runtime/pytest-tmp-bootstrap-local-branch-hotfix

TMPDIR=/tmp/codex-pytest ./.venv/bin/python scripts/agent_pipeline_regression.py --strict

./.venv/bin/python -m ruff check tests/test_agent_pipeline_automation.py scripts/agent_pipeline_regression.py

./.venv/bin/python -m py_compile tests/test_agent_pipeline_automation.py scripts/agent_pipeline_regression.py

git diff --check
```

## 测试结果

- `pytest tests/test_agent_pipeline_automation.py`: `79 passed in 0.50s`
- `scripts/agent_pipeline_regression.py --strict`: `PASS`
- `ruff check`: `All checks passed!`
- `py_compile`: 通过
- `git diff --check`: 通过

## 覆盖说明

已设计覆盖：

1. workflow 包含本地分支残留检测。
2. workflow 包含 reset 提示文案。
3. workflow 使用 `git switch -C $branch`。
4. workflow 不再使用 `git switch -c $branch`。
5. regression 对应 marker 存在。

## 安全确认

1. 未修改业务模块。
2. 未触碰交易敏感路径。
3. main 手动合并边界保持不变。

## 最终结论

PASS
