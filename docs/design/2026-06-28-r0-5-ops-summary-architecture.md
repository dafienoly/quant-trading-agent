# R0.5 Ops Summary 架构

## 架构目标

建立统一只读摘要层，聚合 R0.3 运行画像、R0.4 质量摘要和 roadmap docs 状态，为后续 AgentOps 展示和 CI 报告提供基础。

## 模块结构

```text
src/product_app/ops_summary/
├── __init__.py
├── models.py
└── builder.py

scripts/ops_summary.py
tests/test_ops_summary.py
```

## Contract

```text
ops_summary.v1
```

## Section 设计

每个 section 使用统一结构：

```text
name
available
status
note
```

当前 sections：

```text
runtime_profiles
quality_summary
roadmap_docs
```

## 聚合逻辑

1. runtime profiles 来自 agent runtime resolver。
2. quality summary 来自 quality index builder。
3. roadmap docs 检查 canonical roadmap 文件是否存在。

## 安全设计

1. builder 只读。
2. CLI 默认只输出 JSON。
3. 不执行阶段运行器。
4. 不改 workflow。
5. 不输出运行配置原文。

## 后续扩展

后续可以把 `scripts/ops_summary.py` 接入 CI artifact，也可以在 AgentOps UI 增加 summary 页面。

## 安全确认

本架构不运行外部工具、不调用 Agent、不新增 HTTP API、不触碰业务执行模块。