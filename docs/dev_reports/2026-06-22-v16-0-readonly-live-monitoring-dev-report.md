# V16.0 只读实盘行情跟踪与确定性信号观测闭环

## 变更范围

- DataHealthGate 新增单条行情健康状态评估
  - HEALTHY / STALE / UNAVAILABLE / DEMO
  - 过期阈值 30 秒
- DataHealthGate STALE 阈值可配置
- LiveDataService 新增刷新任务状态常量
- ServiceManager 新增刷新结果存储
- LiveSignalOrchestrator 导入健康门禁

## 功能到代码映射

| 功能 | 文件 |
|------|------|
| 行情健康状态 | src/product_app/data_health_gate.py |
| 刷新任务状态 | src/product_app/live_data_service.py |
| 刷新结果存储 | src/product_app/service_manager.py |
| 确定性信号健康门禁 | src/product_app/live_signal_orchestrator.py |

## 测试命令

```
./.venv/bin/python -m pytest tests/test_live_data_service.py tests/test_product_market_data.py tests/test_product_realtime_api.py tests/test_product_service_manager_quotes.py tests/test_phase4_realtime_health.py tests/test_live_signal.py tests/test_product_dashboard_source.py -q
ruff check src/product_app/
```

## 测试结果

- 聚焦 53 passed
- 全量 857 passed, 6 skipped
- Ruff All checks passed
- 无交易敏感模块修改

## 安全确认

不创建订单、不调用券商、不修改 execution_engine/risk_engine/broker/order/account。

## 最终结论

ACCEPTED
