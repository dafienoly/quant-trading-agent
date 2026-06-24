# Agent Automation Architecture

This document defines the Issue-driven Agent automation layer for Level 2 +
controlled Level 3 development.

The goal is to remove manual copy/paste between Codex, Claude Code/DeepSeek,
test agents, bugfix agents, and GitHub while preserving the repository's
trading-safety gates.

## Operating Model

GitHub is the single source of truth for automation state:

- GitHub Issue: user request and pipeline entry point.
- GitHub labels: current stage and routing signal.
- Epic branch: integration branch for the feature.
- Feature/fix/test branches: isolated implementation and verification branches.
- Pull request: review, CI, merge gate, and audit surface.
- Repository files: durable handoff state and required reports.

Agents must not rely on private chat history as their source of truth. Every
handoff must be written to the repository under `.agent/`, `docs/`, or
`feedback/bugs/`.

## Automation Components

| Component | Path | Purpose |
|---|---|---|
| Pipeline state | `.agent/state.json` | Machine-readable current feature metadata |
| Current task | `.agent/current_task.yaml` | Agent-readable task state |
| Handoff prompts | `.agent/handoff/*.md` | Stage-specific prompts for Codex A/B, OpenCode Lead, Claude Developer, OpenCode Tester, acceptance, bugfix, and postmortem |
| Gate outputs | `.agent/gates/*.json` | Deterministic pass/fail evidence for stage gates |
| CLI | `scripts/agent_pipeline.py` | Creates state, handoff prompts, report gates, and auto-merge decisions |
| GitHub workflows | `.github/workflows/` | Trigger issue-driven stages, CI, bugfix loop, review, acceptance, and merge gate |
| Issue template | `.github/ISSUE_TEMPLATE/agent_feature_request.yml` | Standard request format for automatic pipelines |

## Level 2 Flow: Issue Driven Pipeline

```text
GitHub Issue with agent:pipeline
  -> Codex A creates requirements
  -> Codex B creates architecture
  -> epic/<date-feature> branch is created
  -> OpenCode GLM 5.2 Lead creates phase plan
  -> Claude Code ultracode-xhigh implements one phase
  -> OpenCode DeepSeek V4 Pro max verifies that phase
  -> if more phases remain, route back to Claude Code Developer
  -> OpenCode Lead reviews the completed team delivery
  -> Codex B writes final architecture review
  -> Codex A writes PM acceptance report
  -> merge gate decides automatic or manual main merge
```

## Controlled Level 3 Flow: Auto Main Merge

The merge gate may merge to `main` automatically only when all conditions hold:

1. Required reports exist through acceptance.
2. CI passes.
3. Architecture review is present.
4. PM acceptance is present.
5. Changed files are entirely in the safe auto-merge allowlist.
6. No trading-sensitive or secret-sensitive path is touched.

If any condition fails, the gate fails closed and requires human approval.

## Agent Command Integration

Codex stages continue to call external commands through repository secrets or
variables. Team stages use repository-owned runners so the selected model,
effort/variant, workflow, and superpowers contract cannot be silently replaced
by a repository variable.

Expected command variables/secrets:

| Variable/Secret | Stage |
|---|---|
| `CODEX_A_PM_AGENT_COMMAND` | Codex A requirements generation |
| `CODEX_B_ARCHITECT_AGENT_COMMAND` | Codex B architecture generation |
| `CODEX_B_REVIEW_AGENT_COMMAND` | Codex B final architecture review |
| `CODEX_A_ACCEPTANCE_AGENT_COMMAND` | Codex A PM acceptance |

Team-stage execution is fixed:

| Compatibility stage ID | Repository runner | Runtime |
|---|---|---|
| `claude_lead_plan`, `claude_lead_review`, `postmortem` | `scripts/run-pipeline-team-agent.sh` | OpenCode `opencode-go/glm-5.2` + superpowers |
| `claude_developer`, `bugfix` | `scripts/run-pipeline-team-agent.sh` | Claude Code `ultracode-xhigh`, `effort=xhigh`, feature-dev + superpowers |
| `claude_tester` | `scripts/run-pipeline-team-agent.sh` | OpenCode `opencode-go/deepseek-v4-pro`, `variant=max`, superpowers |

The `claude_*` stage IDs remain only for workflow, label, and gate compatibility.
They no longer identify the actual Lead or Test Engineer implementation.

Each command must read the relevant `.agent/handoff/<stage>.md`, repository
policy documents, and current branch. It must write the required report before
returning success.

## Fail-Closed Defaults

The automation must fail closed when:

- pipeline state is missing;
- required reports are missing;
- CI fails;
- changed files include restricted trading paths;
- changed files include unknown business code outside the auto-merge allowlist;
- an agent command is not configured for a non-dry-run pipeline;
- `team_pipeline.all_phases_tested` is false when Codex B review is requested;
- Codex B review has failed three times without a postmortem;
- secrets, credentials, account files, broker paths, risk policy, or execution
  policy are touched.

## Relationship to Existing Process

This document does not replace:

- `docs/process/AGENT_DEVELOPMENT_PIPELINE.md`
- `docs/process/BRANCH_WORKFLOW.md`
- `docs/policy/RISK_POLICY.md`
- `docs/policy/EXECUTION_POLICY.md`
- `docs/policy/SELF_TEST_CHECKLIST.md`

It automates them. Where there is a conflict, safety policy and the branch
workflow win.
