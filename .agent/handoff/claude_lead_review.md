# Agent Handoff: claude_lead_review

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
- Act as Claude Code A, the small-team lead reviewer.
- Review all phase development reports and test reports.
- Confirm every planned phase is complete and tested before handing off to Codex B.
- Produce `docs/review/20260616-v12-real-codex-pm-architect-smoke-claude-lead-review.md`.
- If any phase is incomplete, route back to Claude Code B/C instead of escalating to Codex B.
