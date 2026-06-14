# Team Plan: Smoke Test Real Claude Lead Plan V6

## Objective

Validate the end-to-end Claude-first team pipeline (PM → Architecture → Team Plan → Phase Dev → Phase Test → Lead Review → Codex Review → Acceptance → Merge) using a lightweight, zero-risk smoke test feature. The smoke test exercises every pipeline gate with a minimal docs-only change so that real feature development can proceed with confidence that the automation wiring, handoff contracts, branch workflow, merge gates, and agent routing all function correctly.

## Inputs Reviewed

| Input | Source |
|---|---|
| Requirements doc | `docs/requirements/2026-06-14-smoke-test-real-claude-lead-plan-v6-requirements.md` |
| Architecture doc | `docs/design/2026-06-14-smoke-test-real-claude-lead-plan-v6-architecture.md` |
| AGENTS.md | Repository root |
| AGENT_DEVELOPMENT_PIPELINE.md | `docs/process/` |
| BRANCH_WORKFLOW.md | `docs/process/` |
| AGENT_AUTOMATION_ARCHITECTURE.md | `docs/pipeline/` |
| AUTO_MERGE_POLICY.md | `docs/pipeline/` |
| Pipeline state | `.agent/state.json` |
| Current task state | `.agent/current_task.yaml` |
| Codex A PM handoff | `.agent/handoff/claude_lead_plan.md` (input context) |
| Codex B Architect handoff | `.agent/handoff/codex_architect.md` |

## Scope

**In scope:**
- Define 4 incremental phases that each test a subset of the pipeline stages.
- Each phase produces a verifiable artifact (document or report) with zero production code changes.
- Exercise the full cycle: epic branch → feat branch → dev report → test report → review → acceptance.
- Produce canonical deliverables under `docs/dev_plans/`, `docs/dev_reports/`, `docs/test_reports/`, `docs/review/`, `docs/acceptance/`.
- Validate branch creation, handoff routing, merge-gate detection, and manual-approval gating.
- All phases are docs-only; no trading, broker, order, risk, or execution code is touched.

**Out of scope / Non-goals:**
- No real trading code, strategy changes, or market data modifications.
- No modification to pipeline automation scripts or GitHub Actions workflows.
- No changes to CI/CD secrets, environment config, or deploy infrastructure.
- No performance, load, or security testing — smoke test only.
- No modification of risk policies, execution policies, or stock pool filters.
- No weakening of the merge gate or auto-merge enablement.

## Non-Goals

- The smoke test is NOT a production feature; it is a pipeline-integrity validation.
- It does NOT produce user-facing functionality.
- It makes NO changes to `src/`, `tests/`, `config/`, `scripts/`, or any runtime directory.
- It does NOT require deployment, database migrations, or external service integration.

## Safety Constraints

1. **Docs-only / pipeline-only:** All phase work is limited to `docs/` and `.agent/` directories. No source code, tests, or configuration files are created or modified.
2. **No trading module access:** Do NOT create, modify, or reference files under broker/, execution/, order/, account/, risk/, miniQMT/, or any live-trading path.
3. **No merge-gate weakening:** Do NOT alter `.github/workflows/`, merge policies, or auto-merge configuration. All merges require manual approval as specified in `AUTO_MERGE_POLICY.md`.
4. **No secrets exposure:** Do NOT write API keys, tokens, passwords, or credentials into any file.
5. **No auto-merge to main:** The epic branch must not auto-merge to main. Merge requires manual approval per the pipeline state's `manual_approval_required_for` list.
6. **No policy modification:** Do NOT modify `RISK_POLICY.md`, `EXECUTION_POLICY.md`, or any enforcement logic.
7. **All changes traceable:** Every commit must reference the feature issue (#22) and the phase number.

## Proposed Phases

### Phase 1 — Pipeline Scaffold & Handoff Validation

| Attribute | Detail |
|---|---|
| **Scope** | Validate that the team plan can be produced, stored, and routed to Claude B for development. Exercise the `claude_lead_plan` → `phase_dev` handoff contract. |
| **Owner** | Claude A (Lead Planner) |
| **Branch** | `feat/smoke-test/phase-1-scaffold` (from epic branch) |
| **Artifacts** | `docs/dev_plans/2026-06-14-smoke-test-real-claude-lead-plan-v6-team-plan.md` (this document); Phase 1 handoff marker in `.agent/state.json` |
| **Self-test** | 1. Confirm `docs/dev_plans/` directory exists and team plan is valid Markdown with all required sections (Objective, Inputs Reviewed, Scope, Non-Goals, Safety Constraints, Proposed Phases, Agent Assignments, Validation Plan, Exit Criteria). 2. Confirm no source files outside `docs/` or `.agent/` were created or modified. 3. Confirm plan embeds all 6 safety constraints. |
| **Tester checks** | 1. Verify all Inputs Reviewed are actually readable at the paths listed. 2. Verify Phase 2's branch and owner are correctly specified. 3. Verify exit criteria are measurable. |
| **Release criteria** | Team plan document exists at correct path; Phase 1 staged and committed on correct branch; handoff to Claude B succeeds. |

### Phase 2 — Developer Phase & Dev Report

| Attribute | Detail |
|---|---|
| **Scope** | Claude B executes a minimal docs-only development task: create a Phase 2 dev report that logs the handoff receipt and validates the developer toolchain. |
| **Owner** | Claude B (Developer Agent) |
| **Branch** | `feat/smoke-test/phase-2-dev-report` (from epic branch) |
| **Artifacts** | `docs/dev_reports/2026-06-14-smoke-test-real-claude-lead-plan-v6-phase-2-dev-report.md` |
| **Self-test** | 1. Dev report contains: handoff receipt confirmation, branch used, list of files created/modified, self-test results, and any risks noted. 2. No source files touched. 3. Commit message references issue #22 and phase 2. |
| **Tester checks** | 1. Confirm dev report accurately describes what was done. 2. Confirm no unintended file modifications. 3. Run `git diff epic/<date>...feat/smoke-test/phase-2-dev-report` — only expected docs/report files differ. |
| **Release criteria** | Dev report committed on correct feat branch; handoff to Claude C (tester) succeeds. |

### Phase 3 — Test Phase & Test Report

| Attribute | Detail |
|---|---|
| **Scope** | Claude C receives the Phase 2 dev report, creates a temporary test branch, and produces a test report verifying the Phase 2 deliverable against the architecture and requirements. |
| **Owner** | Claude C (Test Engineer Agent) |
| **Branch** | `test/smoke-test/phase-3-test-<tester>-<timestamp>` (local temporary, from epic branch) |
| **Artifacts** | `docs/test_reports/2026-06-14-smoke-test-real-claude-lead-plan-v6-phase-3-test-report.md` |
| **Self-test** | 1. Test report contains: test scope, test cases executed, results (pass/fail) for each, bug list (if any), and overall verdict. 2. At least 3 test cases covering: artifact existence, content correctness, safety constraint compliance. 3. If bugs found, they are documented in `feedback/bugs/open/`. |
| **Tester checks** | 1. Re-run all test cases from the report and confirm results. 2. Verify no bugs were missed (spot-check architecture doc vs dev report alignment). 3. Confirm test branch was temporary and cleaned up. |
| **Release criteria** | Test report committed; test branch cleaned up; handoff to Claude A (Lead Review) succeeds. |

### Phase 4 — Review, Acceptance & Merge Gate

| Attribute | Detail |
|---|---|
| **Scope** | Claude A performs lead review; Codex B performs codex review; Codex A performs PM acceptance. Validate the review/acceptance artifact chain and the merge-gate mechanism. |
| **Owner** | Claude A (Lead Review) → Codex B (Architect Reviewer) → Codex A (PM Acceptance) |
| **Branch** | Reviews recorded on epic branch directly; any fix branches use `fix/smoke-test/<issue>` |
| **Artifacts** | `docs/review/2026-06-14-smoke-test-real-claude-lead-plan-v6-claude-lead-review.md`, `docs/review/2026-06-14-smoke-test-real-claude-lead-plan-v6-codex-review-r1.md`, `docs/acceptance/2026-06-14-smoke-test-real-claude-lead-plan-v6-acceptance.md` |
| **Self-test** | 1. Lead review documents phase completeness, safety compliance, and any blocking issues. 2. Codex review verifies architecture consistency across all phases. 3. PM acceptance confirms all smoke-test objectives met. 4. If any review fails, a fix branch is created and the phase loops. |
| **Tester checks** | 1. Confirm all required review artifacts exist. 2. Verify acceptance sign-off is explicit ("Accepted" or "Rejected" with rationale). 3. Confirm merge gate was triggered (manual approval required per pipeline state). |
| **Release criteria** | All reviews passed; acceptance signed off; merge gate acknowledged (manual approval pending per policy); branch ready for Owner merge. |

## Agent Assignments

| Phase | Role | Agent | Responsibility |
|---|---|---|---|
| 1 | Lead Planner | Claude A | Produce team plan, define phases, assign agents, set exit criteria |
| 2 | Developer | Claude B | Execute dev task, produce dev report, self-test |
| 3 | Test Engineer | Claude C | Produce test report, verify artifact correctness, log bugs |
| 4a | Lead Reviewer | Claude A | Review all phase artifacts, document completeness |
| 4b | Architect Reviewer | Codex B | Architecture consistency review, codex review report |
| 4c | PM Acceptance | Codex A | Functional acceptance against requirements doc |
| — | Codex Review (backup) | Codex B | Up to 3 review attempts if initial review fails |

### Handoff routing

- After each phase's release criteria are met, route back to the pipeline dispatcher so it can invoke the next agent.
- Phase 1 → Claude B (phase_dev)
- Phase 2 → Claude C (phase_test)
- Phase 3 → Claude A (claude_lead_review)
- Phase 4a → Codex B (codex_review)
- Phase 4b → Codex A (acceptance)
- Phase 4c → Owner (manual merge)

## Validation Plan

| Check | When | How |
|---|---|---|
| Artifact existence | After each phase | Confirm file exists at expected path; file is non-empty valid Markdown |
| Content correctness | Phase 3 (test) | Compare each artifact against architecture doc requirements |
| Safety compliance | Phase 3, Phase 4a | Grep for any modified files outside `docs/` and `.agent/`; confirm no trading paths touched |
| Branch isolation | Phase 3 | Confirm feat/test branches are based on epic, not on main |
| Handoff contract | Phase 2, 3, 4 | Verify handoff files in `.agent/handoff/` contain expected stage markers |
| Merge gate | Phase 4c | Confirm merge gate is triggered and manual approval is required |
| Pipeline state | Continuous | `.agent/state.json` stage_status fields advance correctly after each phase |

## Exit Criteria

All of the following must be true for the smoke test to be considered complete:

1. [ ] Team plan (`docs/dev_plans/`) created and published.
2. [ ] Dev report (`docs/dev_reports/`) created and self-tested.
3. [ ] Test report (`docs/test_reports/`) created with ≥3 test cases, all passing.
4. [ ] Lead review (`docs/review/claude-lead-review.md`) completed with no blocking findings.
5. [ ] Codex review (`docs/review/codex-review-r1.md`) completed with no blocking findings (or ≤3 review attempts exhausted).
6. [ ] PM acceptance (`docs/acceptance/`) signed off as "Accepted".
7. [ ] Zero files modified outside `docs/` and `.agent/` directories.
8. [ ] All commits reference issue #22.
9. [ ] Merge gate triggered; manual approval pending per policy (no auto-merge to main).
10. [ ] Pipeline state (`stage_status`) reflects completion of all stages.
