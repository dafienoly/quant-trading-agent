# Agent Handoff: claude_developer

Feature: smoke-test-real-claude-tester-v8-1
Title: [Feature] Smoke Test Real Claude Tester V8.1
Epic branch: epic/20260614-smoke-test-real-claude-tester-v8-1
Risk level: unknown

Required read order:
1. AGENTS.md
2. docs/process/AGENT_DEVELOPMENT_PIPELINE.md
3. docs/process/BRANCH_WORKFLOW.md
4. docs/pipeline/AGENT_AUTOMATION_ARCHITECTURE.md
5. docs/pipeline/AUTO_MERGE_POLICY.md

Task:
- Act as Claude Code B, the phase developer.
- Implement only the current phase from `docs/dev_plans/20260614-smoke-test-real-claude-tester-v8-1-team-plan.md`.
- Start from `epic/20260614-smoke-test-real-claude-tester-v8-1` and create `feat/smoke-test-real-claude-tester-v8-1/phase-<n>-<module>`.
- Write focused tests first where practical.
- Produce `docs/dev_reports/20260614-smoke-test-real-claude-tester-v8-1-phase-<n>-dev-report.md` with exact self-test commands.
- After Claude Code C verifies the phase, continue with the next planned phase until all phases are tested.
- Do not touch restricted trading modules unless the architecture document explicitly permits it.
