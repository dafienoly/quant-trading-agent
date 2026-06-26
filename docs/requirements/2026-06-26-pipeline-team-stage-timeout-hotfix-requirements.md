# Pipeline Team Stage Timeout Hotfix Requirements

## 用户目标

修复 Issue-driven Agent pipeline 在 Team stage 长时间无响应时无法 fail closed 的问题，避免 `claude_lead_plan`、`claude_developer`、`claude_tester` 等阶段无限挂起，阻塞 V16.3 和后续版本推进。

## 背景

当前 `scripts/run-pipeline-team-agent.sh` 对 runtime preflight 已配置超时，但对正式 `opencode run` 没有硬超时。

已观测到的真实问题：

- V16.3 issue `#91`
- Bootstrap run `28215996497`
- PM 与 Architect 已完成
- 卡在 `Run OpenCode GLM 5.2 team-plan or generate handoff-only dry run`

## 目标

1. 给正式 Team stage 执行增加硬超时。
2. 超时后必须返回清晰错误，workflow fail closed。
3. 允许通过环境变量按角色配置 timeout。
4. 保持现有 preflight、固定模型、superpowers 和 WSL bridge 行为不变。

## 非目标

1. 不修改业务功能。
2. 不调整 Team pipeline 角色模型分配。
3. 不改动交易、风控、券商或行情业务逻辑。
4. 不在本 hotfix 中直接完成 V16.3 功能开发。

## 功能要求

### F-001 正式 Team stage 硬超时

对以下正式 stage 增加 timeout：

- `claude_lead_plan`
- `claude_lead_review`
- `postmortem`
- `claude_developer`
- `bugfix`
- `claude_tester`

### F-002 按角色可配置 timeout

至少支持以下环境变量：

- `AGENT_LEAD_STAGE_TIMEOUT_SECONDS`
- `AGENT_TESTER_STAGE_TIMEOUT_SECONDS`
- `AGENT_DEVELOPER_STAGE_TIMEOUT_SECONDS`

若未配置，应有仓库内默认值。

### F-003 超时错误可诊断

超时发生时，stderr 必须明确包含：

- 当前 `stage`
- timeout 秒数
- fail closed 退出

### F-004 回归守护

现有 automation tests 和 pipeline regression 必须覆盖：

- 正式 Team runner 包含新的 timeout 配置
- regression 检查要求新的 marker

## 验收标准

1. `scripts/run-pipeline-team-agent.sh` 正式 stage 执行包含 timeout。
2. 新的 timeout 环境变量存在且会校验正整数。
3. automation tests 通过。
4. `scripts/agent_pipeline_regression.py --strict` 通过。
5. 不影响现有 preflight timeout 行为。
6. 不触碰交易敏感模块。

## 安全约束

1. 不自动合并 `main`。
2. 不允许为“避免挂起”而跳过 gate 或将失败伪装为成功。
3. 不提交 `.agent/tmp/**`、`.agent/reports/**`、`runtime/**`、`feedback/index.json`。

