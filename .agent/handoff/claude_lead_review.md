# Agent Handoff: claude_lead_review

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
- Compatibility stage ID: `claude_lead_review`; actual role: OpenCode Team Leader Reviewer.
- Runtime is fixed to `opencode-go/deepseek-v4-pro`, `variant=max`, and must use superpowers.
- Review all phase development reports, test reports, actual git diff, delivery gates, and phase metadata.
- Confirm every planned phase is complete and tested before handing off to Codex B.
- Produce `docs/features/bug-auto-fix-system-governance/opencode-lead-review.md` with an explicit APPROVED, APPROVED_WITH_NOTES, CHANGES_REQUESTED, or BLOCKED decision.
- If any phase is incomplete, route back to OpenCode Developer / OpenCode Test Engineer instead of escalating to Codex B.
