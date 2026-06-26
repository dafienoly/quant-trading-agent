# Pipeline Bootstrap 本地 Epic 分支残留 Hotfix 开发报告

## 变更范围

本次修复针对 Issue bootstrap 在 self-hosted runner 上重复触发同一 issue 时的幂等性问题。

涉及文件：

- `.github/workflows/agent-issue-bootstrap.yml`
- `tests/test_agent_pipeline_automation.py`
- `scripts/agent_pipeline_regression.py`
- `docs/requirements/2026-06-26-pipeline-bootstrap-local-epic-branch-hotfix-requirements.md`
- `docs/design/2026-06-26-pipeline-bootstrap-local-epic-branch-hotfix-architecture.md`
- `docs/test_reports/2026-06-26-pipeline-bootstrap-local-epic-branch-hotfix-test-report.md`
- `docs/acceptance/2026-06-26-pipeline-bootstrap-local-epic-branch-hotfix-acceptance.md`

## 对应文档

- Requirement: `docs/requirements/2026-06-26-pipeline-bootstrap-local-epic-branch-hotfix-requirements.md`
- Architecture: `docs/design/2026-06-26-pipeline-bootstrap-local-epic-branch-hotfix-architecture.md`

## 实现说明

1. 在 `Create or switch epic branch` 步骤中新增本地 branch 残留检测：
   - `git show-ref --verify --quiet "refs/heads/$branch"`
2. 当不存在可复用远端 open PR 时，将：
   - `git switch -c $branch`
   改为：
   - `git switch -C $branch`
3. 若检测到本地残留 branch，输出明确诊断：
   - `Local branch '$branch' already exists on self-hosted runner; resetting it to current HEAD.`
4. 自动化测试与 regression marker 同步更新。

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

## 安全确认

1. 未触碰交易敏感模块。
2. 未新增真实交易能力。
3. 未绕过 PR state 校验。
4. main 仍需手动合并。

## 剩余风险

1. 本修复完成后，仍需再次重触发 issue `#91` 才能验证 bootstrap 全链路恢复。

## 最终结论

PASS
