# A-share Live Data Closed-loop Acceptance Fix — Review Fix Report

## Review Document

- **Review report**: `docs/review/2026-06-11-a-share-live-data-closed-loop-acceptance-fix-architecture-review.md`
- Conclusion: **CHANGES_REQUESTED**
- Blocking defects: S1 (smoke script `args.symbols_requested`), S2 (no smoke script tests)

## Fix Scope

修复严格限定在架构 Review 报告指出的两个阻断项内，未扩大范围。

### S1 fix: `scripts/smoke_live_quotes.py`

`args.symbols_requested`（不存在于 argparse Namespace）被替换为 `report['symbols_requested']`（已在报告骨架中初始化）。

- 第 207 行：`args.symbols_requested` → `report['symbols_requested']`
- 第 216 行：`args.symbols_requested` → `report['symbols_requested']`

Exit-code 契约未改变：0 全量通过 / 1 脚本错误 / 2 fail closed / 3 部分通过。

### S2 fix: `tests/test_smoke_live_quotes.py`

新增 8 个测试，全部 mock `get_live_data_service()`，不调用真实外部 provider：

| # | 场景 | mock 条件 | 期望 exit code | JSON status |
|---|---|---|---|---|
| 1 | Full success | `data_status=OK`, 3 quotes, min-success=2 | 0 | `passed` |
| 2 | Partial success | `data_status=OK`, 2 quotes, min-success=5 | 3 | `partial` |
| 3 | All providers failed | `data_status=FAILED`, 0 quotes | 2 | `failed` |
| 4 | Demo blocked | `is_demo=True`, 未传 --allow-demo | 2 | `failed` |
| 5 | Demo allowed | `is_demo=True`, 传 --allow-demo | 0 | `passed` |
| 6 | Empty symbols | 空字符串 | 1 | — |
| 7 | Negative min-success | min-success=0 | 1 | — |
| 8 | Service exception | `get_live_data_service` 抛出异常 | 1 | `failed` |

每个测试验证：
- exit code 符合契约
- JSON 输出文件正确写入
- `status` / `symbols_requested` / `symbols_succeeded` / `provider` / `fallback_chain` / `data_status` / `is_demo` / `feedback_bug_id` 等字段正确

## Changed Files

| File | Status | Change |
|---|---|---|
| `scripts/smoke_live_quotes.py` | Modified | 2 lines: `args.symbols_requested` → `report['symbols_requested']` |
| `tests/test_smoke_live_quotes.py` | **New** | 8 tests, mock provider, no network |

## Verification Results

### Static checks

```bash
./.venv/bin/python -m ruff check scripts/smoke_live_quotes.py tests/test_smoke_live_quotes.py
# All checks passed!

./.venv/bin/python -m py_compile scripts/smoke_live_quotes.py
# (no output — OK)
```

### Smoke script tests

```bash
./.venv/bin/python -m pytest tests/test_smoke_live_quotes.py -q \
  --basetemp=runtime/pytest-tmp-smoke-review-fix
# 8 passed in 4.67s
```

### Broad regression

```bash
./.venv/bin/python -m pytest \
  tests/test_stock_pool_service.py tests/test_eastmoney_provider.py \
  tests/test_smoke_live_quotes.py -q \
  --basetemp=runtime/pytest-tmp-architect-review-r2
# 55 passed, 1 warning (pre-existing StarletteDeprecationWarning)
```

### Git

```bash
git status --short --branch
# feature/quant-factor-v1...origin/feature/quant-factor-v1

git diff --stat
# scripts/smoke_live_quotes.py | 4 ++--

git diff --check
# (no output — clean)
```

## Safety Confirmation

- ✅ Fail-closed 行为未改变（exit code 2 保留）
- ✅ 未引入 demo fallback 作为通过条件（`is_demo=True` 且无 `--allow-demo` 时 exit 2）
- ✅ 未修改真实交易、风控、执行、订单相关逻辑
- ✅ 仅修改了 smoke 脚本和新增了测试文件
- ✅ 签名契约（exit code 0/1/2/3）未改变
- ✅ 所有测试使用 mock，不依赖真实外部网络

## Remaining Risk

1. **Market-hours smoke 仍需运行**：这次修复确保脚本本身能正确运行所有路径，但 PM 验收仍需在 A 股交易时段执行真实 provider 验证。
2. **测试覆盖了所有脚本内分支**：full success、partial、failed、demo blocked、参数错误、service exception 共 8 个测试。

## Handoff

修复完成，可交回 Test Engineer Agent 复测。
