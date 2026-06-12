# A-share Live Data Closed-loop PM Acceptance R2

> Role: PM Acceptance Agent  
> Date: 2026-06-11  
> Requirement: `docs/requirements/2026-06-10-a-share-live-data-closed-loop-requirements.md`  
> Architecture: `docs/design/2026-06-10-a-share-live-data-closed-loop-architecture.md`  
> Acceptance-fix architecture: `docs/design/2026-06-11-a-share-live-data-closed-loop-acceptance-fix-architecture.md`  
> Architect review R2: `docs/review/2026-06-11-a-share-live-data-closed-loop-acceptance-fix-architecture-review-r2.md`  
> Conclusion: **REJECTED**

## 1. Acceptance Position

Architecture Review R2 is `APPROVED_WITH_NOTES`: the prior smoke-script defects
are fixed and the implementation is safe to enter product acceptance.

However, product acceptance must validate the user-visible goal from the PRD:
the user must be able to use real A-share data for live monitoring, factor
calculation, backtesting, and signal drafting. The current workspace still does
not provide successful non-demo realtime quote evidence. Therefore this feature
cannot be accepted yet.

This rejection is not because the system is unsafe. The system fails closed
correctly. It is rejected because the core product promise, "at least 10 A-share
mainboard symbols can refresh real non-demo realtime quotes during acceptance",
is still not proven.

## 2. Acceptance Verification Performed

### 2.1 Automated tests

Command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_stock_pool_service.py tests\test_eastmoney_provider.py tests\test_smoke_live_quotes.py tests\test_live_data_mapper.py tests\test_live_data_service.py tests\test_search_evidence.py tests\test_live_signal.py -q --basetemp=runtime\pytest-tmp-pm-acceptance-r2
```

Result:

```text
169 passed, 2 warnings
```

Warnings:

- `StarletteDeprecationWarning` from FastAPI TestClient dependency behavior.
- `PytestCacheWarning` from local `.pytest_cache` creation on this Windows worktree.

These warnings do not block PM acceptance.

### 2.2 Static check

Command:

```powershell
.\.venv\Scripts\python.exe -m ruff check scripts\smoke_live_quotes.py tests\test_smoke_live_quotes.py src\data_gateway\eastmoney_provider.py src\product_app\stock_pool_service.py tests\test_eastmoney_provider.py tests\test_stock_pool_service.py
```

Result:

```text
All checks passed!
```

### 2.3 Theme pool validation

Command:

```powershell
.\.venv\Scripts\python.exe scripts\validate_theme_pool.py
```

Result:

```text
VALIDATION PASSED: 109 stocks, 8 tags
```

### 2.4 Product API smoke

API smoke was executed through FastAPI `TestClient`.

| Endpoint | Result | PM interpretation |
|---|---|---|
| `GET /product/pools` | `status=ok`, theme pool count `109`, tag count `8` | PASS |
| `GET /product/pools/ai_semiconductor` | `status=ok`, count `109`, tags include `ai_chip` and `optical_module` | PASS |
| `GET /product/live-data/providers` | `status=ok`, provider order exposed | PASS_WITH_NOTES |
| `POST /product/live-data/diagnose?symbols=600000.SH,000001.SZ` | provider-level `ERROR` results for realtime/daily/fundamentals | PASS for diagnostic visibility |
| `GET /product/live-data/quotes?symbols=600000.SH,000001.SZ` | `status=failed`, `data_status=FAILED`, `is_demo=false`, feedback bug `BUG_20260611_UB37C1` | FAIL for live quote product goal, PASS for fail-closed |
| `POST /product/live-factors/compute?...` | `status=failed`, `data_status=FAILED`, `is_demo=false` | FAIL for factor user journey in current environment |
| `POST /product/live-backtests/run?...` | `status=failed`, `data_status=FAILED`, `is_demo=false` | FAIL for backtest user journey in current environment |
| `POST /product/signal/draft?...LEVEL_1_SIGNAL_ONLY` | `status=blocked`, `orders=0`, `is_demo=false` | PASS for safety |
| `POST /product/signal/draft?...LEVEL_3_AUTO` | `status=rejected` | PASS |

### 2.5 Product dashboard smoke

Command:

```powershell
.\.venv\Scripts\python.exe -m streamlit run src\ui_report\product_dashboard.py --server.address 127.0.0.1 --server.port 8771 --server.headless true
```

HTTP check:

```text
http://127.0.0.1:8771 -> HTTP 200
```

Result:

- Product web entry starts successfully.
- This confirms entrypoint availability, not live-data functional acceptance.

### 2.6 Official realtime quote smoke

Command:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_live_quotes.py --symbols 600000.SH,000001.SZ,600584.SH,002463.SZ,603986.SH,601138.SH,000021.SZ,600703.SH,603228.SH,002371.SZ --min-success 10 --output docs\test_reports\2026-06-11-a-share-live-quote-smoke-pm-acceptance.json
```

Output file:

`docs/test_reports/2026-06-11-a-share-live-quote-smoke-pm-acceptance.json`

Result excerpt:

```json
{
  "status": "failed",
  "trading_session": "closed",
  "symbols_requested": 10,
  "symbols_succeeded": 0,
  "is_demo": false,
  "provider": "",
  "fallback_chain": [
    "eastmoney: empty_data",
    "akshare_realtime: empty_data",
    "aktools: empty_data"
  ],
  "data_status": "FAILED",
  "feedback_bug_id": "BUG_20260611_UB37C1"
}
```

PM interpretation:

- Safety behavior is correct: no demo data is used, all providers failed closed,
  and feedback is recorded.
- Product acceptance behavior is not satisfied: zero realtime quotes were returned.
- The run occurred at `2026-06-11T20:32:38+08:00`, outside A-share trading hours.
  A trading-hours run is still required for final acceptance.

## 3. Requirement Acceptance Matrix

| ID | Requirement | Acceptance result | PM notes |
|---|---|---:|---|
| F-001 | Multi real data source Provider Hub | PASS_WITH_NOTES | Provider order and fallback exist; no provider succeeded in acceptance smoke. |
| F-002 | Data source diagnosis page/API | PASS | Diagnose API exposes provider-level errors and capabilities. |
| F-003 | Automatic provider fallback | PASS | Fallback chain records `eastmoney -> akshare_realtime -> aktools`. |
| F-004 | All real sources fail closed | PASS | `data_status=FAILED`, `is_demo=false`, signal blocked, feedback bug recorded. |
| F-005 | Watchlist management | PASS | Existing tests pass; mainboard filtering covered. |
| F-006 | AI compute / semiconductor theme pool | PASS | 109 valid mainboard stocks, 8 tags, API returns non-empty pool. |
| F-007 | Realtime A-share watch | **FAIL** | Official 10-symbol smoke returned `0/10` realtime quotes. |
| F-008 | Historical daily bars | **FAIL in acceptance environment** | API smoke returned `data_status=FAILED`; no successful real daily data path observed in this acceptance run. |
| F-009 | Fundamentals data | **FAIL in acceptance environment** | Diagnosis shows provider errors for fundamentals; no successful real fundamentals path observed. |
| F-010 | Theme/news evidence | PARTIAL | Search/evidence services exist in tests, but full theme factor user journey still depends on real data success. |
| F-011 | Provider failure search diagnosis | PASS_WITH_NOTES | Feedback bug generation works; search-enhanced diagnosis depends on configured API keys. |
| F-012 | Minute bar extension point | PASS | Non-blocking extension point. |
| F-013 | Data health gate | PASS | Signal and order draft are blocked when data fails. |
| F-014 | Integrated product UI | PASS_WITH_NOTES | Dashboard starts; live data user journey still blocked by provider failures. |
| F-015 | Automatic feedback | PASS | Provider failure writes/dedupes feedback bug. |

## 4. Blocking Issues

### P0 - Realtime quote monitoring still has no successful real-data evidence

Evidence:

- Official 10-symbol smoke returned `symbols_succeeded=0`.
- `data_status=FAILED`.
- `is_demo=false`.
- `trading_session=closed`.
- Fallback chain shows all realtime providers failed:
  `eastmoney`, `akshare_realtime`, `aktools`.

Why this blocks acceptance:

F-007 is a MUST requirement. The user goal is not only to fail safely; the user
must be able to monitor real A-share data. The acceptance-fix architecture also
states that product acceptance remains `REJECTED` until successful real-data
smoke is captured.

Required next step:

Run the official smoke during A-share trading hours, without `--allow-demo`:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_live_quotes.py --symbols 600000.SH,000001.SZ,600584.SH,002463.SZ,603986.SH,601138.SH,000021.SZ,600703.SH,603228.SH,002371.SZ --min-success 10 --output docs\test_reports\2026-06-11-a-share-live-quote-smoke-pm-acceptance.json
```

Acceptance requires:

- exit code `0`;
- `status="passed"`;
- `symbols_succeeded >= 10`;
- `is_demo=false`;
- `provider` non-empty;
- fallback chain, latency, and `updated_at` fields recorded.

If this still fails during trading hours on a network-enabled machine, the work
must return to Architect/Developer to add a more reliable realtime provider or
provider-specific repair.

### P1 - Live factor and live backtest user journeys are blocked by data failures

Evidence:

- `POST /product/live-factors/compute` returned `status=failed`,
  `data_status=FAILED`, `is_demo=false`.
- `POST /product/live-backtests/run` returned `status=failed`,
  `data_status=FAILED`, `is_demo=false`.

Why this matters:

This is the correct fail-closed behavior, but it still means the product user
journey promised by F-008/F-009/F-014 cannot be accepted in this environment.
Once realtime/daily/fundamental providers produce real data, PM acceptance must
re-check these flows.

## 5. Passed Product Areas

- The built-in AI semiconductor theme pool is now usable.
- Theme pool tags include `ai_chip` and `optical_module`.
- The product API and dashboard entrypoint start successfully.
- Live closed-loop paths do not silently fall back to demo data.
- Provider failures produce structured fallback chain and feedback bug evidence.
- Signal drafting is blocked when data is unhealthy.
- `LEVEL_3_AUTO` remains rejected.
- Smoke script quality issues from the prior architecture review are fixed.

## 6. Non-blocking Follow-ups

1. The `/product/live-data/providers` endpoint initially reports provider
   health as `OK` with zero rows and empty `last_success_at`. The explicit
   diagnose endpoint shows real errors. This is not the main blocker, but the
   provider overview should eventually distinguish "not diagnosed yet" from
   "OK".
2. Search-enhanced diagnosis and Theme evidence still require configured API
   keys for Tavily / AnySearch / Firecrawl.
3. The final product acceptance should include a browser-level walkthrough after
   provider success, not only HTTP smoke.

## 7. Final PM Decision

**REJECTED**

The implementation is safer and materially improved, and the previous theme-pool
blocker is resolved. But the core product goal is still unmet: real A-share live
data did not run successfully in the PM acceptance smoke.

Return path:

1. Re-run official realtime smoke during A-share trading hours on a
   network-enabled machine.
2. If it passes, update the smoke JSON and return directly to PM acceptance
   re-check.
3. If it fails during trading hours, return to Architect/Developer for provider
   reliability repair.

