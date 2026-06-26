# Phase 4 开发报告 — Product API `/product/market/**`

## 基本信息

| 项目 | 内容 |
|---|---|
| 需求文档 | `docs/requirements/2026-06-25-market-data-relay-provider-contract-requirements.md` |
| 架构文档 | `docs/design/2026-06-25-market-data-relay-provider-contract-architecture.md` |
| 团队计划 | `docs/dev_plans/20260625-market-data-relay-provider-contract-team-plan.md` |
| Roadmap 引用 | V16.2 Market Data Relay & Provider Contract |
| 阶段号 | Phase 4 — Product API `/product/market/**`（Slice D） |
| 执行角色 | OpenCode Developer（`opencode-go/deepseek-v4-flash`, `variant=max`, build Agent + superpowers） |

## 变更文件

| 操作 | 文件 | 说明 |
|---|---|---|
| 新增 | `src/api/market_data_routes.py` | `/product/market/**` API 路由实现（6 个端点） |
| 修改 | `src/api/app.py` | 追加一行 router 注册（`include_router`） |
| 新增 | `tests/test_market_data_routes.py` | 18 个测试用例覆盖正/负路径 |

## 功能映射

| 需求条目 | 端点 | 对应代码 |
|---|---|---|
| 需求 §1 Relay 统一产品入口 | `GET /product/market/latest/{symbol}` | `market_data_routes.py:get_latest_quote` |
| 需求 §1 Relay 统一产品入口 | `POST /product/market/latest` | `market_data_routes.py:post_latest_quotes` |
| 需求 §1 Relay 统一产品入口 | `GET /product/market/bars/{symbol}` | `market_data_routes.py:get_bars` |
| 需求 §6 Provider Health | `GET /product/market/providers/health` | `market_data_routes.py:get_providers_health` |
| 需求 §6 Provider Quality | `GET /product/market/providers/quality` | `market_data_routes.py:get_providers_quality` |
| 需求 §6 Fallback Status | `GET /product/market/providers/fallback` | `market_data_routes.py:get_providers_fallback` |

## 测试覆盖

| 测试用例 | 覆盖路径 |
|---|---|
| `test_get_latest_quote_success` | 正常获取单标的行情 |
| `test_get_latest_quote_with_market_param` | 自定义 market 参数 |
| `test_get_latest_quote_provider_fail_closed` | Provider 全失败返回 503（fail-closed） |
| `test_get_latest_quote_internal_error` | 内部异常返回 500，无 traceback/secret |
| `test_post_latest_quotes_success` | 多标的 POST 请求成功 |
| `test_post_latest_quotes_partial_failure` | 部分失败正确记录 item_errors |
| `test_post_latest_quotes_all_failed` | 全部失败返回 503 |
| `test_post_latest_quotes_invalid_body` | 无效请求体返回 422 |
| `test_get_bars_success` | 正常获取历史 K 线 |
| `test_get_bars_missing_params` | 缺少参数返回 422 |
| `test_get_bars_provider_fail_closed` | K 线 provider 失败返回 503 |
| `test_get_providers_health_success` | Provider Health 正常返回 |
| `test_get_providers_quality_success` | Provider Quality 正常返回 |
| `test_get_providers_fallback_success` | Provider Fallback 正常返回 |
| `test_routes_under_product_prefix` | 路由前缀为 `/product/market`，无 `/api/market` |
| `test_error_response_no_secrets` | 错误响应不含 secret、traceback、绝对路径 |
| `test_no_raw_provider_import_in_routes` | 路由文件不导入 raw provider |
| `test_post_latest_with_caller_context` | POST 支持 caller_context 参数 |

## 自测命令与结果

### Ruff 静态检查

```bash
python3 -m ruff check src/api/market_data_routes.py src/api/app.py tests/test_market_data_routes.py
```

结果：All checks passed!

### py_compile

```bash
python3 -m py_compile src/api/market_data_routes.py src/api/app.py
```

结果：无输出（通过）

### Phase 4 测试（18 个用例）

```bash
python3 -m pytest tests/test_market_data_routes.py -q --basetemp=runtime/pytest-tmp-market-data-relay-provider-contract-api
```

结果：18 passed

### 更广回归（触及共享 API entrypoint）

```bash
python3 -m pytest tests/test_product_routes.py tests/test_live_data_service.py tests/test_agentops_routes.py -q --tb=short --basetemp=runtime/pytest-tmp-market-data-relay-provider-contract-api-regression
```

结果：40 passed（无回归性失败）

### git diff --check

```bash
git diff --check
```

结果：无空白错误（CRLF warning 仅限非本阶段修改的 `.agent/` 文件）

## 安全确认

| 检查项 | 结果 |
|---|---|
| 是否新增真实交易能力 | 否 |
| 是否绕过 risk | 否 |
| 是否绕过 stock-pool filtering | 否 |
| 是否绕过 human confirmation | 否 |
| 是否绕过 Provider Contract | 否（路由通过 MarketDataRelay + QualityGate 调用） |
| 是否绕过 Tool Registry | 否（本功能不涉及 Tool Registry） |
| 是否绕过 fail-closed behavior | 否（provider 全失败返回 503，不含 trade 行为） |
| 是否泄露 secret | 否（错误响应经脱敏，不含 traceback/绝对路径） |

## 受限模块触碰声明

- **直接触碰**：`src/api/market_data_routes.py`（新建）、`src/api/app.py`（追加一行 router 注册，已验证回归无破坏）
- **不触碰**：`src/data_gateway/`、`src/risk_engine/`、`src/execution_engine/`、`src/stock_pool/`、`src/backtest_engine/`、`src/strategy_engine/`、`src/factor_engine/`、`src/product_app/agentops/`
- **依赖**：`src/product_app/market_data/relay.py`（Phase 3）、`src/product_app/market_data/contracts.py`（Phase 1）、`src/product_app/market_data/errors.py`（Phase 1）、`src/product_app/market_data/quality.py`（Phase 1）、`src/product_app/market_data/health.py`（Phase 3）、`src/product_app/market_data/audit.py`（Phase 3）

## 剩余风险

- 路由通过 route-level `_get_market_data_relay()` 获取 `MarketDataRelay()` 未初始化 registry 时的行为由 Phase 2/3 负责。本阶段仅假设 Phase 2/3 正确注册了 provider。
- `providers/quality` 和 `providers/fallback` 依赖当前进程内 audit/health 数据，重启后丢失（与 Phase 3 health 一致）。
- 未覆盖的端点 error scenario：`get_bars` 中 date parse 还有更多边界（timezone 非 UTC、格式非法）由 Phase 5 或后续迭代补全。

## 最终结论

**PASS** — 全部 18 个测试通过，ruff/py_compile 通过，更广回归 40 个用例无回归，安全确认无绕过项。
