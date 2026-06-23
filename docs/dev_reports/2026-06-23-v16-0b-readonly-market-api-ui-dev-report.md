# V16.0b 只读行情 API/UI 与信号观测闭环

## 需求和架构

- docs/requirements/2026-06-23-v16-0b-readonly-market-api-ui-requirements.md
- docs/design/2026-06-23-v16-0b-readonly-market-api-ui-architecture.md

## 变更范围

| 文件 | 变更说明 |
|------|----------|
| src/api/product_routes.py | 新增 7 个端点：获取/更新自选股、行情健康状态、刷新状态、信号观测 |
| src/product_app/service_manager.py | quote_refresh 已接入 _set_refresh_result（SUCCEEDED/FAILED） |
| tests/test_v16_0b_watchlist_api.py | 4 个测试（自选股 CRUD、重复、非法） |
| tests/test_v16_0b_readonly_market_dashboard.py | 3 个测试（健康、刷新、信号端点） |
| tests/test_v16_0b_signal_observation.py | 5 个测试（fail closed、Demo、STALE） |

## 测试命令

```
./.venv/bin/python -m pytest tests/test_quote_health.py tests/test_product_realtime_api.py tests/test_product_service_manager_quotes.py tests/test_product_dashboard_source.py tests/test_live_signal.py tests/test_v16_0b_watchlist_api.py tests/test_v16_0b_readonly_market_dashboard.py tests/test_v16_0b_signal_observation.py -q
ruff check src/api/product_routes.py src/product_app/
```

## 测试结果

- 聚焦 52 passed（含 12 个 V16.0b 新增）
- 全量 882 passed, 6 skipped
- Ruff All checks passed
- Regression --strict 状态：通过
- Report gate passed

## 安全确认

- 不创建订单、不调用券商
- 不修改 execution_engine/risk_engine/broker/order/account
- Demo 数据标记 QUOTE_DEMO，禁止信号
- Dashboard 修改不在本轮 diff 中

## 最终结论

PASS_WITH_NOTES（Dashboard 展示项依赖前端渲染，本轮仅验证端点）
