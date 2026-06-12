# A-share Live Data Closed-loop Architecture Review

> Review date: 2026-06-11  
> Reviewer role: Architect Reviewer  
> Conclusion: **CHANGES_REQUESTED**

## 1. Review Scope

Inputs reviewed:

- `docs/requirements/2026-06-10-a-share-live-data-closed-loop-requirements.md`
- `docs/design/2026-06-10-a-share-live-data-closed-loop-architecture.md`
- `docs/dev_reports/2026-06-10-a-share-live-data-closed-loop.md`
- `docs/dev_reports/2026-06-10-a-share-live-data-closed-loop-fix-report.md`
- `docs/dev_reports/2026-06-10-a-share-live-data-closed-loop-fix-report-r2.md`
- `docs/test_reports/2026-06-10-a-share-live-data-closed-loop-test-report.md`
- `docs/test_reports/2026-06-10-a-share-live-data-closed-loop-fix-verification-report.md`
- `docs/test_reports/2026-06-10-a-share-live-data-closed-loop-fix-verification-report-r2.md`
- Current implementation under `src/` and related tests under `tests/`

The test report R2 states that the implementation is ready for architecture review, but architecture review must verify product goal alignment, data safety boundaries, and actual code behavior rather than relying only on test pass counts.

## 2. Blocking Findings

### S1 - Live signal generation bypasses realtime quote health and can produce drafts when live quotes fail

**Evidence**

- Requirement F-004 requires all real providers failing to block watchlist signals, buy/sell signals, and order drafts.
- Requirement F-013 requires unhealthy data to prevent Signal Agent from generating live signals and order drafts.
- Architecture section 5.11 requires `LiveSignalOrchestrator.generate()` to call `live_data_service.get_realtime_quotes(..., allow_demo=False)` and return `blocked` when quotes return `data_status=FAILED`.
- Actual implementation in `src/product_app/live_signal_orchestrator.py` calls only `get_daily_bars()` and `get_fundamentals()` at lines 125 and 128.
- The same method then calls `DataHealthGate.evaluate()` with `quotes_result={"data_status": "OK"}` at line 142.

**Impact**

If realtime quote providers are unavailable, delayed, or returning invalid data while daily bars and fundamentals still return OK, `/product/signal/draft` can still return a signal draft. This violates the feature's central fail-closed promise and the system invariant that data source abnormalities must default to no trading signal.

**Required fix**

1. `LiveSignalOrchestrator.generate_signal_draft()` must call `LiveDataService.get_realtime_quotes(symbols, allow_demo=False)` before factor/backtest/signal generation.
2. `DataHealthGate.evaluate()` must receive the real quotes result, including provider status and delay evidence.
3. If quotes `data_status=FAILED`, the method must return `status=blocked`, `signals/orders=[]` or equivalent empty order draft payload, and include provider failure evidence and feedback Bug ID if generated.
4. Add a regression test where `get_realtime_quotes()` returns `data_status=FAILED` while daily bars and fundamentals return OK; expected result must be blocked.

### S2 - Integrated product Dashboard still uses legacy/demo product paths instead of the live closed-loop entrypoints

**Evidence**

- Requirement F-014 requires one Dashboard entry for data source diagnosis, stock pools, realtime monitoring, factors, backtest, and signals.
- Architecture section 10 requires `product_dashboard.py` to add/refactor views for data source diagnosis, live watch, real factors, real backtest, and real signals, and says live closed-loop pages must not default to demo data.
- Current `src/ui_report/product_dashboard.py` still renders the market page with AkShare/AkTools provider choices and demo fallback enabled by default at lines 234-264, then calls `/product/quotes`.
- The factor page calls `/product/factors/compute` at line 349, not a live-data-backed factor endpoint.
- The backtest page calls `/product/jobs/backtest/start` at line 391, not a live-data-backed backtest endpoint.
- Current `src/api/product_routes.py` exposes `/product/live-data/*` and `/product/signal/draft`, but there are no `/product/live-factors/compute`, `/product/live-backtests/run`, or `/product/live-signals/generate` routes matching the architecture endpoint list.

**Impact**

The deliverable still behaves like a collection of services plus a legacy demo Dashboard, not a user-facing live-data closed-loop product. The browser E2E result in the test report appears to be a smoke check, not a validation that real provider diagnosis, fail-closed states, factor calculation, backtest, and signal generation are usable from the integrated UI.

**Required fix**

1. Add or wire Dashboard views to the live closed-loop APIs:
   - provider diagnosis
   - stock pool and theme pool selection
   - realtime live quotes with fail-closed status
   - live factor computation
   - live backtest execution
   - live signal draft generation with data health evidence
2. Demo fallback may remain only in clearly separated Demo/teaching paths; live closed-loop pages must default to real data and blocked states.
3. Add API/UI tests that assert Dashboard actions call live-data-backed endpoints and display `data_status=FAILED` / `blocked` when live providers fail.

### S2 - Data delay gate is not wired to the LiveDataService quote result shape

**Evidence**

- `DataHealthGate.evaluate()` documents and reads `quotes_result.provider_delay` at `src/product_app/data_health_gate.py:63` and `src/product_app/data_health_gate.py:126`.
- `LiveDataService.get_realtime_quotes()` returns delay data under `data_delay_report`, with `max_delay_seconds` generated by `_build_delay_report()` at `src/product_app/live_data_service.py:311` and `src/product_app/live_data_service.py:674`.
- Because `LiveSignalOrchestrator` currently hardcodes quotes as OK, the delay threshold is not applied in the signal path at all.

**Impact**

The requirement that market delay thresholds affect signal/order safety is not enforced consistently. A quote result can exceed the configured delay threshold without blocking or warning signal generation.

**Required fix**

1. Normalize the quote delay contract: either `LiveDataService` must expose top-level `provider_delay`, or `DataHealthGate` must read `data_delay_report.max_delay_seconds`.
2. Add tests for mode-specific delay thresholds:
   - signal mode: 120 seconds
   - manual confirmation: 60 seconds
   - automated trading: 10 seconds
3. Ensure the signal draft evidence records the actual delay value and threshold.

## 3. Non-blocking Notes

- The provider hub, mapper, stock pool, theme evidence, feedback bug generation, and search provider budget controls appear directionally aligned with the architecture, but they remain partially disconnected from the product Dashboard acceptance path.
- Existing tests are valuable, but several are implementation smoke tests. The next test pass must include negative acceptance tests for live provider failure and UI fail-closed behavior.

## 4. Required Developer Actions Before Re-review

1. Fix `LiveSignalOrchestrator` so realtime quotes are a mandatory input for live signal generation.
2. Wire the Dashboard to live closed-loop endpoints or add the missing live factor/backtest/signal routes and use them from the UI.
3. Fix the delay evidence contract between `LiveDataService` and `DataHealthGate`.
4. Add focused regression tests for all three blocking findings.
5. Update the dev report and test report with exact commands, results, and any known residual risks.

## 5. Review Decision

**CHANGES_REQUESTED**

This feature should not enter PM product acceptance yet. The implementation has made meaningful backend progress, but it still violates two core acceptance criteria:

1. real live data failure must fail closed before signal/order draft generation;
2. the user must be able to operate the live-data closed loop from one integrated Dashboard.

Once the blocking items above are fixed and covered by tests, this feature can return for architecture re-review.
