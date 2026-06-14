# Agent Team Pipeline V2 Requirements

## Background

The V1 Issue-driven Agent pipeline can bootstrap a feature from GitHub Issue
labels and run linear Developer, Tester, Codex Review, PM Acceptance, and Merge
Gate stages. The user now wants to reduce Codex cost by moving high-frequency
development review into a Claude Code small-team loop.

Codex remains the team leader for product requirements, architecture, final
architecture review, PM acceptance, and safety decisions.

## Goals

1. Split Codex responsibilities into Codex A as Product Manager and Codex B as
   Architect / final Architecture Reviewer.
2. Add a Claude Code small team before Codex B review:
   - Claude Code A: team lead, implementation phase planning, internal review,
     performance accountability, and postmortem owner.
   - Claude Code B: phase developer.
   - Claude Code C: phase tester.
3. Ensure each implementation phase loops between Claude Code B and Claude Code
   C until that phase passes.
4. Ensure all phases pass testing before Claude Code A performs the team lead
   review.
5. Ensure Codex B review happens only after Claude Code A approval.
6. Track Codex B review failures and trigger a team incompetence alert after
   three failed Codex B reviews for the same feature.
7. Support multiple Claude teams working in parallel through isolated team,
   feature, phase, test, and fix branches.
8. Preserve full development logs, handoff docs, user manuals, postmortems, and
   workflow-improvement suggestions.
9. Provide GitHub workflow and local Windows/WSL configuration hooks for the
   user's Windows Codex installation, WSL VS Code Claude Code Agent, and Codex
   API access.

## Non-Goals

1. Do not embed direct Codex or Claude API calls into product runtime code.
2. Do not bypass trading safety, risk, execution, or human-confirmation policy.
3. Do not allow automatic main merge for sensitive workflow, script, API, UI,
   data-provider, trading, risk, execution, broker, account, or secret changes.
4. Do not require Codex to review every Claude phase.

## Functional Requirements

| ID | Requirement | Acceptance Criteria | Priority |
|---|---|---|---|
| F-001 | Codex A PM stage | Pipeline can generate a Codex A handoff and expects a requirements document only | MUST |
| F-002 | Codex B architecture stage | Pipeline can generate a Codex B architecture handoff after PM requirements | MUST |
| F-003 | Claude A team planning | Pipeline supports a team-plan stage that creates `docs/dev_plans/*team-plan.md` | MUST |
| F-004 | Phase development loop | Claude B phase development is followed by Claude C phase testing | MUST |
| F-005 | Correct phase transition | If `team_pipeline.all_phases_tested=false`, a passed Claude C phase returns to Claude B for the next phase | MUST |
| F-006 | Final Claude lead review | If all phases are tested, the next stage is Claude A lead review | MUST |
| F-007 | Codex B final review | Codex B review can run only after Claude A lead review evidence exists | MUST |
| F-008 | Review failure penalty | Codex B review failures are counted and documented against Claude A team leadership | MUST |
| F-009 | Three-strike alert | Three Codex B review failures trigger postmortem and user-visible team incompetence alert | MUST |
| F-010 | PM acceptance | Codex A validates final behavior against the requirements after Codex B approval | MUST |
| F-011 | User manual retention | Completed user-facing features must include a user guide under `docs/user_guides/` | SHOULD |
| F-012 | Parallel teams | Pipeline state and branch rules support multiple Claude teams working on separate feature/phase branches | MUST |
| F-013 | Local runtime setup | Documentation explains Windows Codex, WSL Claude Code, GitHub variables/secrets, and local dry-run commands | MUST |

## Safety Requirements

- Codex B final review remains mandatory before PM acceptance.
- Any sensitive changed path still requires manual user approval before merging
  to `main`.
- Claude team review cannot replace Codex B review.
- Missing state, missing reports, or missing commands must fail closed.
- Agents must not rely on private chat context; all stage evidence must be
  written to repository files.

## Required Deliverables

- `docs/requirements/2026-06-14-agent-team-pipeline-v2-requirements.md`
- `docs/design/2026-06-14-agent-team-pipeline-v2-architecture.md`
- `docs/pipeline/TEAM_PIPELINE_V2.md`
- `docs/pipeline/LOCAL_AGENT_RUNTIME_SETUP.md`
- updated `.github/workflows/agent-issue-bootstrap.yml`
- updated `.github/workflows/agent-stage-runner.yml`
- updated `src/product_app/agent_pipeline_automation.py`
- updated `scripts/agent_pipeline.py`
- updated `tests/test_agent_pipeline_automation.py`
