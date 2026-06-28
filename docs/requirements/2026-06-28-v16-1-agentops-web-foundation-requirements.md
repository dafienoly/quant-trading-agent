# V16.1 AgentOps Web Foundation 需求

## 背景

V16.1 总目标是建设 AgentOps Control Tower。后端已具备 `/product/agentops/summary`、`/product/agentops/runtime/{stage}` 和 `/product/agentops/quality` 只读接口。本阶段新增 Frontend v2 的最小 React/Vite/TypeScript 基座。

## 本阶段目标

1. 新增 `apps/web` 前端工程。
2. 新增 React + Vite + TypeScript 基础配置。
3. 新增 AgentOps 只读 API client。
4. 新增 AgentOps 页面骨架。
5. 新增最小 API contract smoke test。
6. 保持现有 Streamlit dashboard 有效，不标记为废弃。

## 非目标

1. 不迁移行情、自选股、信号和交易相关页面。
2. 不触发 workflow。
3. 不新增写操作。
4. 不新增券商、账户、订单或交易能力。
5. 不关闭 V16.1 总 Issue #75。

## 页面入口

```text
apps/web
```

Vite dev server 下默认显示 AgentOps 页面骨架。后续可以映射到 `/agent-pipeline`。

## 验收标准

1. 前端工程文件齐备。
2. API client 指向 `/product/agentops/**` 只读接口。
3. 页面展示 summary、runtime、quality 三个卡片区域。
4. 包含 loading、ready、error 状态。
5. 中文 reports 齐备。
6. CI 通过。

## 安全边界

本阶段仅新增只读前端基座，不改变后端写路径、不改 workflow、不触碰业务执行模块。