# Agent Handoff: claude_developer

Feature: historical-pr-triage-pr-2-and-pr-3
Title: [V15.0 Restart 3] Historical PR Triage: PR #2 and PR #3
Epic branch: epic/20260618-historical-pr-triage-pr-2-and-pr-3
Risk level: unknown

Required read order:
1. AGENTS.md
2. docs/process/AGENT_DEVELOPMENT_PIPELINE.md
3. docs/process/BRANCH_WORKFLOW.md
4. docs/pipeline/AGENT_AUTOMATION_ARCHITECTURE.md
5. docs/pipeline/AUTO_MERGE_POLICY.md

Task:
- Compatibility stage ID: `claude_developer`; actual role: Claude Code Developer.
- Runtime is fixed to `ultracode-xhigh`, `effort=xhigh`, feature-dev workflow, and superpowers.
- Implement only the current phase from `docs/dev_plans/20260618-historical-pr-triage-pr-2-and-pr-3-team-plan.md`.
- In GitHub Stage Runner mode, remain on the checked-out PR branch and let the workflow commit/push; in manual mode follow `docs/process/BRANCH_WORKFLOW.md`.
- Write focused failing tests first where practical.
- Produce `docs/dev_reports/20260618-historical-pr-triage-pr-2-and-pr-3-phase-<n>-dev-report.md` with exact self-test commands.
- After OpenCode Test Engineer verifies the phase, continue with the next planned phase until all phases are tested.
- Do not touch restricted trading modules unless the architecture document explicitly permits it.
