# Team Plan: Historical PR Triage — PR #2 and PR #3

## Objective

Implement the triage pipeline for two historical pull requests (PR #2 and PR #3) that were left unmerged or incomplete. The triage workflow must: identify each PR's current state, extract its diff and associated issues, run automated compatibility checks against the current `main` branch, produce a triage report per PR, and — if the PR is viable — generate a rebased or reconstructed branch with passing CI checks. All triage artifacts must be stored under `docs/triage/` and linked from the feature acceptance record.

## Inputs Reviewed

| Document | Path |
|---|---|
| Requirements | `docs/requirements/2026-06-18-historical-pr-triage-pr-2-and-pr-3-requirements.md` |
| Architecture | `docs/design/2026-06-18-historical-pr-triage-pr-2-and-pr-3-architecture.md` |
| Pipeline Guide | `docs/pipeline/AGENT_AUTOMATION_ARCHITECTURE.md` |
| Branch Workflow | `docs/process/BRANCH_WORKFLOW.md` |
| Agent Pipeline | `docs/process/AGENT_DEVELOPMENT_PIPELINE.md` |
| Team Pipeline V2 | `docs/pipeline/TEAM_PIPELINE_V2.md` |
| Postmortem (r3 failure) | `docs/postmortems/2026-06-18-historical-pr-triage-pr-2-and-pr-3-r3-failure.md` |

## Scope

1. Build the triage script framework (`scripts/triage/`) with reusable modules: PR-state query, diff extraction, compatibility scan, rebase attempt, report generation.
2. Run triage on **PR #2** — produce triage report, rebased branch, and test results.
3. Run triage on **PR #3** — produce triage report, rebased branch, and test results.
4. Generate a consolidated triage summary and update the epic integration branch.
5. All artifacts pass Claude Lead review and Codex Architect review before acceptance.

## Non-Goals

- Do **not** modify trading-sensitive modules: broker, execution, order, account, risk, miniQMT, live trading, real order submission.
- Do **not** modify merge-gate policies or CI gate logic.
- Do **not** auto-merge any reconstructed branch to `main`.
- Do **not** alter existing issue-tracker entries or close PRs automatically — all triage actions must produce a report for human decision.
- Do **not** modify policy enforcement (`docs/policy/`) or risk controls (`docs/risk/`).
- Do **not** introduce new dependencies outside of what is already in `pyproject.toml` or `requirements.txt`.

## Safety Constraints

1. **Docs-only / pipeline-only by default.** All triage scripts operate on git metadata and diff text; they never read or write real trading state.
2. **No trading-sensitive module access.** Scripts must not import or invoke broker, execution, order, account, or risk modules.
3. **No gate weakening.** The triage pipeline must not alter CI gating, auto-merge rules, or manual-approval requirements.
4. **No secret exposure.** All triage operations use `gh` CLI authenticated via environment; no tokens are embedded in scripts or reports.
5. **No auto-merge to `main`.**
6. **No policy modification.**
7. **All triage branches are temporary.** After acceptance, the epic branch is merged; triage branches may be deleted.
8. **Each PR's rebase attempt must be isolated.** A failed rebase for one PR must not block triage of the other.

## Proposed Phases

### Phase 1 — Triage Framework & Infrastructure

| Field | Value |
|---|---|
| **Scope** | Create `scripts/triage/` directory with the triage engine: `pr_state.py` (query PR metadata, labels, comments, linked issues), `diff_extractor.py` (fetch PR diff, detect merge conflicts with current `main`), `compat_scanner.py` (scan changed files against current module structure, detect deleted/renamed files), `rebase_attempt.py` (attempt `git rebase` onto `main`, report conflict files), `report_generator.py` (produce Markdown triage report with structured sections). Write unit tests for each module under `tests/triage/`. |
| **Owner** | Claude Code B (Developer Agent) |
| **Branch** | `feat/historical-pr-triage/triage-framework` from epic branch |
| **Self-test commands** | `cd scripts/triage && python -m pytest tests/triage/ -v` (all unit tests pass); `python scripts/triage/pr_state.py --help` exits 0; `python scripts/triage/report_generator.py --help` exits 0 |
| **Tester checks** | Test Engineer Agent (Claude Code C) runs: (1) all unit tests pass on clean checkout, (2) each module's CLI entry point accepts `--help`, (3) `diff_extractor` correctly detects a known-conflicting diff injected into a test repo, (4) `rebase_attempt` handles dry-run flag, (5) `report_generator` produces valid Markdown with required sections. |
| **Release criteria** | All self-tests pass; tester report confirms all modules functional; no regressions in `tests/` suite. |
| **Gate after phase** | Route back to Claude Code A (Lead) for phase-complete sign-off, then proceed to Phase 2. |

### Phase 2 — PR #2 Triage Execution

| Field | Value |
|---|---|
| **Scope** | Run the triage framework against PR #2. Tasks: (1) Query PR #2 metadata (author, date, labels, linked issue, last commit sha, CI status), (2) Extract diff against `main` at PR-creation time, (3) Attempt rebase onto current `main`, record conflict files if any, (4) Run compatibility scan on all changed files, (5) Generate triage report `docs/triage/PR-2-triage-report.md` with sections: Summary, Author & Date, Diff Statistics, Rebase Result (success/fail + conflict list), Compatibility Scan, Recommendation (Merge / Close / Needs Discussion), (6) If rebase succeeds, create branch `triage/pr-2-reconstructed` from successful rebase and push, (7) If rebase fails, create a conflict-annotated diff patch at `docs/triage/PR-2-conflict.patch`. |
| **Owner** | Claude Code B (Developer Agent) |
| **Branch** | `feat/historical-pr-triage/pr-2-triage` from epic branch |
| **Self-test commands** | `python scripts/triage/run_triage.py --pr 2 --output docs/triage/PR-2-triage-report.md` exits 0; report file exists and is valid Markdown; `python -c "import yaml; yaml.safe_load(open('docs/triage/PR-2-triage-report.md'))"` (if YAML frontmatter required) |
| **Tester checks** | Test Engineer Agent (Claude Code C) verifies: (1) Report is generated at correct path, (2) All required sections present, (3) Diff statistics are consistent with `gh pr diff 2`, (4) Rebase result section accurately reflects real git state, (5) No trading modules were imported during execution, (6) If a reconstructed branch was created, it exists and `git log` shows the correct commit ancestry. |
| **Release criteria** | Report generated and validated; reconstructed branch or conflict patch available; tester confirms no safety violations. |
| **Gate after phase** | Route back to Claude Code A for review; proceed to Phase 3 upon sign-off. |

### Phase 3 — PR #3 Triage Execution

| Field | Value |
|---|---|
| **Scope** | Run the same triage framework against PR #3. Tasks mirror Phase 2: (1) Query metadata, (2) Extract diff, (3) Attempt rebase, (4) Compatibility scan, (5) Generate report `docs/triage/PR-3-triage-report.md`, (6) Create reconstructed branch `triage/pr-3-reconstructed` or conflict patch. The framework must already handle both PRs; this phase exercises the same pipeline on a second PR. |
| **Owner** | Claude Code B (Developer Agent) |
| **Branch** | `feat/historical-pr-triage/pr-3-triage` from epic branch |
| **Self-test commands** | Same as Phase 2 with `--pr 3`; `python scripts/triage/run_triage.py --pr 3 --output docs/triage/PR-3-triage-report.md` exits 0; report validated. |
| **Tester checks** | Same checklist as Phase 2 but applied to PR #3. Additionally verify that Phase 2 artifacts are unchanged (no cross-contamination between PR triages). |
| **Release criteria** | PR #3 report generated and validated; Phase 2 artifacts intact; tester confirms isolation. |
| **Gate after phase** | Route back to Claude Code A for review; proceed to Phase 4 upon sign-off. |

### Phase 4 — Consolidated Summary & Integration

| Field | Value |
|---|---|
| **Scope** | (1) Generate consolidated triage summary `docs/triage/consolidated-triage-summary.md` that compares both PRs, highlights shared issues, and recommends a combined action plan. (2) Update the epic branch with all triage artifacts committed. (3) Run full CI suite on epic branch. (4) Produce developer report `docs/dev_reports/2026-06-18-historical-pr-triage-pr-2-and-pr-3-dev-report.md`. |
| **Owner** | Claude Code B (Developer Agent) |
| **Branch** | Epic branch `epic/20260618-historical-pr-triage-pr-2-and-pr-3` |
| **Self-test commands** | `python scripts/triage/generate_summary.py --input-dir docs/triage/ --output docs/triage/consolidated-triage-summary.md` exits 0; all prior triage reports remain unchanged; `git status` shows only expected files. |
| **Tester checks** | (1) Summary correctly references both reports, (2) No stale/redundant branches left unmerged, (3) Full regression suite passes, (4) All triage artifacts are under `docs/triage/`, (5) No secrets or tokens in any committed file. |
| **Release criteria** | Consolidated summary approved; full CI green; developer report complete. |
| **Gate after phase** | Route to Claude Code A for Claude Lead Review, then to Codex B for Codex Architect Review, then to Codex A for PM Acceptance. |

## Agent Assignments

| Role | Agent | Phases |
|---|---|---|
| Lead Planning & Review | Claude Code A | Pre-phase planning, post-phase sign-off gates, Claude Lead Review |
| Developer | Claude Code B | Phase 1 (framework), Phase 2 (PR #2), Phase 3 (PR #3), Phase 4 (summary) |
| Test Engineer | Claude Code C | Post-phase test verification for all four phases |
| Architect Reviewer | Codex B | Final Codex Review after all phases pass |
| PM Acceptance | Codex A | Final acceptance against requirements |

## Validation Plan

| Check | When | How |
|---|---|---|
| Unit tests pass | Each Phase gate | `pytest tests/triage/ -v` — all green |
| CLI smoke test | Each Phase gate | Each script `--help` exits 0 |
| Report completeness | Phase 2, 3, 4 gates | Script validates required sections exist |
| Regression suite | Phase 4 gate | Full project test suite (excluding trading-sensitive modules) |
| Safety audit | Phase 4 gate | Grep for any import of broker/execution/order/account/risk modules in triage scripts |
| No secrets leak | Phase 4 gate | `git diff --cached` reviewed for credentials, tokens, keys |
| Tester sign-off | Each Phase gate | Test Engineer Agent produces phase test report to `docs/test_reports/` |

## Exit Criteria

All of the following must be true before the epic branch is declared complete:

1. ✅ Triage framework scripts exist at `scripts/triage/` with passing unit tests.
2. ✅ PR #2 triage report (`docs/triage/PR-2-triage-report.md`) produced and validated.
3. ✅ PR #3 triage report (`docs/triage/PR-3-triage-report.md`) produced and validated.
4. ✅ Consolidated triage summary (`docs/triage/consolidated-triage-summary.md`) produced.
5. ✅ Reconstructed branches or conflict patches created for each PR.
6. ✅ No trading-sensitive modules were touched.
7. ✅ Full project test suite passes on the epic branch.
8. ✅ Developer report delivered to `docs/dev_reports/`.
9. ✅ Claude Lead Review completed with no blockers.
10. ✅ Codex Architect Review completed with no blockers.
11. ✅ PM Acceptance completed against requirements.
