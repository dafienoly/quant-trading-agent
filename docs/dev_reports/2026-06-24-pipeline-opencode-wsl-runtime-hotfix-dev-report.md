# Pipeline OpenCode WSL Runtime Hotfix 功能说明

需求文档：
`docs/requirements/2026-06-24-pipeline-opencode-wsl-runtime-hotfix-requirements.md`

架构文档：
`docs/design/2026-06-24-pipeline-opencode-wsl-runtime-hotfix-architecture.md`

## 变更范围

1. `scripts/run-team-stage.ps1`
   - 增加 `-PreflightOnly`。
   - 将 WSL 启动改为 `--cd` 与 `bash -i` 独立参数调用，加载 runner 用户
     已配置的代理和 CLI 环境。
   - Preflight 返回后强制校验本角色 metadata，防止空执行返回 0。
2. `scripts/run-pipeline-team-agent.sh`
   - 增加 `--preflight-only`。
   - 移除 OpenCode 的无效 `--permission-mode allow`。
   - 移除 `--dangerously-skip-permissions`。
   - 增加 OpenCode `build` agent 配置预检。
   - 所有 OpenCode 非交互调用固定 `--format json`。
   - 增加 GLM 5.2、DeepSeek V4 Pro max、Claude ultracode-xhigh 真实只读探针。
   - 探针输出必须包含 `PIPELINE_RUNTIME_OK`，且运行前后 git 状态必须一致。
   - CLI discovery 与模型调用增加可配置硬超时。
3. 新增 `.github/workflows/agent-runtime-preflight.yml`
   - 支持 `all`、`lead`、`tester`、`developer`。
   - 使用 Windows self-hosted runner 真实验证三个角色。
   - 上传 `.agent/tmp/runtime-preflight-*` 诊断 artifact。
   - hidden artifact 显式启用，诊断文件缺失时 fail closed。
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
| R-001 WSL 运行环境 | `run-team-stage.ps1` 使用 `bash -i` 独立参数和 metadata 校验 |
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

- Pipeline 聚焦测试：`82 passed in 3.24s`。
- Pipeline strict regression：`PASS`，严重失败 `0`，警告 `0`。
- 全量测试：`991 passed, 6 skipped, 2 warnings in 60.37s`。
- Ruff：`All checks passed!`。
- `py_compile`、Bash syntax、workflow YAML、`git diff --check`：通过。
- 本地真实 GLM 5.2 Lead 探针：通过。
- 本地真实 DeepSeek V4 Pro max Tester 探针：通过。
- 本地真实 Claude ultracode-xhigh Developer 探针：通过。
- 2 个 warning 来自既有第三方依赖弃用提示。
- Windows self-hosted Runtime Preflight：
  [Actions run 28083597461](https://github.com/dafienoly/quant-trading-agent/actions/runs/28083597461)
  成功，三个角色全部通过，正式 `run-stage` job 跳过。
- Artifact `runtime-preflight-all-28083597461` 上传成功，共 9 个文件；
  Lead、Tester、Developer 各有 stdout、stderr 和 execution metadata。
- 三份 stdout 均包含 `PIPELINE_RUNTIME_OK`；metadata 分别确认：
  - Lead：`opencode-go/glm-5.2`，variant `max`，superpowers required；
  - Tester：`opencode-go/deepseek-v4-pro`，variant `max`，superpowers required；
  - Developer：`ultracode-xhigh`，effort `xhigh`，feature-dev 与 superpowers required。
- Actions run `28082310344` 发现旧复合命令未执行 runner 且 hidden artifact
  被忽略；该次绿色状态不作为通过证据，已增加后置证据校验和 artifact
  fail-closed。
- Actions run `28082773049` 真实执行后发现 OpenCode 默认 renderer 在 stdout
  重定向场景超时；同模型诊断使用 JSON event stream 均约 5 秒成功，已将
  preflight 和正式 Lead/Tester 调用固定为 `--format json`。
- Actions run `28083279232` 进一步确认 Windows service 启动的非交互 WSL
  没有加载 runner 用户代理环境；交互式 WSL 同模型正常。桥接已改为
  `bash -i`，不在仓库硬编码代理或凭据；同时避免 login logout 覆盖退出码。

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

- 模型服务后续发生认证、配额或模型下线时会 fail closed，需要运维处理。

## 最终结论

`PASS`。本地回归、真实本地探针和 Windows self-hosted 三角色动态预检均
通过。PR 仍保持 Draft，合并前需人工审阅。
