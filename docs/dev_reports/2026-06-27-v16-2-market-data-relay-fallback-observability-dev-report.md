# V16.2 Market Data Relay 收尾补强开发报告

## 变更范围

本次开发以 `main` 已合并的 `PR #90` 为基线，补齐 V16.2 最后一层可观测性和验收可读性：

- `MarketDataEnvelope` 增强 fallback / cache / usage 相关字段。
- `ProviderHealth` / `DataSourceHealth` 增加字段覆盖率和 fallback 激活计数。
- 保持 V16.2 原语义：`signal` 可读 cache 证据但必须阻断，`execution` 禁止 cache fallback。
- Streamlit 健康面板增加 “Fallback 次数” 和 “字段覆盖”。

## 文档引用

- Requirement：`docs/requirements/2026-06-27-v16-2-market-data-relay-fallback-observability-requirements.md`
- Architecture：`docs/design/2026-06-27-v16-2-market-data-relay-fallback-observability-architecture.md`
- 路线图：`docs/roadmap/MASTER_ROADMAP_AGENT_EXECUTABLE.md` 中 V16.2 Market Data Relay & Provider Contract

## 代码改动

| 文件 | 说明 |
| --- | --- |
| `src/data_gateway/provider_contracts.py` | 扩充 envelope / health 观测字段 |
| `src/data_gateway/provider_hub.py` | fallback 激活计数与 fallback 结果语义修正 |
| `src/product_app/market_data_relay.py` | usage-aware blocking reason、cache 语义保持、响应元数据增强 |
| `src/ui_report/product_dashboard.py` | 展示 fallback 次数和字段覆盖 |
| `tests/test_market_data_relay_service.py` | 增强 cache / signal / execution / usage 字段断言 |
| `tests/test_market_relay_provider.py` | 新增 provider hub fallback success 健康断言 |
| `tests/test_market_routes.py` | 新增统一 envelope 观测字段断言 |

## Feature-to-Code Mapping

| 功能 | 代码位置 |
| --- | --- |
| Envelope 观测字段 | `src/data_gateway/provider_contracts.py`, `src/product_app/market_data_relay.py` |
| Provider fallback 计数 | `src/data_gateway/provider_hub.py` |
| Signal / execution 阻断原因 | `src/product_app/market_data_relay.py` |
| Dashboard 健康增强 | `src/ui_report/product_dashboard.py` |

## 测试命令

```bash
./.venv/bin/python -m py_compile src/data_gateway/provider_contracts.py src/data_gateway/provider_hub.py src/product_app/market_data_relay.py src/ui_report/product_dashboard.py tests/test_market_data_relay_service.py tests/test_market_relay_provider.py tests/test_market_routes.py

./.venv/bin/python -m pytest tests/test_market_data_relay_service.py tests/test_market_relay_provider.py tests/test_market_routes.py tests/test_product_dashboard_source.py -q --tb=short --basetemp=runtime/pytest-tmp-v16-2-followup-focused

./.venv/bin/python -m pytest tests/test_market_data_quality.py tests/test_market_data_relay_service.py tests/test_market_routes.py tests/test_market_data_routes.py tests/test_market_relay_provider.py tests/test_market_data_health.py tests/test_market_data_provider_registry.py tests/test_product_market_data.py tests/test_product_dashboard_source.py tests/test_live_data_service.py -q --tb=short --basetemp=runtime/pytest-tmp-v16-2-followup-broad

./.venv/bin/python -m pytest tests -q --tb=short --basetemp=runtime/pytest-tmp-v16-2-followup-full

TMPDIR=/tmp/codex-pytest ./.venv/bin/python scripts/agent_pipeline_regression.py --strict

./.venv/bin/python -m ruff check src/data_gateway/provider_contracts.py src/data_gateway/provider_hub.py src/product_app/market_data_relay.py src/ui_report/product_dashboard.py tests/test_market_data_relay_service.py tests/test_market_relay_provider.py tests/test_market_routes.py

git diff --check
```

## 测试结果

- `py_compile`：通过
- focused 回归：`20 passed, 1 warning`
- broad 兼容回归：`129 passed, 2 warnings`
- 全量测试：`1365 passed, 6 skipped, 2 warnings`
- Pipeline 严格回归：`PASS`
- Ruff：`All checks passed!`
- `git diff --check`：通过

警告说明：

- `py_mini_racer` 的 `DeprecationWarning` 为既有第三方依赖告警。
- `fastapi.testclient` 的 `StarletteDeprecationWarning` 为当前依赖组合既有告警。

## 数据质量与 API 影响

1. API 返回结构现在更容易验收：
   - `fallback_used`
   - `fallback_reason`
   - `cache_status`
   - `blocking_reason`
   - `provider_chain`
   - `requested_usage`
2. Provider 健康数据对用户更透明：
   - `field_coverage`
   - `fallback_activation_count`
3. 未新增新的 `/api/**` 前缀，仍保留 `/product/market/**`。

## UI 影响

Streamlit 的 `Market Data Relay 健康状态` 增加：

- `Fallback 次数`
- `字段覆盖`

未引入 React / TypeScript 基座变更。

## 安全确认

1. 未新增真实交易、自动下单、券商写操作。
2. 未触碰 `src/broker/**`、`src/execution/**`、`src/order/**`、`src/account/**`、`src/risk/**`、`miniQMT/**`。
3. 未暴露 `LEVEL_3_AUTO`。
4. 未允许 LLM 直接买卖、下单或覆盖风控。
5. 未提交 `.agent/tmp/**`、`.agent/reports/**`、`runtime/**`、`feedback/index.json`。

## 剩余风险

1. 本次是 V16.2 follow-up，不等价于完整 V16.3 provider fallback governance。
2. 真实外部 provider smoke 未执行；当前结论基于确定性 mock / fixture / route patch 回归。

## 最终结论

PASS
