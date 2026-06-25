# pipeline-transaction-controller-hotfix Architecture

## Architecture Summary

将 Stage Runner 收敛为以 `.agent/state.json` 为租约、以组合 transition gate 为提交条件的单入口状态机。GitHub label 只展示状态，不能触发执行。

## Module Plan

- `.github/workflows/agent-stage-runner.yml`：单入口、PR 级串行、阶段租约和组合门禁。
- `src/product_app/agent_pipeline_automation.py`：确定性 start lease 与 transition decision。
- `scripts/agent_pipeline.py`：暴露控制器 CLI。
- `scripts/validate_pr_reports.py`：报告生命周期 profile。
- `scripts/run-pipeline-team-agent.sh`：Tester 运行时副作用清理。
- `tests/`：控制面与报告治理回归。

## Technical Decisions

1. `workflow_dispatch` 是 Stage Runner 唯一执行入口。
2. 并发键为 PR 编号，不包含阶段名，避免相邻阶段并行。
3. `validate-stage-start` 在 Agent 命令前比较请求阶段与持久化状态。
4. `evaluate-stage-transition` 同时读取报告 gate 和交付 gate，生成唯一结论。
5. 状态同步只能发生在组合结论通过之后。
6. Pipeline 进行中使用阶段报告 profile；最终状态使用五章节严格 profile。
7. docs-only 资格只来自当前 team plan 阶段中的明确声明。

## Failure Routing

- Developer 报告或交付失败：停止自动路由，标记人工处理，避免自循环。
- Tester 驳回：在预算内回 Developer；预算耗尽转人工。
- 旧队列：不调用 Agent，直接失败关闭。
- 状态或 gate 缺失、feature 不匹配：失败关闭。

## Test Strategy

- 静态 workflow 契约测试。
- start lease 与 transition 组合逻辑单元测试。
- docs-only 阶段交付测试。
- Pipeline 中间/最终报告 profile 测试。
- 严格 Pipeline regression。

## Safety Impact

不改变产品交易功能。修复降低错误阶段推进和错误批准风险，并继续要求 main 人工审阅与合并。

## Development Guidance

先运行新增失败测试，再实现控制逻辑。禁止通过跳过 gate、允许任意 Tester 修改或恢复 label 双触发来解决表面错误。
