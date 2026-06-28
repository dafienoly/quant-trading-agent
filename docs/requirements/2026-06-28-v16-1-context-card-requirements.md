# V16.1 Context Card 需求

## 背景

后端已经提供 AgentOps context 只读快照。前端需要先建立数据读取和展示适配层，为后续把卡片挂到主页面做准备。

## 本阶段目标

1. 新增 context API client。
2. 新增 context 展示选择器。
3. 新增 selector 单元测试。
4. 保持主页面不变，降低本次变更风险。

## 非目标

1. 不改后端接口。
2. 不新增写操作。
3. 不接入凭据或外部服务。
4. 不关闭 V16.1 总 Issue。

## 验收标准

1. context client 使用 GET 读取只读快照。
2. selector 对空值有安全 fallback。
3. selector 能映射第一条 source。
4. PR 轻量验证通过。
