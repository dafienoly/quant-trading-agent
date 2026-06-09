# Product Delivery Sub-Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current Phase 1-5 services, APIs, scripts, and Streamlit panels into a deployable user-facing demo product with one-click startup, integrated operation UI, and automatic bug feedback collection.

**Architecture:** Keep the current safety-first trading architecture. Add a thin product delivery layer around existing capabilities instead of rewriting research, risk, backtest, or execution engines. The demo product must remain at `LEVEL_1_SIGNAL_ONLY` by default and support `LEVEL_2_HUMAN_CONFIRM` only with explicit configuration and paper broker by default.

**Tech Stack:** Python, FastAPI, Streamlit for Demo V1, APScheduler or lightweight asyncio jobs, local SQLite/JSON storage, pytest, ruff, optional Playwright/browser smoke checks for frontend verification.

---

## 1. Product Boundary

This roadmap is **Phase 5.5: Product Delivery Demo**.

It is not Phase 6. It must not enable small-fund automatic trading, real broker automation, batch buy confirmation, or any path that bypasses Risk Agent.

The target user outcome is:

1. User clones the repository.
2. User runs one bootstrap command.
3. User runs one start command.
4. Browser opens a single product entry page.
5. User can configure data source, trading mode, watchlist, backtest parameters, risk limits, refresh frequency, and paper account settings.
6. User can view realtime quotes, watchlist updates, risk state, factor scores, strategy backtests, generated signals, order drafts, and human-confirmation orders.
7. If any service or UI action fails, the system writes a structured bug report to a known directory for developers.

---

## 2. Non-Negotiable Product Rules

- Default config must remain `MAX_TRADING_LEVEL=LEVEL_1_SIGNAL_ONLY`.
- `ENABLE_LIVE_TRADING=false` must remain the default.
- Demo startup must use `BROKER_ADAPTER=paper`.
- No UI page may expose `LEVEL_3_AUTO` enablement as a casual toggle.
- Human confirmation must remain per-order for buys. Batch reject and batch cancel are allowed; batch buy confirm is forbidden.
- Every order shown in UI must include signal ID, risk check ID, stock pool filter result, stop-loss, take-profit, risk note, and current order state.
- Every backtest launched from UI must include commission, stamp duty, slippage, limit-up/limit-down handling, and suspension handling.
- LLM-generated content, if later added, may only produce explanations, labels, evidence, summaries, and bug triage text. It must not directly decide buy/sell/position.
- Secrets must never be accepted into repo files. Product UI may write local `.env` or local config files only if they are ignored by Git.
- Data-source failure must degrade to safe read-only state and produce a visible health warning plus a feedback bug record.

---

## 3. Target File Structure

### New Product Layer

- Create `README.md`
  Public entry document: quick start, one-click startup, product screens, safety defaults, demo workflow.

- Create `scripts/bootstrap.py`
  Checks Python version, virtualenv presence, dependency installation state, writable local directories, `.env` existence, and prints exact remediation commands.

- Create `scripts/start_product.py`
  One command to start API, background jobs, and frontend; performs port checks, health checks, and writes process logs.

- Create `scripts/stop_product.py`
  Stops processes started by `start_product.py` using a PID file.

- Create `src/product_app/`
  Product orchestration package. It should not contain strategy logic.

- Create `src/product_app/config_service.py`
  Loads, validates, masks, updates, and persists user-facing configuration.

- Create `src/product_app/service_manager.py`
  Starts and monitors API/frontend/background workers for local demo mode.

- Create `src/product_app/feedback.py`
  Structured bug-report writer, dedupe hash generator, sanitization rules, bug index maintenance.

- Create `src/product_app/demo_data.py`
  Provides deterministic demo fixtures when realtime data is unavailable or the market is closed.

- Create `src/product_app/health.py`
  Aggregates API health, data source health, risk state, job state, storage state, and feedback backlog.

### API Layer

- Modify `src/api/app.py`
  Add product endpoints for config, jobs, feedback, full dashboard summary, backtest jobs, and manual refresh actions.

- Add `src/api/product_routes.py`
  Keep product-facing routes separate from trading execution routes.

### Frontend Layer

- Modify `src/ui_report/dashboard.py` or create `src/ui_report/product_dashboard.py`
  Demo V1 should use Streamlit because it is already in the stack. It must become the single integrated product entry, not a narrow order panel.

### Feedback Storage

- Create `feedback/README.md`
  Explains bug report lifecycle and developer triage process.

- Runtime-created ignored directories:
  - `feedback/bugs/open/`
  - `feedback/bugs/triaged/`
  - `feedback/bugs/fixed/`
  - `feedback/bugs/ignored/`
  - `feedback/index.json`

### Tests

- Add `tests/test_product_config_service.py`
- Add `tests/test_product_feedback.py`
- Add `tests/test_product_health.py`
- Add `tests/test_product_api.py`
- Add `tests/test_product_startup.py`
- Add frontend smoke tests if the chosen runner supports local browser checks.

---

## 4. Phase 5.5-A: Delivery Baseline And Safety Fixes

**Purpose:** Before building product UI, remove known delivery blockers from Phase 5 audit.

**Required fixes:**

- [ ] Fix sell order draft quantity: `ExecutionService.signal_to_draft()` must read broker positions and use available sell quantity.
- [ ] Ensure ST stocks are blocked by default in order checking or stock-pool filtering before buy orders are created.
- [ ] Ensure `ExecutionService` automatically records fills through `TradeRecorder` or exposes a mandatory wiring path used by the API.
- [ ] Ensure PaperBroker uses structured market status for limit-up, limit-down, and suspension checks instead of parsing free-text `risk_note`.
- [ ] Add `README.md` with one-command demo workflow.
- [ ] Add tests for each fix before implementation.

**Development criteria:**

- Do not change strategy scoring formulas in this phase.
- Do not introduce real broker connectivity.
- Preserve existing API compatibility.
- All fixes must be covered by unit or integration tests.

**Acceptance checks:**

- `.venv\Scripts\python.exe -m pytest tests/test_phase5_execution.py tests/test_phase5_order_checker.py tests/test_phase5_paper_broker.py tests/test_phase5_e2e.py -q`
- `.venv\Scripts\python.exe -m ruff check src/execution_engine src/risk_engine src/stock_pool tests/test_phase5_execution.py tests/test_phase5_order_checker.py tests/test_phase5_paper_broker.py tests/test_phase5_e2e.py`
- Manual check: sell signal with an existing paper position creates a nonzero sell draft.

---

## 5. Phase 5.5-B: One-Click Bootstrap And Startup

**Purpose:** Make the product runnable by a user without knowing internal scripts.

**User-facing commands:**

```powershell
.venv\Scripts\python.exe scripts\bootstrap.py
.venv\Scripts\python.exe scripts\start_product.py
```

**Startup behavior:**

- Create missing local directories: `data/`, `logs/`, `feedback/bugs/open/`.
- If `.env` is missing, create it from `.env.example` with safe defaults.
- Validate critical defaults:
  - `MAX_TRADING_LEVEL=LEVEL_1_SIGNAL_ONLY`
  - `ENABLE_LIVE_TRADING=false`
  - `REQUIRE_HUMAN_CONFIRMATION=true`
  - `BROKER_ADAPTER=paper`
- Start FastAPI on configurable port, default `8000`.
- Start Streamlit product dashboard on configurable port, default `8501`.
- Start background polling job only after API health is OK.
- Write process IDs to `runtime/product.pid.json`.
- Write startup logs to `logs/product_startup.log`.
- Print the product URL at the end: `http://localhost:8501`.

**Development criteria:**

- Startup must fail closed if config enables live trading without explicit confirmation file.
- Port conflict must produce a clear message and a feedback bug record.
- `start_product.py` must not hide child process failures.
- `stop_product.py` must only stop PIDs recorded by this project.

**Acceptance checks:**

- `.venv\Scripts\python.exe scripts\bootstrap.py` exits 0 on a healthy workspace.
- `.venv\Scripts\python.exe scripts\start_product.py --dry-run` prints planned services and ports without starting processes.
- `.venv\Scripts\python.exe -m pytest tests/test_product_startup.py -q`
- `.venv\Scripts\python.exe -m ruff check scripts src/product_app tests/test_product_startup.py`

---

## 6. Phase 5.5-C: Product Configuration Center

**Purpose:** All user-facing settings must be visible and editable from the product, with safe validation.

**Configuration groups:**

- Trading mode:
  - `MAX_TRADING_LEVEL`
  - `ENABLE_LIVE_TRADING`
  - `REQUIRE_HUMAN_CONFIRMATION`
  - `BROKER_ADAPTER`
- Data source:
  - `DEFAULT_DATA_PROVIDER`
  - realtime quote provider
  - refresh interval
  - fallback demo-data mode
- Stock pool:
  - market selection
  - semiconductor sub-themes
  - custom watchlist
  - exclusions and blacklist display
- Risk limits:
  - max single-stock position
  - max sector position
  - min cash ratio
  - single-stock loss warning/stop
  - daily loss controls
  - max drawdown controls
- Backtest:
  - initial capital
  - date range
  - commission
  - stamp duty
  - slippage
  - benchmark
- UI/runtime:
  - API URL
  - refresh interval
  - feedback capture level
  - log level

**Development criteria:**

- Secrets must be masked and must not be shown in full.
- Config writes must use a local ignored file such as `.env` or `runtime/user_config.json`.
- Unsafe upgrades to `LEVEL_2_HUMAN_CONFIRM` must show a confirmation screen and keep `BROKER_ADAPTER=paper` by default.
- `LEVEL_3_AUTO` must remain blocked in Demo V1.
- Invalid config must not be persisted.

**Acceptance checks:**

- Config API returns masked values for secret-like keys.
- UI can edit safe risk/backtest/watchlist values and persist them.
- Attempting to enable live trading from UI is blocked unless explicit hard-gate conditions are satisfied.
- `.venv\Scripts\python.exe -m pytest tests/test_product_config_service.py tests/test_product_api.py -q`
- `.venv\Scripts\python.exe -m ruff check src/product_app src/api tests/test_product_config_service.py tests/test_product_api.py`

---

## 7. Phase 5.5-D: Integrated Web Product Demo

**Purpose:** Replace scattered scripts and narrow panels with one clear frontend entry.

**Demo V1 frontend sections:**

1. **Home / System Status**
   - API status
   - data source status
   - risk status
   - trading mode
   - paper/live indicator
   - feedback backlog count

2. **Realtime Market**
   - symbol search
   - realtime quote table
   - quote delay badge
   - data source badge
   - manual refresh button
   - auto-refresh interval control

3. **Watchlist Monitor**
   - configured watchlist
   - latest price and pct change
   - sector/theme
   - risk block reason
   - triggered alerts
   - no-order guarantee in `LEVEL_1_SIGNAL_ONLY`

4. **Factor Lab**
   - select symbols/date range
   - compute technical, sentiment, fundamental, and theme scores
   - show factor table and explanation
   - show missing-data and survivor-bias warnings

5. **Backtest Lab**
   - select strategy, symbols, date range, capital, costs, slippage
   - run backtest as a tracked job
   - show performance summary, equity curve, drawdown, trade list
   - block results without cost/limit/suspension assumptions

6. **Signal Center**
   - latest generated signals
   - signal explanation
   - stock-pool filter result
   - risk note
   - suggested action
   - order draft availability by mode

7. **Human Confirmation**
   - pending orders
   - confirm/reject/cancel per order
   - buy orders must not support batch confirmation
   - batch reject/cancel allowed
   - account and position summary

8. **Configuration**
   - all user-facing settings from Phase 5.5-C
   - validation messages
   - safe defaults restore

9. **Feedback**
   - open bug list
   - bug detail
   - export path
   - mark as triaged/fixed/ignored for developer workflow

**Development criteria:**

- The first screen must be the working product cockpit, not a marketing landing page.
- UI copy must be operational and concise; avoid long instructions inside the app.
- Every user action must show success, failure, and loading states.
- All error states must call the feedback writer.
- Market-closed state must be obvious and must offer deterministic demo data.
- The UI must remain usable at 1366px desktop width.

**Acceptance checks:**

- User can complete this demo flow from browser:
  1. open dashboard
  2. verify system health
  3. configure watchlist
  4. refresh realtime quotes
  5. run a small factor calculation
  6. run a small backtest
  7. generate signals
  8. inspect an order draft in paper LEVEL_2 mode
  9. reject or confirm one paper order
  10. see feedback bug list remain empty for successful flow
- `.venv\Scripts\python.exe -m pytest tests/test_product_api.py tests/test_product_health.py -q`
- Frontend smoke check with local browser or Streamlit test harness.
- Screenshot review: no overlapping text, no hidden critical controls, no accidental auto-trading controls.

---

## 8. Phase 5.5-E: Realtime Jobs And State Model

**Purpose:** Make realtime updates reliable without turning the product into a fragile collection of manual refresh buttons.

**State model:**

- `runtime/state/system_status.json`
- `runtime/state/latest_quotes.json`
- `runtime/state/latest_signals.json`
- `runtime/state/latest_risk.json`
- `runtime/state/jobs.json`
- `runtime/state/backtests/{job_id}.json`

**Jobs:**

- quote refresh job
- watchlist monitor job
- signal generation job
- risk snapshot job
- backtest job
- feedback compaction job

**Development criteria:**

- Jobs must have explicit states: `IDLE`, `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED`.
- Long-running backtests must not block API responsiveness.
- Failed jobs must generate feedback bug records.
- Realtime polling must respect mode-specific quote delay thresholds from risk policy.
- UI must show last successful update time and current job state.

**Acceptance checks:**

- A failed quote refresh creates one deduplicated bug record.
- A backtest job can be started, monitored, and completed from API/UI.
- API remains responsive while a backtest job is running.
- `.venv\Scripts\python.exe -m pytest tests/test_product_health.py tests/test_product_api.py -q`
- `.venv\Scripts\python.exe -m ruff check src/product_app src/api tests/test_product_health.py tests/test_product_api.py`

---

## 9. Phase 5.5-F: Automatic Feedback And Bug Intake

**Purpose:** Every product error should become an actionable developer artifact.

**Bug report directory:**

```text
feedback/
  README.md
  index.json
  bugs/
    open/
    triaged/
    fixed/
    ignored/
```

**Bug record format:**

Each bug must be written as both Markdown and JSON:

- `feedback/bugs/open/{bug_id}.md`
- `feedback/bugs/open/{bug_id}.json`

Required fields:

- `bug_id`
- `created_at`
- `updated_at`
- `status`
- `severity`
- `component`
- `title`
- `summary`
- `user_action`
- `endpoint_or_page`
- `exception_type`
- `exception_message`
- `sanitized_traceback`
- `runtime_context`
- `config_snapshot_masked`
- `reproduction_steps`
- `dedupe_hash`
- `related_log_files`

**Capture points:**

- FastAPI exception middleware.
- Product API route failures.
- Background job failures.
- Streamlit UI action failures.
- Startup/bootstrap failures.
- Data-source health failures.

**Sanitization rules:**

- Mask keys containing `TOKEN`, `KEY`, `SECRET`, `PASSWORD`, `COOKIE`, `ACCOUNT`, `BROKER`.
- Do not include full `.env`.
- Do not include raw broker credentials.
- Do not include raw user private account identifiers.
- Stack traces are allowed after sanitization.

**Deduplication rules:**

- Same component + exception type + normalized message + endpoint/page within 24 hours maps to the same `dedupe_hash`.
- Duplicate reports increment `occurrence_count` in JSON and append a timestamp to Markdown.

**Development criteria:**

- Feedback writer must never crash the product path; if bug writing fails, log locally.
- Bug records must be useful without requiring developers to reproduce immediately.
- UI must show the open bug count and allow opening the feedback directory path.

**Acceptance checks:**

- Inject a fake API exception and verify Markdown + JSON are created.
- Inject a fake Streamlit action exception and verify report creation.
- Verify secrets are masked in generated bug files.
- Verify duplicate exceptions update occurrence count instead of creating unlimited files.
- `.venv\Scripts\python.exe -m pytest tests/test_product_feedback.py -q`
- `.venv\Scripts\python.exe -m ruff check src/product_app/feedback.py tests/test_product_feedback.py`

---

## 10. Phase 5.5-G: Demo Packaging And Release Gate

**Purpose:** Make the product presentable to a user and stable enough for other Agents to extend.

**Deliverables:**

- `README.md`
- `docs/USER_GUIDE.md` updated with product demo workflow.
- `docs/roadmap/PRODUCT_DELIVERY_SUB_ROADMAP.md` kept current.
- `.env.example` updated with product demo settings.
- One-click startup scripts.
- Integrated dashboard.
- Feedback bug intake directory and README.
- Demo data fallback.
- Product smoke test checklist.

**Release gate:**

- No failing tests.
- No untriaged critical product feedback bugs.
- Startup succeeds from a clean clone after dependency install.
- Product opens in browser and shows health status within 10 seconds after services are ready.
- User can run one successful end-to-end paper demo without touching CLI scripts.
- UI does not expose any accidental real-trading path.

**Required final verification commands:**

```powershell
.venv\Scripts\python.exe -m pytest tests -q
.venv\Scripts\python.exe -m ruff check src scripts tests
git diff --check
```

If frontend browser automation is available, also run a local smoke check against `http://localhost:8501`.

---

## 11. Suggested Agent Assignment

- **Agent A: Delivery Bootstrap**
  - Phase 5.5-A and 5.5-B.
  - Owns startup scripts, README, severe Phase 5 delivery fixes.

- **Agent B: Product API And Config**
  - Phase 5.5-C and product routes.
  - Owns config service, health aggregation, job APIs.

- **Agent C: Integrated Frontend**
  - Phase 5.5-D.
  - Owns Streamlit product dashboard and browser smoke checks.

- **Agent D: Jobs And Realtime State**
  - Phase 5.5-E.
  - Owns scheduler, job state, cached runtime state.

- **Agent E: Feedback Pipeline**
  - Phase 5.5-F.
  - Owns bug record format, exception capture, sanitization, dedupe, feedback UI.

- **Agent F: Release Coordinator**
  - Phase 5.5-G.
  - Owns cross-agent integration, final docs, full tests, demo rehearsal.

Agents must work on separate `codex/` branches and merge only after focused tests pass. Any core trading change must include tests in the same commit.

---

## 12. Product Demo Acceptance Script

The release coordinator must verify this exact flow:

1. Start from latest `main`.
2. Run `.venv\Scripts\python.exe scripts\bootstrap.py`.
3. Run `.venv\Scripts\python.exe scripts\start_product.py`.
4. Open `http://localhost:8501`.
5. Confirm system status shows API OK, feedback OK, and live trading disabled.
6. Set watchlist to at least `002463`, `600584`, `603228`.
7. Refresh realtime market. If market/data source unavailable, enable demo data and verify the UI clearly labels it.
8. Run factor calculation for the watchlist.
9. Run a short backtest with explicit commission, stamp duty, and slippage.
10. Generate latest signals.
11. Switch to `LEVEL_2_HUMAN_CONFIRM` with paper broker only.
12. Create or view one paper order draft.
13. Confirm one paper order or reject it.
14. Verify order/trade trace includes signal ID and risk check ID.
15. Trigger one controlled demo exception and verify a bug report appears under `feedback/bugs/open/`.
16. Stop services with `.venv\Scripts\python.exe scripts\stop_product.py`.

The demo fails if any step requires editing source code, manually calling internal APIs, or bypassing risk/execution policy.