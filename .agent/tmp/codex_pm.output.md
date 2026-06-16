# v12-real-codex-pm-architect-smoke Requirements

## User Goal

Validate that the V12 automation pipeline can execute a real Codex PM stage and hand off cleanly to a real Codex Architect stage for a docs-only smoke feature.

The feature must prove that Codex A, acting as PM Agent, can produce a complete requirements document that downstream architecture, planning, development, testing, review, and acceptance stages can consume without changing product code or trading behavior.

## Functional Requirements

1. Produce a PM requirements document for feature `v12-real-codex-pm-architect-smoke`.

2. The requirements document must define the expected behavior and scope for a docs-only pipeline smoke test.

3. The document must include:
   - User goal.
   - Functional requirements.
   - Non-functional requirements.
   - Acceptance criteria.
   - Safety constraints.

4. The PM stage must remain limited to requirements definition.

5. The PM stage must not create architecture, implementation plans, development reports, test reports, review reports, acceptance reports, product code, or runtime artifacts.

6. The feature must require the downstream Architect Agent to consume this requirements document and produce the matching architecture document.

7. The feature must require downstream stages to preserve docs-only scope unless a later stage explicitly identifies a documented process defect requiring correction.

8. The feature must verify the automation handoff path for:
   - PM requirements generation.
   - Architect document generation.
   - Stage-status tracking.
   - Required-document path consistency.
   - Evidence that no trading-sensitive code path was modified.

9. The requirements document target path is:

   `docs/requirements/2026-06-16-v12-real-codex-pm-architect-smoke-requirements.md`

10. If automation metadata references an alternate date format for the same requirements document, downstream agents must treat the path in this requirements document as the PM-stage target and report any mismatch as a documentation or pipeline consistency note.

## Non-functional Requirements

1. The feature must be docs-only.

2. The feature must not alter production behavior, product routes, trading workflows, market data providers, strategy logic, risk logic, execution logic, backtesting behavior, or UI behavior.

3. The feature must remain traceable to:
   - Feature ID: `v12-real-codex-pm-architect-smoke`
   - Epic branch: `epic/20260616-v12-real-codex-pm-architect-smoke`
   - Risk level: `docs-only`
   - Issue: `#50`

4. All downstream evidence must use reproducible commands where commands are run.

5. Reports must clearly distinguish docs-only validation from runtime product validation.

6. No stage may claim live trading, real market-data validation, execution readiness, or production release readiness from this smoke feature alone.

7. Generated documentation must be concise, deterministic, and suitable for automated stage consumption.

8. The work must follow repository process rules for role boundaries, handoff evidence, and stage gates.

## Acceptance Criteria

1. A requirements document exists at the required target path for the PM stage.

2. The requirements document contains all required sections in the required order:
   - `# v12-real-codex-pm-architect-smoke Requirements`
   - `## User Goal`
   - `## Functional Requirements`
   - `## Non-functional Requirements`
   - `## Acceptance Criteria`
   - `## Safety Constraints`

3. The requirements document clearly identifies the feature as docs-only.

4. The requirements document clearly states that no production code or trading-sensitive module changes are in scope.

5. The requirements document gives the Architect Agent enough information to produce an architecture document without inventing product behavior.

6. Downstream architecture output references this requirements document and preserves docs-only scope.

7. Downstream development and test evidence, if generated, confirms that no trading-sensitive code paths were modified.

8. Any path inconsistency between automation metadata and PM output requirements is documented rather than silently ignored.

9. Final acceptance can pass only if all required documents for the smoke pipeline are present or any missing documents are explicitly explained by stage scope.

10. Final acceptance must not claim product feature delivery beyond validation of the PM-to-Architect automation smoke path.

## Safety Constraints

1. No real automatic trading may be enabled, simulated as enabled, or implied by this feature.

2. Risk Agent veto behavior must not be changed.

3. Execution policy, human confirmation, broker integration, order state handling, and trading-hour enforcement must not be changed.

4. Market data provider behavior, fallback behavior, demo-data behavior, and fail-closed behavior must not be changed.

5. Stock-pool filtering, including ChiNext, STAR Market, ST, and delisting-arrangement restrictions, must not be changed.

6. No strategy may be modified to bypass stock-pool filtering.

7. No LLM decision boundary may be changed.

8. No secrets, credentials, tokens, cookies, account information, broker credentials, or `.env` content may be introduced.

9. No restricted modules may be modified as part of this docs-only smoke feature.

10. If any downstream stage determines that code changes are required, the stage must stop and return to the appropriate prior planning role for scope revision instead of expanding this PM requirement silently.