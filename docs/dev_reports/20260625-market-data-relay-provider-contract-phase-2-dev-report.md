# Phase 2 开发报告 — Provider Registry + Adapter (Slice B)

- **需求文档**: `docs/requirements/2026-06-25-market-data-relay-provider-contract-requirements.md`
- **架构文档**: `docs/design/2026-06-25-market-data-relay-provider-contract-architecture.md`
- **团队计划**: `docs/dev_plans/20260625-market-data-relay-provider-contract-team-plan.md`
- **路线图**: V16.2 Market Data Relay & Provider Contract
- **阶段**: Phase 2 — Provider Registry + Adapter（Slice B）

---

## 变更文件

| 操作 | 文件 |
|------|------|
| 新增 | `src/product_app/market_data/provider_registry.py` |
| 新增 | `src/product_app/market_data/adapters.py` |
| 新增 | `tests/test_market_data_provider_registry.py` |
| 新增 | `tests/test_market_data_adapters.py` |

未修改任何既有文件，未触碰受限模块。

---

## 功能映射

| 功能点 | 实现文件 | 测试文件 |
|--------|----------|----------|
| `ProviderRegistry.register()` | `provider_registry.py:53-61` | `test_market_data_provider_registry.py` |
| `ProviderRegistry.select()` | `provider_registry.py:63-90` | `test_market_data_provider_registry.py` |
| `SelectedProvider` 模型 | `provider_registry.py:12-17` | `test_market_data_provider_registry.py` |
| `MarketDataAdapter` 抽象基类 | `adapters.py:221-248` | `test_market_data_adapters.py::TestMarketDataAdapter` |
| `EastmoneyRealtimeAdapter` | `adapters.py:268-276` | `test_market_data_adapters.py::TestEastmoneyRealtimeAdapter` |
| `AkShareRealtimeAdapter` | `adapters.py:278-286` | `test_market_data_adapters.py::TestAkShareRealtimeAdapter` |
| DataFrame → MarketQuote 映射 | `adapters.py:56-94` | `test_market_data_adapters.py::TestDataQualityMetadataPopulation` |
| 空数据/失败 → `MarketDataUnavailableError` | `adapters.py:166-191, 206-227` | `test_market_data_adapters.py` |

---

## 接口设计

### `ProviderRegistry`

```python
class ProviderRegistry:
    def register(
        self,
        contract: MarketDataProviderContract,
        priority: int,
        fallback_allowed: bool,
        risk_sensitive_allowed: bool,
    ) -> None: ...

    def select(
        self,
        market: str,
        asset_type: str,
        endpoint: str,
        granularity: str | None = None,
    ) -> list[SelectedProvider]: ...
```

- `select` 按 `market_scope`、`supported_asset_types`、`supported_endpoints`、`supported_granularities` 过滤，按 `priority` 升序返回。
- 未知条件返回空列表（不抛裸异常）。
- `SelectedProvider.adapter` 默认为 `None`，留给 Phase 3 (Relay) 设置。

### `MarketDataAdapter`

```python
class MarketDataAdapter(ABC):
    @property
    @abstractmethod
    def contract(self) -> MarketDataProviderContract: ...
    def fetch_latest_quote(symbol, timeout=None, priority=1) -> MarketQuote: ...
    def fetch_latest_quotes(symbols, timeout=None, priority=1) -> MultiSymbolQuoteResult: ...
    def fetch_bars(symbol, granularity, start, end, timeout=None) -> list[MarketBar]: ...
```

### `EastmoneyRealtimeAdapter` / `AkShareRealtimeAdapter`

- 内部持有 `DataProviderHub` + 具体 provider 实例。
- 通过 `hub.fetch_with_fallback()` 获取 `ProviderResult`，映射为 `MarketQuote`。
- `priority` 参数决定 `quality.is_fallback` 和 `quality.source_priority`。
- 空数据/失败状态抛 `MarketDataUnavailableError`（含 `provider_attempts`、`safe_reason`）。
- `fetch_bars` 暂抛 `NotImplementedError`。

### 数据质量元数据

- `source_provider` = `ProviderResult.provider` 或 `contract.provider_id`
- `source_priority` = 传入的 `priority` 参数
- `is_fallback` = `(priority != 1)`
- `request_id` = 每次新调用的唯一 hex id
- `quality_status` = `OK`（成功时）；`UNAVAILABLE`（失败时）
- `provider_latency_ms` = `ProviderResult.elapsed_ms`

---

## 自测命令与结果

**命令 1**: `git status --short --branch`
```
## epic/20260625-market-data-relay-provider-contract-run-28168858781...
```
结果: 当前在 epic 分支，4 个新增 untracked 文件。

**命令 2**: `git diff --stat`
```
src/product_app/market_data/adapters.py (新)
src/product_app/market_data/provider_registry.py (新)
tests/test_market_data_adapters.py (新)
tests/test_market_data_provider_registry.py (新)
```

**命令 3**: `ruff check`
```
All checks passed! (0 errors)
```

**命令 4**: `py_compile`
```
(no output — success)
```

**命令 5**: `pytest tests/test_market_data_provider_registry.py tests/test_market_data_adapters.py`
```
28 passed in 1.62s
```
- `test_market_data_provider_registry.py`: 12 passed
- `test_market_data_adapters.py`: 16 passed

**命令 6**: `git diff --check`
```
(only pre-existing CRLF warnings in .agent/ files, no new whitespace errors)
```

---

## 数据源与数据质量处理

- Adapter 通过 `DataProviderHub.fetch_with_fallback()` 获取数据，该 hub 已包含熔断、空缺字段检测、自动降级。
- 所有返回的 `MarketQuote` 携带 `DataQualityMetadata`（`source_provider`、`source_priority`、`quality_status`、`is_fallback`、`request_id`、`provider_latency_ms` 等）。
- 空 DataFrame 或 `status=="failed"` 抛 `MarketDataUnavailableError`，不做伪装成功。

---

## Provider Priority 与 Fallback

- `ProviderRegistry.select()` 按 priority 升序返回 provider 列表。
- `fallback_allowed` / `risk_sensitive_allowed` 在 `SelectedProvider` 中保留，由 Phase 3 (Relay) 使用。
- Adapter 的 `priority` 参数控制 `is_fallback` 标记（priority != 1 即为 fallback）。

---

## API 契约影响

无。本阶段仅新增产品层内部模块（registry + adapter），不新增 API 路由。

---

## UI 影响

无。本阶段不修改 UI。

---

## Agent / LLM 边界影响

无。本阶段不涉及 LLM 直接调用。

---

## 未运行或跳过的项目

- **更广回归测试**：本阶段未触碰 `src/api/app.py`、数据 gateway、既有 `product_routes`，按计划不要求广回归。
- **`fetch_bars`**：两个 adapter 均抛 `NotImplementedError`，因 Phase 2 仅要求 `latest_quote` / `latest_quotes`。Phase 3 (Relay) 会处理 bars 需求。
- **环境差异**：运行环境无 `.venv`，使用系统 `python3`。`EastmoneyProvider` 构造时因 SOCKS5 代理环境缺少 `socksio` 包而报错；测试通过注入 mock hub 规避该问题。

---

## 剩余风险

1. Adapter 的 `fetch_bars` 未实现，Phase 3 需补。
2. `SelectedProvider.adapter` 当前为 `Any` 类型（`None` 默认），Phase 3 设置 adapter 实例时需确保类型安全。
3. 测试覆盖 mock hub，未测试 real provider 集成（属 acceptance 范围）。

---

## 是否影响真实交易能力

否。本阶段仅新增数据访问内部组件，不涉及下单、风控、仓位。

---

## Safety Confirmation

| 检查项 | 结果 |
|--------|------|
| 是否新增真实交易能力 | 否 |
| 是否绕过 risk | 否 |
| 是否绕过 stock-pool filtering | 否 |
| 是否绕过 human confirmation | 否 |
| 是否绕过 Provider Contract | 否（adapter 严格使用 Phase 1 contract 模型） |
| 是否绕过 Tool Registry | 否（本功能不涉及 Tool Registry） |
| 是否绕过 fail-closed behavior | 否（空数据/失败显式抛 `MarketDataUnavailableError`） |
| 是否泄露 secret | 否（无 secret 处理路径） |

---

## 最终结论

**PASS**

- 28/28 测试通过
- ruff 0 errors
- py_compile 通过
- 新增 4 个文件，未修改任何既有文件
- 未触碰受限模块
- 所有 Safety Confirmation 项均为"否"
