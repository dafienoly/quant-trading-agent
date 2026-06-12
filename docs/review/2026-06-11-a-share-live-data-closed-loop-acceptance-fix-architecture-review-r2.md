# A-share Live Data Closed-loop Acceptance Fix Architecture Review R2

> Role: Architect Reviewer  
> Date: 2026-06-11  
> Requirement: `docs/requirements/2026-06-10-a-share-live-data-closed-loop-requirements.md`  
> Architecture: `docs/design/2026-06-11-a-share-live-data-closed-loop-acceptance-fix-architecture.md`  
> Prior review: `docs/review/2026-06-11-a-share-live-data-closed-loop-acceptance-fix-architecture-review.md`  
> Dev fix report: `docs/dev_reports/2026-06-11-a-share-live-data-closed-loop-acceptance-fix-review-fix-report.md`  
> Test fix report: `docs/test_reports/2026-06-11-a-share-live-data-closed-loop-acceptance-fix-review-fix-verification-report.md`  
> Conclusion: **APPROVED_WITH_NOTES**

## 1. Review Scope

This R2 review only verifies whether the blocking findings from the previous
architecture review were fixed:

1. `scripts/smoke_live_quotes.py` must no longer crash on success or partial
   success paths.
2. Smoke script success, partial, fail-closed, and demo-blocked branches must be
   covered by deterministic tests.
3. The fix must preserve live-data fail-closed behavior and must not change
   trading, risk, execution, or order logic.

## 2. Prior Blocking Findings

| Finding | Prior severity | R2 result |
|---|---:|---|
| Smoke script referenced missing `args.symbols_requested` | S1 | **Fixed** |
| Smoke script had no tests for success/partial branches | S2 | **Fixed** |

## 3. Code Review Result

### S1 fixed

`scripts/smoke_live_quotes.py` now uses `report["symbols_requested"]` in both
affected output branches:

- partial success branch
- full success branch

No remaining `args.symbols_requested` references exist.

### S2 fixed

`tests/test_smoke_live_quotes.py` was added and covers:

- full success: exit code `0`, JSON `status="passed"`;
- partial success: exit code `3`, JSON `status="partial"`;
- all providers failed: exit code `2`, JSON `status="failed"`;
- demo blocked without `--allow-demo`: exit code `2`;
- demo allowed with `--allow-demo`: exit code `0` for test-only behavior;
- empty symbols: exit code `1`;
- invalid `--min-success`: exit code `1`;
- service exception: exit code `1` with service error recorded.

The tests mock `get_live_data_service()` and do not call external providers.

### Safety boundaries preserved

The fix is limited to the smoke script and smoke tests. It does not modify:

- `src/risk_engine/`
- `src/execution_engine/`
- order submission paths
- signal generation logic
- provider failover logic
- live-data service fail-closed behavior

The real command-line smoke run in this review still failed closed in the current
environment, with `is_demo=false` and a feedback bug id recorded. That is the
expected safety behavior outside a successful provider/trading-hours run.

## 4. Architect Verification

Commands run by Architect Reviewer:

```powershell
.\.venv\Scripts\python.exe -m ruff check scripts\smoke_live_quotes.py tests\test_smoke_live_quotes.py
```

Result:

```text
All checks passed!
```

```powershell
.\.venv\Scripts\python.exe -m py_compile scripts\smoke_live_quotes.py
```

Result:

```text
PASS
```

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_smoke_live_quotes.py -q --basetemp=runtime\pytest-tmp-architect-review-r2-smoke
```

Result:

```text
8 passed, 1 warning
```

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_stock_pool_service.py tests\test_eastmoney_provider.py tests\test_smoke_live_quotes.py -q --basetemp=runtime\pytest-tmp-architect-review-r2
```

Result:

```text
55 passed, 2 warnings
```

```powershell
.\.venv\Scripts\python.exe scripts\validate_theme_pool.py
```

Result:

```text
VALIDATION PASSED: 109 stocks, 8 tags
```

Short command-line smoke run:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_live_quotes.py --symbols 600000.SH,000001.SZ --min-success 2 --output runtime\architect-review-r2-smoke.json
```

Observed result:

- exit path: fail-closed;
- `trading_session="closed"`;
- `data_status="FAILED"`;
- `is_demo=false`;
- `feedback_bug_id="BUG_20260611_UB37C1"`;
- fallback chain recorded: `eastmoney`, `akshare_realtime`, `aktools`.

This confirms the script still records a structured failure report when public
providers are unavailable.

## 5. Remaining Notes

### N1 - PM acceptance still needs a trading-hours real-provider smoke

This is not a code-review blocker anymore, but it remains a PM acceptance gate.
The final product acceptance must run the official smoke command during A-share
trading hours and capture at least 10 non-demo realtime quotes:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_live_quotes.py --symbols 600000.SH,000001.SZ,600584.SH,002463.SZ,603986.SH,601138.SH,000021.SZ,600703.SH,603228.SH,002371.SZ --min-success 10 --output docs\test_reports\2026-06-11-a-share-live-quote-smoke.json
```

The PM acceptance command must not use `--allow-demo`.

### N2 - Warnings are non-blocking

The reviewed pytest runs produced only known non-blocking warnings:

- `StarletteDeprecationWarning` from FastAPI TestClient dependency behavior.
- `PytestCacheWarning` from local `.pytest_cache` creation on this Windows worktree.

No warning changes the review conclusion.

## 6. Review Decision

**APPROVED_WITH_NOTES**

The previous architecture-review blockers are fixed. The implementation can
proceed to PM acceptance.

The only remaining gate is product evidence, not code correctness: PM acceptance
must run the market-hours realtime smoke and verify a non-demo provider success
for at least 10 A-share mainboard symbols.

