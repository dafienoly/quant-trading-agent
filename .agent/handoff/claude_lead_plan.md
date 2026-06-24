# Agent Handoff: claude_lead_plan

Feature: agentops-control-tower-foundationpipeline-api-re
Title: [V16.1] AgentOps Control Tower Foundation：Pipeline 观测契约、只读聚合 API 与 React 状态中心
Epic branch: epic/20260624-agentops-control-tower-foundationpipeline-api-re-issue-75
Risk level: unknown

Required read order:
1. AGENTS.md
2. docs/process/AGENT_DEVELOPMENT_PIPELINE.md
3. docs/process/BRANCH_WORKFLOW.md
4. docs/pipeline/AGENT_AUTOMATION_ARCHITECTURE.md
5. docs/pipeline/AUTO_MERGE_POLICY.md

Task:
- Compatibility stage ID: `claude_lead_plan`; actual role: OpenCode Team Leader.
- Runtime is fixed to `opencode-go/glm-5.2` and must use superpowers.
- Read `docs/design/20260624-agentops-control-tower-foundationpipeline-api-re-architecture.md` and split implementation into ordered phases.
- Produce `docs/dev_plans/20260624-agentops-control-tower-foundationpipeline-api-re-team-plan.md`.
- Each phase must have scope, owner, branch, self-test commands, tester checks, and release criteria.
- After each phase test passes, route back to Claude Code Developer for the next phase until all phases are complete.
