# V16.2 Market Data Relay & Provider Contract 整合测试报告

## 变更范围

本报告验证 PR #90 与 Codex V16.2 实现整合后的市场数据 Relay、Provider 契约、缓存、fallback、质量门禁、API 注册、旧入口兼容和 Streamlit 健康展示。

## 文档引用

- Requirement：`docs/requirements/2026-06-25-market-data-relay-provider-contract-requirements.md`
- Requirement 补充：`docs/requirements/2026-06-25-v16-2-market-data-relay-provider-contract-requirements.md`
- Architecture：`docs/design/2026-06-25-market-data-relay-provider-contract-architecture.md`
- Architecture 补充：`docs/design/2026-06-25-v16-2-market-data-relay-provider-contract-architecture.md`
- Development report：`docs/dev_reports/2026-06-26-v16-2-market-data-relay-integrated-dev-report.md`

## Roadmap Section

- V16.2 Market Data Relay & Provider Contract

## Test Environment

- WSL/Linux workspace
- Python：`.venv`
- 外部行情源：未直接调用真实网络，使用 mock、fixture、route patch 和静态 source 检查

## 测试范围

- Provider contract Pydantic model
- Provider registry
- Quality gate
- Cache policy
- Audit event
- Health aggregation
- PR #90 `MarketDataRelay`
- Codex `MarketDataRelayService`
- AkShare relay provider mapping
- `/product/market/**` API route 注册与错误响应
- 旧 `src.product_app.market_data` import 兼容
- Streamlit dashboard source 更新

## Requirement Coverage Matrix

| 要求 | 覆盖方式 | 结果 |
| --- | --- | --- |
| Provider 契约必须结构化 | `tests/test_market_data_contracts.py`, `tests/test_market_relay_contracts.py` | PASS |
| Provider fallback 必须可观测 | `tests/test_market_data_relay.py`, `tests/test_market_data_health.py` | PASS |
| stale/mock/cache 不得进入 signal/execution | `tests/test_market_data_relay_service.py`, `tests/test_market_data_quality.py` | PASS |
| API 必须位于 `/product/market/**` | `tests/test_market_routes.py`, `tests/test_market_data_routes.py` | PASS |
| 旧产品行情入口不得破坏 | `tests/test_product_market_data.py`, `tests/test_product_realtime_api.py`, `tests/test_realtime_provider.py` | PASS |
| dashboard 可见健康入口 | `tests/test_market_routes.py`, `tests/test_product_dashboard_source.py` | PASS |
| 不提交运行态 artifact | `git diff --check` 与后续 git tracked 检查 | PASS |

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

- `tests/test_market_data_*`、`tests/test_market_relay_*`、`tests/test_market_routes.py`、`tests/test_market_data_routes.py`：`201 passed, 2 warnings`
- 旧入口兼容回归：`44 passed, 2 warnings`
- 全量测试：`1363 passed, 6 skipped, 2 warnings`
- Ruff：`All checks passed!`
- `py_compile`：通过
- `git diff --check`：通过

## API/UI/Data Source Evidence

- API：`create_app()` 已注册 `/product/market/latest`、`/product/market/providers/*`、`/product/market/health`、`/product/market/quotes`、`/product/market/indexes`、`/product/market/etfs`、`/product/market/sectors`、`/product/market/calendar`。
- UI：`product_dashboard.py` 包含 `/product/market/health` 与 `market_relay_health`。
- Data source：真实 provider 调用在测试中 mock 或 fixture，避免外部网络和交易时段依赖。

## Data Quality 与 Fail-Closed Evidence

- `QualityGate` 对 signal_generation、real_trading、position_sizing 阻断 stale/mock/demo/fallback/非 OK 数据。
- `MarketDataRelayService` 在 cache fallback 时设置 `cached=True`、`blocking_for_signal=True`。
- `ManualFixtureProvider` 标记 `mock=True`，signal 路径阻断。
- Provider 全失败时返回 `MarketDataUnavailableError` 或 `unavailable` envelope，不伪造成功。

## 缺陷列表

无阻断缺陷。

## Feedback Bug Files

本次未生成新的 `feedback/bugs/open/BUG_*.md` 或 `.json`。

## 剩余风险

- 未执行外部真实行情 provider smoke test。
- V16.3 应继续统一 PR #90 relay 与 Codex envelope relay 的长期接口边界。

## 安全确认

- 未新增真实交易路径。
- 未触碰 broker、execution、order、account、risk、miniQMT。
- 未允许 LLM 下单。
- 未提交 `.agent/tmp/**`、`.agent/reports/**`、`runtime/**`、`feedback/index.json`。

## 最终结论

PASS
