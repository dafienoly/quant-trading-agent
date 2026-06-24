# Pipeline 交付证据与失败路由 Hotfix 功能说明

## 变更范围

- Developer runtime 改为 OpenCode DeepSeek V4 Flash `max`、build Agent 和 superpowers。
- 新增 Developer 真实 diff、测试文件及报告声称路径验证。
- 新增 Test/Review/Acceptance 最终结论解析和 fail-closed 路由。
- 修复陈旧 feature gate 污染和单 phase 通过即误判全部完成的问题。
- Stage Runner 现在提交 `feedback/`，失败证据落库后再退回责任阶段。
- 更新 Issue 模板、runtime preflight、状态机、handoff 和 Team Pipeline 文档。

## 测试命令

```bash
../../../.venv/bin/python -m pytest tests/test_agent_pipeline_automation.py tests/test_agent_pipeline_regression.py -q --basetemp=runtime/pytest-tmp-pipeline-gates
../../../.venv/bin/python scripts/agent_pipeline_regression.py --strict
../../../.venv/bin/python -m ruff check src/product_app/agent_pipeline_automation.py scripts/agent_pipeline.py scripts/agent_pipeline_regression.py tests/test_agent_pipeline_automation.py tests/test_agent_pipeline_regression.py
../../../.venv/bin/python -m py_compile src/product_app/agent_pipeline_automation.py scripts/agent_pipeline.py scripts/agent_pipeline_regression.py
bash -n scripts/run-pipeline-team-agent.sh
bash scripts/run-pipeline-team-agent.sh claude_developer --preflight-only
../../../.venv/bin/python -m pytest tests -q --tb=short --basetemp=runtime/pytest-tmp-pipeline-gates-full
git diff --check
```

## 测试结果

- Pipeline 聚焦测试：`89 passed`。
- strict regression：`PASS`，`8/8 gates`。
- Ruff、`py_compile`、Bash syntax、workflow YAML、`git diff --check`：通过。
- 全量测试：`998 passed, 6 skipped, 2 warnings`。
- OpenCode Developer runtime preflight：通过，实际模型
  `opencode-go/deepseek-v4-flash`，`variant=max`，返回 `PIPELINE_RUNTIME_OK`，
  stderr 为空，工作区状态未改变。
- 6 个 skip 为既有可选 E2E/浏览器条件；2 个 warning 为第三方弃用提示。

## 安全确认

- 未修改任何 restricted trading module。
- 未启用真实交易、自动下单或 LLM 直接交易决策。
- 未绕过 Risk Agent、股票池过滤、人工确认或 fail-closed。
- 未自动合并 `main`。
- 未提交 `.agent/tmp/**`、`.agent/reports/**`、密钥或账户凭据。

## 最终结论

PASS。实现、聚焦回归、strict regression、全量测试和真实 runtime preflight 均通过。
PR 合并前仍需取得 GitHub Actions 自托管 runner 的远端验证证据。
