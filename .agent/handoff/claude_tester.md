# Agent Handoff: claude_tester

Feature: post-merge-v11-real-codex-acceptance-smoke-r2
Title: Post-merge V11 real Codex Acceptance R2
Epic branch: epic/20260616-post-merge-v11-real-codex-acceptance-smoke-r2
Risk level: docs-only

Required read order:
1. AGENTS.md
2. docs/process/AGENT_DEVELOPMENT_PIPELINE.md
3. docs/process/BRANCH_WORKFLOW.md
4. docs/pipeline/AGENT_AUTOMATION_ARCHITECTURE.md
5. docs/pipeline/AUTO_MERGE_POLICY.md

Task:
- Act as Claude Code C, the phase tester.
- Create a temporary local `test/post-merge-v11-real-codex-acceptance-smoke-r2/phase-<n>-tester-<timestamp>` branch from the phase branch under test.
- Verify the requirements, architecture, team plan, phase dev report, and diff.
- Produce `docs/test_reports/20260616-post-merge-v11-real-codex-acceptance-smoke-r2-phase-<n>-test-report.md`.
- If the phase passes, route back to Claude Code B for the next phase unless all phases are complete.
- Generate `feedback/bugs/open/BUG_*.md` and `.json` for reproducible blockers.
