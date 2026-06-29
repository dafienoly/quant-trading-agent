# Agent Handoff: claude_tester

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
- Compatibility stage ID: `claude_tester`; actual role: OpenCode Test Engineer.
- Runtime is fixed to `opencode-go/deepseek-v4-flash`, `variant=max`, build Agent permissions, and superpowers.
- Create a temporary local `test/bug-auto-fix-system-governance/phase-<n>-tester-<timestamp>` branch from the phase branch under test.
- Verify the requirements, architecture, team plan, phase dev report, actual diff, and claimed changed paths.
- Use verification-before-completion; use systematic-debugging for failures.
- Return to the original branch, delete the temporary test branch, and produce `docs/features/bug-auto-fix-system-governance/phase-<n>-test-report.md` without changing business code on the original branch.
- The final decision must be exactly PASS, PASS_WITH_NOTES, or REJECTED; REJECTED routes back to OpenCode Developer.
- If the phase passes, route back to OpenCode Developer for the next phase unless all phases are complete.
- Generate and actually persist `feedback/bugs/open/BUG_*.md` and `.json` for reproducible blockers.
