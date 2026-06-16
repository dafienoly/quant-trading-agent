# Requirements: Post-merge V11 Real Codex Acceptance Smoke R2

## Goal

Validate that V11 real `codex_acceptance` works from clean `origin/main` after PR #36 and PR #38 have been merged.

## Scope

This is a docs-only smoke validation.

Allowed:
- Generate pipeline artifacts required by the Agent pipeline.
- Validate real `codex_reviewer`.
- Validate real `codex_acceptance`.
- Validate acceptance gate generation.
- Validate state/gate consistency.
- Validate Merge Gate manual approval behavior.

Not allowed:
- Modify trading modules.
- Modify broker / execution / order / account / risk / miniQMT / live trading.
- Submit real orders.
- Auto-merge main.
- Bypass manual approval.

## Acceptance Criteria

- `claude_lead_plan` succeeds.
- `claude_developer` succeeds.
- `claude_tester` succeeds.
- `claude_lead_review` succeeds.
- `codex_reviewer` succeeds in real mode.
- `codex_acceptance` succeeds in real mode with strict mode enabled.
- `.agent/gates/acceptance_gate.json` has `passed=true`.
- Acceptance decision is `ACCEPTED` or `ACCEPTED_WITH_NOTES`.
- `artifact_manifest_codex_acceptance.json` is generated.
- Merge Gate succeeds and preserves `stage:manual-approval-required`.
- No trading-sensitive files are modified.
