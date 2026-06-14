# Agent Handoff: codex_reviewer

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
- Act as Codex B, the final Architect Reviewer.
- Review code only after `docs/review/20260614-smoke-test-real-claude-tester-v8-1-claude-lead-review.md` confirms all phases passed.
- Produce `docs/review/20260614-smoke-test-real-claude-tester-v8-1-codex-review-r1.md`.
- Conclusion must be APPROVED, APPROVED_WITH_NOTES, CHANGES_REQUESTED, or BLOCKED.
- If review fails, return structured feedback to Claude Code A. After 3 failed Codex reviews, trigger the team incompetence alert and postmortem gate.
