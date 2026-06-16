# Architecture: Post-merge V11 Real Codex Acceptance Smoke R2

## Overview

This smoke test validates the post-merge V11 Agent pipeline behavior using a docs-only feature branch.

The pipeline should produce normal PM, architecture, team plan, development report, test report, lead review, Codex review, and Codex acceptance artifacts without touching trading modules.

## Pipeline Flow

Expected stage order:

1. `claude_lead_plan`
2. `claude_developer`
3. `claude_tester`
4. `claude_lead_review`
5. `codex_reviewer`
6. `codex_acceptance`
7. `agent-main-merge-gate`

## V11-specific Behavior

`codex_acceptance` must run in real Codex mode when:

- `AGENT_REAL_CODEX_ACCEPTANCE=true`
- `AGENT_REAL_CODEX_ACCEPTANCE_STRICT=true`

Strict mode must not fall back to mock output.

## Safety Constraints

- Do not modify trading modules.
- Do not modify broker / execution / order / account / risk / miniQMT / live trading.
- Do not submit real orders.
- Do not bypass manual approval.
- Do not auto-merge main.

## Validation Artifacts

The final acceptance stage should generate:

- `docs/acceptance/20260616-post-merge-v11-real-codex-acceptance-smoke-r2-acceptance.md`
- `.agent/gates/acceptance_gate.json`
- `.agent/artifact_manifest_codex_acceptance.json`

## Merge Gate Expectation

The smoke PR should end with:

- `stage:merge-ready`
- `stage:manual-approval-required`

The smoke PR should be closed after validation and should not be merged into main.
