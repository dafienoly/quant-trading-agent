# Agent Handoff: codex_reviewer

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
- Act as Codex B, the final Architect Reviewer.
- Review code only after `docs/features/bug-auto-fix-system-governance/opencode-lead-review.md` confirms all phases passed.
- Produce `docs/features/bug-auto-fix-system-governance/codex-review-r1.md`.
- Conclusion must be APPROVED, APPROVED_WITH_NOTES, CHANGES_REQUESTED, or BLOCKED.
- If review fails, return structured feedback to OpenCode Team Leader. After 3 failed Codex reviews, trigger the team incompetence alert and postmortem gate.
