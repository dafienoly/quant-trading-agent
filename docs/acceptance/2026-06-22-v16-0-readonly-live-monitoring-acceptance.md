# V16.0a 行情健康门禁与刷新状态基础能力

## 变更范围

- DataHealthGate：新增 QUOTE_HEALTHY/STALE/UNAVAILABLE/DEMO 四状态、get_quote_health()、STALE_THRESHOLD_SECONDS，注入 _now 参数
- LiveDataService：新增 REFRESH_IDLE/QUEUED/RUNNING/SUCCEEDED/FAILED/CANCELLED 常量
- ServiceManager：新增 get_refresh_status/_set_refresh_result 方法
- tests/test_quote_health.py：13 个测试覆盖健康状态、刷新状态和 fail-closed

## 测试命令

```
ruff check src/product_app/live_data_service.py src/product_app/data_health_gate.py src/product_app/service_manager.py tests/test_quote_health.py
./.venv/bin/python -m pytest tests/test_quote_health.py -q
./.venv/bin/python -m pytest tests -q --tb=short --basetemp=runtime/pytest-tmp-v16-0-full
python -m py_compile src/product_app/data_health_gate.py src/product_app/live_data_service.py src/product_app/service_manager.py
git diff --check
```

## 测试结果

- Ruff（V16.0 触碰文件）exit=0 ✅
- test_quote_health.py 13 passed ✅
- 全量 870 passed, 6 skipped ✅
- py_compile 通过 ✅
- git diff --check 通过 ✅
- Restricted modules 无改动 ✅
- .agent/tmp、.agent/reports、feedback 未进 PR diff ✅

## 安全确认

- 不创建订单、不调用券商
- 不修改 execution_engine/risk_engine/broker/order/account
- Demo 数据返回 QUOTE_DEMO
- STALE/UNAVAILABLE 时 evaluate() 禁止信号

## V16.0a 范围说明

本版本仅交付健康门禁和刷新状态基础能力。以下功能计划 V16.0b：
API 端点、Dashboard 展示、去重反馈、自选股存储、定时刷新调度、信号观测链路。

## 最终结论

PASS_WITH_NOTES ｜ V16.0b 待定
