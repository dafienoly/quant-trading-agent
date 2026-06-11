# A-share Live Data Closed-loop Acceptance Fix — Development Report

## Scope

- **Requirements**: `docs/requirements/2026-06-10-a-share-live-data-closed-loop-requirements.md`
- **Architecture (original)**: `docs/design/2026-06-10-a-share-live-data-closed-loop-architecture.md`
- **Architecture (acceptance fix)**: `docs/design/2026-06-11-a-share-live-data-closed-loop-acceptance-fix-architecture.md`
- **Python interpreter**: `./.venv/bin/python` — Python 3.13.5

## Changed Files

### Modified files (tracked):

| File | Change |
|---|---|
| `.gitignore` | Un-ignore `data/reference/theme_pools/` so curated reference data is tracked |
| `src/data_gateway/eastmoney_provider.py` | Harden: browser-like headers, single-symbol fallback, proper timeouts |
| `src/product_app/stock_pool_service.py` | Add `pool_id` to `get_theme_pool()` response |
| `tests/test_stock_pool_service.py` | Add theme pool contract tests + pool API endpoint test |

### New files (untracked):

| File | Purpose |
|---|---|
| `data/reference/theme_pools/ai_semiconductor.json` | Updated metadata fields: `data_source`, `universe`, `exchange`, `is_st`, `is_delisting`, `evidence` per architecture contract |
| `scripts/validate_theme_pool.py` | Validates theme pool JSON against architecture contract rules |
| `scripts/smoke_live_quotes.py` | Market-hours smoke script for live quote acceptance (exit codes 0/1/2/3) |
| `tests/test_eastmoney_provider.py` | Unit tests for Eastmoney provider: headers, bulk path, single-symbol fallback, full failure |

## Feature-to-Code Mapping

| Feature ID | Description | Code File(s) |
|---|---|---|
| F-001 / F-003 | Multi-provider hub, auto fallback | `eastmoney_provider.py` (bulk + single-symbol fallback) |
| F-005 | Watchlist management | `stock_pool_service.py` |
| F-006 | AI算力/半导体 theme pool | `ai_semiconductor.json` (updated), `stock_pool_service.py` (pool_id fix) |
| F-007 | Real-time quote acceptance | `scripts/smoke_live_quotes.py` |
| P0-1 fix | Theme pool not empty, valid data | `ai_semiconductor.json` contract fields, `validate_theme_pool.py`, contract tests |
| P0-2 fix | Live quote provider hardening | `eastmoney_provider.py` headers + single-symbol fallback, `test_eastmoney_provider.py` |

## Verification Commands and Results

### Static checks

```bash
./.venv/bin/python -m ruff check \
  scripts/validate_theme_pool.py scripts/smoke_live_quotes.py \
  src/data_gateway/eastmoney_provider.py src/product_app/stock_pool_service.py \
  tests/test_stock_pool_service.py tests/test_eastmoney_provider.py
# Result: All checks passed!

./.venv/bin/python -m py_compile \
  src/data_gateway/eastmoney_provider.py src/product_app/stock_pool_service.py \
  scripts/validate_theme_pool.py scripts/smoke_live_quotes.py
# Result: (no output — OK)
```

### Tests

```bash
./.venv/bin/python -m pytest \
  tests/test_stock_pool_service.py tests/test_eastmoney_provider.py \
  tests/test_live_data_mapper.py tests/test_live_data_service.py \
  tests/test_search_evidence.py tests/test_live_signal.py \
  -q --basetemp=runtime/pytest-tmp-acceptance-fix
# Result: 161 passed, 1 warning (pre-existing StarletteDeprecationWarning)
```

### Theme pool data validation

```bash
./.venv/bin/python scripts/validate_theme_pool.py
# Result: VALIDATION PASSED: 109 stocks, 8 tags
```

- 109 stocks (range 100-300 ✓)
- Tags include `ai_chip` and `optical_module` ✓
- All symbols match `^\d{6}\.(SH|SZ)$` pattern ✓
- All mainboard (600/601/603/605/000/001/002/003) ✓
- No duplicates ✓
- All stocks have required fields (symbol, name, exchange, board_type, tags, is_st, is_delisting, evidence) ✓

### Smoke script

The smoke script was tested with `--symbols 600000.SH,000001.SZ --min-success 2`. During the test run, all external providers were unavailable (network disconnected / outside market hours), so the script correctly failed closed (exit code 2) with fallback chain recording. The script produces structured JSON output at the specified path.

### Git checks

```bash
git status --short --branch
# feature/quant-factor-v1...origin/feature/quant-factor-v1

git diff --stat
# 4 files changed, 215 insertions(+), 14 deletions(-)

git diff --check
# (no output — OK)
```

## Theme Pool Summary

| Property | Value |
|---|---|
| `pool_id` | `ai_semiconductor` |
| Stock count | 109 |
| `data_source` | `curated_reference` |
| `universe` | `a_share_mainboard` |
| `version` | `2026-06-11` |
| Required tags | `ai_chip`, `optical_module` (both present) |
| Mainboard only | Yes |
| No ChiNext/STAR/ST | Yes |

## Skipped / Not Run

- **Real-time smoke with external network**: Not run because the development environment has no internet access to Eastmoney/AkShare endpoints. The smoke script is structurally complete and will be run during PM acceptance in a network-enabled environment during A-share trading hours (09:30-11:30 or 13:00-15:00 Asia/Shanghai).
- **Full project regression**: The acceptance fix only touches theme pool and Eastmoney provider. The relevant test files were run. Running broader regression is deferred to the Test Engineer Agent, who can decide if broad `tests/` run is needed.

## Safety Confirmation

- Default live trading remains disabled (`ENABLE_LIVE_TRADING=false`, `MAX_TRADING_LEVEL=LEVEL_1_SIGNAL_ONLY`).
- Risk Agent veto is not bypassed.
- No secrets committed (keys from env vars only).
- No batch buy confirmation introduced.
- All providers failing results in `data_status=FAILED` and blocks signal / order draft.
- `allow_demo=False` is the hardcoded default for live closed-loop paths.
- Theme pool excludes ChiNext (`300`/`301`), STAR (`688`/`689`), ST, and delisting stocks.
- The Eastmoney provider uses browser-like headers but never sends credentials or tokens.
- `LEVEL_3_AUTO` is rejected by the `/signal/draft` API endpoint.

## Residual Risk

1. **External provider availability**: Eastmoney, AkShare, and AkTools are free public APIs that may change endpoints or block requests. The smoke script is designed to document their actual availability during acceptance.
2. **Theme pool coverage**: The current 109-stock pool is curated manually. As the AI semiconductor industry evolves, the pool should be periodically reviewed by a domain expert.
3. **Market-hours dependency**: The realtime quote acceptance smoke must be run during A-share trading hours (09:30-11:30 or 13:00-15:00 Asia/Shanghai) to produce passing evidence. The script correctly reports fail-closed behavior outside trading hours.

## Handoff

This development report, together with the code changes and test results, is ready for the **Test Engineer Agent** to verify and produce a test report at `docs/test_reports/2026-06-11-a-share-live-data-closed-loop-acceptance-fix-verification-report.md`.
