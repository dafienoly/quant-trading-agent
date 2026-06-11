# A-share Live Data Closed-loop PM Acceptance

> Acceptance date: 2026-06-11  
> Role: PM Acceptance Agent  
> Requirement: `docs/requirements/2026-06-10-a-share-live-data-closed-loop-requirements.md`  
> Architecture: `docs/design/2026-06-10-a-share-live-data-closed-loop-architecture.md`  
> Architecture reviews:
> - R1 mapped to `docs/review/2026-06-11-a-share-live-data-closed-loop-architecture-review.md`
> - `docs/review/2026-06-11-a-share-live-data-closed-loop-architecture-review-r2.md`
> - `docs/review/2026-06-11-a-share-live-data-closed-loop-architecture-review-r3.md`
>
> Conclusion: **REJECTED**

## 1. Acceptance Position

The architecture review R3 conclusion is `APPROVED_WITH_NOTES`, and the major safety fixes are confirmed: live signal generation now consumes realtime quote health, live Factor/Backtest routes exist, and `LEVEL_3_AUTO` is blocked in the live signal path.

However, PM acceptance must verify the product from the user journey and PRD acceptance criteria, not only architecture repair scope. This feature cannot be accepted yet because at least two MUST product goals are not satisfied in the current workspace:

1. The built-in AI compute / semiconductor theme pool is empty.
2. Realtime live quote smoke did not return usable real quotes during this acceptance run; it failed closed correctly, but the product goal is live watchlist monitoring with real data.

## 2. Acceptance Verification Performed

### 2.1 Automated acceptance tests

Initial command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_live_data_mapper.py tests\test_provider_hub.py tests\test_live_data_service.py tests\test_stock_pool_service.py tests\test_search_evidence.py tests\test_live_signal.py -q --basetemp=runtime\pytest-tmp-pm-acceptance
```

Result:

- Failed before running because `tests/test_provider_hub.py` does not exist.
- Provider hub tests are actually embedded in `tests/test_live_data_mapper.py`.

Adjusted command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_live_data_mapper.py tests\test_live_data_service.py tests\test_stock_pool_service.py tests\test_search_evidence.py tests\test_live_signal.py -q --basetemp=runtime\pytest-tmp-pm-acceptance
```

Result:

- `129 passed`
- `4 failed`

Failures:

- `tests/test_stock_pool_service.py::TestThemePoolService::test_get_theme_pool`
- `tests/test_stock_pool_service.py::TestThemePoolService::test_get_theme_tags`
- `tests/test_stock_pool_service.py::TestThemePoolService::test_filter_by_tag`
- `tests/test_stock_pool_service.py::TestThemePoolService::test_theme_pool_stocks_are_mainboard`

The failure reason is product-significant: `data/reference/theme_pools/ai_semiconductor.json` is missing, so `ThemePoolService` loads an empty theme pool.

### 2.2 Static check

Focused command:

```powershell
.\.venv\Scripts\python.exe -m ruff check src\data_gateway src\product_app src\api src\ui_report\product_dashboard.py tests\test_live_data_mapper.py tests\test_live_data_service.py tests\test_stock_pool_service.py tests\test_search_evidence.py tests\test_live_signal.py
```

Result:

- `All checks passed!`

Broader note:

- A broader ruff command that included `src/ui_report/dashboard.py` still reports pre-existing unused imports. This is not the primary acceptance blocker, but it should be cleaned before release.

### 2.3 API smoke from user perspective

Using FastAPI TestClient through `src.api.app.create_app()`:

- `/product/pools`: `theme_pool.stock_count=0`, `tags=[]`
- `/product/pools/ai_semiconductor`: `stocks=[]`, `tags=[]`
- `/product/live-data/providers`: `200 OK`
- `/product/live-data/quotes?symbols=600000.SH,000001.SZ`: `status=failed`, `data_status=FAILED`, `is_demo=False`
- `/product/live-factors/compute?...`: `status=failed`, `data_status=FAILED`, `is_demo=False`
- `/product/live-backtests/run?...`: `status=ok`, `data_status=OK`, `is_demo=False`
- `/product/signal/draft?...`: `status=blocked`, `is_demo=False`
- `/product/signal/draft?...trading_mode=LEVEL_3_AUTO`: `status=rejected`

Interpretation:

- Fail-closed behavior works and demo data is not being disguised as live data.
- Realtime quote monitoring did not produce usable real quotes in this acceptance run.
- Backtest can use live daily bars in at least one smoke path.

## 3. Requirement Acceptance Matrix

| ID | Requirement | Acceptance Result | PM Notes |
|---|---|---:|---|
| F-001 | Multi real data provider hub | PASS | Provider order, fallback chain, and failed-provider behavior exist and are covered by tests. |
| F-002 | Data source diagnosis page | PASS | Live Data tab and `/product/live-data/diagnose` exist; provider status is exposed. |
| F-003 | Automatic provider fallback | PASS | Covered by `DataProviderHub` tests embedded in `tests/test_live_data_mapper.py`. |
| F-004 | All real sources fail closed | PASS | Realtime quote failure returns `FAILED`, signal is `blocked`, and feedback Bug is generated/deduped. |
| F-005 | Watchlist management | PASS | Watchlist APIs and validation exist; mainboard filtering covered by tests. |
| F-006 | AI compute / semiconductor theme pool | **FAIL** | Theme pool file is missing; API returns zero stocks and zero tags. This is a MUST blocker. |
| F-007 | Realtime A-share watch | **FAIL / NOT VERIFIED** | Current smoke returned `data_status=FAILED` for live quotes. Fail-closed is correct, but real monitoring did not run successfully. Needs trading-hour or reliable-source verification. |
| F-008 | Historical daily bars | PASS_WITH_NOTES | Live backtest smoke successfully obtained daily bars and returned `data_status=OK`; earlier factor call saw provider instability. |
| F-009 | Fundamentals data | PASS_WITH_NOTES | Fundamentals are integrated into LiveDataService and signal health, but provider missing-field behavior still produced failures in smoke logs. |
| F-010 | Theme/news evidence | PARTIAL | Search/theme services exist, but empty theme pool prevents product-level theme workflow from being complete. |
| F-011 | Provider failure search diagnosis | PASS_WITH_NOTES | Feedback Bug generation works; search-enhanced diagnosis should be verified with configured API keys. |
| F-012 | Minute bar extension point | PASS | Non-blocking architecture extension point exists by design; not required for MVP acceptance. |
| F-013 | Data health gate | PASS | Signal path blocks realtime quote failure and delay cases; `LEVEL_3_AUTO` is rejected. |
| F-014 | Integrated product UI | PASS_WITH_NOTES | Dashboard exposes live data, live factor, live backtest, and signal flows. The feature is not accepted because the theme pool and realtime quote result fail product criteria. |
| F-015 | Automatic feedback | PASS | Failures write/dedupe bugs in `feedback/bugs/open`; API exposes feedback queue. |

## 4. Blocking Issues

### P0 - Built-in AI semiconductor theme pool is missing

Evidence:

- `src/product_app/stock_pool_service.py` expects `data/reference/theme_pools/ai_semiconductor.json`.
- The file/directory is absent in the current workspace.
- `ThemePoolService` logs that the theme pool file does not exist and returns an empty dataset.
- `/product/pools` returns `theme_pool.stock_count=0`.
- `/product/pools/ai_semiconductor` returns `stocks=[]`.
- Four theme-pool acceptance tests fail.

Why this blocks acceptance:

F-006 is a MUST requirement. The product explicitly promises a built-in AI compute / semiconductor pool with 100-300 candidates, organized by tags, usable by live watch, factor computation, backtest, and signal generation. An empty theme pool breaks that user journey.

Required fix:

1. Add `data/reference/theme_pools/ai_semiconductor.json`.
2. Include 100-300 A-share mainboard candidates with stable schema:
   - `symbol`
   - `name`
   - `board_type`
   - `tags`
   - optional sector/subtheme metadata
3. Include tags such as `ai_chip` and `optical_module`, matching existing tests.
4. Re-run `tests/test_stock_pool_service.py`.

### P0 - Realtime quote monitoring did not return usable real data in acceptance smoke

Evidence:

- `/product/live-data/quotes?symbols=600000.SH,000001.SZ` returned `status=failed`, `data_status=FAILED`, `is_demo=False`.
- The logs show all realtime providers failed during the smoke run and a feedback Bug was created/deduped.

Why this blocks acceptance:

The core user goal is to use real A-share live data for watchlist monitoring. Fail-closed behavior is correct, but a product acceptance pass needs at least one verified path where the user can see real live quote data, ideally with 10 mainboard symbols during trading hours.

Required fix:

1. Provide a deterministic trading-hour smoke script or acceptance fixture for 10 mainboard symbols.
2. Confirm at least one real provider returns live quotes with `is_demo=False`.
3. Record provider, latency, updated_at, fallback chain, and data health in the acceptance report.
4. Keep fail-closed behavior for provider failure.

## 5. Non-blocking Follow-ups

1. Remove `LEVEL_3_AUTO` from the generic Configuration page selector, even though it is not saved and live signal/API layers reject it. The product should avoid presenting unavailable automated trading modes.
2. Expand live Factor Lab beyond technical factors. Current implementation is acceptable as a technical-factor MVP, but the PRD user story expects daily bars, fundamentals, and theme evidence to support factor exploration.
3. Retire or quarantine legacy test failures around demo fallback product quotes before a release-quality gate.
4. Clean pre-existing ruff issues in `src/ui_report/dashboard.py`.
5. Add an explicit PM acceptance script that can be run during A-share trading hours and records live quote success/failure without relying on manual interpretation.

## 6. Final PM Decision

**REJECTED**

The implementation should return to Developer/Test Engineer for a focused product acceptance fix pass:

1. Restore/populate the built-in AI semiconductor theme pool.
2. Provide proof that realtime quotes can run successfully from at least one real provider in the product UI/API path.
3. Re-run PM acceptance tests and update the test report with exact evidence.

After those two P0 items are fixed, this feature can return for PM acceptance re-check.
