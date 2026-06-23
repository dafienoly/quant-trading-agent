# V16.0b 只读行情 API/UI、自选股、刷新诊断与信号观测闭环架构

## 数据链路

```
Watchlist (state.json / runtime/)
  → LiveDataService (readonly snapshot)
  → DataHealthGate (HEALTHY/STALE/UNAVAILABLE/DEMO)
  → LiveSignalOrchestrator (deterministic signal)
  → API (product_routes.py)
  → Dashboard (product_dashboard.py)
```

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| /product/watchlist | GET | 获取自选股 |
| /product/watchlist | PUT | 更新自选股 |
| /product/quotes | GET | 获取只读行情快照 |
| /product/quote-health | GET | 获取行情健康状态 |
| /product/quote-refresh | POST | 启动只读刷新 |
| /product/refresh-status | GET | 获取刷新任务状态 |
| /product/signal-observation | GET | 获取信号观测结果 |

## Dashboard 展示

自选股表格 → 价格、涨跌幅、来源、行情时间、延迟、健康状态
信号观测表格 → 信号类型、级别、健康阻断原因（如有）
刷新状态 → IDLE/QUEUED/RUNNING/SUCCEEDED/FAILED
