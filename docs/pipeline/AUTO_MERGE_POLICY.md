# Auto Merge Policy

This document defines controlled Level 3 automatic merge behavior.

## Policy Summary

Automatic main merge is allowed only for non-trading, low-risk changes after the
full Issue-driven pipeline passes. Trading-sensitive changes always require
human confirmation before merging to `main`.

## Auto-Merge Eligible Categories

The merge gate may allow automatic main merge when all changed files are limited
to these categories:

- documentation;
- tests and test fixtures;
- GitHub Issue templates;
- pipeline state and gate files;

## Always Manual Categories

The merge gate must require manual approval when any changed file touches or is
related to:

- GitHub Actions workflows;
- scripts or automation commands;
- API routes or UI entrypoints;
- data providers, even mock/demo providers;
- `src/risk_engine/`;
- `src/execution_engine/`;
- broker/order/account modules;
- miniQMT, XtQuant, live broker adapters, account assets, positions, order
  submission, cancelation, fills, or trade records;
- live strategy mode;
- risk policy, execution policy, self-test policy;
- secrets, credentials, cookies, tokens, account files, `.env` files;
- any unknown business code outside the auto-merge allowlist.

## Gate Inputs

The merge gate reads:

1. changed files from `git diff --name-only origin/main...HEAD`;
2. required report presence through acceptance;
3. CI result;
4. `.agent/current_task.yaml`;
5. `.agent/gates/auto_merge_gate.json`.

## Gate Output

The merge gate writes:

```json
{
  "eligible_for_auto_main_merge": true,
  "requires_manual_approval": false,
  "risk_level": "safe-auto-main",
  "changed_files": [],
  "restricted_files": [],
  "unsafe_files": [],
  "safe_files": [],
  "reasons": []
}
```

If `requires_manual_approval` is true, the workflow must not merge to `main`.
It should instead label the PR or issue as `stage:manual-approval-required`.

## Relationship to User Approval

A user may request full automation, but this policy is still fail-closed for
trading-sensitive paths. Full automation means the system automatically reaches a
merge-ready PR and auto-merges only when the deterministic risk gate allows it.
It does not mean bypassing safety policy.
