# V16.0a 行情健康门禁与刷新状态基础能力

## 需求变更

原始需求标题已更新：V16.0 → V16.0a，范围缩小为健康门禁和刷新状态基础能力。
API/UI/自选股/去重反馈/定时调度/信号链路计划移至 V16.0b。

## 变更范围

| 文件 | 变更说明 |
|------|----------|
| src/product_app/data_health_gate.py | 新增 QUOTE_HEALTHY/STALE/UNAVAILABLE/DEMO、get_quote_health()、STALE_THRESHOLD_SECONDS、_now 时钟注入 |
| src/product_app/live_data_service.py | 新增 REFRESH_* 常量（在 import 后） |
| src/product_app/service_manager.py | 新增 get_refresh_status/_set_refresh_result（ServiceManager 类内，JobInfo 重复已清理） |
| tests/test_quote_health.py | 新增 13 个测试（固定时钟） |

## V16.0a 交付说明

- get_quote_health 方法是验证过的可用能力
- REFRESH_* 常量和 ServiceManager 方法是基础能力
- 刷新结果接入、定时调度、API、UI、自选股、去重反馈、信号链路不属于 V16.0a
- 未提供 pip freeze 依赖锁（计划 V17）

## 测试命令

```
./.venv/bin/python -m pytest tests/test_live_data_service.py tests/test_product_market_data.py tests/test_product_realtime_api.py tests/test_phase4_realtime_health.py tests/test_live_signal.py tests/test_product_dashboard_source.py tests/test_quote_health.py -q
ruff check src/product_app/live_data_service.py src/product_app/data_health_gate.py src/product_app/service_manager.py tests/test_quote_health.py
```

## 测试结果

- 聚焦 66 passed（8 文件，含 13 个 V16.0a 新增）
- 全量 870 passed, 6 skipped
- Ruff exit=0（仅预存 F821）
- py_compile 通过

## 安全确认

- 不创建订单、不调用券商
- 不修改 execution_engine/risk_engine/broker/order/account
- Demo 数据返回 QUOTE_DEMO
- STALE/UNAVAILABLE 时 evaluate() 禁止信号和订单

## 最终结论

PASS_WITH_NOTES ｜ V16.0b 待定
