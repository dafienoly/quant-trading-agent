# V16.1 Remote Context 设计

## 设计目标

建立远程上下文的只读数据契约，为后续 AgentOps Control Tower 聚合远程运行元数据打基础。

## 模块结构

```text
src/product_app/agentops/remote_context.py
src/api/agentops_routes.py
```

## 数据策略

1. 默认不读取运行环境。
2. 默认不发起网络请求。
3. 只接受调用方传入的公开 metadata。
4. 只保留白名单字段。
5. commit 字段只保留短值。

## API

```text
GET /product/agentops/remote
```

该接口返回只读 snapshot。当前默认为空状态，后续可由受控调用方注入公开元数据。

## 安全边界

本阶段不处理凭据，不访问远程 API，不写入任何数据，不改变现有流水线。