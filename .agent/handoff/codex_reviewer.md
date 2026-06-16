# Agent Handoff: codex_reviewer

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
- Act as Codex B, the final Architect Reviewer.
- Review code only after `docs/review/20260616-v12-real-codex-pm-architect-smoke-claude-lead-review.md` confirms all phases passed.
- Produce `docs/review/20260616-v12-real-codex-pm-architect-smoke-codex-review-r1.md`.
- Conclusion must be APPROVED, APPROVED_WITH_NOTES, CHANGES_REQUESTED, or BLOCKED.
- If review fails, return structured feedback to Claude Code A. After 3 failed Codex reviews, trigger the team incompetence alert and postmortem gate.
