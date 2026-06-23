# V16.0 只读实盘行情跟踪与确定性信号观测闭环架构

## 数据链路

```
DataProviderHub
  → LiveDataService (只读快照)
  → DataHealthGate (健康门禁)
  → read-only snapshot (带健康状态)
  → LiveSignalOrchestrator (确定性信号)
  → API / Dashboard
```

## 核心组件

### DataHealthGate
- 判断行情健康状态：HEALTHY / STALE / UNAVAILABLE / DEMO
- 过期阈值：30 秒（可配置）
- allow_demo=False 时拒绝 Demo 数据

### LiveDataService
- 提供只读行情快照
- 记录数据来源、行情时间、接收时间、延迟
- 去重反馈记录

### LiveSignalOrchestrator
- 仅接收 HEALTHY 行情生成信号
- 确定性因子 + 风控规则
- LLM 仅解释结果

### ServiceManager 刷新任务
- 状态机：IDLE → QUEUED → RUNNING → SUCCEEDED/FAILED

## 安全边界
- 不创建订单、不调用券商
- 不修改 execution_engine、risk_engine、broker、order、account
- Demo 数据显著标记
