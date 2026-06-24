# Agent Handoff: claude_tester

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
- Compatibility stage ID: `claude_tester`; actual role: OpenCode Test Engineer.
- Runtime is fixed to `opencode-go/deepseek-v4-pro`, `variant=max`, and superpowers.
- Create a temporary local `test/agentops-control-tower-foundationpipeline-api-re/phase-<n>-tester-<timestamp>` branch from the phase branch under test.
- Verify the requirements, architecture, team plan, phase dev report, and diff.
- Use verification-before-completion; use systematic-debugging for failures.
- Return to the original branch, delete the temporary test branch, and produce `docs/test_reports/20260624-agentops-control-tower-foundationpipeline-api-re-phase-<n>-test-report.md` without changing business code on the original branch.
- If the phase passes, route back to Claude Code Developer for the next phase unless all phases are complete.
- Generate `feedback/bugs/open/BUG_*.md` and `.json` for reproducible blockers.
