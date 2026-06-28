# R0.5 Ops Summary 需求

## 背景

R0.2 已完成 AgentOps 只读观测，R0.3 已完成 runtime profile，R0.4 已完成 quality index。R0.5 需要把这些基础能力聚合成一个统一的只读摘要，供 CI、AgentOps 和人工验收查看。

## 目标

1. 新增 `src/product_app/ops_summary/`。
2. 聚合 runtime profile、quality summary 和 roadmap docs 状态。
3. 新增 CLI：`scripts/ops_summary.py`。
4. 新增测试覆盖 empty repo、quality counts、runtime profile 安全输出、roadmap docs、CLI JSON。
5. 增加 R0.5 中文 requirements / architecture / dev report / test report / review / acceptance。

## 非目标

1. 不改 workflow 编排。
2. 不运行外部工具。
3. 不新增 HTTP API。
4. 不新增写接口。
5. 不修改行情、策略、风控、执行、账户、券商接入等业务模块。

## 输出契约

```text
ops_summary.v1
```

核心字段：

```text
readonly
repo_root
sections
runtime_profiles
quality_summary
overall_status
warnings
```

## 验收标准

1. CLI 可输出 JSON。
2. runtime profile 不暴露命令原文。
3. quality summary 能被嵌入输出。
4. roadmap docs 状态可检查。
5. 测试与中文 reports 齐备。
6. CI 通过。

## 安全边界

R0.5 只做只读摘要聚合，不改变执行链路、不写业务数据、不调用外部 Agent。