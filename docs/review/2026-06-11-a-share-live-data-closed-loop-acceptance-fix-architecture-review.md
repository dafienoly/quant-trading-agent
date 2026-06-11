# A-share Live Data Closed-loop Acceptance Fix Architecture Review

> Role: Architect Reviewer  
> Date: 2026-06-11  
> Requirement: `docs/requirements/2026-06-10-a-share-live-data-closed-loop-requirements.md`  
> Architecture: `docs/design/2026-06-11-a-share-live-data-closed-loop-acceptance-fix-architecture.md`  
> Development report: `docs/dev_reports/2026-06-11-a-share-live-data-closed-loop-acceptance-fix-dev-report.md`  
> Test report: `docs/test_reports/2026-06-11-a-share-live-data-closed-loop-acceptance-fix-verification-report.md`  
> Conclusion: **CHANGES_REQUESTED**

## 1. Review Scope

Reviewed the acceptance-fix implementation against the PM rejection blockers:

1. Built-in `ai_semiconductor` theme pool must be non-empty, contract-valid, and usable by product APIs.
2. Realtime quote acceptance smoke must be deterministic and capable of proving at least 10 non-demo realtime quotes during A-share trading hours.
3. Provider failures must remain fail-closed and must not reintroduce demo fallback or unsafe signal/order behavior.

Reviewed files and evidence:

- `data/reference/theme_pools/ai_semiconductor.json`
- `scripts/validate_theme_pool.py`
- `scripts/smoke_live_quotes.py`
- `src/data_gateway/eastmoney_provider.py`
- `src/product_app/stock_pool_service.py`
- `tests/test_stock_pool_service.py`
- `tests/test_eastmoney_provider.py`
- Development and test reports listed above.

## 2. Blocking Findings

### S1 - Smoke script cannot pass or report partial success

File: `scripts/smoke_live_quotes.py`

Lines:

- `207`: `args.symbols_requested`
- `216`: `args.symbols_requested`

The smoke script references `args.symbols_requested`, but the argparse namespace
does not define this field. As a result:

- The partial-success path crashes instead of returning exit code `3`.
- The full-success path crashes instead of returning exit code `0`.
- A real provider success during market hours would still fail to produce the
  official acceptance evidence required by the architecture document.

This directly breaks the P0-2 acceptance-fix requirement:

- "Realtime smoke returns at least 10 usable non-demo quotes."
- "Smoke output records provider, fallback chain, latency, updated_at, and data health."
- Exit-code contract: `0` pass, `3` partial success.

Reproduction used during review:

```powershell
@'
import sys
from unittest.mock import patch
import scripts.smoke_live_quotes as smoke

class FakeService:
    def get_realtime_quotes(self, symbols, pool_type="watchlist", allow_demo=False):
        return {
            "data_status": "OK",
            "quotes": [
                {
                    "symbol": s,
                    "last_price": 1.23,
                    "volume": 100,
                    "updated_at": "2026-06-11T10:00:00+08:00",
                    "data_source": "fake",
                }
                for s in symbols
            ],
            "chosen_provider": "fake",
            "fallback_chain": ["fake"],
            "data_delay_report": {"elapsed_ms": 12},
            "is_demo": False,
            "feedback_bug_id": None,
        }

with patch("src.product_app.live_data_service.get_live_data_service", return_value=FakeService()):
    sys.argv = ["smoke_live_quotes.py", "--symbols", "600000.SH,000001.SZ", "--min-success", "2"]
    smoke.main()
'@ | .\.venv\Scripts\python.exe -
```

Observed result:

```text
AttributeError: 'Namespace' object has no attribute 'symbols_requested'
```

Required fix:

- Replace `args.symbols_requested` with `len(symbol_list)` or `report["symbols_requested"]`.
- Add deterministic tests for:
  - full success returns `0` and writes `status=passed`;
  - partial success returns `3` and writes `status=partial`;
  - all providers failed returns `2`;
  - demo result without `--allow-demo` returns failure.

### S2 - Smoke script success and partial branches are not covered by tests

The developer and tester reports only prove the fail-closed path for the smoke
script. The architecture explicitly requires success, partial, and failure exit
codes, but there is no test file covering `scripts/smoke_live_quotes.py`.

This is why the S1 defect survived both development and verification.

Required fix:

- Add `tests/test_smoke_live_quotes.py` or equivalent.
- Mock `get_live_data_service()` instead of calling external providers.
- Verify both exit code and JSON output contract.

## 3. Non-blocking Observations

### P0-1 theme pool is resolved

`data/reference/theme_pools/ai_semiconductor.json` exists and is tracked by git.
The validation script passes:

```text
VALIDATION PASSED: 109 stocks, 8 tags
```

The reviewed contract tests also pass:

```text
47 passed, 2 warnings
```

The theme pool satisfies the architecture contract:

- 109 stocks.
- Required tags include `ai_chip` and `optical_module`.
- Mainboard-only prefix rules pass.
- No duplicate symbols.
- Required metadata fields are present.

### Eastmoney provider hardening is acceptable

The provider now includes browser-like headers, short timeouts, bulk path, and
single-symbol fallback. Mocked tests cover the intended behavior and pass in the
focused review run.

### Real market-hours evidence is still pending

The test report states that realtime provider smoke was run outside trading
hours and without usable external provider access. This is acceptable as a
testing-environment limitation, but it means PM acceptance still needs a
market-hours run after the smoke script defect is fixed.

## 4. Verification Performed by Architect Reviewer

```powershell
.\.venv\Scripts\python.exe scripts\validate_theme_pool.py
```

Result:

```text
VALIDATION PASSED: 109 stocks, 8 tags
```

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_stock_pool_service.py tests\test_eastmoney_provider.py -q --basetemp=runtime\pytest-tmp-architect-review
```

Result:

```text
47 passed, 2 warnings
```

Additional mocked smoke-script review:

- Full-success path: fails with `AttributeError`.
- Partial-success path: fails with `AttributeError`.

## 5. Review Decision

**CHANGES_REQUESTED**

The implementation cannot proceed to PM acceptance yet.

Reasons:

1. The official realtime acceptance smoke script cannot produce a passing result
   even if a provider returns valid realtime quotes.
2. The smoke script does not have tests for its success or partial-success
   branches.
3. P0-2 remains unproven until the script is fixed and a market-hours non-demo
   quote smoke is captured.

After the required fixes, rerun:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_stock_pool_service.py tests\test_eastmoney_provider.py tests\test_smoke_live_quotes.py -q --basetemp=runtime\pytest-tmp-architect-review-r2
.\.venv\Scripts\python.exe scripts\validate_theme_pool.py
.\.venv\Scripts\python.exe scripts\smoke_live_quotes.py --symbols 600000.SH,000001.SZ,600584.SH,002463.SZ,603986.SH,601138.SH,000021.SZ,600703.SH,603228.SH,002371.SZ --min-success 10 --output docs\test_reports\2026-06-11-a-share-live-quote-smoke.json
```

The last command must be run during A-share trading hours for PM acceptance.

