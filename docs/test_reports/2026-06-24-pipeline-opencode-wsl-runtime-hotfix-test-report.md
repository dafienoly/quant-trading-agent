# Pipeline OpenCode WSL Runtime Hotfix 测试报告

需求文档：
`docs/requirements/2026-06-24-pipeline-opencode-wsl-runtime-hotfix-requirements.md`

架构文档：
`docs/design/2026-06-24-pipeline-opencode-wsl-runtime-hotfix-architecture.md`

开发报告：
`docs/dev_reports/2026-06-24-pipeline-opencode-wsl-runtime-hotfix-dev-report.md`

## 测试环境

- 分支：`fix/pipeline/opencode-wsl-runtime`
- 基线：`origin/main` 的 PR #73 合并提交
- Linux/WSL
- OpenCode `1.17.9`
- Claude Code `2.1.177`
- Python 使用项目既有 `.venv`

## 测试范围

- Windows PowerShell 到 WSL 的启动命令契约。
- OpenCode CLI PATH、模型、variant、superpowers 和 build agent。
- Claude 模型、effort、feature-dev 和 superpowers。
- Runtime Preflight 的只读行为、输出标记和诊断 artifact。
- Issue 模板角色、默认标签和 main 人工合并文案。
- Pipeline strict regression 与全量回归。

Windows self-hosted runner 动态验证将在 Draft PR 创建后运行，因此当前报告为
本地开发阶段验证记录。

## 需求覆盖矩阵

| 需求 | 测试证据 | 结果 |
|---|---|---|
| R-001 登录 shell 与 PATH | PowerShell 静态契约测试、strict regression | PASS |
| R-002 移除危险权限 | runner 负向断言 | PASS |
| R-003 Runtime Preflight | 三个本地真实模型探针、Stage Runner 隔离入口 | PASS |
| R-004 Issue 模板 | 模板角色和 manual merge 测试 | PASS |
| R-005 回归门禁 | 81 个聚焦测试、strict、全量测试 | PASS |

## 测试命令

```bash
../../../.venv/bin/python -m pytest \
  tests/test_agent_pipeline_automation.py \
  tests/test_agent_pipeline_regression.py \
  -q --basetemp=runtime/pytest-tmp-pipeline-runtime-hotfix-focused

../../../.venv/bin/python scripts/agent_pipeline_regression.py --strict

../../../.venv/bin/python -m pytest tests -q --tb=short \
  --basetemp=runtime/pytest-tmp-pipeline-runtime-hotfix-full

bash scripts/run-pipeline-team-agent.sh claude_lead_plan --preflight-only
bash scripts/run-pipeline-team-agent.sh claude_tester --preflight-only
bash scripts/run-pipeline-team-agent.sh claude_developer --preflight-only
```

## 测试结果

- 聚焦测试：`82 passed in 3.27s`。
- Strict regression：`PASS`。
- 全量测试：`991 passed, 6 skipped, 2 warnings in 60.37s`。
- 三个真实本地 Runtime 探针均返回 `PIPELINE_RUNTIME_OK`。
- 探针未修改 git 状态。
- 未出现新增 skip、xfail 或业务失败。
- 2 个 warning 为既有第三方依赖弃用提示。
- Actions run `28082310344` 虽显示 success，但日志没有 Bash 完成输出且
  artifact 为空，判定为无效证据；已复现并修复 PowerShell→WSL 参数吞失。
- Actions run `28082773049` 正确执行并在 180 秒超时，证明 fail-closed
  生效；进一步诊断确认 OpenCode 默认 renderer 是挂起点，GLM 5.2 和
  DeepSeek V4 Pro 使用 `--format json` 均在约 5 秒返回预期标记。

## 缺陷列表

已关闭：

| 严重度 | 缺陷 | 修复 |
|---|---|---|
| S1 | Windows runner 的非登录 WSL shell 找不到 OpenCode | `bash -l` + Bash runner 显式 PATH |
| S1 | `bash -lc` 复合参数被 `wsl.exe` 吞失却返回 0 | `--cd` + `bash -l` 独立参数，metadata 后置校验 |
| S1 | hidden artifact 缺失但 step 仅 warning | 启用 hidden files 并设为 missing=error |
| S2 | Runtime discovery 或模型请求可能挂起 | 增加可配置硬超时 |
| S1 | OpenCode 默认 renderer 在重定向 stdout 时不退出 | 固定 JSON event stream |
| S1 | Tester/Lead 使用危险权限跳过 | 删除危险参数，使用配置权限 |
| S2 | 合并前无法独立验证三个 Runtime | 新增 workflow 和 Stage Runner 隔离兼容入口 |
| S3 | Issue 模板仍描述旧角色和自动合并 | 更新为当前角色与人工合并 |

未关闭：

- Windows self-hosted Runtime Preflight 待 PR 分支运行，不在本地伪造通过。

## 安全确认

- Restricted module check 无命中。
- 无真实交易能力变更。
- 无 LLM 直接下单能力。
- 无危险权限跳过。
- Preflight 不提交、不推送、不合并、不推进 stage。
- `.agent/tmp/**`、`.agent/reports/**` 无 tracked file。

## 剩余风险

- Windows runner 的 WSL distribution、用户 HOME 和模型认证只可由 Actions
  动态验证。

## 最终结论

`PASS_WITH_NOTES`。本地验证通过；Windows self-hosted Runtime Preflight
成功后可升级为 `PASS`。
