# Team Plan: smoke-test-real-claude-tester-v8

## Objective

Implement a smoke test pipeline for the "Real Claude Tester V8" mode, validating that Claude-based test execution works end-to-end across all stages: developer commits, test runner invocation, report generation, and review handoff. The pipeline must be safe to run against isolated worktrees and must not touch any trading-sensitive modules.

## Inputs Reviewed

- `AGENTS.md` — Hard safety invariants, role boundaries, read order
- `docs/process/AGENT_DEVELOPMENT_PIPELINE.md` — Stage gates, role responsibilities, standard deliverables
- `docs/process/BRANCH_WORKFLOW.md` — Branch types, isolation rules for dev/test/fix branches
- `docs/pipeline/AGENT_AUTOMATION_ARCHITECTURE.md` — Issue-driven automation triggers, event flows
- `docs/pipeline/AUTO_MERGE_POLICY.md` — Merge gate conditions, manual approval requirements
- `docs/requirements/2026-06-14-smoke-test-real-claude-tester-v8-requirements.md`
- `docs/design/2026-06-14-smoke-test-real-claude-tester-v8-architecture.md`

## Scope

- Define smoke test scenarios that exercise the full Claude Tester agent lifecycle: checkout, test execution, report artifact generation, exit-code assertion.
- Implement a CLI entry point (`smoke-test.ts` or `smoke_test.py`) that invokes each scenario against an isolated worktree and reports pass/fail for each phase.
- Wire the entry point into the CI/automation pipeline so it can be triggered by issue comments and branch pushes.
- Document expected outputs, exit codes, and failure modes.
- Commit all changes to the `epic/20260614-smoke-test-real-claude-tester-v8` epic branch via feature branches.

## Non-Goals

- No modifications to trading, execution, order, risk, or broker modules.
- No changes to the auto-merge gate or manual approval bypass mechanisms.
- No credential or secret management changes.
- No production deployment or live-market integration.
- No performance benchmarking or load testing.

## Safety Constraints

1. Current task is docs-only / pipeline-only by default.
2. Do NOT modify trading-sensitive modules: broker, execution, order, account, risk, miniQMT, live trading, real order submission.
3. Do NOT weaken the Merge Gate or bypass manual approval.
4. Do NOT write API keys, tokens, or secrets into the repository.
5. Do NOT auto-merge to main.
6. Do NOT modify policy enforcement or risk controls.

## Proposed Phases

### Phase 1 — Scaffold & Smoke Test Runner Script

- **Scope**: Create the smoke test runner entry point that enumerates scenarios, executes them sequentially against isolated worktrees, and produces a structured report.
- **Deliverables**:
  - `scripts/smoke-test-real-claude-tester-v8.sh` (or equivalent cross-platform script) that orchestrates scenario execution.
  - `docs/dev_plans/20260614-smoke-test-real-claude-tester-v8-phase-1-dev-plan.md` — detailed implementation plan for the runner.
- **Branch**: `feat/smoke-test-real-claude-tester-v8/runner`
- **Owner**: Claude B (Developer Agent)
- **Self-test commands**:
  ```bash
  git worktree add ../smoke-test-worktree epic/20260614-smoke-test-real-claude-tester-v8
  bash scripts/smoke-test-real-claude-tester-v8.sh --dry-run
  ```
- **Tester checks**: Verify the script prints scenario list, does not execute real commands in dry-run mode, exits 0.
- **Release criteria**: Script runs with `--help` and lists all planned scenarios; all paths reference existing directories.

### Phase 2 — Scenario 1: Tester Agent Checkout & Environment Validation

- **Scope**: Implement the first smoke scenario — clone the epic branch into a worktree, verify required files exist (architecture doc, requirements doc), check that `AGENTS.md` can be parsed.
- **Deliverables**:
  - Scenario logic embedded in the runner script or a dedicated module.
  - Phase 1 dev report at `docs/dev_reports/20260614-smoke-test-real-claude-tester-v8-phase-1-dev-report.md`.
- **Branch**: `feat/smoke-test-real-claude-tester-v8/scenario-checkout`
- **Owner**: Claude B (Developer Agent)
- **Self-test commands**:
  ```bash
  bash scripts/smoke-test-real-claude-tester-v8.sh --scenario checkout
  ```
- **Tester checks**: Worktree is created; key files exist; script reports `PASS` or `FAIL` with reason; worktree is cleaned up on exit.
- **Release criteria**: Scenario passes against the epic branch HEAD.

### Phase 3 — Scenario 2: Test Execution & Exit Code Assertion

- **Scope**: Implement the second scenario — create a temporary test branch, run a mock test command (e.g., `pytest --collect-only` or a minimal test script), capture exit code and output, assert exit code is 0, report structured results.
- **Deliverables**:
  - Scenario logic for execution and exit-code assertion.
  - Phase 2 dev report at `docs/dev_reports/20260614-smoke-test-real-claude-tester-v8-phase-2-dev-report.md`.
- **Branch**: `feat/smoke-test-real-claude-tester-v8/scenario-execution`
- **Owner**: Claude B (Developer Agent)
- **Self-test commands**:
  ```bash
  bash scripts/smoke-test-real-claude-tester-v8.sh --scenario execution
  ```
- **Tester checks**: Exit code 0 on success; non-zero on simulated failure; output includes exit code, stdout tail, stderr tail; JSON summary artifact generated.
- **Release criteria**: Scenario passes with known-good test; fails with known-bad test.

### Phase 4 — Scenario 3: Report Artifact Generation

- **Scope**: Implement the third scenario — after test execution, validate that the expected report artifacts (`docs/test_reports/YYYY-MM-DD-<feature>-phase-<n>-test-report.md`) are created with required sections (scope, results, bug list).
- **Deliverables**:
  - Scenario logic for artifact validation.
  - Phase 3 dev report at `docs/dev_reports/20260614-smoke-test-real-claude-tester-v8-phase-3-dev-report.md`.
- **Branch**: `feat/smoke-test-real-claude-tester-v8/scenario-artifacts`
- **Owner**: Claude B (Developer Agent)
- **Self-test commands**:
  ```bash
  bash scripts/smoke-test-real-claude-tester-v8.sh --scenario artifacts
  ```
- **Tester checks**: Report file exists; required sections present; no placeholder/todo text remaining; markdown is valid.
- **Release criteria**: Scenario passes when artifacts are well-formed; fails when artifacts are missing or malformed.

### Phase 5 — CI Pipeline Integration

- **Scope**: Wire the smoke test runner into the CI workflow so it triggers on push to the epic branch and on issue-comment commands (`/smoke-test`).
- **Deliverables**:
  - CI workflow file (e.g., `.github/workflows/smoke-test-real-claude-tester-v8.yml`).
  - Phase 4 dev report.
- **Branch**: `feat/smoke-test-real-claude-tester-v8/ci-integration`
- **Owner**: Claude B (Developer Agent)
- **Self-test commands**: Push to epic branch and verify CI job starts; trigger via issue comment on a test issue.
- **Tester checks**: Workflow runs on push; workflow runs on `/smoke-test` comment; job fails if any smoke scenario fails; job succeeds when all pass; run log is accessible.
- **Release criteria**: CI job reports green check on successful run; red X on failure.

### Phase 6 — Full Integration Test & Lead Review

- **Scope**: Run all smoke scenarios sequentially against the epic branch. Fix any failures. Produce the Claude Lead Review report.
- **Deliverables**:
  - `docs/review/20260614-smoke-test-real-claude-tester-v8-claude-lead-review.md`
  - Phase 5 dev report.
- **Branch**: Working on epic branch directly (fix branches as needed).
- **Owner**: Claude A (Lead Planning Agent)
- **Self-test commands**:
  ```bash
  bash scripts/smoke-test-real-claude-tester-v8.sh --all
  ```
- **Tester checks**: All three scenarios pass; CI run is green; report artifacts are generated.
- **Release criteria**: Lead review document is signed off; all phases are marked complete in pipeline state.

## Agent Assignments

| Role | Agent | Responsibility |
|---|---|---|
| Lead Planning / Team Lead | Claude A (current) | Team plan, lead review, team performance, orchestration |
| Developer | Claude B | Phase 1–5 implementation, dev reports |
| Test Engineer | Claude C | Phase 1–5 testing, test reports, bug reports |
| PM Acceptance | Codex A (PM) | Acceptance verification against requirements |
| Architecture / Codex Review | Codex B | Code review, architecture consistency check |

## Validation Plan

- **Per-phase validation**: Each phase must pass its self-test commands and tester checks before the next phase begins.
- **Gate review**: After Phase 5 passes, Claude A performs the lead review. After lead review passes, Codex B performs the architecture code review.
- **Acceptance gate**: Codex A (PM) runs full acceptance against `docs/requirements/2026-06-14-smoke-test-real-claude-tester-v8-requirements.md`.
- **Merge gate**: Manual approval required before merging to `main`. Auto-merge is disabled for this feature.

## Exit Criteria

1. All six phases are implemented and tested.
2. All three smoke scenarios pass in CI on the epic branch.
3. Claude Lead Review report is produced with no blocking findings.
4. Codex Architecture Review passes with no violations of safety invariants.
5. PM Acceptance confirms all requirements are met.
6. All deliverable documents are committed and linked from the pipeline state.
7. Manual approval is obtained for the merge to `main`.
