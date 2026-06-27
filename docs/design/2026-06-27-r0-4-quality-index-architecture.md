# R0.4 Quality Feedback Index 架构

## 架构目标

建立只读质量反馈索引，把项目中的质量反馈文件聚合成统一 summary JSON，为 AgentOps、CI diagnostics 和后续报告展示提供数据基础。

## 模块结构

```text
src/product_app/quality_index/
├── __init__.py
├── constants.py
├── models.py
└── indexer.py

scripts/quality_index_summary.py
tests/test_quality_index.py
```

## Contract

```text
quality_index.summary.v1
```

核心字段：

```text
readonly
scanned_roots
total_count
open_count
resolved_count
invalid_count
priority_counts
state_counts
items
warnings
```

## Item 字段

```text
item_id
state
priority
source_stage
route_back_to
related_paths
item_path
title
safe_summary
created_at
resolved_at
parse_notes
```

## 扫描规则

扫描根目录固定在项目质量反馈区域，支持：

```text
.json
.yaml
.yml
.md
```

不支持文件会被跳过，并写入 warning。

## 安全设计

1. indexer 只读。
2. CLI 只输出 JSON，不修改文件。
3. 扫描根目录固定，且必须保持在 repo root 内。
4. Markdown 只抽取标题、简单 key-value 和短摘要。
5. 文本摘要有长度上限，避免把长日志原文塞进 summary。

## 后续扩展

后续可在 AgentOps 中增加质量反馈展示，也可以在 workflow diagnostics 中生成报告。

## 安全确认

本架构不运行外部工具、不调用 Agent、不改 workflow、不写业务数据、不触碰业务执行模块。