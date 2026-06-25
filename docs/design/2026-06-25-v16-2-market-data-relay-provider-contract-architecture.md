# V16.2 Market Data Relay 与 Provider Contract 架构

## Architecture Summary

在现有 `LiveDataService` 和 `DataProviderHub` 之上增加统一 Relay，不替换旧 API：

```text
FastAPI / Streamlit
  -> MarketDataRelayService
     -> LiveDataService（个股实时、个股日线）
     -> DataProviderHub（指数、ETF、行业、交易日历）
     -> LocalCacheProvider
     -> Quality Gate
  -> MarketDataEnvelope
```

## Module Plan

| 模块 | 职责 |
|---|---|
| `src/data_gateway/provider_contracts.py` | Envelope、Quote、Bar、Health、Usage、Quality |
| `src/data_gateway/provider_hub.py` | fallback、熔断、调用追踪和健康状态 |
| `src/data_gateway/market_relay_provider.py` | AkShare Relay、LocalCache、ManualFixture |
| `src/product_app/market_data_relay.py` | 统一调度、缓存用途治理、质量门禁 |
| `src/api/market_routes.py` | `/product/market/**` |
| `src/ui_report/product_dashboard.py` | Relay 健康视图 |

## Data Flow

```text
请求
  -> 参数与用途校验
  -> 真实 Provider
  -> 字段规范化
  -> 质量与 freshness
  -> complete: 返回并缓存
  -> failure: display/analysis 可读缓存
  -> signal: 缓存证据可返回但 blocking_for_signal=true
  -> execution: 禁止缓存，返回 unavailable
```

## Data Contract

`MarketDataEnvelope` 必含：

```text
request_id
source
provider_name
data_type
fetched_at
latency_ms
cached
stale
mock
quality_status
blocking_for_signal
payload
warnings
errors
```

质量状态：

```text
complete
stale
incomplete
unavailable
inconsistent
mock
```

除 `complete` 外默认阻断信号。多源并行一致性比较在 V16.3 完成，但 V16.2 已固定 `inconsistent` 契约和 fail-closed 语义。

## Provider Design

1. 个股实时和日线继续经过 `LiveDataService`。
2. 指数、ETF、行业和交易日历由 `AkShareMarketRelayProvider` 补充。
3. `ManualFixtureProvider` 非 test_mode 直接拒绝初始化。
4. `LocalCacheProvider` 写入 `runtime/cache/market-relay`，不进入 Git。
5. Provider 空数据、异常和字段缺失均视为失败，不返回伪成功。

## API Design

使用独立 APIRouter 挂载 `/product/market`，不继续扩大 `product_routes.py`。所有端点只读，不包含 approve、merge、order 或 broker 动作。

## Error Handling

1. Provider 超时或异常进入 fallback chain 和 health。
2. LiveDataService 意外异常转换为 unavailable envelope。
3. cache 文件损坏被忽略；cache I/O 失败不掩盖有效 live 数据。
4. UI 对不可用状态显示摘要，不抛未处理异常。
5. API 不返回 traceback、Cookie、Token 或密钥。

## Safety Impact

V16.2 只读，不创建信号或订单。Relay 的 `blocking_for_signal` 是额外门禁，不降低既有 DataHealthGate、Risk Agent、股票池过滤和人工确认约束。

## Testing Strategy

1. 固定时钟验证 freshness 和 stale。
2. monkeypatch AkShare fixture，不访问公网。
3. 覆盖 display、analysis、signal、execution。
4. 覆盖 complete、stale、incomplete、unavailable、mock。
5. 覆盖 API 注册、UI 入口和既有 Provider 回归。

## Development Guidance

先扩展契约和 Hub health，再实现 Provider、Relay、API、UI，最后执行聚焦、广泛和 Pipeline 严格回归。
