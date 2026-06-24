# Agent Handoff Contract

Every automated stage must leave enough information for the next Agent to start
without private chat context.

## Required Handoff Inputs

Every Agent must read:

1. `AGENTS.md`
2. `docs/process/AGENT_DEVELOPMENT_PIPELINE.md`
3. `docs/process/BRANCH_WORKFLOW.md`
4. `docs/pipeline/AGENT_AUTOMATION_ARCHITECTURE.md`
5. `.agent/current_task.yaml`
6. `.agent/handoff/<stage>.md`
7. Current stage's upstream reports

## Required Handoff Outputs

| From | To | Required output |
|---|---|---|
| Codex A PM | Codex B Architect | requirements document |
| Codex B Architect | OpenCode Lead | architecture document and phase guidance |
| OpenCode Lead | OpenCode Developer | team phase plan |
| OpenCode Developer | OpenCode Test Engineer | code, tests, phase dev report, delivery gate, self-test commands |
| OpenCode Test Engineer | OpenCode Developer | phase test report when more phases remain or blockers exist |
| OpenCode Test Engineer | OpenCode Lead | phase test report when all phases pass |
| OpenCode Lead | Codex B Reviewer | OpenCode lead review after all phases pass |
| Codex B Reviewer | OpenCode Lead or Codex A Acceptance | final architecture review report |
| Codex A Acceptance | Merge Gate | acceptance report and user guide when applicable |

## Machine-Readable Handoff Schema

A handoff file may reference this schema:

```yaml
from: developer
to: tester
feature_id: example-feature
epic_branch: epic/20260612-example-feature
working_branch: feat/example-feature/provider
requirements_doc: docs/requirements/2026-06-12-example-feature-requirements.md
architecture_doc: docs/design/2026-06-12-example-feature-architecture.md
dev_report: docs/dev_reports/2026-06-12-example-feature-dev-report.md
team_plan: docs/dev_plans/2026-06-12-example-feature-team-plan.md
phase_id: phase-1
phase_dev_report: docs/dev_reports/2026-06-12-example-feature-phase-1-dev-report.md
phase_test_report: docs/test_reports/2026-06-12-example-feature-phase-1-test-report.md
changed_files:
  - src/data_gateway/providers/example.py
  - tests/test_example_provider.py
self_test_commands:
  - python -m pytest tests/test_example_provider.py -q
known_risks:
  - Public data source may timeout
restricted_modules_touched: false
```

## Non-Negotiable Handoff Rules

1. Never say a stage is done only in chat.
2. Never ask the next Agent to infer requirements from commit messages alone.
3. Never hide skipped tests or external service failures.
4. Never omit whether restricted trading modules were touched.
5. Never use paper/demo success as live-trading proof.
6. Never route from OpenCode Test Engineer directly to Codex B. All phases must
   pass and OpenCode Lead must produce a lead review first.
7. Never request Codex B final review when
   `team_pipeline.all_phases_tested=false`.
8. Never claim a changed path that is absent from the current diff.
9. Never treat report presence as a pass when the final decision is negative.
