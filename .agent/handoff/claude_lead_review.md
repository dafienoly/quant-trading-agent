# Agent Handoff: claude_lead_review

Feature: smoke-test-full-team-pipeline-v4
Title: [Feature] Smoke Test Full Team Pipeline V4
Epic branch: epic/20260614-smoke-test-full-team-pipeline-v4
Risk level: unknown

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
- Produce `docs/review/20260614-smoke-test-full-team-pipeline-v4-claude-lead-review.md`.
- If any phase is incomplete, route back to Claude Code B/C instead of escalating to Codex B.
