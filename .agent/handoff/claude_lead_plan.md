# Agent Handoff: claude_lead_plan

Feature: smoke-test-pm-and-architect-commands
Title: [Feature] Smoke Test PM And Architect Commands
Epic branch: epic/20260614-smoke-test-pm-and-architect-commands
Risk level: unknown

Required read order:
1. AGENTS.md
2. docs/process/AGENT_DEVELOPMENT_PIPELINE.md
3. docs/process/BRANCH_WORKFLOW.md
4. docs/pipeline/AGENT_AUTOMATION_ARCHITECTURE.md
5. docs/pipeline/AUTO_MERGE_POLICY.md

Task:
- Act as Claude Code A, the small-team lead.
- Read `docs/design/20260614-smoke-test-pm-and-architect-commands-architecture.md` and split implementation into ordered phases.
- Produce `docs/dev_plans/20260614-smoke-test-pm-and-architect-commands-team-plan.md`.
- Each phase must have scope, owner, branch, self-test commands, tester checks, and release criteria.
- After each phase test passes, route back to Claude Code B for the next phase until all phases are complete.
