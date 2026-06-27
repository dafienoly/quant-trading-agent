# R0.2 AgentOps Control Tower completion 架构

## 架构目标

把 AgentOps 从“能查一个 pipeline state”增强为“能解释 pipeline instance 当前是否可推进、为什么被挡住、下一步做什么”的只读控制塔。

## 模块边界

```text
src/api/agentops_routes.py
  -> 只注册 GET 路由

src/product_app/agentops/pipeline_contracts.py
  -> Pydantic response contract

src/product_app/agentops/pipeline_aggregator.py
  -> 只读聚合 .agent/state.json、current_task.yaml、handoff、required docs
```

不修改：

```text
src/data_gateway/**
src/strategy_engine/**
src/risk_engine/**
src/execution_engine/**
src/broker/**
src/account/**
```

## 新增契约

### AgentOpsHealth

```text
contract_version = agentops.health.v1
readonly = true
status = ready / empty / error / blocked / stale
available_routes
observed_sources
notes
```

### PipelineInstanceSummary

```text
instance_id
feature_id
issue_number
title
current_stage
risk_level
stage_counts
required_docs_total
required_docs_present
required_docs_missing
required_docs_unreadable
handoff_count
readonly
```

### ControlTowerReadiness

```text
status = ready / blocked / incomplete / unknown
next_action
blockers
warnings
missing_docs
failed_stages
in_progress_stages
confidence
```

## Readiness 判断规则

```text
state missing / unparsable -> unknown 或 empty health
required docs missing -> blocked
failed / blocked stage -> blocked
in-progress stage -> incomplete
no blockers and docs complete -> ready
```

## API 路由

新增：

```text
GET /product/agentops/health
```

保持：

```text
GET /product/agentops/pipelines/{feature_id}
GET /product/agentops/pipelines/by-issue/{issue_number}
```

## 测试策略

```text
tests/test_agentops_routes.py
  - health route
  - existing pipeline routes
  - only GET methods

tests/test_agentops_control_tower.py
  - missing state health
  - ready summary
  - required docs missing -> blocked
  - failed stage -> blocked
```

## 失败处理

AgentOps 不抛出敏感 traceback 给用户。API 层继续使用 sanitized error response。

## 安全确认

本架构保持 read-only，不新增任何写入、执行、账户、交易、外部命令调用或权限升级路径。
