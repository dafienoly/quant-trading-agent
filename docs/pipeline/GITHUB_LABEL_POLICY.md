# GitHub Label Policy

This repository uses GitHub labels as the routing surface for the automated
Agent pipeline.

## Pipeline Activation

| Label | Meaning |
|---|---|
| `agent:pipeline` | Mark the issue as eligible for the Issue-driven pipeline. Bootstrap starts only when this is paired with `stage:pm-pending`. |
| `agent:bootstrapped` | Bootstrap has already created the epic branch and PR; prevents repeated bootstrap runs. |
| `agent:dry-run` | Generate state and handoff prompts only; do not require external agent commands |
| `agent:auto-main` | Request automatic main merge when the merge gate allows it |
| `agent:merge-gate` | Explicitly run the main merge gate for an eligible pipeline PR |

## Agent Roles

| Label | Meaning |
|---|---|
| `agent:pm` | PM requirement generation needed |
| `agent:architect` | Architecture generation needed |
| `agent:claude-lead` | Claude Code A team lead needed |
| `agent:claude-developer` | Claude Code B phase developer needed |
| `agent:claude-tester` | Claude Code C phase tester needed |
| `agent:bugfix` | BugFix Agent needed |
| `agent:reviewer` | Codex B final architecture review needed |
| `agent:acceptance` | Codex A PM acceptance needed |

## Stages

| Label | Meaning |
|---|---|
| `stage:pm-pending` | Waiting for PM requirements |
| `stage:arch-pending` | Waiting for architecture design |
| `stage:team-plan-pending` | Waiting for Claude Code A phase plan |
| `stage:team-dev-pending` | Waiting for Claude Code B phase implementation |
| `stage:team-test-pending` | Waiting for Claude Code C phase verification |
| `stage:claude-lead-review-pending` | Waiting for Claude Code A team lead review after all phases pass |
| `stage:fix-pending` | Waiting for bugfix/review-fix implementation |
| `stage:codex-review-pending` | Waiting for Codex B final architecture review |
| `stage:pm-acceptance-pending` | Waiting for Codex A PM acceptance |
| `stage:postmortem-pending` | Waiting for three-strike team postmortem |
| `stage:merge-ready` | All stage artifacts are present; run merge gate |
| `stage:manual-approval-required` | Auto main merge blocked by policy |
| `stage:merged` | Main merge completed |
| `stage:blocked` | Human intervention required |

## Risk Labels

| Label | Meaning |
|---|---|
| `risk:docs-only` | Documentation-only change |
| `risk:data-provider` | Data source/provider change |
| `risk:dashboard` | UI/dashboard change |
| `risk:ordinary-api` | API change without trading execution impact |
| `risk:test-only` | Test-only change |
| `risk:restricted-module` | Trading-sensitive module touched |
| `risk:live-trading` | Live trading behavior may be affected |
| `risk:secret-sensitive` | Secret/account/credential paths touched |

## Required Label Hygiene

1. Exactly one active `stage:*` label should be present on a pipeline issue or
   pull request.
2. `risk:restricted-module`, `risk:live-trading`, and `risk:secret-sensitive`
   override `agent:auto-main`.
3. Stage labels should be updated by workflows, not by individual agents, unless
   the workflow is unavailable.
4. Bootstrap must be triggered by `stage:pm-pending`, not by `agent:pipeline`
   alone. After Bootstrap succeeds, the workflow must add `agent:bootstrapped`
   and remove `stage:pm-pending`.
5. PR stage workflows should only run from explicit stage labels. Opening or
   synchronizing a PR must not start developer, tester, review, or merge stages
   by itself.
