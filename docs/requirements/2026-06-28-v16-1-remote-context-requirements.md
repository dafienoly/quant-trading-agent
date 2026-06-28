# V16.1 Remote Context 需求

## 背景

V16.1 已完成 AgentOps 后端基础接口、前端基座和前端路由补强。下一步需要为远程上下文聚合建立一个安全的只读契约，后续才能逐步接入远程运行元数据。

## 本阶段目标

1. 新增只读 remote context contract。
2. 新增 `/product/agentops/remote` 只读接口。
3. 只接受公开 metadata 输入。
4. 默认状态为空，不主动读取运行环境。
5. 不发起网络请求。
6. 不暴露敏感字段。

## 非目标

1. 不接入真实远程 API。
2. 不修改 workflow。
3. 不新增写接口。
4. 不关闭 V16.1 总 Issue。

## 验收标准

1. contract version 稳定。
2. 默认返回 empty 状态。
3. 输入公开 metadata 后返回 ready 状态。
4. 非白名单字段不会进入 observed_context。
5. PR 轻量验证通过。
