# Pipeline OpenCode WSL Runtime Hotfix 功能说明

需求文档：
`docs/requirements/2026-06-24-pipeline-opencode-wsl-runtime-hotfix-requirements.md`

架构文档：
`docs/design/2026-06-24-pipeline-opencode-wsl-runtime-hotfix-architecture.md`

## 变更范围

1. `scripts/run-team-stage.ps1`
   - 增加 `-PreflightOnly`。
   - 将 WSL 启动从非登录 `bash -c` 改为 `bash -lc`。
   - 显式加入 `$HOME/.opencode/bin` 和 `$HOME/.local/bin`。
2. `scripts/run-pipeline-team-agent.sh`
   - 增加 `--preflight-only`。
   - 移除 OpenCode 的无效 `--permission-mode allow`。
   - 移除 `--dangerously-skip-permissions`。
   - 增加 OpenCode `build` agent 配置预检。
   - 增加 GLM 5.2、DeepSeek V4 Pro max、Claude ultracode-xhigh 真实只读探针。
   - 探针输出必须包含 `PIPELINE_RUNTIME_OK`，且运行前后 git 状态必须一致。
3. 新增 `.github/workflows/agent-runtime-preflight.yml`
   - 支持 `all`、`lead`、`tester`、`developer`。
   - 使用 Windows self-hosted runner 真实验证三个角色。
   - 上传 `.agent/tmp/runtime-preflight-*` 诊断 artifact。
4. 更新 `.github/workflows/agent-stage-runner.yml`
   - 增加 `runtime_preflight` 兼容入口，用于新 workflow 合并前验证 PR 分支。
   - 使用独立 job，明确跳过 handoff、gate、commit、label 和 stage 推进。
5. 更新 `.github/ISSUE_TEMPLATE/agent_feature_request.yml`
   - 使用当前 OpenCode Lead、Claude Code Developer、OpenCode Test Engineer。
   - 明确 main 只允许人工审阅和手动合并。
6. 扩展 Pipeline 自动化测试和 strict regression。
7. 更新本地 Runtime 文档、Team Pipeline 文档、用户指南和开发日志。

本次未修改任何交易、行情、策略、风控、订单、账户、Broker 或真实执行模块。

## 功能映射

| 需求 | 实现 |
|---|---|
| R-001 WSL 登录环境 | `run-team-stage.ps1` 使用 `bash -lc` 和显式 PATH |
| R-002 安全 OpenCode 调用 | 移除无效和危险权限参数 |
| R-003 Runtime Preflight | runner preflight 模式、独立 workflow 和 Stage Runner 兼容入口 |
| R-004 Issue 模板 | 当前角色与 manual main merge 文案 |
| R-005 回归门禁 | automation tests 和 strict regression |

## 测试命令

```bash
../../../.venv/bin/python -m pytest \
  tests/test_agent_pipeline_automation.py \
  tests/test_agent_pipeline_regression.py \
  -q --basetemp=runtime/pytest-tmp-pipeline-runtime-hotfix-focused

../../../.venv/bin/python scripts/agent_pipeline_regression.py --strict

../../../.venv/bin/python -m pytest tests -q --tb=short \
  --basetemp=runtime/pytest-tmp-pipeline-runtime-hotfix-full

../../../.venv/bin/python -m ruff check \
  scripts/agent_pipeline_regression.py \
  tests/test_agent_pipeline_automation.py \
  tests/test_agent_pipeline_regression.py

../../../.venv/bin/python -m py_compile scripts/agent_pipeline_regression.py
bash -n scripts/run-pipeline-team-agent.sh
git diff --check
```

真实本地 Runtime 探针：

```bash
bash scripts/run-pipeline-team-agent.sh claude_lead_plan --preflight-only
bash scripts/run-pipeline-team-agent.sh claude_tester --preflight-only
bash scripts/run-pipeline-team-agent.sh claude_developer --preflight-only
```

## 测试结果

- Pipeline 聚焦测试：`82 passed in 3.06s`。
- Pipeline strict regression：`PASS`，严重失败 `0`，警告 `0`。
- 全量测试：`990 passed, 6 skipped, 2 warnings in 60.41s`。
- Ruff：`All checks passed!`。
- `py_compile`、Bash syntax、workflow YAML、`git diff --check`：通过。
- 本地真实 GLM 5.2 Lead 探针：通过。
- 本地真实 DeepSeek V4 Pro max Tester 探针：通过。
- 本地真实 Claude ultracode-xhigh Developer 探针：通过。
- 2 个 warning 来自既有第三方依赖弃用提示。
- Windows self-hosted Runtime Preflight：待 Draft PR 分支运行后补充。

## 安全确认

- 已删除 `--dangerously-skip-permissions`。
- Preflight 不读取 handoff/state，不推进 gate、label 或 PR。
- Claude preflight 禁用全部工具；OpenCode 使用只读 prompt 和 plan agent。
- 探针运行前后检查 git 状态，任何仓库修改都会 fail closed。
- 未启用真实交易、自动下单或 `LEVEL_3_AUTO`。
- 未绕过风控、股票池过滤、人工确认或 main 手动合并。
- 未提交凭据、Token、Cookie、账户或 Broker 信息。
- `.agent/tmp/**` 与 `.agent/reports/**` 不纳入提交。

## 剩余风险

- 当前只完成 Linux/WSL 本地真实探针。Windows self-hosted
  PowerShell→WSL 路径必须在 Draft PR 上取得成功 Actions 证据。
- 模型服务后续发生认证、配额或模型下线时会 fail closed，需要运维处理。

## 最终结论

`PASS_WITH_NOTES`。本地实现和验证通过；Windows self-hosted Runtime
Preflight 成功前不得合并。
