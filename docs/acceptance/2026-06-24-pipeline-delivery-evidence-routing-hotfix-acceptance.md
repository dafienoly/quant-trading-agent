# Pipeline 交付证据与失败路由 Hotfix 验收报告

## 变更范围

验收范围包括 Developer OpenCode 路由、真实交付证据 gate、Tester/Reviewer 负面结论
路由、陈旧 gate 隔离、多阶段推进、feedback 提交和相关流程文档。

## 测试命令

```bash
../../../.venv/bin/python -m pytest tests/test_agent_pipeline_automation.py tests/test_agent_pipeline_regression.py -q --basetemp=runtime/pytest-tmp-pipeline-gates
../../../.venv/bin/python scripts/agent_pipeline_regression.py --strict
../../../.venv/bin/python -m pytest tests -q --tb=short --basetemp=runtime/pytest-tmp-pipeline-gates-full
bash scripts/run-pipeline-team-agent.sh claude_developer --preflight-only
git diff --check
```

## 测试结果

- 聚焦回归：`89 passed`。
- strict regression：`PASS`，`8/8 gates`。
- 全量测试：`998 passed, 6 skipped, 2 warnings`。
- Ruff、编译、Bash syntax、workflow YAML、diff check：通过。
- OpenCode Developer runtime preflight：实际使用
  `opencode-go/deepseek-v4-flash`、`variant=max`、superpowers，返回
  `PIPELINE_RUNTIME_OK`，stderr 为空。
- PR #77 已恢复为 Draft，并移除错误的 `stage:merge-ready`。

## 安全确认

- 变更仅限 Agent Pipeline、测试和流程文档。
- Restricted modules 无改动。
- `main` 仍禁止自动合并，必须人工审阅。
- 真实交易、Risk Agent、股票池和人工确认边界未改变。
- `.agent/tmp/**`、`.agent/reports/**` 不进入提交。

## 最终结论

PASS_WITH_NOTES。本地功能、回归和真实模型 preflight 均通过；Hotfix PR 仍应保持 Draft，
等待 GitHub Actions 自托管 runner 远端验证后再人工合并。
