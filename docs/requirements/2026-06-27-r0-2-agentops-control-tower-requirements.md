# R0.2 AgentOps Control Tower completion 需求

## 背景

R0.1 已完成 Roadmap canonical 入口收敛。根据新的 R0 平台优先规则，下一步需要继续补强 AgentOps Control Tower，让用户和 Agent 能从只读接口判断一次 pipeline instance 的状态、缺口和下一步动作。

当前已有 `/product/agentops/pipelines/{feature_id}` 与 `/product/agentops/pipelines/by-issue/{issue_number}`，但返回结构仍偏基础：缺少 pipeline instance summary、readiness、next action 和 health 入口。

## 目标

1. 扩展 AgentOps pipeline observation contract 到 v2。
2. 新增 pipeline instance summary，包括 feature、issue、stage counts、required docs 统计和 handoff 统计。
3. 新增 readiness 信息，说明 ready / blocked / incomplete / unknown、blockers、warnings、missing docs、failed stages 和 next action。
4. 新增只读 `/product/agentops/health`。
5. 增加 route 与 aggregator 测试。

## 非目标

1. 不调用外部 Agent。
2. 不改变 GitHub Actions workflow 编排。
3. 不新增写接口。
4. 不改行情、策略、执行、风控、账户、券商接入等运行时业务模块。
5. 不改变主干合并策略。

## API 契约

新增：

```text
GET /product/agentops/health
```

保持：

```text
GET /product/agentops/pipelines/{feature_id}
GET /product/agentops/pipelines/by-issue/{issue_number}
```

pipeline observation contract 从 `agentops.pipeline_observation.v1` 升级为：

```text
agentops.pipeline_observation.v2
```

## 后端模块

```text
src/product_app/agentops/pipeline_contracts.py
src/product_app/agentops/pipeline_aggregator.py
src/api/agentops_routes.py
```

## 前端要求

本次不修改 Streamlit。后续可由 Streamlit AgentOps 面板消费新增字段。

## 测试要求

至少覆盖：

1. `/product/agentops/health` 返回只读健康信息。
2. pipeline observation 包含 `pipeline_instance` 和 `readiness`。
3. docs complete 时 readiness 为 ready。
4. docs missing 时 readiness 为 blocked。
5. failed stage 被识别为 blocker。
6. AgentOps router 仍只有 GET 方法。

## 验收标准

1. 轻量验证 CI 通过。
2. 新增 contract 字段向后兼容，不删除旧字段。
3. 只读边界保持。
4. 中文 dev/test/acceptance 文档齐备。
5. 不触碰 restricted runtime modules。

## 安全边界

R0.2 是只读观测增强任务，不得引入任何运行时执行能力、账户写入、外部下单或权限升级。