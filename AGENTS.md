# AGENTS.md

## Quick Start

```bash
python -m pytest tests/ -q --basetemp=runtime/pytest-tmp          # all tests
python -m pytest tests/test_stock_pool_service.py -q --basetemp=runtime/pytest-tmp  # single file
python -m ruff check src/ tests/                                   # lint
python -m py_compile src/product_app/stock_pool_service.py         # compile check
```

No `conftest.py` exists. Tests use `unittest.mock.patch` and inline fixtures. API tests use `fastapi.testclient.TestClient` against `src.api.app.app`.

Always pass `--basetemp=runtime/pytest-tmp-<feature>` to isolate test temp files.

## Entrypoints

| Command | Purpose |
|---|---|
| `python main.py api` | FastAPI on :8000 |
| `python main.py dashboard` | Streamlit on :8501 |
| `python main.py signal` | One-shot signal generation |
| `scripts/start.sh` / `start.bat` | One-click start (API + dashboard) |

FastAPI app factory: `src/api/app.py:create_app()`. Module-level `app = create_app()` for uvicorn.
All product routes are under `/product` prefix, defined in `src/api/product_routes.py`.

## Architecture

```
src/
├── api/                  FastAPI routes (product_routes.py) and app factory
├── product_app/          Product services: LiveDataService, StockPoolService, ThemePoolService,
│                         LiveSignalOrchestrator, FeedbackService, DataHealthGate, ConfigService
├── data_gateway/         Provider layer: EastmoneyProvider, AkShareRealtimeProvider, AkToolsProvider
│                         DataProviderHub (auto-fallback + circuit breaker), live_data_mapper
├── risk_engine/          RuntimeRiskEngine with kill switch — ONE-VETO power over all trading
├── execution_engine/     PaperBroker, ExecutionService, OrderChecker
├── backtest_engine/      Event-driven backtest with commission/slippage/stamp duty/limit/suspend
├── factor_engine/        Technical + sentiment + policy + fundamental factors
├── strategy_engine/      Four-factor scoring model, signal generation
├── stock_pool/           Mainboard filter, semiconductor pool
├── agent_orchestrator/   WatchlistMonitor, SignalService orchestration
├── ui_report/            Streamlit dashboards (product_dashboard.py is the live-data one)
├── config/               Settings loaded from .env via python-dotenv
└── models/               Pydantic v2 schemas
```

**LiveDataService** (`src/product_app/live_data_service.py`) is the single data entry point for the live closed-loop. Factor, backtest, and signal code must NOT call providers directly.

**DataProviderHub** (`src/data_gateway/provider_hub.py`) manages provider priority, auto-fallback, and circuit breaking. Provider order: `eastmoney,akshare,aktools` (env `LIVE_DATA_PROVIDER_ORDER`).

**Reference data**: `data/reference/theme_pools/ai_semiconductor.json` — curated JSON with 100-300 mainboard stocks, required tags `ai_chip` and `optical_module`. Not scraped; hand-maintained.

## Hard Safety Invariants

These are non-negotiable. Violations are S0/S1 defects.

1. Default: no real auto-trading. `MAX_TRADING_LEVEL=LEVEL_1_SIGNAL_ONLY`.
2. Risk Agent has one-veto power. `risk_pass=false` blocks all orders.
3. All real orders must be traceable.
4. Data source failure → trading blocked (fail-closed).
5. No ChiNext (300/301), STAR (688/689), ST, or delisting stocks.
6. No strategy may bypass the stock pool filter.
7. Backtests must include commission, slippage, stamp duty, limit-up/down, suspension.
8. LLM must NOT directly decide buy/sell. Only structured tags mapped by rules.
9. All secrets from environment variables only. Never commit `.env`, keys, tokens.
10. Core trading logic changes require tests.

`LEVEL_3_AUTO` must never be exposed as a casual user-selectable option.

`allow_demo=False` is the live closed-loop default. Demo fallback is forbidden for live-data product acceptance. Never disguise demo/paper data as real.

## Development Pipeline

This project enforces a doc-driven pipeline. See `docs/process/AGENT_DEVELOPMENT_PIPELINE.md`.

Before writing code: read the requirement doc (`docs/requirements/`), architecture doc (`docs/design/`), and `docs/policy/SELF_TEST_CHECKLIST.md`.

After writing code: run self-test, then produce a dev report at `docs/dev_reports/YYYY-MM-DD-<feature>-dev-report.md`.

### Self-test Checklist

```bash
git status --short --branch
git diff --stat
python -m ruff check <touched files>
python -m py_compile <touched src files>
python -m pytest <related tests> -q --basetemp=runtime/pytest-tmp-<feature>
git diff --check
```

Self-test level is determined by what you touched (L0-L6). See `docs/policy/SELF_TEST_CHECKLIST.md` §2.

### Restricted Modules

Changes to these directories require extra scrutiny and negative tests:

| Module | Extra requirement |
|---|---|
| `src/risk_engine/` | Negative tests + kill switch tests |
| `src/execution_engine/` | Human confirm, non-trading-hours, insufficient-funds, blacklist tests |
| `src/data_gateway/` | Unit, timezone, delay, fallback, abnormal-data tests |
| `src/backtest_engine/` | Commission, slippage, limit, suspend verification |
| `src/product_app/bug_fix_*` | Approval state machine + restricted-module blocking + rollback |

## Testing Patterns

- **No conftest.py**. Each test class uses `setup_method` or `@pytest.fixture`.
- **API tests**: `from fastapi.testclient import TestClient; from src.api.app import app; client = TestClient(app)`. Mock service singletons via `patch("src.api.product_routes._get_*")`.
- **LiveDataService tests**: Mock `DataProviderHub` and `ProviderCircuitBreaker` at construction, then replace `service._realtime_hub` etc. with `MagicMock`.
- **Theme pool tests**: Require `data/reference/theme_pools/ai_semiconductor.json` to exist. Tests assert `>= 100` stocks and tag presence.
- **Browser E2E**: `tests/test_browser_e2e.py` uses Playwright. Only run when dashboard is live.
- **Live quote smoke**: `scripts/smoke_live_quotes.py` — run during A-share trading hours (09:30-11:30, 13:00-15:00 CST). Exit code 0=pass, 2=fail-closed (safety OK, acceptance fails).

## Environment

- Python 3.10+, venv at `.venv/`
- Config via `.env` (copy from `.env.example`). Loaded by `python-dotenv` in `src/config/settings.py`.
- Key env vars: `LIVE_DATA_PROVIDER_ORDER`, `DATA_FAIL_CLOSED`, `ENABLE_DEMO_FALLBACK_FOR_LIVE_LOOP`, `MAX_TRADING_LEVEL`
- Ruff config in `pyproject.toml`: line-length=100, target=py310
- No mypy, no black, no isort — ruff only

## Key Docs

| Doc | Purpose |
|---|---|
| `docs/design/AGENTS.md` | Agent roles, trading safety rules, code modification rules |
| `docs/process/AGENT_DEVELOPMENT_PIPELINE.md` | Who produces what, when, gate conditions |
| `docs/policy/SELF_TEST_CHECKLIST.md` | Minimum self-test bar before handoff |
| `docs/policy/RISK_POLICY.md` | Risk veto behavior and trading safety boundaries |
| `docs/policy/EXECUTION_POLICY.md` | Order, confirmation, and live execution constraints |
| `docs/design/DATA_CONTRACTS.md` | Market data contracts, units, timestamps, adjustments |
