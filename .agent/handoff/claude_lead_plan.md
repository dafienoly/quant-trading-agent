# Agent Handoff: claude_lead_plan

Feature: bug-auto-fix-system-governance
Title: [V16.4] Bug Auto-Fix System Governance：安全修复白名单、受限模块阻断与审计门禁
Epic branch: epic/20260629-bug-auto-fix-system-governance-issue-122
Risk level: unknown

Required read order:
1. AGENTS.md
2. docs/process/AGENT_DEVELOPMENT_PIPELINE.md
3. docs/process/BRANCH_WORKFLOW.md
4. docs/pipeline/AGENT_AUTOMATION_ARCHITECTURE.md
5. docs/pipeline/AUTO_MERGE_POLICY.md

Task:
- Compatibility stage ID: `claude_lead_plan`; actual role: OpenCode Team Leader.
- Runtime is fixed to `opencode-go/deepseek-v4-pro`, `variant=max`, and must use superpowers.
- Read `docs/features/bug-auto-fix-system-governance/architecture.md` and split implementation into ordered phases.
- Produce `docs/features/bug-auto-fix-system-governance/team-plan.md`.
- Each phase must have scope, owner, branch, self-test commands, tester checks, and release criteria.
- After each phase test passes, route back to OpenCode Developer for the next phase until all phases are complete.
