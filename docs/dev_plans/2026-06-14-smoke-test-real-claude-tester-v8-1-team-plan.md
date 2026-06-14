# Team Plan: Smoke Test Real Claude Tester V8.1

## Objective

Verify that the "real Claude tester" mode (enabled in commits `663deba`, `e6b1594`) works correctly end-to-end in the agent automation pipeline, including stage runner wrapper integration, infinite-loop prevention (commit `8196c5f`), and proper handoff between developer and tester agents. Deliver a repeatable smoke test suite that can be run on demand or triggered by the CI pipeline.

## Inputs Reviewed

| Artifact | Status |
|---|---|
| `docs/requirements/2026-06-14-smoke-test-real-claude-tester-v8-1-requirements.md` | Present (epic branch) |
| `docs/design/2026-06-14-smoke-test-real-claude-tester-v8-1-architecture.md` | Present (epic branch) |
| `.agent/current_task.yaml` | Present (working tree) |
| `.agent/state.json` | Present (working tree) |
| `.agent/handoff/codex_pm.md` | Present (working tree) |
| `.agent/handoff/codex_architect.md` | Present (working tree) |
| `AGENTS.md` — Hard Safety Invariants | Repository root |
| `docs/process/AGENT_DEVELOPMENT_PIPELINE.md` | Repository root |
| `docs/process/BRANCH_WORKFLOW.md` | Repository root |
| `docs/pipeline/AGENT_AUTOMATION_ARCHITECTURE.md` | Repository root |
| `docs/pipeline/AUTO_MERGE_POLICY.md` | Repository root |
| `docs/pipeline/TEAM_PIPELINE_V2.md` | Repository root |

## Scope

- Author smoke test scripts that exercise "real Claude tester" mode (`claude_tester` with real API calls).
- Verify the stage runner wrapper correctly delegates to the tester agent and collects results.
- Verify the infinite-loop guard (`8196c5f`) terminates runaway tester iterations.
- Verify handoff contract between Claude B (Developer) and Claude C (Tester) when running in real mode.
- Produce dev reports, test reports, and review artifacts for each phase.
- Deliver a single `scripts/smoke-test-real-claude-tester.sh` (or `.ps1`) entry point.

## Non-Goals

- No changes to `claude_tester` core logic, stage runner core, or agent runtime.
- No modification to trading-sensitive modules (broker, execution, order, account, risk, miniQMT, live trading).
- No weakening of the Merge Gate or bypass of manual approval.
- No new Claude API keys or tokens committed to the repository.
- No modification to policy enforcement or risk controls.
- No real trading or order submission — all tests are pipeline/documentation only.

## Safety Constraints

1. **Docs-only / pipeline-only by default.** All phases produce documentation, test scripts, and pipeline configuration. No phase alters trading logic, execution policies, risk controls, or secret management.
2. **Do NOT modify trading-sensitive modules**: broker, execution, order, account, risk, miniQMT, live trading, real order submission.
3. **Do NOT weaken the Merge Gate or bypass manual approval.** Auto-merge to `main` is forbidden; merge remains gated by Codex review + PM acceptance.
4. **Do NOT write API keys, tokens, or secrets into the repository.** All API credentials must be sourced from environment variables at runtime.
5. **Do NOT auto-merge to `main`.** The epic branch must be merged manually after all gates pass.
6. **Do NOT modify policy enforcement or risk controls.** The smoke test is observational — it verifies existing behavior, it does not change enforcement.

## Proposed Phases

### Phase 1 — Smoke Test Harness & Base Infrastructure

| Field | Value |
|---|---|
| **Scope** | Create the smoke test entry-point script (`scripts/smoke-test-real-claude-tester.ps1`), common test utilities (log collection, exit-code assertion, duration tracking), and a minimal configuration file that points to the existing `.agent/state.json` pipeline state. Wire the script to be invocable both standalone and from CI. |
| **Owner** | Claude B (Developer Agent) |
| **Branch** | `feat/smoke-test-real-claude-tester-v8-1/harness` (from epic) |
| **Self-test commands** | `pwsh scripts/smoke-test-real-claude-tester.ps1 --list-phases` (must print phase names without error); verify exit code 0. |
| **Tester checks** | Tester verifies script exists at expected path, parses flags correctly, reports `--help` output, and fails gracefully on missing config. |
| **Release criteria** | Script executes without error, logs to `docs/test_reports/` directory, and all test utility functions produce correct exit codes for known pass/fail inputs. |

---

### Phase 2 — Tester Real-Mode Verification Suite

| Field | Value |
|---|---|
| **Scope** | Implement smoke test cases that exercise the `claude_tester` agent in real mode: (a) verify the tester can initialize with the `CLAUDE_API_KEY` environment variable, (b) verify a minimal test plan (single no-op phase) runs to completion, (c) verify the tester produces a valid test report in `docs/test_reports/`. Tests run inside the stage runner wrapper, not against raw API. |
| **Owner** | Claude B (Developer Agent) |
| **Branch** | `feat/smoke-test-real-claude-tester-v8-1/tester-verification` (from epic) |
| **Self-test commands** | `pwsh scripts/smoke-test-real-claude-tester.ps1 --phase tester-init` followed by `pwsh scripts/smoke-test-real-claude-tester.ps1 --phase tester-run-minimal`. Each must exit 0 and leave a report file. |
| **Tester checks** | Tester inspects the generated report for required sections (scope, cases executed, pass/fail counts, duration). Verifies real API calls were made (non-empty response). Verifies no secrets leaked into logs. |
| **Release criteria** | Both test cases pass, report is valid YAML/JSON with correct schema, and no credentials appear in any log or artifact output. |

---

### Phase 3 — Infinite-Loop Guard Verification

| Field | Value |
|---|---|
| **Scope** | Craft a test scenario that would trigger an infinite loop (e.g., a phase that always returns "retry") and verify that the guard from commit `8196c5f` terminates after `max_retries` and reports a clear failure. Test both the happy path (guard triggers) and the edge case (guard threshold configuration via env var). |
| **Owner** | Claude B (Developer Agent) |
| **Branch** | `feat/smoke-test-real-claude-tester-v8-1/loop-guard` (from epic) |
| **Self-test commands** | `pwsh scripts/smoke-test-real-claude-tester.ps1 --phase loop-guard-happy` and `--phase loop-guard-edge`. First expects exit code 0 with "max retries exceeded" in output; second verifies configurable threshold works. |
| **Tester checks** | Tester reviews guard trigger output, checks that no runaway process remained, verifies the guard message is descriptive, and checks that the CI timeout wrapper is not the thing that killed the process. |
| **Release criteria** | Guard triggers within configured retry limit, output clearly states termination reason, and no orphan processes remain after test. |

---

### Phase 4 — Stage Runner Wrapper Integration

| Field | Value |
|---|---|
| **Scope** | Test the full developer → tester handoff through the stage runner wrapper: (a) Claude B produces a phase dev report, (b) stage runner invokes Claude C in real tester mode, (c) Claude C consumes the report and produces a test report, (d) stage runner collects both reports. The smoke test simulates this flow using the existing wrapper scripts. |
| **Owner** | Claude B (Developer Agent) |
| **Branch** | `feat/smoke-test-real-claude-tester-v8-1/stage-runner` (from epic) |
| **Self-test commands** | `pwsh scripts/smoke-test-real-claude-tester.ps1 --phase handoff-dev-to-test`. Expect exit 0, verify `docs/dev_reports/` and `docs/test_reports/` both contain a new file with matching phase number. |
| **Tester checks** | Tester validates the handoff contract: phase number consistency, report UUID linking, agent role annotations (developer vs. tester). Tester also checks that the wrapper did not introduce extraneous files. |
| **Release criteria** | Handoff produces correctly linked dev + test reports, stage runner wrapper exits 0, and all artifacts are in their canonical directories. |

---

### Phase 5 — End-to-End Pipeline Smoke Test

| Field | Value |
|---|---|
| **Scope** | Run the full smoke test suite as a single command: `pwsh scripts/smoke-test-real-claude-tester.ps1 --all`. This executes phases 1–4 in sequence, collects all artifacts, and produces a consolidated summary report at `docs/test_reports/YYYY-MM-DD-smoke-test-real-claude-tester-v8-1-summary.md`. Also wire into the CI pipeline as a manual-trigger job. |
| **Owner** | Claude B (Developer Agent) |
| **Branch** | `feat/smoke-test-real-claude-tester-v8-1/e2e` (from epic) |
| **Self-test commands** | `pwsh scripts/smoke-test-real-claude-tester.ps1 --all` (expect exit 0, total duration under 10 minutes). |
| **Tester checks** | Tester runs the full suite in an isolated worktree, verifies every phase report exists and has correct schema, and checks the summary report covers all phases. Tester attempts a destructive edge case (interrupt mid-run) and verifies partial artifacts are preserved. |
| **Release criteria** | All 4 phases pass, summary report is complete, CI job configuration is valid (dry-run with `--dry-run` flag passes lint). |

---

### Phase 6 — Review & Acceptance Artifacts

| Field | Value |
|---|---|
| **Scope** | Produce Claude Lead Review (`docs/review/YYYY-MM-DD-smoke-test-real-claude-tester-v8-1-claude-lead-review.md`) and Codex Review (`docs/review/YYYY-MM-DD-smoke-test-real-claude-tester-v8-1-codex-review-r1.md`) documents. Address any review findings with fix branches. Final PM acceptance (`docs/acceptance/YYYY-MM-DD-smoke-test-real-claude-tester-v8-1-acceptance.md`). |
| **Owner** | Claude A (Lead Planning / Review) + Codex A/B (Codex Review / PM Acceptance) |
| **Branch** | Reviews committed to epic branch directly; fixes on `fix/smoke-test-real-claude-tester-v8-1/<issue>` branches |
| **Self-test commands** | N/A (documentation review) |
| **Tester checks** | N/A (review artifacts are checked by Codex/PM roles, not by Tester) |
| **Release criteria** | Lead review approved, Codex review passes (≤3 attempts), PM acceptance signed off. Epic branch ready for manual merge to `main`. |

## Agent Assignments

| Phase | Role | Agent | Branch |
|---|---|---|---|
| 1 | Developer | Claude B | `feat/.../harness` |
| 1 | Tester | Claude C | `test/.../harness-<tester>-<ts>` |
| 2 | Developer | Claude B | `feat/.../tester-verification` |
| 2 | Tester | Claude C | `test/.../tester-verification-<tester>-<ts>` |
| 3 | Developer | Claude B | `feat/.../loop-guard` |
| 3 | Tester | Claude C | `test/.../loop-guard-<tester>-<ts>` |
| 4 | Developer | Claude B | `feat/.../stage-runner` |
| 4 | Tester | Claude C | `test/.../stage-runner-<tester>-<ts>` |
| 5 | Developer | Claude B | `feat/.../e2e` |
| 5 | Tester | Claude C | `test/.../e2e-<tester>-<ts>` |
| 6 | Lead Review | Claude A | epic branch |
| 6 | Codex Review | Codex B | epic branch |
| 6 | PM Acceptance | Codex A | epic branch |

## Validation Plan

| Gate | Entry Condition | Exit Criteria | Verifier |
|---|---|---|---|
| Phase 1 → 2 | Phase 1 dev report exists, tester approved | Harness script merged to epic; utilities working | Claude A lead review |
| Phase 2 → 3 | Phase 2 test report posted with passing results | Tester real-mode verified; report schema validated | Claude A lead review |
| Phase 3 → 4 | Loop-guard test report exists | Guard confirmed working for happy path and edge case | Claude A lead review |
| Phase 4 → 5 | Stage-runner integration test report exists | Handoff produces linked dev + test reports | Claude A lead review |
| Phase 5 → 6 | E2E summary report exists; CI config valid | Full suite passes; all artifacts present | Claude A lead review |
| Phase 6 → Merge | Lead review + Codex review + PM acceptance all approved | Review documents signed off; no blocking findings | Claude A orchestrator |

All gates are sequential. Failure at any gate routes back to Claude B (Developer) for a fix branch, then re-tested by Claude C (Tester). After 3 Codex review failures, manual approval is required before continuing.

## Exit Criteria

1. The smoke test entry-point script `scripts/smoke-test-real-claude-tester.ps1` exists and runs all phases to completion (`--all`).
2. All 4 phase-level test suites pass independently.
3. Infinite-loop guard is verified to terminate within configured retry limit.
4. Stage runner handoff produces correctly linked developer and tester reports.
5. End-to-end run produces a consolidated summary report.
6. Claude Lead Review document is approved.
7. Codex Review passes (≤3 attempts).
8. PM Acceptance document is signed off.
9. No trading-sensitive modules were modified.
10. No secrets, API keys, or tokens are stored in the repository.
11. Epic branch is ready for manual merge to `main`.
