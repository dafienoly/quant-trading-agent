# Pipeline State Machine

This document defines labels and file gates used by the Issue-driven Agent
pipeline.

## Stages

| State | Owner | Required output | Next state on pass | Next state on fail |
|---|---|---|---|---|
| `stage:pm-pending` | Codex A PM | requirements document | `stage:arch-pending` | stays pending |
| `stage:arch-pending` | Codex B Architect | architecture document | `stage:team-plan-pending` | `stage:pm-pending` |
| `stage:team-plan-pending` | OpenCode GLM 5.2 lead | phase plan | `stage:team-dev-pending` | `stage:arch-pending` |
| `stage:team-dev-pending` | Claude Code ultracode-xhigh developer | phase code, tests, dev report | `stage:team-test-pending` | stays pending |
| `stage:team-test-pending` | OpenCode DeepSeek V4 Pro max tester | phase test report | `stage:team-dev-pending` or `stage:claude-lead-review-pending` | `stage:fix-pending` |
| `stage:claude-lead-review-pending` | OpenCode GLM 5.2 lead | team lead review | `stage:codex-review-pending` | `stage:team-dev-pending` |
| `stage:fix-pending` | BugFix Agent | fix branch/report/regression tests | `stage:team-test-pending` | `stage:blocked` |
| `stage:codex-review-pending` | Codex B Reviewer | final architecture review | `stage:pm-acceptance-pending` | `stage:team-plan-pending`, `stage:team-dev-pending`, or `stage:postmortem-pending` |
| `stage:pm-acceptance-pending` | Codex A Acceptance | acceptance report | `stage:merge-ready` | `stage:arch-pending` |
| `stage:postmortem-pending` | OpenCode GLM 5.2 lead | three-strike postmortem | `stage:blocked` or user-approved restart | stays pending |
| `stage:merge-ready` | Merge Gate | auto-merge gate JSON | merged or manual approval | `stage:manual-approval-required` |

## Terminal States

| State | Meaning |
|---|---|
| `stage:merged` | Main merge completed |
| `stage:manual-approval-required` | Automatic main merge is blocked by policy |
| `stage:blocked` | Pipeline cannot continue without human intervention |

## Gate Files

The automation writes deterministic gate results under `.agent/gates/`:

| Gate file | Purpose |
|---|---|
| `.agent/gates/dev_gate.json` | Required docs through dev report |
| `.agent/gates/test_gate.json` | Required docs through test report |
| `.agent/gates/review_gate.json` | Required docs through review |
| `.agent/gates/team_plan_gate.json` | Required docs through Claude A team plan |
| `.agent/gates/phase_dev_gate.json` | Required docs through Claude B phase dev |
| `.agent/gates/phase_test_gate.json` | Required docs through Claude C phase test |
| `.agent/gates/claude_lead_review_gate.json` | Required docs through Claude A lead review |
| `.agent/gates/codex_review_gate.json` | Required docs through Codex B final review |
| `.agent/gates/acceptance_gate.json` | Required docs through acceptance |
| `.agent/gates/auto_merge_gate.json` | Changed-file risk classification |

A gate file is evidence, not permission. GitHub branch protection and required
checks still apply.

## State Transition Rules

1. A later stage must not start until earlier required reports exist.
2. Test failure creates `feedback/bugs/open/BUG_*.md` and `.json` when the issue
   is reproducible.
3. OpenCode Test Engineer phase pass returns to `stage:team-dev-pending` until
   `team_pipeline.all_phases_tested=true`.
4. Codex B review may start only after OpenCode Lead review evidence exists.
5. Codex B review failures increment `team_pipeline.codex_review_attempts`.
6. Three Codex B review failures move the pipeline to `stage:postmortem-pending`.
7. Review or acceptance failures use `fix/<feature>/<issue>` or
   `bugfix/<bug-id>-<timestamp>` branches.
8. A stage may only advance by committing its required report or gate result.
9. Any restricted module change moves the merge stage to manual approval.
