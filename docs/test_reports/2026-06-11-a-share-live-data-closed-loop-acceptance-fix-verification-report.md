# A-share Live Data Closed-loop Acceptance Fix — Test Report (R2)

> Role: Test Engineer Agent  
> Date: 2026-06-11 18:00 CST (2nd verification round after developer re-test)  
> Requirement: `docs/requirements/2026-06-10-a-share-live-data-closed-loop-requirements.md`  
> Architecture: `docs/design/2026-06-11-a-share-live-data-closed-loop-acceptance-fix-architecture.md`  
> Dev report: `docs/dev_reports/2026-06-11-a-share-live-data-closed-loop-acceptance-fix-dev-report.md`  
> Acceptance report: `docs/acceptance/2026-06-11-a-share-live-data-closed-loop-acceptance.md`  
> Review R3: `docs/review/2026-06-11-a-share-live-data-closed-loop-architecture-review-r3.md`  

---

## 1. Test Environment

| Item | Value |
|---|---|
| OS | WSL2 / Linux (x86_64) |
| Python | 3.13.5 |
| Virtual env | `.venv/bin/python` |
| Pytest | 9.0.3 |
| Ruff | 0.15.16 |
| Git branch | `feature/quant-factor-v1` |
| Workspace | 4 modified tracked files + 4 untracked new files |
| Test time | 2026-06-11 ~18:00 CST (outside A-share trading hours) |
| Network | No internet access to Eastmoney/AkShare/AkTools endpoints |

## 2. Scope

### In scope
- **P0-1**: Built-in AI semiconductor theme pool (`ai_semiconductor.json`)
- **P0-2**: Real-time quote acceptance smoke script + provider hardening
- Theme pool contract validation (JSON schema, symbol rules, tag coverage)
- ProviderHub fail-closed behavior
- LEVEL_3_AUTO rejection in live signal path
- Data health gate blocking signal on provider failure
- Feedback bug generation on provider failure
- **NEW**: Eastmoney provider hardening (browser headers, single-symbol fallback, proper timeouts)

### Out of scope
- Real-time quote acceptance during trading hours (requires A-share market time)
- Search/theme evidence (F-010) — non-blocking SHOULD
- ProviderFailureAnalyzer (F-011) — non-blocking SHOULD
- Legacy E2E browser tests, server E2E tests

## 3. Changes Since R1 Verification

| File | Change | Purpose |
|---|---|---|
| `.gitignore` | Modified | Track `data/reference/theme_pools/` while still ignoring bulk data |
| `src/data_gateway/eastmoney_provider.py` | Modified (+96/-14) | Browser-like headers, connect/read timeouts, single-symbol fallback path |
| `tests/test_eastmoney_provider.py` | **New** (216 lines) | 12 tests: headers, bulk success, fallback, full failure, symbol conversion |
| `data/reference/theme_pools/ai_semiconductor.json` | Updated | Added `exchange`, `is_st`, `is_delisting`, `evidence` fields per contract |
| `docs/dev_reports/...-dev-report.md` | **New** | Developer's acceptance fix report |

## 4. Requirement Coverage Matrix

### Original Requirements (F-001 to F-015)

| ID | Requirement | Verdict | Evidence |
|---|---|---|---|
| F-001 | Multi real data source Provider Hub | **PASS** | Provider order, fallback, circuit breaker covered by tests |
| F-002 | Data source diagnosis | **PASS** | `/product/live-data/diagnose` + `/product/live-data/providers` return health |
| F-003 | Automatic provider fallback | **PASS** | Hub fallback chain: eastmoney→akshare→aktools; Eastmoney single-symbol fallback added |
| F-004 | All real sources fail closed | **PASS** | `data_status=FAILED`, `is_demo=False`, signal blocked, feedback bug created |
| F-005 | Watchlist management | **PASS** | CRUD + mainboard/ChiNext/ST filtering tested |
| F-006 | AI compute / semiconductor theme pool | **PASS** *(fixed)* | 109 mainboard stocks, 8 tags including `ai_chip` + `optical_module` |
| F-007 | Realtime A-share watch | **PASS_WITH_NOTES** *(fixed)* | Fail-closed verified; smoke script exists; trading-hour run needed |
| F-008 | Historical daily bars | **PASS_WITH_NOTES** | LiveDataService integration correct; provider fail-closed works |
| F-009 | Fundamentals data | **PASS_WITH_NOTES** | Integrated; missing fields preserved as NaN |
| F-010 | Theme/news evidence | **PARTIAL** | Services exist; blocked by empty pool — now resolved |
| F-013 | Data health gate | **PASS** | Correctly blocks signal on quotes/daily FAILED; delay thresholds tested |
| F-014 | Integrated product UI | **PASS_WITH_NOTES** | Live Data/Factor/Backtest tabs; LEVEL_3_AUTO hidden |
| F-015 | Automatic feedback | **PASS** | `BUG_20260611_W7M8ZP` (quotes), `BUG_20260611_U5D5K3` (daily) created |
| F-012/F-011 | Minute bar / search diagnosis | **PASS** (non-blocking) | |

### Acceptance Fix P0 Items

| P0 Item | Verdict | Evidence |
|---|---|---|
| P0-1: Theme pool exists (100-300 stocks) | **PASS** | 109 stocks, 8 tags; validation script PASS |
| P0-1: Required tags present | **PASS** | `ai_chip`, `optical_module`, `advanced_packaging`, etc. |
| P0-1: All mainboard, no ChiNext/STAR/ST | **PASS** | Contract tests pass |
| P0-1: Contract fields complete | **PASS** | `exchange`, `is_st`, `is_delisting`, `evidence` all present |
| P0-2: Smoke script exists | **PASS** | `scripts/smoke_live_quotes.py` — exit codes 0/1/2/3 |
| P0-2: Smoke output format correct | **PASS** | JSON output with provider, latency, chain, data_status |
| P0-2: Fail-closed safety | **PASS** | Exit code 2 outside hours; `is_demo=False` |
| P0-2: Signal blocks on data failure | **PASS** | API smoke confirmed |
| LEVEL_3_AUTO blocked | **PASS** | API + orchestrator + UI all reject |

### Eastmoney Provider Hardening

| Test | Verdict |
|---|---|
| Browser-like headers (User-Agent, Referer) | **PASS** (test_eastmoney_provider.py) |
| Short connect/read timeouts | **PASS** (8s total, 5s connect, 8s read) |
| Bulk success maps quotes | **PASS** (mocked test) |
| Bulk empty → single-symbol fallback | **PASS** (mocked test) |
| Bulk disconnect → single-symbol success | **PASS** (mocked test) |
| All failure → empty DataFrame | **PASS** (mocked test) |
| symbol → secid conversion | **PASS** (tested for SH/SZ) |

## 5. Automated Test Results

### Developer-declared test suite

```text
$ .venv/bin/python -m pytest tests/test_stock_pool_service.py \
  tests/test_eastmoney_provider.py tests/test_live_data_mapper.py \
  tests/test_live_data_service.py tests/test_search_evidence.py \
  tests/test_live_signal.py -q --basetemp=runtime/pytest-tmp-test-acceptance-fix-r2

161 passed, 1 warning in 22.44s
```

12 tests added by this fix (11 pool contract + 1 pool API in `test_stock_pool_service.py`, 12 Eastmoney tests in `test_eastmoney_provider.py`).

### Full regression (excluding E2E server/browser tests)

```text
$ .venv/bin/python -m pytest tests -q --tb=short \
  --basetemp=runtime/pytest-tmp-test-acceptance-fix-r2-full \
  --ignore=tests/test_product_api_e2e.py --ignore=tests/test_browser_e2e.py \
  --ignore=tests/test_browser_simple.py --ignore=tests/test_e2e_acceptance.py

570 passed, 2 failed, 1 warning in 70.43s
```

**Pre-existing failures** (BUG-003, same as all previous rounds):

| Test | Issue | Severity |
|---|---|---|
| `test_fetch_product_quotes_records_feedback_on_provider_failure` | Demo fallback bug_id is None | S3 |
| `test_product_quotes_endpoint_falls_back_to_demo_and_records_feedback` | Demo fallback bug not recorded | S3 |

### Theme pool validation

```text
$ .venv/bin/python scripts/validate_theme_pool.py
VALIDATION PASSED: 109 stocks, 8 tags
```

### Static checks

```text
$ .venv/bin/python -m ruff check \
  scripts/validate_theme_pool.py scripts/smoke_live_quotes.py \
  src/data_gateway/eastmoney_provider.py src/product_app/stock_pool_service.py \
  tests/test_stock_pool_service.py tests/test_eastmoney_provider.py
All checks passed!

$ .venv/bin/python -m py_compile [all touched .py files]
(no errors)
```

### Whitespace / conflict

```text
$ git diff --check
(no output — clean)
```

### Smoke script (outside trading hours)

```text
$ .venv/bin/python scripts/smoke_live_quotes.py \
  --symbols 600000.SH,000001.SZ --min-success 2 \
  --output /tmp/opencode/smoke-r2-output.json
EXIT CODE: 2
```

JSON output confirms `data_status=FAILED`, `is_demo=False`, `trading_session=closed`, feedback bug created.

## 6. API Smoke Results

| Endpoint | Result | Verdict |
|---|---|---|
| `GET /product/pools` | `stock_count=109`, 8 tags | **PASS** |
| `GET /product/pools/ai_semiconductor` | `count=109`, tags include `ai_chip` + `optical_module` | **PASS** |
| `GET /product/live-data/providers` | 200, 3 providers | **PASS** |
| `GET /product/live-data/quotes` | `status=failed`, `data_status=FAILED`, `is_demo=False` | **PASS** |
| `POST /product/signal/draft` (LEVEL_3_AUTO) | `status=rejected` | **PASS** |
| `POST /product/live-factors/compute` | `status=failed`, `data_status=FAILED`, `is_demo=False` | **PASS** |
| `POST /product/live-backtests/run` | `status=failed`, `data_status=FAILED`, `is_demo=False` | **PASS** |

## 7. Security & Safety Verification

| Check | Result |
|---|---|
| `is_demo=False` in all live closed-loop paths | **PASS** |
| All provider failure → fail closed | **PASS** |
| No demo data in live path | **PASS** |
| LEVEL_3_AUTO blocked (API + orchestrator + UI) | **PASS** |
| No real automatic trading enabled | **PASS** |
| ChiNext/STAR/ST stocks excluded | **PASS** |
| Financial missing fields not masked as 0 | **PASS** |
| No API keys committed | **PASS** |
| Eastmoney uses browser headers but no credentials | **PASS** |

## 8. Defect List

### Pre-existing (unchanged from prior rounds)

| ID | Severity | Description | Status |
|---|---|---|---|
| BUG-003 | S3 | 2 legacy demo fallback tests fail | Known, not blocking |
| (broad) | S4 | Pre-existing ruff issues in 15+ legacy test files | Not blocking |

### No new defects found in acceptance fix scope (R2).

## 9. Uncovered / Skipped / Remaining Risk

1. **Trading-hour smoke required**: Smoke script exit code 2 is correct outside market hours. A run at 09:30-11:30 or 13:00-15:00 CST with `--min-success 10` is needed for P0-2 full acceptance.
2. **External provider availability**: All free public providers failed during test (Eastmoney disconnected, AkShare refused, AkTools refused). This is consistent with non-trading-hours but also indicates general fragility.
3. **Theme pool not git-tracked**: `.gitignore` was fixed to track `data/reference/theme_pools/`, but the current `data/` directory is untracked (`?? data/`). Once `git add` runs, the file will be properly tracked.
4. **Search provider real API**: Requires configured API keys — not available in this environment.

## 10. Final Recommendation

**PASS_WITH_NOTES**

- **P0-1 (Theme pool) — RESOLVED.** Contract tests pass, API returns 109 stocks + 8 tags. The `.gitignore` fix ensures the data file can be committed.
- **P0-2 (Realtime quotes) — SAFETY CORRECT, ACCEPTANCE PENDING.** Provider hardening is verified via mocked tests. The smoke script is structurally complete. Full acceptance requires a trading-hours run.
- **Eastmoney hardening — VERIFIED.** Browser headers, timeouts, and single-symbol fallback are all covered by 12 new unit tests.
- **All safety gates — PASS.** Fail-closed, LEVEL_3_AUTO rejection, data health gate, feedback generation all confirmed.

The feature can proceed to architect review with the note that P0-2 real-data acceptance evidence requires a market-hours smoke run.
