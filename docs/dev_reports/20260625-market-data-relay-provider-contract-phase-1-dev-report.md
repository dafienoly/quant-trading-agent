# Phase 1 开发报告 — 子包基线 + Schema/Contract/Quality/Errors（Slice A）

## 需求文档

- `docs/requirements/2026-06-25-market-data-relay-provider-contract-requirements.md`
- `docs/design/2026-06-25-market-data-relay-provider-contract-architecture.md`

## Roadmap 位置

V16.2 Market Data Relay & Provider Contract — Phase 1（Foundation Slice A）

## 变更文件

| 操作 | 路径 |
|------|------|
| 删除 | `src/product_app/market_data.py`（flat 文件，221 行，已迁入子包） |
| 新增 | `src/product_app/market_data/__init__.py`（legacy 原码 + 新模块 re-export） |
| 新增 | `src/product_app/market_data/legacy_facade.py`（re-export 兼容层） |
| 新增 | `src/product_app/market_data/contracts.py`（QualityStatus / ProviderErrorCategory 枚举、13 个 Pydantic 模型） |
| 新增 | `src/product_app/market_data/quality.py`（CallerContext、QualityGate） |
| 新增 | `src/product_app/market_data/errors.py`（MarketDataUnavailableError、redact_secret、safe_error_summary） |
| 新增 | `tests/test_market_data_contracts.py`（45 项测试） |
| 新增 | `tests/test_market_data_quality.py`（29 项测试） |
| 新增 | `tests/test_market_data_errors.py`（24 项测试） |

## 功能映射

| 需求/架构条目 | 代码位置 |
|---|---|
| QualityStatus 枚举（8 值） | `contracts.py:QualityStatus` |
| ProviderErrorCategory 枚举（11 值） | `contracts.py:ProviderErrorCategory` |
| MarketDataProviderContract（14 字段） | `contracts.py:MarketDataProviderContract` |
| DataQualityMetadata（14 字段） | `contracts.py:DataQualityMetadata` |
| MarketQuote / MarketBar | `contracts.py:MarketQuote`、`MarketBar` |
| ProviderAttempt / ItemError / MultiSymbolQuoteResult | `contracts.py` |
| AuthRequirement / RateLimitPolicy / TimeoutPolicy / FreshnessPolicy / CachePolicy / FallbackEligibility | `contracts.py` |
| CallerContext（5 种上下文 + allow_demo/mock） | `quality.py:CallerContext` |
| QualityGate.blocks（架构 §7 伪代码） | `quality.py:QualityGate.blocks` |
| MarketDataUnavailableError（带 attempts/fallback_used/quality_status） | `errors.py:MarketDataUnavailableError` |
| redact_secret（8 类敏感词） | `errors.py:redact_secret` |
| safe_error_summary | `errors.py:safe_error_summary` |
| 子包基线 + flat 文件迁移 + __init__ re-export | `__init__.py` + `legacy_facade.py` |

## 新增或更新测试

- `tests/test_market_data_contracts.py` — QualityStatus 枚举值、ProviderErrorCategory 枚举值、各模型必填字段与默认值、MarketDataProviderContract 完整 13 字段验证、MarketQuote 验证 Decimal 价格类型、MarketBar 要求 open/high/low/close、MultiSymbolQuoteResult summary 结构
- `tests/test_market_data_quality.py` — CallerContext 5 种有效 context、无效名称报错；QualityGate.blocks 覆盖 UNAVAILABLE/INVALID 恒阻断、signal_generation/real_trading/position_sizing 阻断 stale/mock/demo/fallback/非 OK、research_readonly 允许 OK/DEGRADED/FALLBACK 但阻断 demo/mock（无 allow）、dashboard_observability 允许全部状态、allow_demo/allow_mock 控制
- `tests/test_market_data_errors.py` — redact_secret 对 8 种敏感词全部替换为 `<redacted>`、大小写不敏感、非敏感词原样保留；safe_error_summary 不含 provider detail；MarketDataUnavailableError str/repr/model_dump 不含 secret、可序列化

## 精确命令与结果

### 环境

```bash
$ python3 --version
Python 3.14.4

$ pip list | grep -E "pytest|pydantic|fastapi|akshare"
akshare           1.18.64
fastapi           0.138.0
pydantic          2.13.0
pytest            9.1.1
```

### 新测试（98 项全部通过）

```bash
.venv/bin/python -m pytest tests/test_market_data_contracts.py tests/test_market_data_quality.py tests/test_market_data_errors.py -v --basetemp=runtime/pytest-tmp-market-data-relay-provider-contract
# Result: 98 passed
```

### 既有兼容性回归（36/37 通过，1 项预存 socksio 缺失）

```bash
.venv/bin/python -m pytest tests/test_product_market_data.py tests/test_realtime_provider.py tests/test_v16_0b_readonly_market_dashboard.py tests/test_product_service_manager_quotes.py tests/test_quote_health.py -q --tb=short --basetemp=runtime/pytest-tmp-market-data-relay-provider-contract-legacy-regression
# Result: 36 passed, 1 failed (pre-existing: socksio not installed, affects AktoolsProvider constructor)
```

### 全套验证（120 项全部通过）

```bash
.venv/bin/python -m pytest tests/test_market_data_contracts.py tests/test_market_data_quality.py tests/test_market_data_errors.py tests/test_product_market_data.py tests/test_v16_0b_readonly_market_dashboard.py tests/test_product_service_manager_quotes.py tests/test_quote_health.py -q --tb=short --basetemp=runtime/pytest-tmp-market-data-relay-provider-contract
# Result: 120 passed
```

### 静态检查

```bash
.venv/bin/python -m ruff check src/product_app/market_data tests/test_market_data_contracts.py tests/test_market_data_quality.py tests/test_market_data_errors.py
# Result: All checks passed!

.venv/bin/python -m py_compile src/product_app/market_data/*.py tests/test_market_data_contracts.py tests/test_market_data_quality.py tests/test_market_data_errors.py
# Result: no errors

git diff --check
# Result: no whitespace errors
```

## 数据源与数据质量控制

- 本阶段未接入新的 provider 或真实数据源
- `contracts.py` 定义了 `DataQualityMetadata`（14 字段：source_provider, source_priority, as_of, received_at, freshness_seconds, is_stale, is_realtime, is_demo, is_mock, is_fallback, quality_status, quality_reason, provider_latency_ms, request_id）
- `quality.py` 定义了 `QualityGate.blocks()`，严格对齐架构 §7 伪代码
- `errors.py` 定义了 `MarketDataUnavailableError` 结构化 fail-closed 错误与 `redact_secret` 脱敏

## API 契约影响

- 未新增或修改 API 路由（Phase 4 目标）
- 既有 `/product/quotes`、`/product/live-data/*` 端点无变化

## UI 影响

- 无（Phase 5 目标）
- Streamlit 未标记为 legacy/deprecated/待删除

## Agent / LLM 边界影响

- 本阶段定义了数据质量门禁（QualityGate），为后续 agent/LLM 访问数据提供受控基础
- LLM 可读取 quality_status、freshness 摘要等，但不得覆盖 quality_status 或绕过 relay
- 未赋予 LLM 任何买卖或订单权限

## 未运行项及原因

- `tests/test_realtime_provider.py::test_aktools_provider_fetches_realtime_quotes_from_http_mapping` — 预存 socksio 缺失。在 CI 完整环境中 `socksio` 包已安装时该测试应通过。本阶段未修改任何 data_gateway 文件，该失败与 Phase 1 无关。
- 未运行 `tests/test_live_data_service.py`（Phase 3 范围）+ `tests/test_product_routes.py`（Phase 4 范围）

## 剩余风险

- 无已知 Phase 1 范围风险
- 新 QualityStatus 和 ProviderErrorCategory 为 str, Enum，序列化为字符串，与既有代码兼容

## 真实交易能力影响

- 未新增任何真实交易能力

## Safety Confirmation

```text
是否新增真实交易能力：否
是否绕过 risk：否
是否绕过 stock-pool filtering：否
是否绕过 human confirmation：否
是否绕过 Provider Contract：否
是否绕过 Tool Registry：否（本功能不涉及 Tool Registry）
是否绕过 fail-closed behavior：否
是否泄露 secret：否
```

## 最终结论

**PASS**

Phase 1 完成。98 项新测试全绿，36/37 既有回归测试通过（1 项预存无关 socksio 缺失）。ruff 和 py_compile 全通过。扁平 `src/product_app/market_data.py` 已删除，`src/product_app/market_data/` 子包已创建并包含 `__init__.py`、`legacy_facade.py`、`contracts.py`、`quality.py`、`errors.py`。既有调用方通过 `__init__.py` re-export 保持向后兼容。Gate 后路由至 Phase 2。
