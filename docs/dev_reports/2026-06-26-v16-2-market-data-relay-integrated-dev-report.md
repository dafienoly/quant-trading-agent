# V16.2 Market Data Relay & Provider Contract 整合开发报告

## 变更范围

本次整合以最新 `origin/main` 为基线，合并 PR #90 的 Team Pipeline Phase 1-4 产物和 Codex V16.2 增强实现，形成单一 V16.2 主干候选。

整合内容：

- 纳入 PR #90 的 `src/product_app/market_data/` 包化实现，包括 provider contract、adapter、registry、quality gate、cache、audit、health 和 relay。
- 将原 `src/product_app/market_data.py` 迁移为 `src/product_app/market_data/__init__.py`，保留旧 import 兼容入口。
- 纳入 PR #90 的 `/product/market/latest`、`/product/market/bars/{symbol}`、provider health/quality/fallback 观测端点。
- 纳入 Codex 增强的 `src/data_gateway/market_relay_provider.py`、`src/product_app/market_data_relay.py`、`src/api/market_routes.py`，提供股票、指数、ETF、行业、日线、交易日历的统一 envelope。
- 在 `src/api/app.py` 同时注册契约观测 router 和统一 Relay router，统一使用 `/product/market/**` 前缀。
- 在 Streamlit dashboard 中加入 Market Data Relay 健康展示入口。
- 保留 PR #90 的 Phase 1-4 中文需求、架构、开发、测试报告，并新增本整合报告作为最终整合说明。

未纳入内容：

- 未纳入 PR #90 中 `.agent/current_task.yaml`、`.agent/gates/**`、`.agent/handoff/**`、`.agent/state.json` 等运行态流水线状态文件。
- 未引入新的真实交易、下单、券商执行或自动合并能力。

## 需求与架构文档

- PR #90 需求文档：`docs/requirements/2026-06-25-market-data-relay-provider-contract-requirements.md`
- Codex 补充需求文档：`docs/requirements/2026-06-25-v16-2-market-data-relay-provider-contract-requirements.md`
- PR #90 架构文档：`docs/design/2026-06-25-market-data-relay-provider-contract-architecture.md`
- Codex 补充架构文档：`docs/design/2026-06-25-v16-2-market-data-relay-provider-contract-architecture.md`

## Roadmap 对应

- `docs/roadmap/MASTER_ROADMAP.md`
- `docs/roadmap/MASTER_ROADMAP_AGENT_EXECUTABLE.md`
- V16.2：Market Data Relay & Provider Contract

## Feature-to-Code Mapping

| 功能 | 代码位置 |
| --- | --- |
| Provider 契约、质量状态、错误分类 | `src/product_app/market_data/contracts.py` |
| Provider registry 与 fallback 选择 | `src/product_app/market_data/provider_registry.py` |
| Provider health 聚合 | `src/product_app/market_data/health.py` |
| Cache 与 audit 事件 | `src/product_app/market_data/cache.py`, `src/product_app/market_data/audit.py` |
| PR #90 Relay | `src/product_app/market_data/relay.py` |
| 旧产品行情入口兼容 | `src/product_app/market_data/__init__.py`, `src/product_app/market_data/legacy_facade.py` |
| Codex 统一 envelope Relay | `src/product_app/market_data_relay.py` |
| AkShare 指数、ETF、行业、日历 provider | `src/data_gateway/market_relay_provider.py` |
| ProviderHub 请求元数据与健康状态 | `src/data_gateway/provider_contracts.py`, `src/data_gateway/provider_hub.py` |
| 产品 API | `src/api/market_data_routes.py`, `src/api/market_routes.py`, `src/api/app.py` |
| Streamlit 健康展示 | `src/ui_report/product_dashboard.py`, `src/ui_report/i18n.py` |

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

警告说明：

- `py_mini_racer` 的 Python 3.14 兼容性弃用警告为既有第三方依赖警告。
- `fastapi.testclient` 的 `StarletteDeprecationWarning` 为当前依赖组合警告，不影响本次断言结果。

## 数据源与数据质量处理

- 所有产品新增市场数据入口均通过 Provider contract、registry、hub、quality gate 或 `MarketDataRelayService`。
- `MarketDataEnvelope` 显式暴露 `cached`、`stale`、`mock`、`quality_status`、`blocking_for_signal`。
- mock、stale、cache fallback 在 signal/execution 路径 fail closed。
- Manual fixture provider 仅允许 `test_mode=True`，不会伪装为 live provider。

## API Contract Impact

新增或补强：

- `/product/market/latest/{symbol}`
- `/product/market/latest`
- `/product/market/bars/{symbol}`
- `/product/market/providers/health`
- `/product/market/providers/quality`
- `/product/market/providers/fallback`
- `/product/market/health`
- `/product/market/sources`
- `/product/market/quotes`
- `/product/market/indexes`
- `/product/market/etfs`
- `/product/market/sectors`
- `/product/market/bars`
- `/product/market/calendar`

未新增 `/api/**` 平行业务前缀。

## UI Impact

- Streamlit 产品 dashboard 新增 Market Data Relay health 展示入口。
- UI 文案通过 `src/ui_report/i18n.py` 增加中文 key。
- 未引入 React/TypeScript 前端基线变更。

## Agent / LLM Boundary Impact

- 本次未新增 LLM 调用。
- 未允许 LLM 直接读取 raw provider。
- 未允许 LLM 生成买入、卖出、订单或仓位决策。

## 安全确认

- 未触碰 `src/broker/**`、`src/execution/**`、`src/order/**`、`src/account/**`、`src/risk/**`、`miniQMT/**`。
- 未新增真实下单、自动交易、券商写操作或 `LEVEL_3_AUTO` 暴露。
- 未提交 `.agent/tmp/**`、`.agent/reports/**`、`runtime/**` 或 `feedback/index.json`。
- 数据源失败默认返回结构化 unavailable/fail-closed 状态，不把 mock、demo、stale、cache 数据伪装为 live trading 能力。

## 跳过或未运行项

- 未运行真实外部 provider smoke test；本次验证以确定性 mock、fixture 和契约测试为主，避免外部行情源波动污染合并判断。
- 已运行完整 `pytest tests`；其中 6 个 skipped 为既有条件跳过测试。

## 剩余风险

- PR #90 的 `MarketDataRelay` 与 Codex 的 `MarketDataRelayService` 当前并存；已通过不同测试文件覆盖，后续 V16.3 应继续收敛 provider fallback governance，减少长期双层 relay 心智负担。
- `/product/market/bars/{symbol}` 与 `/product/market/bars` 同前缀不同契约，已避免路径冲突；后续可在 V16.3 统一响应格式。

## 最终结论

PASS
