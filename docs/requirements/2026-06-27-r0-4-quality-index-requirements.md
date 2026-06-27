# R0.4 Quality Feedback Index 需求

## 背景

R0.1 已完成 Roadmap canonical 入口，R0.2 已完成 AgentOps 只读观测，R0.3 已完成 Agent Runtime profile。R0.4 继续补齐开发系统自身的质量反馈索引能力。

当前测试反馈文件可能分布在：

```text
feedback/bugs/open/**
feedback/bugs/resolved/**
```

需要一个只读 indexer，把这些文件聚合成可供 AgentOps、CI diagnostics 和后续报告查看的 summary JSON。

## 目标

1. 新增 `src/product_app/quality_index/`。
2. 定义 quality feedback summary contract。
3. 新增只读 indexer，扫描固定目录。
4. 新增 CLI：`scripts/quality_index_summary.py`。
5. 新增测试覆盖 empty、open、resolved、markdown、invalid、unsupported file、CLI JSON。
6. 新增 R0.4 中文 requirements / architecture / dev report / test report / review / acceptance。

## 非目标

1. 不运行外部工具。
2. 不改 workflow 编排。
3. 不新增写接口。
4. 不修改业务模块。
5. 不自动处理任何反馈项。

## 后端模块

```text
src/product_app/quality_index/__init__.py
src/product_app/quality_index/constants.py
src/product_app/quality_index/models.py
src/product_app/quality_index/indexer.py
scripts/quality_index_summary.py
```

## 数据范围

只读扫描：

```text
feedback/bugs/open
feedback/bugs/resolved
```

支持文件：

```text
.json
.yaml
.yml
.md
```

## 测试要求

```text
python -m pytest tests/test_quality_index.py -q
```

## 验收标准

1. summary JSON contract 为 `quality_index.summary.v1`。
2. summary 只包含安全摘要、路径、状态、优先级和统计信息。
3. unsupported file 被跳过并产生 warning。
4. CLI 可输出 JSON。
5. 中文 reports 齐备。
6. CI 通过。

## 安全边界

R0.4 是只读质量反馈索引，不执行外部命令、不改工作流、不写入仓库、不修改业务执行链路。