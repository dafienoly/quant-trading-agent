# historical-pr-triage-pr-2-and-pr-3 Architecture

## Architecture Summary

This design defines a controlled, document-driven triage workflow for historical GitHub PR #2 and PR #3 in the `quant-trading-agent` repository. The workflow is evidence-first: it inspects historical PR metadata, diffs, comments, CI status, current repository compatibility, safety impact, and test coverage before recommending whether either PR should be adopted, partially preserved, redesigned, rejected, or deferred.

No production code, tests, trading logic, pipeline state, branch history, or policy documents are modified by this architecture stage. Historical PR content is not accepted by default. Every recommendation must be traceable to recorded evidence and must preserve the repository's trading safety invariants, branch workflow, development pipeline, auto-merge policy, and current product boundaries.

The downstream implementation is a triage documentation task, not a code-adoption task. Any future adoption of useful historical content from PR #2 or PR #3 must become separate scoped development work with requirements, architecture review, tests, development report, independent test report, review, and acceptance evidence.

Target architecture output path:

`docs/design/2026-06-18-historical-pr-triage-pr-2-and-pr-3-architecture.md`

Required downstream artifacts:

- Team plan: `docs/dev_plans/20260618-historical-pr-triage-pr-2-and-pr-3-team-plan.md`
- Phase development reports: `docs/dev_reports/20260618-historical-pr-triage-pr-2-and-pr-3-phase-<n>-dev-report.md`
- Phase test reports: `docs/test_reports/20260618-historical-pr-triage-pr-2-and-pr-3-phase-<n>-test-report.md`
- Claude lead review: `docs/review/20260618-historical-pr-triage-pr-2-and-pr-3-claude-lead-review.md`
- Codex review: `docs/review/20260618-historical-pr-triage-pr-2-and-pr-3-codex-review-r1.md`
- Acceptance: `docs/acceptance/20260618-historical-pr-triage-pr-2-and-pr-3-acceptance.md`

## Module Plan

This feature does not introduce new runtime modules. It operates through repository inspection, GitHub PR inspection, and documentation artifacts.

The workflow boundaries are:

| Area | Role in this feature | Allowed actions | Disallowed actions |
|---|---|---|---|
| GitHub PR #2 and #3 | Historical evidence source | Inspect metadata, diff, files, comments, CI, merge state | Merge, close, rebase, cherry-pick, push changes |
| Current repository | Compatibility and safety reference | Inspect file tree, policies, current module boundaries | Modify production code or tests during triage |
| `docs/requirements/` | PM source of truth | Read requirement document | Rewrite requirements in architecture stage |
| `docs/design/` | Architecture output | Produce architecture document | Add sprint-specific root instructions |
| `docs/dev_reports/` | Developer evidence | Record triage evidence in phase reports | Claim implementation success without evidence |
| `docs/test_reports/` | Independent verification | Record verification results | Approve without reproducible evidence |
| Restricted modules | Safety-sensitive review areas | Identify impact and require follow-up review/tests | Change or weaken behavior during triage |

Restricted or safety-sensitive areas include:

- `src/risk_engine/`
- `src/execution_engine/`
- `src/data_gateway/`
- `src/backtest_engine/`
- `src/factor_engine/`
- `src/strategy_engine/`
- `src/stock_pool/`
- `src/api/`
- `src/product_app/`
- `src/ui_report/`
- Pipeline, automation, branch, or auto-merge policy files

### Evidence Model

Each PR must produce a structured triage record with this shape:

```yaml
pr_number:
title:
author:
source_branch:
base_branch:
state:
merged:
mergeable_state:
created_at:
updated_at:
changed_files:
diff_summary:
comments_summary:
review_summary:
ci_summary:
current_applicability:
restricted_modules_touched:
safety_impact:
secret_scan_result:
test_coverage_assessment:
compatibility_risks:
operational_risks:
recommended_disposition:
manual_approval_required:
required_follow_up:
closure_or_rework_recommendation:
evidence_links:
```

### Classification Outcomes

Each PR must be classified independently as exactly one of:

- `ADOPT_AS_IS`
- `ADOPT_WITH_CHANGES`
- `PARTIAL_ADOPT`
- `REJECT`
- `NEEDS_MORE_INFO`

Disposition rules:

| Condition | Required disposition behavior |
|---|---|
| PR contains secrets or committed credentials | `REJECT` until remediated and documented |
| PR bypasses risk, execution, stock-pool, human confirmation, or fail-closed behavior | `REJECT` or `ADOPT_WITH_CHANGES` only after redesign |
| PR touches restricted modules | Manual approval flag plus architecture review and negative tests before adoption |
| PR is obsolete but contains useful intent | `PARTIAL_ADOPT` or `ADOPT_WITH_CHANGES` |
| PR is incompatible with current architecture | Reimplementation preferred over direct adoption |
| PR evidence is unavailable or inconclusive | `NEEDS_MORE_INFO` |
| PR is docs-only and still valid | May be `ADOPT_AS_IS` if no policy conflict exists |

### Phase Slices

Phase 1: Evidence Collection

Owner: Claude Team B  
Verifier: Claude Team C

Scope:

- Inspect PR #2 metadata, files, diff, comments, reviews, CI, and merge state.
- Inspect PR #3 metadata, files, diff, comments, reviews, CI, and merge state.
- Record evidence without modifying repository code.
- Check changed paths against restricted-module list.
- Check diffs and comments for secrets or unsafe credential handling.

Expected output:

- Phase 1 development report with raw evidence summary.
- No code changes.
- No adoption decision beyond preliminary evidence labels.

Phase 2: Compatibility and Safety Analysis

Owner: Claude Team B  
Verifier: Claude Team C

Scope:

- Compare each PR against current repository layout and architecture boundaries.
- Identify obsolete paths, removed APIs, renamed modules, or product direction conflicts.
- Identify impact on live data, signal generation, execution, risk, stock-pool filtering, backtesting, API contracts, UI behavior, automation workflow, and auto-merge policy.
- Mark manual approval requirements where applicable.

Expected output:

- Phase 2 development report with applicability and safety matrix.
- Phase 2 test report verifying evidence completeness and conservative safety handling.

Phase 3: Disposition and Handoff Package

Owner: Claude Team B  
Verifier: Claude Team C  
Lead review: Claude Team A

Scope:

- Assign final recommended disposition for PR #2.
- Assign final recommended disposition for PR #3.
- Identify selected reusable content, if any.
- Define follow-up implementation tasks, if any.
- Recommend safe closure, superseding, rework, or additional investigation.
- Produce final user-facing triage summary.

Expected output:

- Phase 3 development report.
- Phase 3 test report.
- Claude lead review.
- Codex review input.
- Acceptance-ready disposition summary.

## Technical Decisions

1. Triage is documentation-first.

Historical PR content must not be merged, cherry-picked, rebased, copied into production files, or used to modify behavior during this feature. The only permitted outputs are design, plan, report, review, and acceptance documents.

2. GitHub PR evidence is the primary source for historical content.

The workflow should inspect PR metadata, diff, changed files, comments, reviews, CI checks, and merge discussion where available. If GitHub evidence is unavailable, the PR must not be assumed safe.

3. Current repository policy is the authority.

PR #2 and PR #3 must be evaluated against current repository rules, especially:

- Root `AGENTS.md`
- `docs/process/AGENT_DEVELOPMENT_PIPELINE.md`
- `docs/process/BRANCH_WORKFLOW.md`
- `docs/pipeline/AGENT_AUTOMATION_ARCHITECTURE.md`
- `docs/pipeline/AUTO_MERGE_POLICY.md`
- `docs/policy/RISK_POLICY.md` when safety impact exists
- `docs/policy/EXECUTION_POLICY.md` when execution impact exists

4. Unknown safety impact is treated conservatively.

If a PR may affect trading behavior but evidence is incomplete, mark the relevant area as safety-sensitive and require follow-up architecture review, tests, and manual approval before adoption.

5. Historical implementation and historical intent are separate.

A PR may contain a useful idea even if the patch is obsolete. The triage must distinguish:

- Reusable historical code
- Reusable tests
- Reusable documentation
- Reusable intent requiring reimplementation
- Unsafe or obsolete content that should be rejected

6. Secret handling is a hard gate.

Any PR content containing `.env` material, API keys, tokens, cookies, broker credentials, account credentials, private endpoints, or unsafe credential storage must be rejected until remediated. The report must record the finding without reproducing secret values.

7. Direct adoption requires the strongest evidence.

`ADOPT_AS_IS` is allowed only when the PR is still compatible, has no safety or policy conflict, has adequate tests or is docs-only, does not touch restricted modules, and does not introduce migration or operational risk.

8. Restricted-module touch requires negative testing before future adoption.

Any future implementation derived from historical PRs that touches restricted modules must include targeted negative tests for fail-closed behavior, veto behavior, policy enforcement, invalid inputs, and unsafe bypass attempts.

### Triage Algorithm Pseudocode

```text
for pr_number in [2, 3]:
    evidence = collect_pr_evidence(pr_number)

    if evidence.unavailable:
        classify(pr_number, NEEDS_MORE_INFO)
        record_required_follow_up("Recover PR metadata/diff/comments/CI evidence")
        continue

    changed_areas = map_changed_files_to_current_modules(evidence.changed_files)
    restricted_hits = detect_restricted_modules(changed_areas)
    safety_hits = detect_safety_sensitive_behavior(evidence.diff_summary, changed_areas)
    secret_hits = scan_for_secret_indicators(evidence.diff, evidence.comments)

    applicability = compare_to_current_repo(evidence.changed_files, evidence.diff_summary)
    tests = assess_test_coverage(evidence.changed_files, evidence.diff_summary)
    policy_conflicts = compare_against_current_policy(evidence, changed_areas)

    if secret_hits.present:
        disposition = REJECT
        follow_up = "Remediate secret exposure and document incident before any adoption"
    else if policy_conflicts.blocking or safety_hits.bypass_detected:
        disposition = REJECT
        follow_up = "Redesign under current architecture and safety policies"
    else if evidence.incomplete_for_decision:
        disposition = NEEDS_MORE_INFO
        follow_up = "Collect missing evidence"
    else if applicability.directly_compatible and tests.adequate and no restricted_hits and no safety_hits:
        disposition = ADOPT_AS_IS
        follow_up = "Proceed only through normal development/test/review pipeline"
    else if applicability.partially_compatible and evidence.contains_useful_content:
        disposition = PARTIAL_ADOPT
        follow_up = "Preserve selected intent/tests/docs through scoped follow-up work"
    else if evidence.contains_useful_content:
        disposition = ADOPT_WITH_CHANGES
        follow_up = "Reimplement under current architecture with tests"
    else:
        disposition = REJECT
        follow_up = "Close or supersede historical PR"

    manual_approval_required = (
        restricted_hits.present
        or safety_hits.live_trading
        or safety_hits.execution_policy
        or safety_hits.risk_policy
        or safety_hits.stock_pool
        or safety_hits.live_data_fail_closed
        or safety_hits.auto_merge_policy
    )

    write_structured_triage_record(
        pr_number,
        evidence,
        changed_areas,
        restricted_hits,
        safety_hits,
        applicability,
        tests,
        policy_conflicts,
        disposition,
        manual_approval_required,
        follow_up,
    )
```

### Safety Impact Detection Pseudocode

```text
function detect_safety_sensitive_behavior(diff, changed_areas):
    result = empty_safety_result()

    if changed_areas includes src/risk_engine:
        result.risk_policy = true

    if changed_areas includes src/execution_engine:
        result.execution_policy = true

    if changed_areas includes src/data_gateway or LiveDataService or DataProviderHub:
        result.live_data_fail_closed = true

    if changed_areas includes src/stock_pool:
        result.stock_pool = true

    if changed_areas includes src/strategy_engine or signal generation paths:
        result.signal_generation = true

    if changed_areas includes src/backtest_engine:
        result.backtest_assumptions = true

    if changed_areas includes automation, branch, or auto-merge policy files:
        result.auto_merge_policy = true

    if diff suggests direct broker submission, human confirmation bypass, LEVEL_3_AUTO exposure,
       demo fallback as live data, direct LLM buy/sell decision, or missing risk veto:
        result.bypass_detected = true

    return result
```

## Safety Impact

This architecture preserves all hard safety invariants by preventing direct adoption during triage and by requiring conservative classification where impact is unclear.

Hard gates:

- No real automatic trading may be introduced.
- Risk Agent veto behavior must not be weakened.
- Execution checks and human confirmation must not be bypassed.
- Stock-pool filtering must not be bypassed.
- Data source failure must continue to block trading by default.
- Demo, mock, and paper trading must not be represented as real live trading.
- `LEVEL_3_AUTO` must not be exposed as a casual user-selectable option.
- LLM output must not directly decide buy or sell actions.
- Secrets must not be committed, copied, reproduced in reports, or adopted.
- Backtest changes must preserve commission, slippage, limit-up/down, and suspension handling.

Manual approval is required before any future adoption if either PR affects:

- Live trading
- Broker execution
- Human confirmation
- Risk policy
- Execution policy
- Stock-pool filtering
- Live data fail-closed behavior
- Provider fallback behavior
- Signal generation
- Auto-merge policy
- Restricted modules

Safety classification for each PR must use this matrix:

| Safety level | Meaning | Required handling |
|---|---|---|
| `NO_TRADING_IMPACT` | Docs, tests, or tooling with no runtime trading behavior | Normal pipeline evidence |
| `INDIRECT_TRADING_IMPACT` | Changes supporting research, UI, API, or automation that may affect trading decisions | Compatibility review and targeted tests |
| `RESTRICTED_MODULE_IMPACT` | Touches restricted modules | Architecture review, negative tests, manual approval if policy-sensitive |
| `DIRECT_TRADING_IMPACT` | Affects orders, execution, risk, live data, stock pools, or signals | Manual approval, safety tests, independent verification |
| `UNKNOWN_TRADING_IMPACT` | Evidence incomplete or ambiguous | Treat as blocked pending more information |

Secret handling:

- Reports may state that secret-like material was found.
- Reports must not quote or reproduce secret values.
- Any secret exposure must block direct adoption.
- Follow-up must include remediation documentation before further work.

## Development Guidance

Claude Team A, B, and C must treat this as a triage and evidence workflow. Do not modify production code, tests, trading modules, or policy behavior while executing this feature.

### Claude Team A Handoff Guidance

Claude Team A owns team planning, phase coordination, and lead review.

Responsibilities:

- Create the team plan at `docs/dev_plans/20260618-historical-pr-triage-pr-2-and-pr-3-team-plan.md`.
- Split work into the three phases defined in this architecture.
- Ensure Claude Team B does not perform implementation adoption.
- Ensure Claude Team C verifies evidence completeness and safety classification.
- Perform final lead review after all phase test reports are complete.
- Confirm that PR #2 and PR #3 each have an independent disposition.
- Confirm that manual approval flags are present where required.
- Confirm that final outputs support Codex review and PM acceptance.

Team A must reject the handoff if:

- PR #2 and PR #3 are combined into a single undifferentiated decision.
- Any historical PR content is adopted without separate development and test evidence.
- Safety-sensitive impact is marked safe without evidence.
- Missing GitHub evidence is treated as approval.
- Secret exposure is reproduced in reports.

### Claude Team B Handoff Guidance

Claude Team B owns development-stage triage evidence and report creation.

Allowed work:

- Inspect PR metadata, diffs, files, comments, review state, CI, and merge status.
- Inspect current repository structure and policy documents.
- Compare historical changed files to current module boundaries.
- Produce phase development reports.
- Recommend disposition based on evidence.

Disallowed work:

- Do not merge, cherry-pick, rebase, or close PR #2 or PR #3.
- Do not edit production code.
- Do not edit tests to preserve historical behavior.
- Do not modify risk, execution, stock-pool, provider, signal, API, UI, or pipeline behavior.
- Do not expose or copy secrets into reports.

Suggested development report structure:

```markdown
# historical-pr-triage-pr-2-and-pr-3 Phase <n> Development Report

## Scope
## Requirement and Architecture References
## PR #2 Evidence
## PR #2 Applicability and Safety Analysis
## PR #2 Recommended Disposition
## PR #3 Evidence
## PR #3 Applicability and Safety Analysis
## PR #3 Recommended Disposition
## Changed Files
## Commands and Results
## Skipped or Unavailable Evidence
## Remaining Risks
## Real Trading Capability Impact
## Safety Confirmation
```

Development reports must explicitly state:

- Whether real trading capability is affected.
- Whether risk, stock-pool filtering, human confirmation, and fail-closed behavior were bypassed.
- Whether restricted modules were touched by the historical PR.
- Whether tests exist or are required before future adoption.
- Whether manual approval is required.

### Claude Team C Handoff Guidance

Claude Team C owns independent verification.

Required verification:

- Re-check that PR #2 and PR #3 evidence exists and is independently summarized.
- Verify changed-file summaries against PR diffs.
- Verify restricted-module classification.
- Verify safety-sensitive impact classification.
- Verify secret-scan result is recorded without exposing values.
- Verify test coverage assessment is present.
- Verify disposition follows the rules in this architecture.
- Verify no production code was modified by the triage phase.
- Verify no branch workflow or auto-merge rules were bypassed.

Test Engineer branch behavior must follow `docs/process/BRANCH_WORKFLOW.md`. If a temporary local test branch is required, create it from the current development branch, perform verification, return to the original branch, and delete the temporary branch.

Suggested test report structure:

```markdown
# historical-pr-triage-pr-2-and-pr-3 Phase <n> Test Report

## Requirement, Architecture, and Development Report References
## Test Environment
## Test Scope
## Out-of-Scope Items
## Requirement Coverage Matrix
## PR #2 Verification
## PR #3 Verification
## Commands and Results
## API/UI/CLI/Data-Source Smoke Evidence
## Defects
## Feedback Bug Files
## Remaining Risk
## Final Result
```

Final result must be one of:

- `PASS`
- `PASS_WITH_NOTES`
- `REJECTED`

Use `REJECTED` if:

- A PR disposition lacks evidence.
- Restricted or safety-sensitive impact is missed.
- Secret exposure is mishandled.
- The workflow modifies production code during triage.
- Historical content is accepted without pipeline evidence.
- PR #2 and PR #3 are not assessed independently.

### Required Test Strategy

Because this feature is documentation and triage oriented, tests are evidence-verification checks rather than runtime unit tests.

Minimum checks:

```bash
git status --short --branch
git diff --stat
git diff --check
```

Evidence checks:

- Confirm PR #2 metadata is recorded.
- Confirm PR #2 changed files are recorded.
- Confirm PR #2 comments/reviews/CI are recorded or marked unavailable.
- Confirm PR #2 safety impact is classified.
- Confirm PR #2 disposition is one of the allowed values.
- Confirm PR #3 metadata is recorded.
- Confirm PR #3 changed files are recorded.
- Confirm PR #3 comments/reviews/CI are recorded or marked unavailable.
- Confirm PR #3 safety impact is classified.
- Confirm PR #3 disposition is one of the allowed values.
- Confirm manual approval flags are present when required.
- Confirm no production code changes are present in the triage diff.
- Confirm reports do not contain secret values.

Broader runtime tests are not required unless a downstream phase improperly modifies code. If code is modified despite this architecture, Claude Team C must mark the phase `REJECTED` and require return to the correct role boundary.

### Final Triage Output Expectations

The final triage package must include a user-facing summary with:

- Recommended disposition for PR #2.
- Recommended disposition for PR #3.
- Required follow-up work, if any.
- Whether each PR can be safely closed, superseded, reworked, or needs more information.
- Manual approval requirements.
- Residual risk.

The final acceptance stage should be able to determine success by reviewing the requirements document, this architecture document, team plan, phase development reports, phase test reports, Claude lead review, Codex review, and acceptance document without needing unstated oral context.