# Agent Issue Pipeline Automation Requirements

## Background

The repository already has a document-driven Agent development pipeline and a
parallel branch workflow. The user wants Level 2 Issue-driven automation plus
controlled Level 3 automatic main merge for non-trading changes.

The current pain point is manual context transfer between Codex, Claude
Code/DeepSeek, test agents, review agents, and GitHub.

## Goals

1. A GitHub Issue can start an Agent pipeline.
2. The pipeline creates durable repository state and handoff prompts.
3. Agent stages can be triggered by GitHub labels or workflow dispatch.
4. Stage gates verify that required reports exist before moving forward.
5. A deterministic merge gate decides whether automatic main merge is allowed.
6. Trading-sensitive changes must require manual approval.

## Non-Goals

1. Do not implement direct LLM API calls inside product code.
2. Do not bypass existing trading safety policy.
3. Do not allow unattended merge for risk, execution, broker, order, account,
   miniQMT, or live-trading changes.
4. Do not replace the existing `AGENT_DEVELOPMENT_PIPELINE.md` or
   `BRANCH_WORKFLOW.md`.

## Functional Requirements

| ID | Requirement | Acceptance Criteria | Priority |
|---|---|---|---|
| F-001 | Issue-driven bootstrap | Repository has an Issue template and bootstrap workflow that creates `.agent` state and handoff prompts | MUST |
| F-002 | Stage runner | Repository has a stage runner workflow for developer, tester, bugfix, reviewer, and acceptance stages | MUST |
| F-003 | Deterministic gates | CLI can check required report presence through a selected stage | MUST |
| F-004 | Auto-merge classification | CLI classifies changed files as safe-auto-main or manual-main-approval | MUST |
| F-005 | Controlled auto-main merge | Workflow auto-merges only if gate passes and changed files are safe | MUST |
| F-006 | Manual approval for sensitive modules | Risk/execution/broker/order/account/miniQMT/live-trading paths block auto-main merge | MUST |
| F-007 | Handoff contract | Docs define how agents exchange state without private chat context | MUST |
| F-008 | Configuration hooks | Workflows support external agent commands through repo secrets or variables | MUST |

## Safety Requirements

- Missing state or missing reports must fail closed.
- Unknown business code outside the safe allowlist must require manual approval.
- Secrets and `.env` paths must require manual approval.
- Workflow, script, API, UI, and data-provider changes must require manual
  approval unless a later architecture document explicitly narrows and approves
  a safer allowlist.
- Agent commands are configurable and are not hard-coded into the product code.
- Workflows must not expose trading automation as a casual user-selectable option.

## Test Requirements

- Unit tests cover safe auto-merge classification.
- Unit tests cover restricted module classification.
- Unit tests cover unknown business code classification.
- Unit tests cover workflow changes requiring manual approval.
- Unit tests cover feature state and handoff generation.
- Unit tests cover report gate pass/fail behavior.
