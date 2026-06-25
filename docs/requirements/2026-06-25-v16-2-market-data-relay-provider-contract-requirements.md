# V16.2 Market Data Relay 与 Provider Contract 需求

## 背景

现有实时行情、历史日线和 Provider fallback 返回结构不一致，用户无法统一判断来源、缓存、过期、测试数据、质量状态和信号可用性。V16.2 建立后续研究、证据、仓位和风险能力共同依赖的数据入口。

## 目标

1. 建立统一 `MarketDataEnvelope`、`QuoteSnapshot`、`BarSeries` 和 `DataSourceHealth`。
2. 通过 `/product/market/**` 提供个股、指数、ETF、行业、日线、交易日历和健康状态。
3. 区分 live、cache、mock、stale、incomplete、inconsistent、unavailable。
4. 对 display、analysis、signal、execution 实施不同缓存策略。
5. Provider 失败时明确报错并 fail closed，不导致页面白屏。

## 非目标

1. 不接入真实交易。
2. 不删除现有 `/product/live-data/**`。
3. 不实现分钟线、资金流、IOPV 或外盘映射。
4. 不把 fixture、demo 或缓存冒充实时数据。

## 功能需求

| ID | 功能点 | 验收标准 |
|---|---|---|
| R-001 | 统一 Envelope | 所有 Relay 数据响应包含 request_id、source、provider_name、data_type、fetched_at、latency_ms、cached、stale、mock、quality_status、blocking_for_signal、payload、warnings、errors |
| R-002 | 个股行情 | 返回标准 QuoteSnapshot |
| R-003 | 指数行情 | 来源、时间和质量可见 |
| R-004 | ETF 行情 | 与个股类型明确区分 |
| R-005 | 日线 | 支持 stock/index/ETF，明确 frequency 和 adjust |
| R-006 | 行业板块 | 返回标准快照，异常不产生页面白屏 |
| R-007 | 交易日历 | 返回区间内交易日 |
| R-008 | Provider 健康 | 显示最近成功、最近错误、延迟、限流和错误摘要 |
| R-009 | 缓存治理 | display/analysis 可 fallback；signal 默认阻断；execution 禁止缓存 |
| R-010 | Fixture 边界 | ManualFixtureProvider 只能显式 test_mode |
| R-011 | 质量门禁 | 仅 complete 且 freshness 合格的数据可进入候选信号 |
| R-012 | UI | Streamlit 展示 Relay 健康和阻断原因 |

## API

```text
GET /product/market/health
GET /product/market/sources
GET /product/market/quotes?symbols=
GET /product/market/indexes?symbols=
GET /product/market/etfs?symbols=
GET /product/market/sectors?symbols=
GET /product/market/bars?symbol=&start=&end=&frequency=&adjust=&asset_type=
GET /product/market/calendar?start=&end=
```

## 安全约束

1. stale、mock、incomplete、inconsistent、unavailable 全部阻断信号。
2. execution 禁止 cache 和 fixture。
3. 不使用搜索 API 拉行情。
4. 密钥只能来自环境变量。
5. 不修改 Risk Agent、股票池过滤和人工确认规则。

## 测试要求

1. 所有新增 Provider 使用确定性 fixture。
2. 覆盖正常、空数据、异常、缓存、过期、mock 和字段缺失。
3. 覆盖 API 注册和非法参数。
4. 覆盖既有 data gateway 和 live-data 回归。
5. 覆盖 Streamlit 健康入口。

## 最终验收

V16.2 路线图十项验收标准必须全部有代码和测试证据；不得提交 runtime、`.agent/tmp`、`.agent/reports`，不得修改交易敏感模块。
