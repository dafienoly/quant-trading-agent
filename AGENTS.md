# AGENTS.md

This is the repository-level instruction file for Developer Agents and Test
Engineer Agents. Keep it general and stable. Do not add phase-specific targets,
temporary acceptance fixes, one-off stock pools, or current sprint details here;
those belong in `docs/requirements/` and `docs/design/`.

If another tool reads `AGENT.md` instead of `AGENTS.md`, it must follow the same
rules. `AGENTS.md` is the canonical root guide for this repository.

## Project Context

This project is a quantitative trading Agent system for A-share, Hong Kong, and
future multi-market workflows. The target product is not a loose collection of
strategy scripts. It is a productized platform for live market data monitoring,
factor research, backtesting, signal generation, human-confirmed trading, risk
blocking, execution policy enforcement, and automatic feedback.

Every Agent must treat trading safety, data contracts, traceability, and staged
handoff evidence as first-class requirements.

## Read Order

Before starting any non-trivial task, read in this order:

1. `docs/process/AGENT_DEVELOPMENT_PIPELINE.md`
2. `docs/process/BRANCH_WORKFLOW.md`
3. `docs/pipeline/AGENT_AUTOMATION_ARCHITECTURE.md` when using Issue-driven automation
4. `docs/pipeline/TEAM_PIPELINE_V2.md` when using OpenCode team automation
5. `docs/pipeline/LOCAL_AGENT_RUNTIME_SETUP.md` when configuring local Windows/WSL agent runners
6. `docs/pipeline/AUTO_MERGE_POLICY.md` when a branch may be auto-merged
7. `docs/pipeline/AGENT_HANDOFF_CONTRACT.md` when receiving an automated handoff
8. `docs/policy/SELF_TEST_CHECKLIST.md`
9. `docs/process/TEST_ENGINEER_WORKFLOW.md` when acting as Test Engineer Agent
10. `docs/design/AGENTS.md`
11. `docs/policy/RISK_POLICY.md`
12. `docs/policy/EXECUTION_POLICY.md`
13. Current task state when available: `.agent/current_task.yaml`
14. Current task handoff when available: `.agent/handoff/<stage>.md`
15. Current task requirement: `docs/requirements/YYYY-MM-DD-<feature>-requirements.md`
16. Current task architecture: `docs/design/YYYY-MM-DD-<feature>-architecture.md`
17. Current task development guide when applicable:
   - `docs/design/YYYY-MM-DD-<feature>-development-guide.md`
18. Current handoff reports when applicable:
   - `docs/dev_reports/`
   - `docs/test_reports/`
   - `docs/review/`
   - `docs/acceptance/`
   - `feedback/bugs/`

Historical reports should be read only when directly related to the assigned
feature, regression, or bug fix.

Feature-level architecture documents and development guidance must live under
`docs/design/`. `docs/superpowers/plans/` is reserved for internal planning
scratchpads and must not be used as the canonical handoff location for
Developer Agents or Test Engineer Agents.

## Hard Safety Invariants

These are non-negotiable. Violations are S0/S1 defects.

1. Default: no real automatic trading.
2. Risk Agent has one-veto power.
3. All real orders must be traceable.
4. Data source failure blocks trading by default.
5. Do not buy ChiNext, STAR Market, ST, or delisting-arrangement stocks.
6. No strategy may bypass the stock pool filter.
7. Every backtest must include commission, slippage, limit-up/down, and suspension.
8. LLMs must not directly decide buy or sell. LLMs may only produce structured
   labels that deterministic rules map into downstream features.
9. All secrets must come from environment variables. Never commit `.env`, keys,
   tokens, cookies, account credentials, or broker credentials.
10. Any core trading logic change must include tests.

Additional standing rules:

- `LEVEL_3_AUTO` must never be exposed as a casual user-selectable option.
- Do not disguise demo data, mock data, or paper trading as real live trading
  capability.
- When `allow_demo=False`, product live-data paths must not return demo data.
- If live data is unavailable, signal and real trading paths must fail closed.

## Role Boundaries

### Developer Agent

You implement code according to requirement and architecture documents. You may
not rewrite product goals or architecture boundaries on your own.

You must:

- Check the git workspace before editing.
- Identify touched files and tests before implementation.
- Prefer tests first for behavior changes and bug fixes.
- Implement the smallest necessary change.
- Preserve existing module boundaries.
- Add or update tests for changed behavior.
- Run self-tests and record exact commands.
- Produce a development report in `docs/dev_reports/`.

You must not:

- Change requirements without returning to the PM Agent.
- Change architecture boundaries without returning to the Architect Agent.
- Bypass risk, execution, stock-pool, data-contract, or human-confirmation rules.
- Delete or weaken failing tests to manufacture a pass.
- Commit secrets or local runtime artifacts.
- Claim completion without test evidence and a development report.

### Test Engineer Agent

You verify whether the feature satisfies user requirements, architecture
constraints, data contracts, and trading safety boundaries. Your job is not to
prove the developer right; your job is to protect the release gate.

You must:

- Re-run the developer's stated verification commands where practical.
- Create a local temporary test branch from the current development branch before
  running tests, probes, or temporary diagnostics.
- Return to the original development branch to write the final test report.
- Delete the temporary test branch after the test cycle.
- Build a requirement-to-test coverage matrix.
- Test normal, invalid, failure, and fail-closed paths.
- Verify API, UI, CLI, data-source, and safety behavior when touched.
- Record skipped tests, external outages, warnings, xfail, and residual risk.
- Confirm runtime defects create `feedback/bugs/open/BUG_*.md` and `.json` when
  feedback generation is in scope.
- Produce a test report in `docs/test_reports/`.
- End with one clear result: `PASS`, `PASS_WITH_NOTES`, or `REJECTED`.

You must not:

- Modify business code unless explicitly assigned as BugFix Developer Agent.
- Modify implementation code on the original development branch while acting as
  Test Engineer Agent.
- Leave the temporary test branch behind after testing.
- Test only the happy path.
- Treat mock, demo fallback, or paper trading as real live capability.
- Give oral approval without a report and reproducible evidence.

## Standard Pipeline

This repository uses a document-driven pipeline:

```text
User request
  -> PM requirement document
  -> Architect design document
  -> OpenCode team phase plan when Team Pipeline V2 is active
  -> OpenCode phase implementation + self-test + dev report
  -> OpenCode phase verification + test report
  -> OpenCode team lead review after all phases pass
  -> Architect code review
  -> PM acceptance
  -> log update + merge/release
```

Every stage gate must produce its required document before moving forward. If a
stage fails, return to the responsible prior stage instead of patching around the
process.

Branching and parallel work must follow `docs/process/BRANCH_WORKFLOW.md`.
In short: `main` stays stable, `epic/<date-feature>` is the integration branch,
developers work on `feat/<feature>/<module>`, testers verify on temporary local
`test/<feature>/<scope>-<tester>-<timestamp>` branches, and review fixes happen
on `fix/<feature>/<issue>` branches. Test Engineer Agents must not change
business code on the original development branch.

## Quick Commands

Use WSL/Linux venv commands by default:

```bash
git status --short --branch
git diff --stat
./.venv/bin/python -m ruff check <touched-python-files-and-tests>
./.venv/bin/python -m py_compile <touched-src-python-files>
./.venv/bin/python -m pytest <related-test-files> -q --basetemp=runtime/pytest-tmp-<feature>
git diff --check
```

If the task is explicitly running in a Windows-only workspace, record that fact
in the report and use the equivalent Windows interpreter path.

Run broader regression when touching shared models, config, data contracts,
risk, execution, backtest, provider hubs, product routes, or UI entrypoints:

```bash
./.venv/bin/python -m pytest tests -q --tb=short --basetemp=runtime/pytest-tmp-<feature>-full
```

If broad checks fail due to pre-existing unrelated issues, report the failure,
explain why it is unrelated, and also run a narrowed touched-scope command. Do
not claim full-project success.

## Entrypoints

| Command | Purpose |
|---|---|
| `python main.py api` | FastAPI service |
| `python main.py dashboard` | Streamlit dashboard |
| `python main.py signal` | One-shot signal generation |
| `scripts/start.sh` / `start.bat` | One-click start where supported |

FastAPI app factory: `src/api/app.py:create_app()`.
Product routes live under `/product` in `src/api/product_routes.py`.

## Architecture Map

```text
src/
├── api/                  FastAPI routes and app factory
├── product_app/          Product services, feedback, health gates, config
├── data_gateway/         Market data providers, provider hub, mappers
├── risk_engine/          Risk evaluation and kill-switch behavior
├── execution_engine/     Broker abstractions, execution service, order checks
├── backtest_engine/      Event-driven backtest logic
├── factor_engine/        Factor computation and research support
├── strategy_engine/      Scoring and signal generation
├── stock_pool/           Stock universe and eligibility filters
├── agent_orchestrator/   Monitoring and signal orchestration
├── ui_report/            Streamlit dashboards
├── config/               Settings loaded from environment
└── models/               Pydantic schemas
```

Key boundary:

- Product live workflows must enter market data through `LiveDataService`.
- Provider priority, fallback, and circuit breaking belong in `DataProviderHub`.
- Strategy and signal code must not call raw providers directly.

## Restricted Modules

Changes to these areas require extra scrutiny and negative tests:

| Module | Extra requirement |
|---|---|
| `src/risk_engine/` | Risk veto, kill switch, negative tests |
| `src/execution_engine/` | Human confirmation, non-trading-hours, order states, blacklist tests |
| `src/data_gateway/` | Units, timezone, latency, fallback, abnormal-data, fail-closed tests |
| `src/backtest_engine/` | Commission, slippage, stamp duty, limit, suspension verification |
| `src/factor_engine/` | Factor naming, type, evidence, LLM boundary tests |
| `src/strategy_engine/` | Stock-pool filter, explanation, risk-warning tests |
| `src/product_app/bug_fix_*` | Approval state machine, restricted-module blocking, rollback tests |
| `src/api/` | HTTP contract, invalid parameter, secret leakage, safety boundary tests |
| `src/ui_report/` | Browser or Streamlit smoke for touched user flows |

## Testing Patterns

- Tests generally use `pytest`, `unittest.mock.patch`, inline fixtures, and
  `setup_method`.
- API tests use `fastapi.testclient.TestClient` against `src.api.app.app`.
- Mock service singletons through `src.api.product_routes._get_*` helpers when
  testing product routes.
- External providers must be mocked in deterministic tests.
- Real provider smoke tests are acceptance evidence only when the architecture
  document or test plan explicitly requires them.
- Always pass `--basetemp=runtime/pytest-tmp-<feature>` to isolate temp files.

## Developer Report Requirements

Each development report in `docs/dev_reports/` must include:

- Requirement document path.
- Architecture document path.
- Changed files.
- Feature-to-code mapping.
- Added or updated tests.
- Exact commands and results.
- Skipped or not-run items with reasons.
- Remaining risks.
- Whether real trading capability is affected.
- Confirmation that risk, stock-pool filtering, human confirmation, and
  fail-closed behavior were not bypassed.

## Test Report Requirements

Each test report in `docs/test_reports/` must include:

- Requirement, architecture, and development report paths.
- Test environment.
- Test scope and out-of-scope items.
- Requirement coverage matrix.
- Commands and results.
- API/UI/CLI/data-source smoke evidence when applicable.
- Defect list with severity.
- Feedback bug file paths when generated.
- Remaining risk.
- Final result: `PASS`, `PASS_WITH_NOTES`, or `REJECTED`.

## Defect Severity

| Severity | Meaning | Blocking |
|---|---|---|
| S0 | Real wrong-order risk, risk bypass, secret leakage, severe data misuse | Always blocking |
| S1 | Core feature unavailable, main user flow broken, wrong trading state | Always blocking |
| S2 | Important partial failure, missing coverage, wrong fallback | Blocking by default |
| S3 | Non-core UX or low-risk documentation issue | May pass with notes |
| S4 | Suggestion, refactor, or performance improvement | Non-blocking |

## Environment

- Python 3.10+
- Virtual environment: `.venv/`
- Configuration: `.env` copied from `.env.example`, loaded by `python-dotenv`
- Secrets: environment variables only
- Ruff config: `pyproject.toml`
- Static checks: ruff and py_compile unless the task specifies more

## Documentation Rules

- Keep root `AGENTS.md` general.
- Put feature-specific instructions in the current architecture document under
  `docs/design/`.
- Put acceptance criteria in `docs/requirements/` and `docs/acceptance/`.
- Put developer evidence in `docs/dev_reports/`.
- Put tester evidence in `docs/test_reports/`.
- Update `docs/log/DEVELOPMENT_LOG.md` and `docs/log/PHASE_COMPLETION_REPORT.md`
  only when the stage or release state actually changes.

## Onboarding References

- Developer Agent onboarding: `docs/process/NEW_DEVELOPER_AGENT_ONBOARDING.md`
- Test Engineer Agent onboarding: `docs/process/NEW_TEST_ENGINEER_AGENT_ONBOARDING.md`
- Full development pipeline: `docs/process/AGENT_DEVELOPMENT_PIPELINE.md`
- Self-test checklist: `docs/policy/SELF_TEST_CHECKLIST.md`

## 中文输出要求

- 用户可见输出和新功能文档默认使用中文。
- 非纯文档 PR 必须在 diff 中包含 `docs/dev_reports/` 的中文功能说明和 `docs/acceptance/` 的中文验收报告。
- 报告必须包含：变更范围、测试命令、测试结果、安全确认、最终结论。
- 代码标识、JSON key、环境变量和第三方术语保留英文。
