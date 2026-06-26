# V16.2 Market Data Relay 与 Provider Contract 开发报告

## 需求与架构

- 需求：`docs/requirements/2026-06-25-v16-2-market-data-relay-provider-contract-requirements.md`
- 架构：`docs/design/2026-06-25-v16-2-market-data-relay-provider-contract-architecture.md`

## 实现范围

1. 扩展 Provider Contract，新增统一 Envelope、Quote、Bar、Health、Usage 和 Quality 模型。
2. 为 `DataProviderHub` 增加 request_id、调用时间、最近成功、最近错误、延迟、行数和字段覆盖率。
3. 新增 AkShare 指数、ETF、行业板块、交易日历 Relay Provider。
4. 新增 JSON 本地缓存和仅测试可用的 `ManualFixtureProvider`。
5. 新增 `MarketDataRelayService`，实现 display、analysis、signal、execution 四类用途治理。
6. 新增 `/product/market/**` 八个只读 API。
7. 在 Streamlit 实时数据页增加 Relay 健康状态表。
8. 保留既有 `/product/live-data/**` 和 `LiveDataService` 兼容入口。

## 变更文件

```text
src/data_gateway/provider_contracts.py
src/data_gateway/provider_hub.py
src/data_gateway/market_relay_provider.py
src/product_app/market_data_relay.py
src/api/market_routes.py
src/api/app.py
src/ui_report/i18n.py
src/ui_report/product_dashboard.py
tests/test_market_relay_contracts.py
tests/test_market_relay_provider.py
tests/test_market_data_relay.py
tests/test_market_routes.py
```

## 功能到代码映射

| 功能 | 实现 |
|---|---|
| 统一 Envelope | `provider_contracts.MarketDataEnvelope` |
| 个股实时与日线 | `MarketDataRelayService` 复用 `LiveDataService` |
| 指数、ETF、板块、日历 | `AkShareMarketRelayProvider` |
| 缓存 fallback | `LocalCacheProvider` |
| test fixture 边界 | `ManualFixtureProvider(test_mode=True)` |
| 质量门禁 | `_quality_for_payload`、`blocking_for_signal` |
| API | `src/api/market_routes.py` |
| UI 健康状态 | `render_live_data()` |

## 新增与更新测试

1. Contract 枚举和序列化。
2. AkShare fixture 映射。
3. Provider health 成功状态。
4. live 成功、异常、空数据、incomplete。
5. display cache、signal blocking、execution cache 禁止。
6. cache stale 和 cache I/O 异常。
7. Manual fixture mock 与 test_mode 阻断。
8. API 函数、路由注册、非法 usage。
9. Dashboard Relay 健康入口。

## 自测命令与结果

```bash
./.venv/bin/python -m pytest \
  tests/test_market_relay_contracts.py \
  tests/test_market_relay_provider.py \
  tests/test_market_data_relay.py \
  tests/test_market_routes.py \
  tests/test_live_data_mapper.py \
  tests/test_live_data_service.py \
  tests/test_product_market_data.py \
  tests/test_realtime_provider.py \
  tests/test_eastmoney_provider.py \
  -q --tb=short --basetemp=runtime/pytest-tmp-v16-2-final-focused \
  -k 'not TestLiveDataAPI'
```

结果：`113 passed, 6 deselected, 1 warning`。

```bash
./.venv/bin/python -m pytest tests -q --tb=short \
  --basetemp=runtime/pytest-tmp-v16-2-broad-clean \
  --ignore=<16 个使用 TestClient 的文件>
```

结果：`953 passed, 6 skipped, 1 warning`。

```bash
./.venv/bin/python -m ruff check <V16.2 触碰文件>
./.venv/bin/python -m py_compile <V16.2 触碰源码>
git diff --check
TMPDIR=/tmp/codex-pytest ./.venv/bin/python scripts/agent_pipeline_regression.py --strict
```

结果：全部通过；Pipeline 严格回归 `8/8 gates passed`。

## 未执行项与原因

当前本地虚拟环境为 Python 3.14.4。仓库既有所有 `fastapi.testclient.TestClient` 用例在该环境中会挂起，连未修改的既有 API 用例也可复现。V16.2 新路由已通过端点函数调用、FastAPI 路由注册检查和参数枚举 fail-closed 测试；完整 TestClient 集需在项目标准 Python 3.11 CI 中执行。

## 剩余风险

1. V16.2 建立 `inconsistent` 契约，但多源并行比对阈值将在 V16.3 完成。
2. AkShare 生产可用性仍受外部网络、限流和源站字段变更影响，V16.3 将补全 Provider 异常矩阵。
3. 行业板块成交量继承源站“手”单位并转换为内部数值，后续需在 Provider 契约测试中持续核验源站语义。

## 安全确认

1. 未新增真实交易、订单、账户或券商能力。
2. 未修改 `src/risk_engine/`、`src/execution_engine/`、订单和 Broker 模块。
3. stale、cache、mock、incomplete、unavailable 全部默认阻断信号。
4. execution usage 禁止缓存和 fixture。
5. 未绕过 Risk Agent、股票池过滤或人工确认。
6. `runtime/**`、`.agent/tmp/**`、`.agent/reports/**` 未纳入版本控制。

## 最终结论

`PASS_WITH_NOTES`。V16.2 功能实现与本地可执行测试通过；备注仅为 Python 3.14 下既有 TestClient 兼容问题及 V16.3 计划内的多源一致性治理。
