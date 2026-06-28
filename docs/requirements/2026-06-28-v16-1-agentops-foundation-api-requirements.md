# V16.1 AgentOps Foundation API 需求

## 背景

V16.1 总目标是建设 AgentOps Control Tower。当前 R0.3 已提供 runtime profile，R0.4 已提供 quality index，R0.5 已提供 ops summary。本阶段先把这些只读能力接入 `/product/agentops` API，为后续前端状态中心提供稳定后端入口。

## 本阶段目标

1. 新增 `/product/agentops/summary`。
2. 新增 `/product/agentops/runtime/{stage}`。
3. 新增 `/product/agentops/quality`。
4. 保持所有 AgentOps endpoint 为 GET-only。
5. 增强错误信息脱敏，覆盖 Windows 绝对路径。
6. 增加后端路由测试。

## 非目标

1. 不建设 React/Vite 前端。
2. 不接入 GitHub 远程聚合。
3. 不新增写接口。
4. 不触发、重跑、取消或合并任何流水线。
5. 不修改交易、行情、策略、风控、账户、券商接入等业务模块。

## API 契约

```text
GET /product/agentops/summary
GET /product/agentops/runtime/{stage}
GET /product/agentops/quality
```

三个接口均为只读 JSON 输出。

## 验收标准

1. 新接口返回 200 和稳定 JSON shape。
2. runtime profile 不暴露运行配置原文。
3. quality summary 可返回只读摘要。
4. 内部错误返回已脱敏错误结构。
5. AgentOps 路由仍然只有 GET/HEAD。
6. CI 通过。

## 安全边界

本阶段只是产品层只读 API foundation，不改变 workflow、不执行外部工具、不写仓库、不接触业务执行链路。