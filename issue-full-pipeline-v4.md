## User Goal

验证 Agent Bootstrap workflow 改为 issues: opened/reopened 后，可以在新建 Issue 时只触发 1 条 Agent Issue Bootstrap，并继续跑通完整模拟 Agent pipeline。

## Expected Outputs

- docs/requirements/...requirements.md
- docs/design/...architecture.md
- docs/dev_plans/...team-plan.md
- docs/dev_reports/...phase-1-dev-report.md
- docs/test_reports/...phase-1-test-report.md
- docs/review/...claude-lead-review.md
- .agent/handoff/claude_lead_plan.md

## Constraints and Non-Goals

- 只测试 Agent pipeline 的模拟 wrapper 调用链路
- 不调用真实 Codex API
- 不调用真实 Claude Code
- 不调用 ccswitch / OpenCodeGo / DeepSeek
- 不做真实业务开发
- 不修改交易、下单、风控、账户、broker、miniQMT 等敏感模块
- 不合并 main
- 不自动发布

## Risk Level

docs-only

## Acceptance Criteria

- 新建 Issue 后只出现 1 条 Agent Issue Bootstrap run
- Issue 自动添加 agent:bootstrapped
- Issue 自动移除 stage:pm-pending
- PR 自动创建或更新
- PR 中包含 requirements、architecture、team plan、dev report、test report、lead review report
- PR label 最终推进到 stage:codex-review-pending
