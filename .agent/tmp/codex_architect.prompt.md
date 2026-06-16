Generate an architecture/design document in Markdown format. Output ONLY the raw Markdown content to stdout \u2014 do NOT write any file, do NOT use any tools, do NOT include conversational text, greetings, or meta-commentary.

## Context

### Current Stage
codex_architect \u2014 You are Codex B (Architect). You must produce the architecture/design document for this feature.

### Feature ID
v12-real-codex-pm-architect-smoke

### Handoff Content

# Agent Handoff: codex_architect

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
- Read the requirements document at `docs/requirements/20260616-v12-real-codex-pm-architect-smoke-requirements.md`.
- Produce the architecture design at `docs/design/20260616-v12-real-codex-pm-architect-smoke-architecture.md`.
- Include module boundaries, phase slices, technical choices, pseudocode, test strategy, and handoff guidance for Claude Team A/B/C.
- Do not write product code in this stage.


### Pipeline State

{
  "feature_id": "v12-real-codex-pm-architect-smoke",
  "title": "V12 real Codex PM and Architect smoke",
  "risk_level": "docs-only",
  "issue_number": 50,
  "issue_url": "https://github.com/dafienoly/quant-trading-agent/pull/50",
  "epic_branch": "epic/20260616-v12-real-codex-pm-architect-smoke",
  "current_stage": "manual_approval_required_pending",
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


### Requirements Document

# v12-real-codex-pm-architect-smoke Requirements

## User Goal

Validate that the V12 automation pipeline can execute a real Codex PM stage and hand off cleanly to a real Codex Architect stage for a docs-only smoke feature.

The feature must prove that Codex A, acting as PM Agent, can produce a complete requirements document that downstream architecture, planning, development, testing, review, and acceptance stages can consume without changing product code or trading behavior.

## Functional Requirements

1. Produce a PM requirements document for feature `v12-real-codex-pm-architect-smoke`.

2. The requirements document must define the expected behavior and scope for a docs-only pipeline smoke test.

3. The document must include:
   - User goal.
   - Functional requirements.
   - Non-functional requirements.
   - Acceptance criteria.
   - Safety constraints.

4. The PM stage must remain limited to requirements definition.

5. The PM stage must not create architecture, implementation plans, development reports, test reports, review reports, acceptance reports, product code, or runtime artifacts.

6. The feature must require the downstream Architect Agent to consume this requirements document and produce the matching architecture document.

7. The feature must require downstream stages to preserve docs-only scope unless a later stage explicitly identifies a documented process defect requiring correction.

8. The feature must verify the automation handoff path for:
   - PM requirements generation.
   - Architect document generation.
   - Stage-status tracking.
   - Required-document path consistency.
   - Evidence that no trading-sensitive code path was modified.

9. The requirements document target path is:

   `docs/requirements/2026-06-16-v12-real-codex-pm-architect-smoke-requirements.md`

10. If automation metadata references an alternate date format for the same requirements document, downstream agents must treat the path in this requirements document as the PM-stage target and report any mismatch as a documentation or pipeline consistency note.

## Non-functional Requirements

1. The feature must be docs-only.

2. The feature must not alter production behavior, product routes, trading workflows, market data providers, strategy logic, risk logic, execution logic, backtesting behavior, or UI behavior.

3. The feature must remain traceable to:
   - Feature ID: `v12-real-codex-pm-architect-smoke`
   - Epic branch: `epic/20260616-v12-real-codex-pm-architect-smoke`
   - Risk level: `docs-only`
   - Issue: `#50`

4. All downstream evidence must use reproducible commands where commands are run.

5. Reports must clearly distinguish docs-only validation from runtime product validation.

6. No stage may claim live trading, real market-data validation, execution readiness, or production release readiness from this smoke feature alone.

7. Generated documentation must be concise, deterministic, and suitable for automated stage consumption.

8. The work must follow repository process rules for role boundaries, handoff evidence, and stage gates.

## Acceptance Criteria

1. A requirements document exists at the required target path for the PM stage.

2. The requirements document contains all required sections in the required order:
   - `# v12-real-codex-pm-architect-smoke Requirements`
   - `## User Goal`
   - `## Functional Requirements`
   - `## Non-functional Requirements`
   - `## Acceptance Criteria`
   - `## Safety Constraints`

3. The requirements document clearly identifies the feature as docs-only.

4. The requirements document clearly states that no production code or trading-sensitive module changes are in scope.

5. The requirements document gives the Architect Agent enough information to produce an architecture document without inventing product behavior.

6. Downstream architecture output references this requirements document and preserves docs-only scope.

7. Downstream development and test evidence, if generated, confirms that no trading-sensitive code paths were modified.

8. Any path inconsistency between automation metadata and PM output requirements is documented rather than silently ignored.

9. Final acceptance can pass only if all required documents for the smoke pipeline are present or any missing documents are explicitly explained by stage scope.

10. Final acceptance must not claim product feature delivery beyond validation of the PM-to-Architect automation smoke path.

## Safety Constraints

1. No real automatic trading may be enabled, simulated as enabled, or implied by this feature.

2. Risk Agent veto behavior must not be changed.

3. Execution policy, human confirmation, broker integration, order state handling, and trading-hour enforcement must not be changed.

4. Market data provider behavior, fallback behavior, demo-data behavior, and fail-closed behavior must not be changed.

5. Stock-pool filtering, including ChiNext, STAR Market, ST, and delisting-arrangement restrictions, must not be changed.

6. No strategy may be modified to bypass stock-pool filtering.

7. No LLM decision boundary may be changed.

8. No secrets, credentials, tokens, cookies, account information, broker credentials, or `.env` content may be introduced.

9. No restricted modules may be modified as part of this docs-only smoke feature.

10. If any downstream stage determines that code changes are required, the stage must stop and return to the appropriate prior planning role for scope revision instead of expanding this PM requirement silently.

### Output Format

The architecture document MUST contain these sections (in order):

# v12-real-codex-pm-architect-smoke Architecture
## Architecture Summary
## Module Plan
## Technical Decisions
## Safety Impact
## Development Guidance

### Important Notes

- You are Codex B (Architect) \u2014 NOT a developer, tester, or PM.
- Do NOT modify production code or trading-sensitive modules.
- The target output path is: docs\design\2026-06-16-v12-real-codex-pm-architect-smoke-architecture.md

REMINDER: Output ONLY the raw markdown. No conversation. No tool use. No file writing.