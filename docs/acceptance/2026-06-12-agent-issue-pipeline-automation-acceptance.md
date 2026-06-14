# Agent Issue Pipeline Automation Acceptance

## User Goal

Implement Level 2 Issue-driven automation with controlled Level 3 automatic main
merge for safe non-trading changes, while requiring manual approval for
trading-sensitive modules.

## Acceptance Matrix

| User Need | Result | Evidence |
|---|---|---|
| GitHub Issue can trigger the pipeline | ACCEPTED | Issue template and bootstrap workflow added |
| PM/Architect outputs can be automated | ACCEPTED_WITH_FOLLOWUPS | Workflow supports `PM_ARCHITECT_AGENT_COMMAND`; owner must configure it |
| Developer/Test/BugFix/Review/Acceptance can run by label | ACCEPTED_WITH_FOLLOWUPS | Stage runner supports all stages through configurable commands |
| Auto merge main for safe changes | ACCEPTED | Merge gate and workflow added |
| Manual approval for trading-sensitive modules | ACCEPTED | Restricted classifier blocks execution/risk/broker/order/account/miniQMT/live paths |
| Avoid manual copy/paste between Agents | ACCEPTED | `.agent/current_task.yaml` and `.agent/handoff/*.md` provide durable handoff state |

## Notes for Owner Setup

Before using non-dry-run automation, configure the repository with the desired
external Agent commands:

- `PM_ARCHITECT_AGENT_COMMAND`
- `DEVELOPER_AGENT_COMMAND`
- `TEST_AGENT_COMMAND`
- `BUGFIX_AGENT_COMMAND`
- `REVIEW_AGENT_COMMAND`
- `ACCEPTANCE_AGENT_COMMAND`

For first use, create an Issue from the Agent Feature Request template and add
`agent:dry-run` to verify branch, PR, state, and handoff creation without
calling external Agents.

## Conclusion

ACCEPTED_WITH_FOLLOWUPS
