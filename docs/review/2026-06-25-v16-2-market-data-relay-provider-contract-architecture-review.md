# V16.2 Market Data Relay 与 Provider Contract 架构 Review

## Review 范围

检查需求映射、Provider 边界、缓存策略、API 契约、UI 入口、异常处理、交易安全和测试证据。

## 主要结论

1. Relay 复用现有 `LiveDataService`，没有创建第二条个股真实数据旁路。
2. `/product/market/**` 使用独立 router，避免继续扩大 `product_routes.py`。
3. `MarketDataEnvelope` 能表达来源、时间、延迟、缓存、过期、mock、质量和信号阻断。
4. Fixture Provider 需要显式 test_mode，默认生产注册表不包含 fixture。
5. 缓存只在 live complete 时写入；execution 禁止缓存 fallback。
6. Provider 和 cache 异常均 fail closed，不向页面返回伪成功。

## 架构一致性

| 检查项 | 结论 |
|---|---|
| 产品 API 使用 `/product/market/**` | 通过 |
| 新数据入口经过 Relay/LiveDataService | 通过 |
| 不使用搜索 API 拉行情 | 通过 |
| Provider 字段和来源可追溯 | 通过 |
| mock/cache/stale 不进入信号 | 通过 |
| 不新增真实交易能力 | 通过 |
| Streamlit 保持有效产品入口 | 通过 |

## 非阻断备注

1. 多源一致性阈值和交叉比较属于 V16.3。
2. 当前本地 Python 3.14 不能完成既有 TestClient 集，需依赖 Python 3.11 CI。

## 安全确认

未发现 Risk Agent、股票池过滤、人工确认、真实交易或 `LEVEL_3_AUTO` 边界被绕过。

## Review Decision

`APPROVED_WITH_NOTES`
