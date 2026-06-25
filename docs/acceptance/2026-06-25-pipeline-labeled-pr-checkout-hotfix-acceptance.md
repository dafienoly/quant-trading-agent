# Pipeline 标签触发 PR 分支检出修复验收报告

## 变更范围

验收 `pull_request:labeled` 入口是否与 `workflow_dispatch` 一样显式检出 PR head，避免 Agent 提交后因 detached HEAD 无法推送。

## 测试命令

```bash
python -m pytest tests/test_agent_pipeline_automation.py tests/test_agent_pipeline_regression.py -q
python scripts/agent_pipeline_regression.py --strict
python -m ruff check tests/test_agent_pipeline_automation.py
git diff --check
```

## 测试结果

静态契约确认标签事件使用 PR 编号解析分支，并在 Agent 命令前执行 `git checkout "$branch"`；Developer handoff 同时要求显式输出 `PASS` 或 `PASS_WITH_NOTES`。相关回归全部通过。

## 安全确认

- 不涉及行情、策略、风控、账户或订单执行。
- PR 仍保持人工审阅与手动合并。
- 无运行期临时文件被跟踪。

## 最终结论

PASS。修复可阻止标签触发 Stage Runner 再次在 detached HEAD 上提交。
