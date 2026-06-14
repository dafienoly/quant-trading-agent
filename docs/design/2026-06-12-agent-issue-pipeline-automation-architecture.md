# Agent Issue Pipeline Automation Architecture

## Overview

This feature adds a deterministic orchestration layer around the existing Agent
development process.

The architecture deliberately separates:

- deterministic pipeline mechanics in Python;
- GitHub event handling in workflow YAML;
- actual LLM/Agent execution through configurable external commands.

This prevents product code from depending on a specific LLM vendor and keeps
merge safety auditable.

## Components

| Component | Path | Responsibility |
|---|---|---|
| `agent_pipeline_automation.py` | `src/product_app/` | Pure Python state, handoff, report-gate, and auto-merge classification helpers |
| CLI | `scripts/agent_pipeline.py` | GitHub Actions and local developer entry point |
| Issue template | `.github/ISSUE_TEMPLATE/agent_feature_request.yml` | Standardized user request format |
| Bootstrap workflow | `.github/workflows/agent-issue-bootstrap.yml` | Creates pipeline state, epic branch, PR, and PM/architect handoff |
| Stage runner workflow | `.github/workflows/agent-stage-runner.yml` | Runs developer/tester/bugfix/reviewer/acceptance commands |
| Merge gate workflow | `.github/workflows/agent-main-merge-gate.yml` | Checks reports and changed-file risk before main merge |
| Pipeline docs | `docs/pipeline/` | Automation architecture, state machine, labels, handoff, auto-merge policy |

## Data Flow

```text
Issue / workflow_dispatch
  -> scripts/agent_pipeline.py init-feature
  -> .agent/state.json + .agent/current_task.yaml
  -> .agent/handoff/pm_architect.md
  -> external PM/Architect command
  -> requirements + architecture docs
  -> epic branch PR
  -> stage labels / workflow_dispatch
  -> external stage commands
  -> dev/test/review/acceptance reports
  -> scripts/agent_pipeline.py classify-changes
  -> .agent/gates/auto_merge_gate.json
  -> auto merge if safe, manual approval if restricted
```

## Auto-Merge Gate

The changed-file classifier is conservative:

- all files must be in safe auto-merge prefixes;
- no file may match restricted trading or secret-sensitive prefixes/tokens;
- unknown business code requires manual approval.

Safe examples:

- `docs/**`
- `tests/**`
- `.github/ISSUE_TEMPLATE/**`
- `.agent/**`

Restricted examples:

- `.github/workflows/**`
- `scripts/**`
- `src/api/**`
- `src/ui_report/**`
- data provider paths
- `src/risk_engine/**`
- `src/execution_engine/**`
- broker/order/account paths
- miniQMT/XtQuant paths
- `.env*`
- risk/execution/self-test policies

## External Agent Command Contract

The workflows read these optional secrets/variables:

- `PM_ARCHITECT_AGENT_COMMAND`
- `DEVELOPER_AGENT_COMMAND`
- `TEST_AGENT_COMMAND`
- `BUGFIX_AGENT_COMMAND`
- `REVIEW_AGENT_COMMAND`
- `ACCEPTANCE_AGENT_COMMAND`

Each command runs inside the checked-out repository. It must read the relevant
`.agent/handoff/<stage>.md` file and write the required stage report before
returning success.

Dry-run mode generates state and handoff only.

## Failure Handling

- Missing agent command in non-dry-run mode fails the workflow.
- Missing reports fail the corresponding gate.
- Restricted paths fail the auto-merge gate.
- Test/review/acceptance failures route back to `stage:fix-pending` by label.
- Auto-main merge failure labels the PR as `stage:manual-approval-required`.

## Branch Plan

This feature is safe infrastructure and does not touch live trading modules.
Expected branch plan:

```text
epic/20260612-agent-issue-pipeline-automation
feat/agent-issue-pipeline-automation/pipeline-cli
feat/agent-issue-pipeline-automation/github-workflows
```

## Test Strategy

Unit tests cover deterministic Python behavior. GitHub workflow execution is
validated by static review and dry-run semantics because Actions cannot be fully
executed in local unit tests.
