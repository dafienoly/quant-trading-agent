# historical-pr-triage-pr-2-and-pr-3 Requirements

## User Goal

The user needs a controlled, document-driven triage of historical GitHub PR #2 and PR #3 for the `quant-trading-agent` repository so the project team can decide whether any useful changes, bug fixes, tests, or documentation from those PRs should be preserved, reimplemented, rejected, or closed without weakening current trading safety, product boundaries, or pipeline discipline.

The PM outcome for this stage is a clear requirements document that enables the Architect Agent to design a safe triage workflow before any implementation, merge, or code modification occurs.

## Functional Requirements

1. The system or agent workflow must identify and inspect historical PR #2 and PR #3, including:
   - PR title, author, branch, base branch, state, and merge status.
   - Changed files and diff summary.
   - Review comments, issue comments, CI status, and merge discussion when available.
   - Relationship to current repository structure and current product direction.

2. The triage must classify each PR independently into one of the following outcomes:
   - `ADOPT_AS_IS`: PR is still valid and can be incorporated with minimal changes.
   - `ADOPT_WITH_CHANGES`: PR contains useful work but needs redesign, rebasing, test updates, or safety corrections.
   - `PARTIAL_ADOPT`: only selected files, ideas, tests, or documentation should be preserved.
   - `REJECT`: PR conflicts with current requirements, architecture, safety constraints, or product direction.
   - `NEEDS_MORE_INFO`: the team cannot safely decide without additional evidence.

3. The triage must produce a structured evidence record for each PR covering:
   - What the PR attempted to change.
   - Whether the change still applies to the current codebase.
   - Whether the change touches restricted or trading-sensitive modules.
   - Whether the change affects live data, signal generation, execution, risk, stock-pool filtering, backtesting, API contracts, UI behavior, or automation workflow.
   - Whether the PR includes or requires tests.
   - Whether the PR introduces migration, compatibility, or operational risk.

4. The triage must compare each PR against current repository rules, including:
   - Root `AGENTS.md`.
   - Development pipeline requirements.
   - Branch workflow requirements.
   - Agent automation architecture.
   - Auto-merge policy.
   - Risk and execution safety invariants when relevant.

5. If either PR touches restricted modules or safety-sensitive behavior, the triage must require explicit follow-up handling before adoption, including architecture review and negative tests.

6. The workflow must not merge, cherry-pick, rebase, or modify production code during the PM requirements stage.

7. The workflow must not treat historical PR content as accepted solely because it exists. Each PR must be evaluated against current requirements, architecture, and safety rules.

8. The triage must define the expected downstream artifacts:
   - Architecture document at `docs/design/20260618-historical-pr-triage-pr-2-and-pr-3-architecture.md`.
   - Team plan at `docs/dev_plans/20260618-historical-pr-triage-pr-2-and-pr-3-team-plan.md`.
   - Development and test reports using the configured phase report patterns.
   - Final review and acceptance documents listed in the pipeline state.

9. The triage must result in a user-facing summary that clearly states:
   - Recommended disposition for PR #2.
   - Recommended disposition for PR #3.
   - Required follow-up work, if any.
   - Whether either PR can be safely closed, superseded, or reworked.

### Non-goals

1. Do not implement code changes in this stage.
2. Do not write or modify architecture documents in this stage.
3. Do not merge PR #2 or PR #3 in this stage.
4. Do not perform live trading, simulated trading, broker execution, or live market data operations.
5. Do not change risk policy, execution policy, stock-pool filtering, provider fallback behavior, or auto-merge rules.
6. Do not bypass the repository pipeline by accepting historical code without development, testing, review, and acceptance evidence.
7. Do not use historical PRs to introduce temporary sprint-specific behavior into root-level instructions.

## Non-functional Requirements

1. The triage process must be auditable and reproducible from recorded evidence.

2. All conclusions must be traceable to PR metadata, diffs, comments, tests, repository policy, or current code structure.

3. The triage must be conservative where safety impact is unclear. Unknown trading, execution, risk, data-source, or stock-pool impact must be treated as requiring further review.

4. The workflow must preserve existing module boundaries and current product direction.

5. The workflow must avoid secret exposure. PR diffs and comments must be checked for credentials, tokens, cookies, broker credentials, `.env` content, and other sensitive data before any adoption recommendation.

6. The triage must be compatible with the repository's document-driven pipeline and branch workflow.

7. The resulting implementation work, if any, must be scoped into reviewable phases suitable for developer self-test and independent test engineer verification.

8. The process must support a final decision even if one or both historical PRs are obsolete, closed, unmergeable, or no longer available.

9. The triage must clearly distinguish between:
   - Historical code that can be reused.
   - Historical intent that should be reimplemented differently.
   - Historical work that should be rejected.

10. Any future code change derived from the triage must include appropriate tests before it can be accepted.

## Acceptance Criteria

1. A requirements document exists at the required requirements path for this feature.

2. The requirements document includes:
   - User goal.
   - Functional requirements.
   - Non-functional requirements.
   - Acceptance criteria.
   - Safety constraints.

3. The Architect Agent can use this document to create a design for safely inspecting and classifying PR #2 and PR #3.

4. The future triage output for PR #2 includes:
   - PR metadata summary.
   - Changed-files summary.
   - Safety impact classification.
   - Current applicability assessment.
   - Test coverage assessment.
   - Recommended disposition.
   - Required follow-up work or closure recommendation.

5. The future triage output for PR #3 includes:
   - PR metadata summary.
   - Changed-files summary.
   - Safety impact classification.
   - Current applicability assessment.
   - Test coverage assessment.
   - Recommended disposition.
   - Required follow-up work or closure recommendation.

6. If either PR touches restricted modules, the triage identifies the restricted area and requires architecture review plus negative test coverage before adoption.

7. If either PR affects live trading, execution policy, risk policy, stock-pool filtering, live data fail-closed behavior, or auto-merge policy, the triage marks manual approval as required before any merge or release.

8. If either PR contains secrets or unsafe credential handling, the triage rejects adoption until the secret exposure is remediated and documented.

9. If either PR relies on obsolete paths, removed APIs, or incompatible architecture, the triage recommends reimplementation or rejection rather than direct adoption.

10. No production code, tests, architecture files, or pipeline state files are modified during the PM stage.

11. The final acceptance stage can determine whether the feature succeeded by reviewing the produced triage evidence, test reports, review reports, and acceptance document.

## Safety Constraints

1. Default: no real automatic trading.

2. Risk Agent one-veto authority must not be weakened or bypassed.

3. Historical PR code must not be adopted if it bypasses risk checks, execution checks, human confirmation, stock-pool filtering, data contracts, or fail-closed behavior.

4. Any PR content affecting real orders must preserve full order traceability.

5. Data source failure must continue to block trading by default.

6. The workflow must not introduce buying of ChiNext, STAR Market, ST, or delisting-arrangement stocks.

7. No strategy code may bypass the stock pool filter.

8. Backtest-related historical changes must not be accepted unless commission, slippage, limit-up/down, and suspension handling are preserved or explicitly tested.

9. LLMs must not directly decide buy or sell actions. Any historical PR content that enables direct LLM trading decisions must be rejected or redesigned.

10. Secrets must come only from environment variables. Historical PR content that commits or depends on `.env`, credentials, keys, tokens, cookies, account credentials, or broker credentials must be rejected until remediated.

11. `LEVEL_3_AUTO` must not be exposed as a casual user-selectable option.

12. Demo data, mock data, and paper trading must not be represented as real live trading capability.

13. When `allow_demo=False`, product live-data paths must not return demo data.

14. If live data is unavailable, signal and real trading paths must fail closed.

15. Any future adoption of code from PR #2 or PR #3 that changes core trading logic must include tests and independent verification before acceptance.