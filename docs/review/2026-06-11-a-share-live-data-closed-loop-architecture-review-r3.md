# A-share Live Data Closed-loop Architecture Review R3

> Review date: 2026-06-11  
> Reviewer role: Architect Reviewer  
> Input review: `docs/review/2026-06-11-a-share-live-data-closed-loop-architecture-review-r2.md`  
> Fix report: `docs/dev_reports/2026-06-11-a-share-live-data-closed-loop-architecture-review-r2-fix-report.md`  
> Verification report: `docs/test_reports/2026-06-11-a-share-live-data-closed-loop-architecture-review-r2-verification-report.md`  
> Conclusion: **APPROVED_WITH_NOTES**

## 1. Review Scope

This R3 review checked the R2 blocking findings against the current implementation, with specific attention to:

1. Factor Lab and Backtest no longer using legacy/demo product paths.
2. Live factor and live backtest API routes exist and route through live-data-backed services.
3. `LEVEL_3_AUTO` is not exposed as a live signal generation mode and is rejected server-side.
4. Focused regression tests and static checks pass on the touched areas.

## 2. Verification Commands

Architect Reviewer ran:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_live_signal.py tests\test_live_data_service.py -q --basetemp=runtime\pytest-tmp-arch-review-r3
.\.venv\Scripts\python.exe -m ruff check src\api\product_routes.py src\product_app\live_signal_orchestrator.py src\product_app\live_factor_service.py src\product_app\live_backtest_service.py src\ui_report\product_dashboard.py tests\test_live_signal.py tests\test_live_data_service.py
```

Results:

- `42 passed`
- `ruff`: `All checks passed!`

## 3. Findings

No S0/S1/S2 blocking findings remain for the R2 review scope.

## 4. Fixed Items Confirmed

### R2-S2-1 fixed - Factor Lab and Backtest now use live closed-loop routes

Evidence:

- `src/api/product_routes.py:630` defines `POST /product/live-factors/compute`.
- `src/api/product_routes.py:643` defines `POST /product/live-backtests/run`.
- `src/ui_report/product_dashboard.py:333` labels the page as `Factor Lab (Live)`.
- `src/ui_report/product_dashboard.py:342` calls `/product/live-factors/compute`.
- `src/ui_report/product_dashboard.py:372` labels the page as `Backtest (Live)`.
- `src/ui_report/product_dashboard.py:381` calls `/product/live-backtests/run`.

Legacy calls to `/product/factors/compute` and `/product/jobs/backtest/start` are no longer present in `product_dashboard.py`.

### R2-S2-2 fixed - LEVEL_3_AUTO is blocked in the live signal path

Evidence:

- `src/ui_report/product_dashboard.py:787` exposes only `LEVEL_1_SIGNAL_ONLY` and `LEVEL_2_HUMAN_CONFIRM` in the Live Data signal mode selector.
- `src/api/product_routes.py:589` rejects `trading_mode == "LEVEL_3_AUTO"` at the API route.
- `src/product_app/live_signal_orchestrator.py:114` rejects `LEVEL_3_AUTO` before data access or signal generation.
- Regression tests cover API and orchestrator rejection in `tests/test_live_signal.py:432` and `tests/test_live_signal.py:485`.

This satisfies the current phase boundary: no live closed-loop `LEVEL_3` automated trading entry is exposed.

## 5. Non-blocking Notes For PM Acceptance

### S3 - Configuration page still shows LEVEL_3_AUTO as a selectable display option

`src/ui_report/product_dashboard.py:482-488` still shows `LEVEL_3_AUTO` in the generic Configuration page selector, with a danger banner. The selected value is not included in the saved config payload at `src/ui_report/product_dashboard.py:491-499`, and the live signal path blocks it at both API and orchestrator layers.

This is not a release blocker for architecture review, but PM acceptance should consider removing the option entirely to avoid user confusion.

### S3 - Live Factor Lab is currently technical-factor focused

The new live factor API is backed by `LiveFactorService.get_factor_summary()` and uses real daily bars, which satisfies the R2 blocker. However, the current Factor Lab UI primarily presents technical factors. The broader architecture target still includes technical, fundamental, and theme factors in the product-facing experience.

This should be tracked as a follow-up product enhancement, especially before calling the factor research experience complete.

### S3 - Verification reports contain inconsistent full-suite counts

The developer fix report states a full regression result of `544 passed, 0 failed`, while the tester verification report states `542 passed, 2 failed`. The two reported failures are described as pre-existing. This R3 review independently verified the touched live-data scope, but the next release gate should retire or explicitly quarantine those legacy failures.

## 6. Review Decision

**APPROVED_WITH_NOTES**

The R2 blocking issues are fixed and covered by focused tests. The feature can move to PM acceptance, with the non-blocking notes above carried into acceptance criteria and follow-up cleanup.
