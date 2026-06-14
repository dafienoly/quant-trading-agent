# Agent Handoff: claude_lead_plan

Feature: smoke-test-real-claude-tester-v8
Title: [Feature] Smoke Test Real Claude Tester V8
Epic branch: epic/20260614-smoke-test-real-claude-tester-v8
Risk level: unknown

Required read order:
1. AGENTS.md
2. docs/process/AGENT_DEVELOPMENT_PIPELINE.md
3. docs/process/BRANCH_WORKFLOW.md
4. docs/pipeline/AGENT_AUTOMATION_ARCHITECTURE.md
5. docs/pipeline/AUTO_MERGE_POLICY.md

Task:
- Act as Claude Code A, the small-team lead.
- Read `docs/design/20260614-smoke-test-real-claude-tester-v8-architecture.md` and split implementation into ordered phases.
- Produce `docs/dev_plans/20260614-smoke-test-real-claude-tester-v8-team-plan.md`.
- Each phase must have scope, owner, branch, self-test commands, tester checks, and release criteria.
- After each phase test passes, route back to Claude Code B for the next phase until all phases are complete.
