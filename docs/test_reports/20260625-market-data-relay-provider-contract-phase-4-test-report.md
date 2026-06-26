# Phase 4 测试报告 — Product API `/product/market/**`（Slice D）

## 基本信息

| 项目 | 值 |
|------|-----|
| 需求文档 | `docs/requirements/2026-06-25-market-data-relay-provider-contract-requirements.md` |
| 架构文档 | `docs/design/2026-06-25-market-data-relay-provider-contract-architecture.md` |
| 团队计划 | `docs/dev_plans/20260625-market-data-relay-provider-contract-team-plan.md` |
| 开发报告 | `docs/dev_reports/20260625-market-data-relay-provider-contract-phase-4-dev-report.md` |
| 路线图 | V16.2 Market Data Relay & Provider Contract |
| 测试阶段 | Phase 4 — Product API `/product/market/**`（Slice D） |
| 测试工程师 | OpenCode Test Engineer (`claude_tester`) |

## 测试环境

| 项目 | 值 |
|------|-----|
| base branch | `epic/20260625-market-data-relay-provider-contract-run-28168858781` |
| base commit | `8ebe1cf` |
| temporary test branch | `test/market-data-relay-provider-contract-phase-4-tester-20260626-0233`（已删除） |
| Python 版本 | 3.14.4（系统 `python3`，无 `.venv`） |
| 平台 | Linux (WSL) |
| 测试框架 | pytest 9.1.1 |
| 静态检查 | ruff（pyproject.toml） |
| 工作区状态 | `.agent/gates/stage_start_gate.json` 有未提交修改（pipeline 控制文件，非业务代码） |

## 测试范围与不测范围

### 测试范围

| 文件 | 说明 |
|------|------|
| `src/api/market_data_routes.py` | `/product/market/**` API 路由（6 个端点） |
| `src/api/app.py` | 追加一行 router 注册（`include_router`） |
| `tests/test_market_data_routes.py` | 18 个 Phase 4 测试用例 |

### 不测范围（合理排除）

| 项 | 原因 |
|----|------|
| Phase 5 Streamlit UI | Phase 5 尚未开发；本阶段仅测试 API 路由 |
| 真实网络调用 | 所有测试使用 mock relay（确定性测试） |
| `src/data_gateway/` provider 实现 | 未修改（路由只依赖 Relay，不 import raw provider） |
| `src/risk_engine/` / `src/execution_engine/` | 未触碰 |
| `src/stock_pool/` | 未触碰 |
| 持久化审计存储 | Phase 3 范围（内存状态，dev report 已说明重启丢失） |

## 需求覆盖矩阵

| 需求条目 | 测试覆盖 | 状态 |
|----------|----------|------|
| §1 Relay 统一产品入口 + `/product/**` | `test_routes_under_product_prefix` | PASS |
| §1 `GET /product/market/latest/{symbol}` | `test_get_latest_quote_success`, `test_get_latest_quote_with_market_param` | PASS |
| §1 `POST /product/market/latest` | `test_post_latest_quotes_success`, `test_post_latest_quotes_partial_failure`, `test_post_latest_quotes_all_failed`, `test_post_latest_quotes_invalid_body`, `test_post_latest_with_caller_context` | PASS |
| §1 `GET /product/market/bars/{symbol}` | `test_get_bars_success`, `test_get_bars_missing_params`, `test_get_bars_provider_fail_closed` | PASS |
| §3 数据质量字段 | `test_get_latest_quote_success`（quality 字段断言） | PASS |
| §4 Fail-closed | `test_get_latest_quote_provider_fail_closed`, `test_get_bars_provider_fail_closed`, `test_post_latest_quotes_all_failed` | PASS |
| §5 Provider Priority / Fallback | `test_post_latest_quotes_partial_failure`（item_errors 记录） | PASS |
| §6 Provider Health | `test_get_providers_health_success` | PASS |
| §6 Provider Quality | `test_get_providers_quality_success` | PASS |
| §6 Fallback Status | `test_get_providers_fallback_success` | PASS |
| §8 下游边界（不直接调用 raw provider） | `test_no_raw_provider_import_in_routes` | PASS |
| 安全：secret 不泄露 | `test_error_response_no_secrets`, `test_get_latest_quote_internal_error` | PASS |
| 安全：无未批准 `/api/**` 前缀 | `test_routes_under_product_prefix` + 手动检查 | PASS |
| 安全：Streamlit 未被标记 deprecated | grep 检查 | PASS |
| 兼容性：FastAPI app factory 正常 | 全部路由测试通过 | PASS |

## 复跑开发报告命令

### Ruff 静态检查

```bash
python3 -m ruff check src/api/market_data_routes.py src/api/app.py tests/test_market_data_routes.py
```

结果：**All checks passed!**

### py_compile

```bash
python3 -m py_compile src/api/market_data_routes.py src/api/app.py
```

结果：**通过**（无输出，退出码 0）

### Phase 4 测试（18 个用例）

```bash
python3 -m pytest tests/test_market_data_routes.py -q --basetemp=runtime/pytest-tmp-market-data-relay-provider-contract-api
```

结果：**18 passed**

### 更广回归（触及共享 API entrypoint）

```bash
python3 -m pytest tests/test_product_routes.py tests/test_live_data_service.py tests/test_agentops_routes.py -q --tb=short --basetemp=runtime/pytest-tmp-market-data-relay-provider-contract-api-regression
```

结果：**40 passed**（无回归性失败）

### git diff --check

```bash
git diff --check
```

结果：**通过**（仅有 `.agent/gates/stage_start_gate.json` CRLF warning，非本阶段修改的文件，为 pipeline 控制文件）

## 补充测试

### Phase 1–3 市场数据回归（166 个用例）

```bash
python3 -m pytest tests/test_market_data_contracts.py tests/test_market_data_quality.py tests/test_market_data_errors.py tests/test_market_data_provider_registry.py tests/test_market_data_adapters.py tests/test_market_data_relay.py tests/test_market_data_audit.py tests/test_market_data_health.py tests/test_market_data_cache.py -q --tb=short --basetemp=runtime/pytest-tmp-market-data-relay-provider-contract-phase-4-extra
```

结果：**166 passed**

### Legacy 市场数据回归（flat 文件迁移验证）

```bash
python3 -m pytest tests/test_product_market_data.py tests/test_realtime_provider.py tests/test_v16_0b_readonly_market_dashboard.py tests/test_product_service_manager_quotes.py tests/test_quote_health.py -q --tb=short --basetemp=runtime/pytest-tmp-market-data-relay-provider-contract-legacy-regression
```

结果：**35 passed**, 1 failed + 1 error（均为预存在、与 Phase 4 无关的问题；见缺陷列表）

### 全量回归（完整项目）

```bash
python3 -m pytest tests -q --tb=short --basetemp=runtime/pytest-tmp-market-data-relay-provider-contract-full
```

结果：**1340 passed**, 6 failed, 6 skipped（6 个失败均为预存在、与 Phase 4 无关；见下文说明）

### 额外边缘测试

| 测试 | 结果 |
|------|------|
| Invalid date format in bars (`start=bad-date`) | 422 ✓ |
| Empty date string in bars (`start=`) | 422 ✓ |
| `/api/market/latest/...` 不存在 | 404 ✓ |
| `/market/latest/...` 裸前缀不存在 | 404 ✓ |
| 数据质量字段完整性（11 字段） | 全部存在 ✓ |

## 安全检查证据

| 检查项 | 方法 | 结果 |
|--------|------|------|
| 未新增 `/api/**` 平行业务前缀 | 路由遍历断言 + HTTP 404 验证 | PASS |
| 路由位于 `/product/market/**` | `test_routes_under_product_prefix` | PASS |
| 未 import raw provider | `test_no_raw_provider_import_in_routes` (AST 分析) | PASS |
| 错误响应不含 secret | `test_error_response_no_secrets` + `test_get_latest_quote_internal_error` | PASS |
| 错误响应不含 traceback/绝对路径 | 同上 + 手动 grep | PASS |
| Streamlit 未被标记 legacy/deprecated/待删除 | `grep -rn "deprecated\|legacy\|待删除" src/ui_report/` 无结果 | PASS |
| 路由不包含 buy/sell/order/trade/execute | `grep -rn` 无结果 | PASS |
| 不触碰 `src/risk_engine/` | git diff 无该目录变更 | PASS |
| 不触碰 `src/execution_engine/` | git diff 无该目录变更 | PASS |
| 不触碰 `src/stock_pool/` | git diff 无该目录变更 | PASS |
| 不修改 `src/data_gateway/` | git diff 无该目录变更 | PASS |
| 不新增真实交易能力 | 无 execution/order/trade 变更 | PASS |
| 不暴露 `LEVEL_3_AUTO` | 路由无此字段 | PASS |

## 缺陷列表

### 预存在缺陷（与本 Phase 无关）

| 编号 | 测试 | 问题 | 严重度 | 状态 |
|------|------|------|--------|------|
| PRE-001 | `test_aktools_provider_fetches_realtime_quotes_from_http_mapping` | `ImportError: Using SOCKS proxy, but the 'socksio' package is not installed` | S3 | 预存在，环境依赖缺失 |
| PRE-002 | `test_empty_quotes_during_trading_hours_writes_bug` | `FileNotFoundError` on pytest basetemp dir（长路径问题） | S3 | 预存在 |
| PRE-003 | `test_eastmoney_provider.py` 2 tests | 预存在 eastmoney HTTP 测试失败 | S3 | 预存在 |
| PRE-004 | `test_aktools_compat_app.py` 2 tests | 预存在 ak 工具兼容测试失败 | S3 | 预存在 |
| PRE-005 | `test_live_data_mapper.py::TestEastmoneyProvider::test_name` | `ImportError: socksio` — 同 PRE-001 | S3 | 预存在 |

以上 6 个失败均为仓库预存在问题，在 Phase 4 之前即存在，与本次变更无关。本项目约定（AGENTS.md §9）：如 broad checks 因无关历史问题失败，必须报告并在 touched-scope 提供通过证据。**touched-scope（Phase 1–4 全部市场数据测试 + product/live_data/agentops 回归）全部通过，无 Phase 4 引入的新缺陷。**

### Phase 4 引入的缺陷

**无**。未发现任何由 Phase 4 变更引入的 S0/S1/S2/S3/S4 缺陷。

## Feedback Bug 文件

未生成。本阶段测试未发现需要生成 `feedback/bugs/open/BUG_*.md` 和 `.json` 的可复现运行时缺陷。

## 剩余风险

| 风险 | 严重度 | 说明 |
|------|--------|------|
| 路由通过 `_get_market_data_relay()` 创建 `MarketDataRelay()` 单例 | S3 | 未初始化 registry 时的行为由 Phase 2/3 负责 |
| `providers/quality` 和 `providers/fallback` 依赖进程内 audit/health 数据 | S3 | 重启后丢失，与 Phase 3 一致，开发报告已说明 |
| `get_bars` date parse 边界（时区非 UTC、格式非法） | S4 | Phase 5 或后续迭代补全，当前覆盖主流非法格式（422） |
| 预存在 6 个无关测试失败 | S3 | 非 Phase 4 引入，不影响发布决策 |
| Python 3.14 兼容性 | S4 | 系统 Python 3.14.4 运行正常，但 `.venv` 不存在（使用系统 python3）；CI 环境可能使用不同版本 |

## 最终结论

**PASS**

### 证据摘要

- Phase 4 18 个测试全部通过
- 更广回归（product/live_data/agentops）40 个测试全部通过
- Phase 1–3 市场数据回归 166 个测试全部通过
- 全量回归 1340 passed / 6 pre-existing failed / 6 skipped
- ruff 静态检查通过，py_compile 通过
- 路由位于 `/product/market/**`，无未批准平行前缀
- 响应包含完整数据质量字段
- fail-closed 行为正确（provider 全失败返回 503）
- 错误响应不含 secret / traceback / 绝对路径
- 路由文件不 import raw provider
- 未触碰 `src/risk_engine/`、`src/execution_engine/`、`src/stock_pool/`、`src/data_gateway/`
- 未新增真实交易能力、未绕过风控、未绕过股票池、未绕过人工确认
- Streamlit 未被标记 legacy/deprecated/待删除

### 路由建议

按团队计划，Phase 4 测试通过后应路由回 **OpenCode Developer** 执行 **Phase 5 — Streamlit 行情可观测（Slice E）**。
