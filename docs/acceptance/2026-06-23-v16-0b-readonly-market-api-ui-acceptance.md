# V16.0b 只读行情 API/UI 与信号观测闭环

## 变更范围

src/api/product_routes.py（6 端点）、src/product_app/service_manager.py（refresh 接入）、3 测试文件（12 用例）

## 测试命令

```
./.venv/bin/python -m pytest tests/test_v16_0b_watchlist_api.py tests/test_v16_0b_readonly_market_dashboard.py tests/test_v16_0b_signal_observation.py -q
ruff check src/api/product_routes.py
```

## 测试结果

- 52 passed（专注），882 passed（全量）
- Ruff exit=0
- Regression PASS
- Report gate passed

## 安全确认

- ✅ 不创建订单、不调用券商
- ✅ 不修改交易敏感模块
- ✅ Demo/STALE 禁止信号
- ✅ Dashboard 不展示交易按钮

## 最终结论

PASS_WITH_NOTES
