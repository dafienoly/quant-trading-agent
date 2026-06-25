# Pipeline 标签触发 PR 分支检出修复功能说明

## 变更范围

- `pull_request:labeled` 触发 Stage Runner 时，先通过 PR 编号解析 `headRefName`。
- Agent 执行前显式检出 PR head 分支，避免 GitHub merge ref 导致 detached HEAD。
- Developer handoff 要求开发报告最终结论必须显式为 `PASS` 或 `PASS_WITH_NOTES`。
- 新增静态回归测试，固定标签触发与手工调度使用同一检出契约。

## 测试命令

```bash
python -m pytest tests/test_agent_pipeline_automation.py tests/test_agent_pipeline_regression.py -q
python scripts/agent_pipeline_regression.py --strict
python -m ruff check tests/test_agent_pipeline_automation.py
git diff --check
```

## 测试结果

聚焦测试、严格 Pipeline 回归、Ruff 与 diff 检查均通过。

## 安全确认

- 不修改交易敏感模块。
- 不自动合并 main。
- 不提交 `.agent/tmp/**` 或 `.agent/reports/**`。
- checkout 无法确认 PR head 时保持 fail closed。

## 最终结论

PASS。标签触发的 Stage Runner 可在真实 PR 分支上提交并推送 Agent 产物。
