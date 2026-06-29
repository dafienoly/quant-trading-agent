# Agent Handoff: claude_developer

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
- Compatibility stage ID: `claude_developer`; actual role: OpenCode Developer.
- Runtime is fixed to `opencode-go/deepseek-v4-flash`, `variant=max`, build Agent permissions, and superpowers.
- Implement only the current phase 1 from `docs/features/bug-auto-fix-system-governance/team-plan.md`.
- In GitHub Stage Runner mode, remain on the checked-out PR branch and let the workflow commit/push; in manual mode follow `docs/process/BRANCH_WORKFLOW.md`.
- Write focused failing tests first where practical.
- Produce `docs/features/bug-auto-fix-system-governance/phase-1-dev-report.md` with exact self-test commands and a truthful changed-file list.
- Every claimed changed path must exist and appear in the current diff; non-documentation phases require implementation and test changes.
- After OpenCode Test Engineer verifies the phase, continue with the next planned phase until all phases are tested.
- Do not touch restricted trading modules unless the architecture document explicitly permits it.
