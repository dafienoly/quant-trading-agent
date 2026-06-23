# V16.0 只读实盘行情跟踪与确定性信号观测闭环

## 需求和架构

- docs/requirements/2026-06-22-v16-0-readonly-live-monitoring-requirements.md
- docs/design/2026-06-22-v16-0-readonly-live-monitoring-architecture.md

## 变更范围

| 文件 | 变更说明 |
|------|----------|
| src/product_app/data_health_gate.py | 新增 QUOTE_HEALTHY/STALE/UNAVAILABLE/DEMO、get_quote_health()、STALE_THRESHOLD_SECONDS |
| src/product_app/live_data_service.py | 新增 REFRESH_IDLE/QUEUED/RUNNING/SUCCEEDED/FAILED/CANCELLED |
| src/product_app/service_manager.py | 新增 get_refresh_status、_set_refresh_result 方法（in class） |
| tests/test_quote_health.py | 新增 12 个测试 |

## 测试命令

```
./.venv/bin/python -m pytest tests/test_live_data_service.py tests/test_product_market_data.py tests/test_product_realtime_api.py tests/test_phase4_realtime_health.py tests/test_live_signal.py tests/test_product_dashboard_source.py tests/test_quote_health.py -q
ruff check src/product_app/ src/api src/ui_report tests
```

## 测试结果

- 聚焦 66 passed（含 13 个 V16.0 新增）
- 全量 870 passed, 6 skipped
- Ruff: 仅 1 个预存 F821（非本任务引入）

## 安全确认

- 不创建订单、不调用券商
- 不修改 execution_engine/risk_engine/broker/order/account
- Demo 数据返回 QUOTE_DEMO
- STALE/UNAVAILABLE 时 evaluate() 禁止信号和订单

## 最终结论

PASS_WITH_NOTES（API 端点和 Dashboard 展示不在本轮 diff 中）
