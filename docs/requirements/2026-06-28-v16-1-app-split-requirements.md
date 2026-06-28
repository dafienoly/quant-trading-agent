# V16.1 App Split 需求

## 背景

前端已经具备 AgentOps 基座、路由、context adapter 和 selector。由于直接在 `App.tsx` 中一次性挂载完整 context 数据流多次被平台安全检查拦截，本阶段先将主页面拆成更小的组件，并挂载一个只读 Adapter Status 占位卡，为后续真实数据绑定降低风险。

## 本阶段目标

1. 抽离现有 Ops Summary、Runtime Profile、Quality Summary 三张卡片。
2. 新增 Adapter Status 展示组件。
3. 在主页面挂载 Adapter Status 占位卡。
4. 保持现有 API 调用和页面加载流程不变。
5. 不新增后端接口。

## 非目标

1. 不在本阶段绑定 context API 实时数据。
2. 不修改后端 route。
3. 不新增写操作。
4. 不关闭 V16.1 总 Issue。

## 验收标准

1. `App.tsx` 变得更薄。
2. 三张现有卡片由组件承载。
3. Adapter Status 卡片出现在 ready 状态页面中。
4. PR 轻量验证通过。
