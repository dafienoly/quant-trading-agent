# V16.1 App Split 设计

## 设计目标

本阶段采用小步重构方式，把主页面中已有卡片拆成独立组件。这样后续继续挂载真实 adapter 数据时，只需要改动更小的区域，降低回归风险和平台拦截概率。

## 文件结构

```text
apps/web/src/App.tsx
apps/web/src/components/AgentOpsCards.tsx
apps/web/src/components/AdapterStatusCard.tsx
```

## 页面结构

`App.tsx` 继续负责加载状态、错误状态和 ready 状态切换。三张已有卡片由 `AgentOpsCards.tsx` 承载，新增的 Adapter Status 卡片由独立组件承载。

## 数据策略

Adapter Status 当前使用只读 placeholder display，不直接绑定 context API。真实数据绑定留到后续 PR，避免在一个 PR 中同时做组件拆分、网络调用扩展和 UI 行为改变。

## 安全边界

本阶段只改前端展示结构，不新增后端接口，不新增写操作，不读取凭据，不修改交易相关模块。