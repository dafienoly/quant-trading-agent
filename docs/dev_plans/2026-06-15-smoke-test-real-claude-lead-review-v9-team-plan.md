# Team Plan: Smoke Test Real Claude Lead Review V9

## Objective

Implement and validate the "Claude Lead Review" pipeline stage (`claude_lead_review`) within the agent development pipeline, enabling Claude Code A to perform structured code review as a pipeline gate. This is a docs/pipeline-only feature that adds the review stage infrastructure, agent logic, handoff contracts, and test automation — no trading or execution logic is touched.

## Inputs Reviewed

| Document | Path | Status |
|---|---|---|
| AGENTS.md | `AGENTS.md` | Hard safety invariants confirmed |
| Agent Development Pipeline | `docs/process/AGENT_DEVELOPMENT_PIPELINE.md` | Stage gate model: PM → Arch → Dev → Test → Review → Acceptance |
| Branch Workflow | `docs/process/BRANCH_WORKFLOW.md` | Branch type & naming rules confirmed |
| Agent Automation Architecture | `docs/pipeline/AGENT_AUTOMATION_ARCHITECTURE.md` | Pipeline orchestration model |
| Auto-Merge Policy | `docs/pipeline/AUTO_MERGE_POLICY.md` | Merge gate rules confirmed |
| Requirements | `docs/requirements/2026-06-15-smoke-test-real-claude-lead-review-v9-requirements.md` | Feature requirements |
| Architecture | `docs/design/2026-06-15-smoke-test-real-claude-lead-review-v9-architecture.md` | Module design, interfaces, gates |
| Pipeline State | `.agent/state.json` | Current stage: `pm_pending`, phase 1, claude_first_review mode |

## Scope

1. **Claude Lead Review Pipeline Stage** — implement `claude_lead_review` as a named stage in the team pipeline, with its own stage gate, entry criteria, and exit criteria.
2. **Review Agent Logic** — define what Claude Code A checks during lead review: architecture conformance, safety invariant compliance, code quality, test coverage sufficiency, and handoff completeness.
3. **Handoff Contract** — specify the input/output artifacts for the lead review stage (input: dev report + test report; output: review report + pass/fail decision).
4. **Phase Gating** — after each phase test passes, route back to Claude Code B for the next phase until all phases complete.
5. **Review Report Template** — create the canonical review report format under `docs/review/`.
6. **Self-Test & Smoke Test** — validate the review pipeline with a synthetic phase that exercises the full flow.

## Non-Goals

- NOT implementing any trading, execution, order, risk, or broker logic.
- NOT modifying the merge gate or auto-merge policy.
- NOT weakening manual approval requirements for restricted modules.
- NOT changing existing phase dev or phase test workflows — only adding the review stage.
- NOT introducing new CI/CD pipelines outside of the existing agent automation architecture.
- NOT storing secrets, API keys, or credentials.

## Safety Constraints

1. Current task is docs-only / pipeline-only by default.
2. Do NOT modify trading-sensitive modules: broker, execution, order, account, risk, miniQMT, live trading, real order submission.
3. Do NOT weaken the Merge Gate or bypass manual approval.
4. Do NOT write API keys, tokens, or secrets into the repository.
5. Do NOT auto-merge to main.
6. Do NOT modify policy enforcement or risk controls.

## Proposed Phases

### Phase 1: Pipeline Configuration & Stage Definition

| Attribute | Value |
|---|---|
| **Scope** | Define the `claude_lead_review` stage in the pipeline configuration, entry/exit criteria, stage transitions, and routing rules. Update `.agent/` pipeline state schema to support the new stage. |
| **Owner** | Claude Code A (Lead Planning Agent — via claude_a role) |
| **Branch** | `feat/smoke-test-real-claude-lead-review-v9/pipeline-config` (from epic branch) |
| **Deliverable** | Updated pipeline state schema and stage transition logic in `.agent/state.json`, pipeline configuration under `.agent/pipeline/`. |

**Self-Test Commands:**
```bash
# 1. Validate pipeline state schema
python -c "import yaml; s=yaml.safe_load(open('.agent/state.json')); assert s['stage_status']['claude_lead_review']=='pending'"

# 2. Validate stage list includes claude_lead_review
python -c "assert 'claude_lead_review' in [s['name'] for s in yaml.safe_load(open('.agent/pipeline/stages.yaml'))['stages']]"
```

**Tester Checks:**
- Pipeline state file parses correctly with new stage.
- Stage list contains `claude_lead_review` at correct position (between `phase_test` and `codex_review`).
- Stage transition rules correctly route pass → codex_review, fail → phase_dev.
- No existing stage behavior is altered by the addition.

**Release Criteria:**
- Pipeline validates successfully with the new stage.
- Stage transition logic produces correct next-stage output for both pass and fail cases.

---

### Phase 2: Lead Review Agent Logic

| Attribute | Value |
|---|---|
| **Scope** | Implement the Claude Code A review logic: architecture conformance checks, safety invariant scan, code quality assessment, test coverage check, and handoff completeness validation. Produce `docs/review/2026-06-15-smoke-test-real-claude-lead-review-v9-claude-lead-review.md` as the review report template. |
| **Owner** | Claude Code B (Developer Agent — via claude_b role) |
| **Branch** | `feat/smoke-test-real-claude-lead-review-v9/review-logic` (from epic branch) |
| **Deliverable** | Review agent script (`scripts/pipeline/claude_lead_review.py` or equivalent), review checklist template, review report template. |

**Self-Test Commands:**
```bash
# 1. Run review agent in dry-run mode against a known-good dev report + test report
python scripts/pipeline/claude_lead_review.py --dry-run \
  --dev-report docs/dev_reports/2026-06-15-smoke-test-real-claude-lead-review-v9-phase-1-dev-report.md \
  --test-report docs/test_reports/2026-06-15-smoke-test-real-claude-lead-review-v9-phase-1-test-report.md \
  --output docs/review/2026-06-15-smoke-test-real-claude-lead-review-v9-claude-lead-review.md

# 2. Verify review report is generated with correct structure
python -c "import os; f='docs/review/2026-06-15-smoke-test-real-claude-lead-review-v9-claude-lead-review.md'; assert os.path.exists(f); assert '## Review Result' in open(f).read()"
```

**Tester Checks:**
- Review report template contains all required sections: scope reviewed, conformance checklist, safety invariant scan, code quality summary, test coverage assessment, blocking issues list, non-blocking recommendations, overall verdict.
- Dry-run mode produces a valid report without side effects.
- Review logic correctly flags each safety-invariant violation (test with synthetic bad input).
- Review logic correctly passes when all invariants hold.

**Release Criteria:**
- Review agent runs successfully in dry-run mode.
- Review report structure matches the architecture-defined template.
- Synthetic violation test produces correct rejection.
- Clean input produces correct pass verdict.

---

### Phase 3: Phase Gating & Phase Loop Routing

| Attribute | Value |
|---|---|
| **Scope** | Implement the phase loop routing: after each phase test passes, route back to Claude Code B (developer) for the next phase. Integrate with the existing `claude_first_review` team pipeline mode. Update `.agent/current_task.yaml` handoff logic to support multi-phase sequencing. |
| **Owner** | Claude Code C (Test Engineer Agent — via claude_c role) |
| **Branch** | `feat/smoke-test-real-claude-lead-review-v9/phase-gating` (from epic branch) |
| **Deliverable** | Phase loop routing script (`scripts/pipeline/phase_router.py`), updated handoff contract, updated `.agent/current_task.yaml` schema. |

**Self-Test Commands:**
```bash
# 1. Test phase routing: phase 1 test passes → should route to developer for phase 2
python scripts/pipeline/phase_router.py --current-phase 1 --test-result pass --simulate
# Expected output: next_stage=phase_dev, next_phase=2

# 2. Test phase routing: all phases complete → should route to claude_lead_review
python scripts/pipeline/phase_router.py --current-phase 4 --test-result pass --simulate
# Expected output: next_stage=claude_lead_review
```

**Tester Checks:**
- Phase router correctly iterates from phase N to phase N+1 when test passes.
- Phase router correctly routes to `claude_lead_review` when `all_phases_tested=true`.
- Phase router correctly routes to BugFix loop when test fails.
- Handoff contract is updated to include phase number in the handoff payload.
- Backward compatibility: existing single-phase tasks still work.

**Release Criteria:**
- Phase loop routing produces correct next-stage for all phase positions.
- Integration test with 4 synthetic phases completes end-to-end.
- All existing pipeline tests continue to pass.
- Handoff contract schema validates correctly.

---

### Phase 4: End-to-End Smoke Test & Documentation

| Attribute | Value |
|---|---|
| **Scope** | Run a full pipeline run with synthetic phases that exercise: phase dev → phase test → claude lead review → codex review → acceptance. Produce the final documentation set: user guide (`docs/user_guides/`), acceptance report (`docs/acceptance/`), and postmortem if applicable. |
| **Owner** | Claude Code A (Lead Planning Agent — via claude_a role) |
| **Branch** | `feat/smoke-test-real-claude-lead-review-v9/smoke-test` (from epic branch) |
| **Deliverable** | Smoke test results, user guide, acceptance report. |

**Self-Test Commands:**
```bash
# 1. Run full pipeline smoke test
python scripts/pipeline/smoke_test.py --mode claude_first_review --stages phase_dev,phase_test,claude_lead_review,codex_review,acceptance

# 2. Verify all stage reports exist
python -c "
import glob, os
reports = glob.glob('docs/dev_reports/*.md') + glob.glob('docs/test_reports/*.md') + glob.glob('docs/review/*.md') + glob.glob('docs/acceptance/*.md')
print(f'Total reports: {len(reports)}')
assert len(reports) >= 5
"
```

**Tester Checks:**
- Full pipeline run completes without error.
- Each stage produces the correct deliverable artifact.
- Review verdict correctly gates progression to acceptance.
- User guide documents the lead review flow end-to-end.
- Acceptance report confirms all requirements met.
- Handoff traceability: each stage's output is referenced by the next stage's input.

**Release Criteria:**
- Full smoke test passes with no blocking issues.
- All documentation artifacts are complete and consistent.
- Pipeline state reflects `stage_status.claude_lead_review = completed`.
- Codex review (if applicable) passes with no blocking findings.

## Agent Assignments

| Agent | Role | Phases | Deliverables |
|---|---|---|---|
| Claude Code A (claude_a) | Lead Planning / Lead Review | Phase 1 (Pipeline Config), Phase 4 (Smoke Test) | `.agent/pipeline/` config, smoke test, user guide, acceptance report |
| Claude Code B (claude_b) | Developer Agent | Phase 2 (Review Logic) | Review agent script, review report template |
| Claude Code C (claude_c) | Test Engineer Agent | Phase 3 (Phase Gating) | Phase routing script, handoff contract update |
| Codex B (codex_b) | Architect Reviewer | After all phases | Codex review report (`docs/review/r1/`) |
| Codex A (codex_a) | PM Acceptance Agent | After review passes | Acceptance report (`docs/acceptance/`) |

## Execution Flow

```
Phase 1 (Claude A) ──self-test──> Phase 1 Test (Claude C)
    │ pass                              │
    └────────────────────────────────────┘
    │
    ▼
Phase 2 (Claude B) ──self-test──> Phase 2 Test (Claude C)
    │ pass                              │
    └────────────────────────────────────┘
    │
    ▼
Phase 3 (Claude C) ──self-test──> Phase 3 Test (Claude C)
    │ pass                              │
    └────────────────────────────────────┘
    │
    ▼
Phase 4 (Claude A) ──self-test──> Phase 4 Test (Claude C)
    │ pass                              │
    └────────────────────────────────────┘
    │
    ▼
Claude Lead Review (Claude A) ──pass──> Codex Review (Codex B) ──pass──> Acceptance (Codex A)
```

**Failback paths:**
- Any phase test fails → route back to Claude Code B (or the phase owner) for fix, then re-test.
- Claude Lead Review fails → route back to the failing phase's developer.
- Codex Review fails → up to 3 retry attempts per `max_codex_review_attempts`, then manual approval.
- Acceptance fails → route back to requirements for PM re-evaluation.

## Validation Plan

### Per-Phase Validation

Each phase must pass three validations before proceeding:

1. **Self-Test** — the phase owner runs validation commands and reports results in `docs/dev_reports/YYYY-MM-DD-feature-phase-N-dev-report.md`.
2. **Tester Check** — Claude Code C runs independent verification and reports in `docs/test_reports/YYYY-MM-DD-feature-phase-N-test-report.md`.
3. **Artifact Integrity** — all expected files exist and parse correctly.

### Cross-Phase Validation

- Handoff artifact chain is complete (each stage references prior stage's deliverables).
- No stage's output contradicts a prior stage's constraints.
- All safety invariants from AGENTS.md are checked at every stage.

### Smoke Test Validation

- Full pipeline run with 4 synthetic phases exercises all stage transitions.
- Review gate correctly blocks on deliberate violation injection.
- Phase loop correctly routes through all 4 phases and into review stage.

## Exit Criteria

The feature is complete and ready for Codex review when all of the following are true:

| # | Criterion | Verification |
|---|---|---|
| 1 | All 4 phases are implemented and self-tested | Dev reports exist for all phases |
| 2 | All 4 phases pass tester verification | Test reports exist for all phases |
| 3 | Claude Lead Review stage produces a passing review report for all phases | `docs/review/2026-06-15-smoke-test-real-claude-lead-review-v9-claude-lead-review.md` exists with `## Review Result: PASS` |
| 4 | Phase loop routing correctly sequences all 4 phases | Smoke test log shows phase 1→2→3→4→review |
| 5 | Pipeline state reflects `stage_status.claude_lead_review = completed` | `.agent/state.json` validated |
| 6 | No trading-sensitive modules were modified | `git diff epic/main -- broker/ execution/ order/ account/ risk/ miniQMT/` is empty |
| 7 | No secrets or credentials in the repository | `git diff --name-only` checked for `.env`, `*.key`, `credentials*` |
| 8 | All documentation artifacts are present | Files exist under `docs/design/`, `docs/dev_reports/`, `docs/test_reports/`, `docs/review/`, `docs/acceptance/`, `docs/user_guides/` |
| 9 | Full smoke test passes | Smoke test exit code 0 |
| 10 | Feature branch is up to date with epic branch | `git merge-base --is-ancestor origin/epic/... HEAD` returns 0 |
