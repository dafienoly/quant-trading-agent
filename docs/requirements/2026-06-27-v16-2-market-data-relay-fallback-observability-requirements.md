# V16.2 Market Data Relay 收尾补强需求

## 背景

`PR #90` 已将 `V16.2 Market Data Relay & Provider Contract` 合并到 `main`，但当前主干仍有两类收尾问题需要补齐：

1. fallback、cache、usage、provider health 的可观测字段不够完整。
2. Streamlit 健康面板只能看到基础状态，缺少 fallback 次数和字段覆盖信息。

本次补强必须建立在已合并的 `V16.2` 基线之上，不把版本线抬升为 `V16.3`，也不重写既有双层 market data stack。

## 目标

1. 为 `MarketDataEnvelope` 补齐 fallback / cache / usage 相关观测字段。
2. 为 `ProviderHealth` / `DataSourceHealth` 补齐字段覆盖率与 fallback 激活计数。
3. 保持 `V16.2` 的缓存语义：
   - `display` / `analysis` 可读 cache fallback；
   - `signal` 可返回 cache 证据但必须 `blocking_for_signal=true`；
   - `execution` 禁止读取 cache fallback。
4. 在 Streamlit `Market Data Relay 健康状态` 区块显示 fallback 次数和字段覆盖。

## 非目标

1. 不新建第三套 market data service。
2. 不改写 `PR #90` 已交付的 `/product/market/**` 路由边界。
3. 不把本次补强扩写为 `V16.3 Provider Test Suite & Fallback Governance`。
4. 不触碰真实交易、Risk、Execution、Broker、Order、Account、`miniQMT`。

## 功能需求

| ID | 功能点 | 验收标准 |
| --- | --- | --- |
| R-001 | Envelope 可观测字段 | `MarketDataEnvelope` 响应包含 `fallback_used`、`fallback_reason`、`cache_status`、`blocking_reason`、`provider_chain`、`started_at`、`completed_at`、`requested_usage` |
| R-002 | Provider Health 补强 | `DataSourceHealth` / `ProviderHealth` 输出包含 `field_coverage`、`fallback_activation_count` |
| R-003 | V16.2 cache 语义保持 | `signal` 可看到 cache 证据但被阻断；`execution` 禁止 cache fallback |
| R-004 | Dashboard 可见性 | Streamlit 健康面板显示 “Fallback 次数” 与 “字段覆盖” |
| R-005 | 测试补强 | 新增或更新测试覆盖 relay service、provider hub、market routes、dashboard source |

## 安全约束

1. `/product/**` 前缀不变。
2. Streamlit 仍是有效产品入口。
3. 不新增真实交易、自动下单或 `LEVEL_3_AUTO` 暴露。
4. 不提交 `.agent/tmp/**`、`.agent/reports/**`、`runtime/**`、`feedback/index.json`。
5. LLM 仍不得直接生成买卖、仓位或订单决策。

## 测试要求

至少执行并记录：

```bash
./.venv/bin/python -m py_compile src/data_gateway/provider_contracts.py src/data_gateway/provider_hub.py src/product_app/market_data_relay.py src/ui_report/product_dashboard.py tests/test_market_data_relay_service.py tests/test_market_relay_provider.py tests/test_market_routes.py

./.venv/bin/python -m pytest tests/test_market_data_relay_service.py tests/test_market_relay_provider.py tests/test_market_routes.py tests/test_product_dashboard_source.py -q --tb=short --basetemp=runtime/pytest-tmp-v16-2-followup-focused

./.venv/bin/python -m pytest tests/test_market_data_quality.py tests/test_market_data_relay_service.py tests/test_market_routes.py tests/test_market_data_routes.py tests/test_market_relay_provider.py tests/test_market_data_health.py tests/test_market_data_provider_registry.py tests/test_product_market_data.py tests/test_product_dashboard_source.py tests/test_live_data_service.py -q --tb=short --basetemp=runtime/pytest-tmp-v16-2-followup-broad

./.venv/bin/python -m ruff check src/data_gateway/provider_contracts.py src/data_gateway/provider_hub.py src/product_app/market_data_relay.py src/ui_report/product_dashboard.py tests/test_market_data_relay_service.py tests/test_market_relay_provider.py tests/test_market_routes.py

git diff --check
```

## 最终结论标准

只有当代码、测试和中文 dev/test/acceptance 文档齐备，且不破坏 `PR #90` 的既有 V16.2 契约时，本次补强才可作为 `V16.2` follow-up 合并到主干。
