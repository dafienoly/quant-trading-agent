# A-share Live Data Closed-loop Architecture Review R2

> Review date: 2026-06-11  
> Reviewer role: Architect Reviewer  
> Input review: `docs/review/2026-06-11-a-share-live-data-closed-loop-architecture-review.md`  
> Fix report: `docs/dev_reports/2026-06-11-a-share-live-data-closed-loop-architecture-review-fix-report.md`  
> Verification report: `docs/test_reports/2026-06-11-a-share-live-data-closed-loop-architecture-review-verification-report.md`  
> Conclusion: **CHANGES_REQUESTED**

## 1. Review Scope

This re-review checked the original requirement and architecture documents, the developer fix report, the tester verification report, and the actual implementation.

Focused verification commands run by Architect Reviewer:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_live_signal.py tests\test_live_data_service.py -q --basetemp=runtime\pytest-tmp-arch-review
.\.venv\Scripts\python.exe -m ruff check src\product_app\live_signal_orchestrator.py src\product_app\live_data_service.py src\ui_report\product_dashboard.py tests\test_live_signal.py tests\test_live_data_service.py
```

Results:

- `38 passed`
- `ruff`: `All checks passed!`

## 2. Fixed Items Confirmed

### S1 fixed - Signal generation now consumes realtime quote health

`src/product_app/live_signal_orchestrator.py:125` now calls `get_realtime_quotes(symbols, allow_demo=False)`.

`src/product_app/live_signal_orchestrator.py:145-150` maps quote `data_status` and `data_delay_report.max_delay_seconds` into `DataHealthGate`.

Regression coverage exists in `tests/test_live_signal.py:296`, `tests/test_live_signal.py:318`, and `tests/test_live_signal.py:341`.

This fixes the previous highest-risk issue where realtime quote failure could be bypassed.

### S2 fixed - Delay contract is wired into signal health gate

`src/product_app/live_signal_orchestrator.py:145-147` and `src/product_app/live_data_service.py:481-491` now convert quote delay evidence into the `provider_delay` shape expected by `DataHealthGate`.

`src/product_app/data_health_gate.py:47-49` defines the mode-specific thresholds:

- `LEVEL_1_SIGNAL_ONLY`: 120 seconds
- `LEVEL_2_HUMAN_CONFIRM`: 60 seconds
- `LEVEL_3_AUTO`: 10 seconds

Focused tests confirm the signal path blocks delayed quote data.

## 3. Remaining Blocking Findings

### S2 - Live Dashboard still does not provide real factor computation and real backtest execution

**Evidence**

- Requirement F-014 requires one Dashboard entry for data source diagnosis, stock pools, realtime watch, factors, backtests, and signals.
- Architecture section 6.4 requires live endpoints:
  - `POST /product/live-factors/compute`
  - `POST /product/live-backtests/run`
  - `POST /product/live-signals/generate`
- Architecture section 10 requires UI views for real factors and real backtests.
- Current `src/ui_report/product_dashboard.py:730-824` adds a Live Data tab, but it contains provider diagnosis, live quotes, signal draft, and research context only.
- Current factor and backtest user-facing tabs still call legacy paths:
  - `src/ui_report/product_dashboard.py:349` calls `/product/factors/compute`
  - `src/ui_report/product_dashboard.py:391` calls `/product/jobs/backtest/start`
- Searching current routes finds no implemented `/product/live-factors/compute`, `/product/live-backtests/run`, or `/product/live-signals/generate` endpoints.

**Impact**

The most important fail-closed signal defect is fixed, but the product still cannot satisfy the stated closed-loop user journey from the integrated UI:

1. fetch live data;
2. compute live-data-backed factors;
3. run live-data-backed backtests;
4. generate live-data-gated signals.

The new Research Context panel is useful for diagnostics, but it is not a substitute for user-facing live factor computation and live backtest execution.

**Required fix**

1. Add live factor and live backtest API routes, or explicitly wire existing factor/backtest routes to `LiveDataService` and rename/label them as live closed-loop only when demo fallback is impossible.
2. Update the Dashboard so the Factor and Backtest workflows use real live-data-backed endpoints by default.
3. Add API tests and UI smoke tests proving that factor and backtest actions do not call legacy demo paths in the live closed-loop flow.

### S2 - LEVEL_3_AUTO is exposed as a selectable Live Data signal mode

**Evidence**

- Requirement non-goals state this phase must not provide a `LEVEL_3` automated trading entry.
- The architecture repeats that no `LEVEL_3` entry should be added.
- `src/ui_report/product_dashboard.py:795` exposes `LEVEL_3_AUTO` in the Live Data signal mode dropdown.
- `src/ui_report/product_dashboard.py:796-798` shows a warning banner, but the `Generate Signal Draft` button remains available and the selected mode is still sent to `/product/signal/draft`.

**Impact**

This does not appear to enable real order submission, but it still exposes a prohibited automated-trading mode in the product surface. For a trading system, this should be treated as a safety-boundary defect rather than a cosmetic issue.

**Required fix**

1. Remove `LEVEL_3_AUTO` from the Live Data Dashboard selector for this phase.
2. Add server-side rejection in `/product/signal/draft` when `trading_mode=LEVEL_3_AUTO` unless a future phase explicitly enables it under the execution policy.
3. Add tests proving `LEVEL_3_AUTO` is not exposed in the UI and is rejected by the API in the current phase.

## 4. Non-blocking Notes

- The developer and tester reports are materially improved and accurately capture the repaired signal fail-closed behavior.
- The focused backend tests for the previous S1 issue pass.
- The full verification report still documents two pre-existing failed tests and broader ruff issues outside the touched files. Those are not the main reason for this R2 decision, but they should be retired before a release-quality PM acceptance gate.

## 5. Review Decision

**CHANGES_REQUESTED**

The implementation is safer than the previous review and the most critical signal-path bypass is fixed. However, the feature should not enter PM acceptance yet because the integrated live-data product loop is still incomplete and a prohibited `LEVEL_3_AUTO` product control is exposed.

After the remaining S2 items are fixed and covered by tests, this feature can return for architecture review R3.
