# R0.1 Roadmap Canonicalization 架构

## 架构目标

把 Roadmap 从“多个可读入口”收敛为“一个 canonical 入口 + 一个 compatibility 详细文件 + 一个目录说明”。

## 文件结构

```text
docs/roadmap/
├── MASTER_ROADMAP.md                    # canonical entrypoint
├── MASTER_ROADMAP_AGENT_EXECUTABLE.md   # compatibility detailed roadmap
└── README.md                            # roadmap priority and conflict rules
```

## 读取规则

Agent 读取顺序：

```text
1. docs/roadmap/MASTER_ROADMAP.md
2. docs/roadmap/MASTER_ROADMAP_AGENT_EXECUTABLE.md
3. docs/requirements/<current-feature>.md
4. docs/design/<current-feature>.md
5. historical or archived roadmap notes
```

## 设计决策

### 1. 不删除 compatibility 文件

`MASTER_ROADMAP_AGENT_EXECUTABLE.md` 已被历史 PR、handoff、开发报告和测试报告引用。R0.1 不直接删除它，避免破坏追溯链路。

### 2. canonical 文件成为第一入口

`MASTER_ROADMAP.md` 提供稳定、短路径、长期可引用的入口。后续 Agent 不应继续把 `MASTER_ROADMAP_AGENT_EXECUTABLE.md` 作为第一入口。

### 3. 目录 README 明确优先级

`docs/roadmap/README.md` 承担目录级导航职责，防止后续新增 `DETAILED`、`FINAL`、`V2` 等漂移文件。

### 4. R0 平台优先

Roadmap 中明确 R0 平台能力优先：pipeline、Agent runtime abstraction、bug auto-fix、logging/audit、architecture baseline 先于业务功能扩张。

## 数据流

本任务没有运行时数据流。只涉及仓库文件读取和静态测试。

```text
Agent / Reviewer
  -> read docs/roadmap/MASTER_ROADMAP.md
  -> follow compatibility link if full detailed section needed
  -> apply priority/conflict rules
  -> create feature-specific requirements/design/reports
```

## API 设计

无 API 变更。

## 前端路线

无前端代码变更。Roadmap 明确 Streamlit 仍是当前有效产品入口。

## 测试策略

新增 `tests/test_roadmap_canonicalization.py`：

1. 检查 canonical path 存在。
2. 检查 compatibility file 存在。
3. 检查 README 存在。
4. 检查 canonical 文件包含核心规则。
5. 检查 compatibility 文件仍保留详细 V16/V17 路线。

## 安全审查

本 PR 不修改：

```text
src/broker/**
src/execution/**
src/order/**
src/account/**
src/risk/**
miniQMT/**
```

也不修改 Market Data Relay、Provider、Risk、Strategy 或 Execution 运行时代码。

## 失败处理

若静态测试失败，说明 Roadmap 入口或核心约束被破坏，PR 不应合并。

## 后续扩展

R0.1 合并后，后续可以继续推进：

```text
R0.2 AgentOps Control Tower completion
R0.3 Agent Runtime Abstraction
R0.4 Bug Auto-Fix System productization
R0.5 Logging, audit and operational visibility baseline
V16.3 Provider Test Suite & Fallback Governance
```
