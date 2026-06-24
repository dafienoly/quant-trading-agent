# Team Pipeline V2

This document is the standing workflow for cost-aware multi-agent development.
It extends the Issue-driven pipeline without weakening any trading-safety rule.

## 中文核心规则

- `Codex A` 是产品经理和最终验收角色。
- `Codex B` 是架构师和最终架构 Review 角色。
- `OpenCode Lead` 使用 `opencode-go/glm-5.2`，负责阶段拆分、组内总
  Review 和失败复盘。
- `Claude Code Developer` 使用 `ultracode-xhigh`、`effort=xhigh`、
  `feature-dev` workflow 和 `superpowers`，负责阶段开发和 BugFix。
- `OpenCode Test Engineer` 使用 `opencode-go/deepseek-v4-pro`、
  `variant=max` 和 `superpowers`，负责阶段测试。
- 阶段测试通过后，如果还有后续阶段，必须回到 `Claude Code Developer` 继续开发
  下一阶段。
- 所有阶段测试都通过后，才能交给 `OpenCode Lead` 做组内总 Review。
- `OpenCode Lead` Review 通过后，才允许交给 `Codex B` 做最终 Review。
- `Codex B` 连续 3 次 Review 不通过时，触发开发小组不称职告警和复盘。
- 多个小组并行时，每个小组、每个阶段、每个测试分支必须使用独立
  branch/worktree，不能共用一个工作目录。

## Role Model

| Role | Agent | Responsibility |
|---|---|---|
| Codex A | Product Manager / PM Acceptance | Requirements, user-facing acceptance, final delivery notes |
| Codex B | Architect / Final Reviewer | Architecture, module boundaries, final code review, safety review |
| OpenCode Lead | Small-team Lead | GLM 5.2 phase breakdown, coordination, internal review, postmortem |
| Claude Code Developer | Phase Developer / BugFix | ultracode-xhigh implementation with feature-dev and superpowers |
| OpenCode Test Engineer | Phase Tester | DeepSeek V4 Pro max verification from a temporary test branch |

Codex A and Codex B are judgment gates. The hybrid OpenCode/Claude Code team
handles the high-frequency implementation loop.

## Required Flow

```text
User Issue
  -> Codex A requirements
  -> Codex B architecture
  -> OpenCode GLM 5.2 team phase plan
  -> Claude Code ultracode-xhigh phase development
  -> OpenCode DeepSeek V4 Pro max phase testing
  -> if current phase fails: Claude Code fixes current phase
  -> if current phase passes and more phases remain: Claude Code starts next phase
  -> if all phases pass: OpenCode Lead review
  -> Codex B final architecture review
  -> Codex A PM acceptance
  -> merge gate
```

OpenCode Test Engineer must not route directly to Codex B. OpenCode Lead review is mandatory
after all phase tests pass.

## Phase Contract

Each phase in `docs/dev_plans/*team-plan.md` must include:

- phase ID, title, and branch name;
- files or modules in scope;
- explicit out-of-scope items;
- expected dev report path;
- expected test report path;
- self-test commands;
- tester verification commands;
- pass/fail routing rule;
- whether restricted modules are touched.

## Evidence Contract

| Stage | Required evidence |
|---|---|
| Codex A PM | `docs/requirements/*requirements.md` |
| Codex B Architecture | `docs/design/*architecture.md` |
| OpenCode Lead Team Plan | `docs/dev_plans/*team-plan.md` |
| Claude Code Phase Dev | `docs/dev_reports/*phase-*dev-report.md` |
| OpenCode Phase Test | `docs/test_reports/*phase-*test-report.md` |
| OpenCode Lead Review | `docs/review/*opencode-lead-review.md` |
| Codex B Review | `docs/review/*codex-review*.md` |
| Codex A Acceptance | `docs/acceptance/*acceptance.md` |
| User-facing Feature | `docs/user_guides/*user-guide.md` when applicable |
| Failed Team Loop | `docs/postmortems/*r3-failure.md` |

No stage is complete if its evidence exists only in chat.

## Parallel Team Rules

Multiple Claude teams may work in parallel only when their branch and report
paths are isolated:

```text
team/<feature>/claude-a
feat/<feature>/phase-<n>-<module>
test/<feature>/phase-<n>-claude-c-<timestamp>
fix/<feature>/codex-review-r<n>
postmortem/<feature>/r3-failure
```

The epic branch remains the integration branch. No team may merge directly to
`main`.

Local execution rule:

- Use one terminal or self-hosted runner job per active Agent.
- Use one git worktree per active writing/testing Agent.
- Team stages must use `scripts/run-team-stage.ps1` and
  `scripts/run-pipeline-team-agent.sh`. The repository runner pins the model,
  effort/variant, workflow, and superpowers requirements.

## Codex B Review Attempts

Codex B review failures are quality signals against the Claude team lead:

| Attempt | Action |
|---|---|
| 1 | Record failure category, route feedback to OpenCode Lead |
| 2 | Record repeat issue, require OpenCode Lead to update team plan/checklist |
| 3 | Trigger `stage:postmortem-pending` and stop normal automation |

Failure categories:

- requirement drift;
- architecture boundary violation;
- missing or weak tests;
- trading-safety risk;
- data-contract risk;
- incomplete user flow;
- missing evidence/report;
- code quality or maintainability risk.

## Workflow Improvement Log

Every feature should append process lessons to the development or postmortem
report:

- what slowed the team down;
- what caused rework;
- what handoff was ambiguous;
- which test should have caught the defect earlier;
- what prompt, checklist, or gate should be improved.
