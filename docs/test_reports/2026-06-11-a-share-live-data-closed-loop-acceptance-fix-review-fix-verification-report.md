# A-share Live Data Closed-loop Acceptance Fix — Architecture Review Fix Verification Report

> Role: Test Engineer Agent  
> Date: 2026-06-11 18:10 CST  
> Review report: `docs/review/2026-06-11-a-share-live-data-closed-loop-acceptance-fix-architecture-review.md`  
> Dev fix report: `docs/dev_reports/2026-06-11-a-share-live-data-closed-loop-acceptance-fix-review-fix-report.md`  
> Original requirement: `docs/requirements/2026-06-10-a-share-live-data-closed-loop-requirements.md`  
> Architecture: `docs/design/2026-06-11-a-share-live-data-closed-loop-acceptance-fix-architecture.md`  

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
| Git workspace | 1 modified + 2 untracked (fix scope only) |
| Network | No internet access to Eastmoney/AkShare/AkTools |

## 2. Scope

This verification is strictly scoped to the architecture review blocking findings:

### S1 — Smoke script references non-existent `args.symbols_requested`
- [x] All `args.symbols_requested` references replaced with `report['symbols_requested']`
- [x] Full success path returns exit code 0
- [x] Partial success path returns exit code 3
- [x] All providers failed path returns exit code 2
- [x] Demo blocked path returns exit code 2
- [x] Invalid arguments return exit code 1
- [x] Service exception returns exit code 1

### S2 — No smoke script tests
- [x] `tests/test_smoke_live_quotes.py` exists
- [x] Tests mock `get_live_data_service()`, no external network
- [x] Tests cover: full success, partial, all failed, demo blocked, demo allowed, invalid args, service exception
- [x] Tests verify both exit code and JSON output fields

### Safety verification
- [x] Fail-closed behavior unchanged (`data_status=FAILED` → exit 2)
- [x] No demo fallback introduced as passing path
- [x] No trading/risk/execution/order logic modified

## 3. Verification Commands and Results

### Git workspace

```text
$ git status --short --branch
## feature/quant-factor-v1...origin/feature/quant-factor-v1
 M scripts/smoke_live_quotes.py
?? docs/dev_reports/2026-06-11-a-share-live-data-closed-loop-acceptance-fix-review-fix-report.md
?? tests/test_smoke_live_quotes.py

$ git diff --stat
 scripts/smoke_live_quotes.py | 4 ++--
 1 file changed, 2 insertions(+), 2 deletions(-)

$ git diff --check
(no output — clean)
```

The fix is minimal: 2 lines changed in the smoke script, no other files touched.

### S1 fix inspection

**Before** (the bug):
```python
f"PARTIAL: Got {succeeded}/{args.symbols_requested} quotes, ..."  # line 207
f"PASSED: {succeeded}/{args.symbols_requested} quotes from ..."   # line 216
```

**After** (the fix):
```python
f"PARTIAL: Got {succeeded}/{report['symbols_requested']} quotes, ..."
f"PASSED: {succeeded}/{report['symbols_requested']} quotes from ..."
```

Confirmed: both references to `args.symbols_requested` replaced with `report['symbols_requested']`.

### Static checks

```text
$ ./.venv/bin/python -m ruff check scripts/smoke_live_quotes.py tests/test_smoke_live_quotes.py
All checks passed!

$ ./.venv/bin/python -m py_compile scripts/smoke_live_quotes.py
(no output — OK)
```

### Automated test results

**Smoke script tests** (8 tests, all mock):

```text
$ ./.venv/bin/python -m pytest tests/test_smoke_live_quotes.py -q \
  --basetemp=runtime/pytest-tmp-smoke-review-verification
8 passed in 4.72s
```

| Test | Exit code | JSON status | Verdict |
|---|---|---|---|
| `test_full_success` | 0 | `passed` | PASS |
| `test_partial_success` | 3 | `partial` | PASS |
| `test_all_providers_failed` | 2 | `failed` | PASS |
| `test_demo_blocked_without_flag` | 2 | `failed` | PASS |
| `test_demo_allowed_with_flag` | 0 | `passed` | PASS |
| `test_empty_symbols` | 1 | — | PASS |
| `test_negative_min_success` | 1 | — | PASS |
| `test_service_exception` | 1 | `failed` | PASS |

**Broad regression** (pool + eastmoney + smoke, 55 tests):

```text
$ ./.venv/bin/python -m pytest tests/test_stock_pool_service.py \
  tests/test_eastmoney_provider.py tests/test_smoke_live_quotes.py \
  -q --basetemp=runtime/pytest-tmp-architect-review-r2-verification
55 passed, 1 warning in 18.61s
```

### Manual mock verification (4 exit-code branches)

Each scenario was verified with a standalone Python script mocking `get_live_data_service()`:

| Scenario | Mock condition | Exit code | Status | Verified |
|---|---|---|---|---|
| Full success | `data_status=OK`, 3 quotes, min-success=2 | **0** | `passed` | PASS |
| Partial success | `data_status=OK`, 2 quotes, min-success=5 | **3** | `partial` | PASS |
| All providers failed | `data_status=FAILED`, 0 quotes | **2** | `failed` | PASS |
| Demo blocked | `is_demo=True`, no `--allow-demo` | **2** | `failed` | PASS |

## 4. JSON Output Field Verification

The smoke script outputs a JSON report with all fields required by the architecture document (`docs/design/2026-06-11-a-share-live-data-closed-loop-acceptance-fix-architecture.md` §4.3):

| Field | Required | In script | Verified |
|---|---|---|---|
| `status` | Yes | `report["status"]` | ✅ full success/partial/failed |
| `run_at` | Yes | `run_at.isoformat()` | ✅ |
| `trading_session` | Yes | `_trading_session()` | ✅ |
| `symbols_requested` | Yes | `len(symbol_list)` | ✅ 3/3, 3/2 |
| `symbols_succeeded` | Yes | `len(quotes)` | ✅ 3, 2, 0 |
| `is_demo` | Yes | `result.get("is_demo")` | ✅ false/true |
| `provider` | Yes | `result.get("chosen_provider")` | ✅ "eastmoney" |
| `fallback_chain` | Yes | `result.get("fallback_chain")` | ✅ |
| `latency_ms` | Yes | `data_delay_report.elapsed_ms` | ✅ 12ms |
| `data_status` | Yes | `result.get("data_status")` | ✅ OK/FAILED |
| `updated_at_min` | Yes | `min(timestamps)` | ✅ |
| `updated_at_max` | Yes | `max(timestamps)` | ✅ |
| `feedback_bug_id` | Yes | `result.get("feedback_bug_id")` | ✅ None/"BUG_..." |
| `quotes_sample` | Yes | First 5 quotes excerpted | ✅ up to 5 |

All 14 required fields are present in the JSON output. Verified via both automated tests and manual mock runs.

The `quotes_sample` entry shape:
```json
{
  "symbol": "600000.SH",
  "price": 10.0,
  "volume": 1000,
  "updated_at": "2026-06-11T10:00:00+08:00",
  "provider": "eastmoney"
}
```

## 5. Safety Verification

| Check | Result |
|---|---|
| Fail-closed: `data_status=FAILED` → exit code 2 | **PASS** |
| Demo blocked: `is_demo=True` without `--allow-demo` → exit code 2 | **PASS** |
| Demo allowed: `is_demo=True` with `--allow-demo` → exit code 0 | **PASS** (testing helper only) |
| No live closed-loop code modified | **PASS** (only smoke script changed) |
| No trading/risk/execution/order code touched | **PASS** |
| No secrets committed | **PASS** |
| All tests use mock, no external network | **PASS** |

## 6. Test Coverage Matrix

| Test file | Tests | Coverage |
|---|---|---|
| `tests/test_smoke_live_quotes.py` | 8 | S1 fix: all exit-code branches + JSON output contract |
| `tests/test_stock_pool_service.py` | 35 | Theme pool contract (unchanged, re-run for regression) |
| `tests/test_eastmoney_provider.py` | 12 | Eastmoney hardening (unchanged, re-run for regression) |
| **Total** | **55** | All passing |

## 7. Remaining Risk

1. **Market-hours smoke still required**: The smoke script now correctly handles all exit-code branches and produces valid JSON output. However, PM acceptance still requires a run during A-share trading hours (09:30-11:30 or 13:00-15:00 CST) with a real provider returning non-demo quotes for at least 10 symbols.
2. **No regression introduced**: The fix changes only 2 lines in the smoke script. All other acceptance-fix functionality (theme pool, provider hardening, fail-closed) is unchanged and confirmed passing.

## 8. Defect List

No new defects found. Both S1 and S2 from the architecture review are confirmed fixed.

## 9. Final Conclusion

**PASS**

The architecture review blocking findings are fully resolved:

- **S1 (fixed)**: `args.symbols_requested` replaced with `report['symbols_requested']` on both affected lines. All four exit-code paths (0, 1, 2, 3) are verified with mocked tests and manual validation. JSON output contains all 14 required fields.
- **S2 (fixed)**: `tests/test_smoke_live_quotes.py` exists with 8 tests covering full success, partial success, all providers failed, demo blocked, demo allowed (with flag), empty symbols, negative min-success, and service exception. All tests use mock and require no external network.
- **No regression**: The fix is minimal (2 lines in 1 file). All existing tests continue to pass (55 tests).
- **Safety preserved**: Fail-closed (exit 2) and demo-blocked behavior are confirmed. No trading/risk/execution logic was touched.

The implementation can proceed to PM acceptance. The only remaining step is a trading-hours smoke run with real providers to produce the final acceptance JSON evidence.
