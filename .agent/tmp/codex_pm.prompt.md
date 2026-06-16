Generate a requirements document in Markdown format. Output ONLY the raw Markdown content to stdout \u2014 do NOT write any file, do NOT use any tools, do NOT include conversational text, greetings, or meta-commentary.

## Context

### Current Stage
codex_pm \u2014 You are Codex A (PM Agent). You must produce the project requirements document.

### Feature ID
v12-real-codex-pm-architect-smoke

### Handoff Content

# Agent Handoff: codex_pm

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
- Act as Codex A, the PM Agent.
- Produce the PM requirements document at `docs/requirements/20260616-v12-real-codex-pm-architect-smoke-requirements.md`.
- Include goals, non-goals, feature list, acceptance criteria, safety constraints, and user-facing success criteria.
- Do not write architecture or product code in this stage.


### Pipeline State

{
  "feature_id": "v12-real-codex-pm-architect-smoke",
  "title": "V12 real Codex PM and Architect smoke",
  "risk_level": "docs-only",
  "issue_number": 50,
  "issue_url": "https://github.com/dafienoly/quant-trading-agent/pull/50",
  "epic_branch": "epic/20260616-v12-real-codex-pm-architect-smoke",
  "current_stage": "merge_gate_pending",
  "created_at": "2026-06-16T12:26:50.013190+00:00",
  "required_docs": {
    "requirements": "docs/requirements/20260616-v12-real-codex-pm-architect-smoke-requirements.md",
    "architecture": "docs/design/20260616-v12-real-codex-pm-architect-smoke-architecture.md",
    "team_plan": "docs/dev_plans/20260616-v12-real-codex-pm-architect-smoke-team-plan.md",
    "phase_dev_report_pattern": "docs/dev_reports/20260616-v12-real-codex-pm-architect-smoke-phase-<n>-dev-report.md",
    "phase_test_report_pattern": "docs/test_reports/20260616-v12-real-codex-pm-architect-smoke-phase-<n>-test-report.md",
    "claude_lead_review": "docs/review/20260616-v12-real-codex-pm-architect-smoke-claude-lead-review.md",
    "codex_review": "docs/review/20260616-v12-real-codex-pm-architect-smoke-codex-review-r1.md",
    "acceptance": "docs/acceptance/20260616-v12-real-codex-pm-architect-smoke-acceptance.md",
    "user_guide": "docs/user_guides/20260616-v12-real-codex-pm-architect-smoke-user-guide.md",
    "postmortem": "docs/postmortems/20260616-v12-real-codex-pm-architect-smoke-r3-failure.md"
  },
  "team_pipeline": {
    "mode": "claude_first_review",
    "default_team_id": "claude-team-a",
    "max_parallel_teams": 3,
    "max_codex_review_attempts": 3,
    "current_phase": 1,
    "all_phases_tested": true,
    "codex_review_attempts": 0
  },
  "agent_roles": {
    "codex_a": [
      "pm",
      "acceptance"
    ],
    "codex_b": [
      "architecture",
      "codex_review"
    ],
    "claude_a": [
      "team_plan",
      "claude_lead_review",
      "team_performance"
    ],
    "claude_b": [
      "phase_dev"
    ],
    "claude_c": [
      "phase_test"
    ]
  },
  "manual_approval_required_for": [
    "restricted-module",
    "live-trading",
    "risk-policy-change",
    "execution-policy-change",
    "main-merge-when-auto-merge-gate-fails",
    "codex-review-fails-three-times"
  ],
  "stage_status": {
    "pm": "pending",
    "architecture": "pending",
    "team_plan": "pending",
    "phase_dev": "passed",
    "phase_test": "passed",
    "claude_lead_review": "passed",
    "codex_review": "passed",
    "acceptance": "passed"
  }
}


### Output Format

The requirements document MUST contain these sections (in order):

# v12-real-codex-pm-architect-smoke Requirements
## User Goal
## Functional Requirements
## Non-functional Requirements
## Acceptance Criteria
## Safety Constraints

### Important Notes

- You are Codex A (PM Agent) \u2014 NOT a developer, architect, or reviewer.
- Do NOT modify production code or trading-sensitive modules.
- The target output path is: docs\requirements\2026-06-16-v12-real-codex-pm-architect-smoke-requirements.md

REMINDER: Output ONLY the raw markdown. No conversation. No tool use. No file writing.