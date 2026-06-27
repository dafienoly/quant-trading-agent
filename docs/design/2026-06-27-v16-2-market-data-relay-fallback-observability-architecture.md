# V16.2 Market Data Relay 收尾补强架构

## 架构目标

本次不是重做 `V16.2`，而是在 `PR #90` 已合并的基础上做最小补强，让 market relay 的响应更容易诊断、更适合验收，同时保持原有版本边界不漂移。

## 变更范围

限定在以下模块：

```text
src/data_gateway/provider_contracts.py
src/data_gateway/provider_hub.py
src/product_app/market_data_relay.py
src/ui_report/product_dashboard.py
tests/test_market_data_relay_service.py
tests/test_market_relay_provider.py
tests/test_market_routes.py
```

不修改：

```text
src/broker/**
src/execution/**
src/order/**
src/account/**
src/risk/**
miniQMT/**
```

## 数据模型调整

### 1. `MarketDataEnvelope`

新增或显式透出：

```text
fallback_used
fallback_reason
cache_status
blocking_reason
provider_chain
started_at
completed_at
requested_usage
```

### 2. `ProviderHealth` / `DataSourceHealth`

新增或显式透出：

```text
field_coverage
fallback_activation_count
```

## 核心语义

### 1. cache 语义保持 V16.2

```text
display:
  可读取 cache fallback

analysis:
  可读取 cache fallback

signal:
  可返回 cache 证据，但 blocking_for_signal=true

execution:
  不读取 cache fallback，返回 unavailable
```

这条是本次补强与 `V16.3` 的边界线：我们增强可观测性，但不提前改写 `signal` 的 V16.2 行为。

### 2. fallback_used 的含义

`fallback_used=true` 仅表示“最终返回给用户的数据来自 fallback source 或 cache fallback”。

不把“provider 尝试失败过，但最终没有返回 fallback 数据”的情况误记为 `fallback_used=true`。

### 3. blocking_reason 的含义

`blocking_reason` 需要能说明：

```text
为什么 signal 被挡住
为什么 execution 被挡住
是否因为 cache / stale / mock / provider fallback / unavailable
```

## UI 策略

继续使用 Streamlit，不新增 React 基座。

在 `render_live_data()` 的 `Market Data Relay 健康状态` 中增加：

```text
Fallback 次数
字段覆盖
```

这样用户在主入口就能看到 provider 健康不是“绿/红二元”，而是有更细的质量线索。

## 测试策略

1. `tests/test_market_data_relay_service.py`
   - 验证 live complete、cache fallback、signal blocked、execution fail closed
   - 验证 `requested_usage`、`cache_status`、`fallback_reason`
2. `tests/test_market_relay_provider.py`
   - 验证 provider hub 在“前一个 provider 失败、后一个成功”时记录 fallback 激活计数
3. `tests/test_market_routes.py`
   - 验证 `/product/market/**` 统一 envelope 可透出新增观测字段
4. `tests/test_product_dashboard_source.py`
   - 保持 dashboard 入口源码检查

## 安全确认

1. 不新增真实交易路径。
2. 不放宽 risk、execution、stock pool、human confirmation。
3. 不引入新的 `/api/**` 前缀。
4. 不把 mock、cache、fallback 冒充 live signal 可用数据。
