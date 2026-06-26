# V16.2 Market Data Relay & Provider Contract 整合验收报告

## 变更范围

本次验收对象为 PR #90 与 Codex V16.2 市场数据实现的整合结果，目标是作为 V16.2 主干候选交付。

已验收能力：

- Provider contract、registry、quality gate、cache、audit、health、relay 基础设施。
- 旧 `src.product_app.market_data` 入口迁移为包并保持兼容。
- `/product/market/**` 产品 API 覆盖 provider contract 观测和统一 Market Data Relay envelope。
- 股票、指数、ETF、行业、日线、交易日历能力的统一质量状态输出。
- Streamlit dashboard 可见 Market Data Relay health。
- stale/mock/cache/fallback 在 signal/trading 相关路径 fail closed。

## 验收依据

- `docs/requirements/2026-06-25-market-data-relay-provider-contract-requirements.md`
- `docs/requirements/2026-06-25-v16-2-market-data-relay-provider-contract-requirements.md`
- `docs/design/2026-06-25-market-data-relay-provider-contract-architecture.md`
- `docs/design/2026-06-25-v16-2-market-data-relay-provider-contract-architecture.md`
- `docs/dev_reports/2026-06-26-v16-2-market-data-relay-integrated-dev-report.md`
- `docs/test_reports/2026-06-26-v16-2-market-data-relay-integrated-test-report.md`

## 测试命令

```bash
timeout 180s ./.venv/bin/python -m pytest tests/test_market_data_contracts.py tests/test_market_data_errors.py tests/test_market_data_quality.py tests/test_market_data_provider_registry.py tests/test_market_data_health.py tests/test_market_data_cache.py tests/test_market_data_audit.py tests/test_market_data_adapters.py tests/test_market_data_relay.py tests/test_market_data_relay_service.py tests/test_market_relay_contracts.py tests/test_market_relay_provider.py tests/test_market_routes.py tests/test_market_data_routes.py -q --tb=short --basetemp=runtime/pytest-tmp-v16-2-integration-focused

timeout 180s ./.venv/bin/python -m pytest tests/test_product_market_data.py tests/test_product_realtime_api.py tests/test_realtime_provider.py tests/test_live_data_service.py tests/test_product_dashboard_source.py -q --tb=short --basetemp=runtime/pytest-tmp-v16-2-compat

./.venv/bin/python -m ruff check src/api/app.py src/api/market_data_routes.py src/api/market_routes.py src/product_app/market_data src/product_app/market_data_relay.py src/data_gateway/market_relay_provider.py src/data_gateway/provider_contracts.py src/data_gateway/provider_hub.py src/ui_report/i18n.py src/ui_report/product_dashboard.py tests/test_market_data_adapters.py tests/test_market_data_audit.py tests/test_market_data_cache.py tests/test_market_data_contracts.py tests/test_market_data_errors.py tests/test_market_data_health.py tests/test_market_data_provider_registry.py tests/test_market_data_quality.py tests/test_market_data_relay.py tests/test_market_data_relay_service.py tests/test_market_data_routes.py tests/test_market_relay_contracts.py tests/test_market_relay_provider.py tests/test_market_routes.py

./.venv/bin/python -m py_compile src/api/app.py src/api/market_data_routes.py src/api/market_routes.py src/product_app/market_data/__init__.py src/product_app/market_data/adapters.py src/product_app/market_data/audit.py src/product_app/market_data/cache.py src/product_app/market_data/contracts.py src/product_app/market_data/errors.py src/product_app/market_data/health.py src/product_app/market_data/legacy_facade.py src/product_app/market_data/provider_registry.py src/product_app/market_data/quality.py src/product_app/market_data/relay.py src/product_app/market_data_relay.py src/data_gateway/market_relay_provider.py src/data_gateway/provider_contracts.py src/data_gateway/provider_hub.py src/ui_report/i18n.py src/ui_report/product_dashboard.py

git diff --check

timeout 360s ./.venv/bin/python -m pytest tests -q --tb=short --basetemp=runtime/pytest-tmp-v16-2-full-clean
```

## 测试结果

- 聚焦整合测试：`201 passed, 2 warnings`
- 旧产品行情兼容回归：`44 passed, 2 warnings`
- 全量测试：`1363 passed, 6 skipped, 2 warnings`
- Ruff：`All checks passed!`
- `py_compile`：通过
- `git diff --check`：通过

## 安全确认

- 产品 API 仍位于 `/product/**`。
- Streamlit dashboard 保留且继续作为有效产品入口。
- 未新增 `/api/**` 业务前缀。
- 未新增真实交易、自动下单、券商写操作或风险绕过。
- 未触碰 `src/broker/**`、`src/execution/**`、`src/order/**`、`src/account/**`、`src/risk/**`、`miniQMT/**`。
- 未暴露 `LEVEL_3_AUTO` 为普通用户可选项。
- LLM 未获得买入、卖出、下单、仓位或风险 override 权限。
- mock、demo、stale、cache、fallback 数据均通过质量字段显式标记，不作为 live trading 能力。
- 未提交 `.agent/tmp/**`、`.agent/reports/**`、`runtime/**`、`feedback/index.json`。

## 验收检查

| 检查项 | 结果 |
| --- | --- |
| 是否符合 V16.2 路线图 | PASS |
| 是否整合 PR #90 产品代码 | PASS |
| 是否整合 Codex 增强 provider/service/API/UI | PASS |
| 是否保留旧行情入口兼容 | PASS |
| 是否包含中文开发与验收证据 | PASS |
| 是否包含 normal/negative/fail-closed 测试 | PASS |
| 是否保留人工合并边界 | PASS |

## 剩余风险

- 真实外部 provider smoke test 未在本地执行；建议主干 CI 或后续人工验收在稳定网络和交易时段补充。
- V16.3 应把 provider fallback governance 继续收敛为更少、更统一的对外接口。

## 最终结论

PASS
