# Agent Handoff: claude_tester

Feature: v12-real-codex-pm-architect-smoke
Title: V12 real Codex PM and Architect smoke
Epic branch: epic/20260616-v12-real-codex-pm-architect-smoke
Risk level: docs-only

Required read order:
1. AGENTS.md
2. docs/process/AGENT_DEVELOPMENT_PIPELINE.md
3. docs/process/BRANCH_WORKFLOW.md
4. docs/pipeline/AGENT_AUTOMATION_ARCHITECTURE.md
5. docs/pipeline/AUTO_MERGE_POLICY.md

Task:
- Act as Claude Code C, the phase tester.
- Create a temporary local `test/v12-real-codex-pm-architect-smoke/phase-<n>-tester-<timestamp>` branch from the phase branch under test.
- Verify the requirements, architecture, team plan, phase dev report, and diff.
- Produce `docs/test_reports/20260616-v12-real-codex-pm-architect-smoke-phase-<n>-test-report.md`.
- If the phase passes, route back to Claude Code B for the next phase unless all phases are complete.
- Generate `feedback/bugs/open/BUG_*.md` and `.json` for reproducible blockers.
