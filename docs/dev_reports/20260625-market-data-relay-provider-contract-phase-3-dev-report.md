# 开发报告 V16.2 Phase 3 — Relay + Audit + Health + Cache（Slice C）

## 引用文档

- 需求文档：`docs/requirements/2026-06-25-market-data-relay-provider-contract-requirements.md`
- 架构文档：`docs/design/2026-06-25-market-data-relay-provider-contract-architecture.md`
- 团队计划：`docs/dev_plans/20260625-market-data-relay-provider-contract-team-plan.md`
- 路线图：`docs/roadmap/MASTER_ROADMAP.md` — V16.2 Market Data Relay & Provider Contract

## 实现范围

### 新增文件

| 文件 | 说明 |
|------|------|
| `src/product_app/market_data/relay.py` | MarketDataRelay 统一编排入口，串联 registry → adapter → quality gate → audit/health/cache |
| `src/product_app/market_data/audit.py` | MarketDataAuditEvent + AuditRecorder（脱敏审计事件记录） |
| `src/product_app/market_data/health.py` | ProviderHealthAggregator（内存聚合 availability/latency/error/fallback 指标） |
| `src/product_app/market_data/cache.py` | MarketDataCache + CachedEntry（显式缓存，stale 时 research 返回 STALE、signal/trading fail-closed） |
| `tests/test_market_data_audit.py` | 审计事件字段、AuditRecorder 记录/清空、secret 脱敏（7 tests） |
| `tests/test_market_data_health.py` | ProviderHealthAggregator snapshot、percentile、availability、consecutive_failures、error_summary（10 tests） |
| `tests/test_market_data_cache.py` | CachedEntry、set/get、stale age、fail-closed 按 caller_context（9 tests） |
| `tests/test_market_data_relay.py` | Relay 编排：单标/多标/bars 成功、fail-closed、fallback、all-fail、signal 阻断、demo 阻断、无 provider、cache hit/stale、audit error_code、request_id 唯一（14 tests） |

### 修改文件

| 文件 | 变更 |
|------|------|
| `src/product_app/market_data/__init__.py` | 新增 re-export Phase 3 符号（AuditRecorder, MarketDataAuditEvent, CachedEntry, MarketDataCache, ProviderHealthAggregator, MarketDataRelay）与 __all__ 追加 |
| `src/product_app/market_data/provider_registry.py` | _RegistryEntry 新增 adapter 槽位；register() 新增 adapter 参数；select() 传递 adapter 到 SelectedProvider |

### 功能映射

| 团队计划 F-xxx | 代码文件 |
|---|---|
| F-Relay 统一编排 | `relay.py:MarketDataRelay`（get_latest_quote / get_latest_quotes / get_bars） |
| F-Audit 审计 | `audit.py:AuditRecorder` + `MarketDataAuditEvent` |
| F-Health 健康聚合 | `health.py:ProviderHealthAggregator` |
| F-Cache 缓存 | `cache.py:MarketDataCache` + `CachedEntry` |
| F-Quality gate | 复用 `quality.py:QualityGate`（Phase 1） |
| F-Registry adapter 传递 | `provider_registry.py:ProviderRegistry.register/select`（adapter 参数） |

## 自测命令与结果

### 环境

- Python 3.14.4, pytest 9.1.1
- 无 `.venv`，使用系统 `python3`
- 未启用 WSL（Linux 原生运行）

### 命令 1：ruff 静态检查

```bash
python3 -m ruff check \
  src/product_app/market_data/relay.py \
  src/product_app/market_data/audit.py \
  src/product_app/market_data/health.py \
  src/product_app/market_data/cache.py \
  src/product_app/market_data/__init__.py \
  src/product_app/market_data/provider_registry.py \
  tests/test_market_data_relay.py \
  tests/test_market_data_audit.py \
  tests/test_market_data_health.py \
  tests/test_market_data_cache.py
```

**结果：** All checks passed（0 错误）

### 命令 2：py_compile

```bash
python3 -m py_compile \
  src/product_app/market_data/relay.py \
  src/product_app/market_data/audit.py \
  src/product_app/market_data/health.py \
  src/product_app/market_data/cache.py \
  src/product_app/market_data/__init__.py \
  src/product_app/market_data/provider_registry.py
```

**结果：** 无输出（全部通过）

### 命令 3：Phase 3 专用测试

```bash
python3 -m pytest tests/test_market_data_audit.py \
  tests/test_market_data_health.py \
  tests/test_market_data_cache.py \
  tests/test_market_data_relay.py \
  -v --tb=short --basetemp=runtime/pytest-tmp-market-data-relay-provider-contract-phase3
```

**结果：** 40 passed（10 health + 9 cache + 7 audit + 14 relay）

### 命令 4：回归测试（既有产品数据入口）

```bash
python3 -m pytest tests/test_live_data_service.py tests/test_quote_health.py \
  -q --tb=short --basetemp=runtime/pytest-tmp-market-data-relay-provider-contract-relay-regression
```

**结果：** 34 passed（无回归性失败）

### 命令 5：完整合并测试（Phase 3 + 回归）

```bash
python3 -m pytest tests/test_live_data_service.py tests/test_quote_health.py \
  tests/test_market_data_audit.py tests/test_market_data_health.py \
  tests/test_market_data_cache.py tests/test_market_data_relay.py \
  -q --tb=short --basetemp=runtime/pytest-tmp-market-data-relay-provider-contract-phase3-full
```

**结果：** 74 passed（Phase 3 40 tests + 回归 34 tests）

### 命令 6：git diff --check

```bash
git diff --check
```

**结果：** 无 trailing whitespace / 无 indent 问题（仅 CRLF warning，属 WSL 环境）

## 数据源与数据质量处理

- **MarketDataRelay** 不直接调用 raw provider，通过 registry 获取已注册 adapter
- 每个 quote/bar 响应携带完整 `DataQualityMetadata`
- **QualityGate** 按 caller_context 分层阻断：signal_generation/real_trading/position_sizing 阻断 stale/mock/demo/fallback/非 OK
- **Cache** 超过 freshness_policy 时 research_readonly 返回 STALE，signal/real_trading/position_sizing fail-closed
- **AuditRecorder** 对所有 event 中 attempt 的 safe_reason 执行 `redact_secret` 脱敏

## Provider Priority 与 Fallback 行为

- Relay 按 registry.select 返回的 priority 升序遍历
- `is_fallback` 标志由 relay 根据 `priority > 1` 设置
- 优先 provider 失败时，若 `fallback_eligibility.can_fallback=True` 则继续尝试下一 provider
- 所有 provider 失败时抛 `MarketDataUnavailableError`，携带完整 `provider_attempts`
- `audit.record_fail_closed` 记录 final error_code 与所有 attempts

## API Contract 影响

- 无 API 变更（Phase 4 新增 `/product/market/**`）
- MarketDataRelay 供未来 Phase 4 API route 消费

## UI 影响

- 无 UI 变更（Phase 5 新增 Streamlit 可观测页面）

## Agent / LLM 边界影响

- MarketDataRelay 是确定性服务层，不含 LLM 调用
- Audit 事件、Health snapshot 可供 AgentOps 可观测性消费
- Relay 不赋予 LLM 买卖/订单/仓位决策权

## 未运行或跳过的项

| 项 | 原因 |
|---|---|
| 永久审计存储 | 按计划 health 使用内存聚合，dev report 说明进程重启丢失 |
| circuit breaker 集成 | ProviderHealthAggregator 含 circuit_breaker_status 字段，但基于内部 consecutive_failures；既有 ProviderCircuitBreaker 可作为增强 |
| 外部 provider 真实网络 | 所有测试使用 mock/fake adapter，不依赖真实网络 |

## 剩余风险

- Health 数据为内存聚合，进程重启后丢失（`snapshot()` 仅反映当前进程状态）
- Relay 的 cache 默认 FreshnessPolicy 为 30s fresh / 300s stale，生产环境可能需要按 symbol/market 差异化配置
- `_select_providers` 使用 `try/except Exception: pass` 屏蔽 registry.select 异常（设计上防止注册异常扩散到数据请求层）

## 真实交易能力影响

- 不新增真实交易能力
- MarketDataRelay 仅提供数据质量可信入口，不提供交易许可
- relay.fail-closed 确保不可信数据不进入 signal/trading 下游

## Safety Confirmation

| 检查项 | 结果 |
|---|---|
| 是否新增真实交易能力 | 否 |
| 是否绕过 risk | 否 |
| 是否绕过 stock-pool filtering | 否 |
| 是否绕过 human confirmation | 否 |
| 是否绕过 Provider Contract | 否（Relay 只消费已注册 contract + adapter） |
| 是否绕过 Tool Registry | 否（本功能不涉及 Tool Registry） |
| 是否绕过 fail-closed behavior | 否（QualityGate 阻断 + cache stale fail-closed + relay fail-closed） |
| 是否泄露 secret | 否（AuditRecorder 对 safe_reason 执行 redact_secret） |

## 受限模块确认

| 模块 | 状态 |
|---|---|
| `src/data_gateway/` | 未修改 |
| `src/risk_engine/` | 未触碰 |
| `src/execution_engine/` | 未触碰 |
| `src/stock_pool/` | 未触碰 |
| `src/backtest_engine/` | 未触碰 |
| `src/strategy_engine/` | 未触碰 |
| `src/factor_engine/` | 未触碰 |

## 最终结论

**PASS**

Phase 3 完成全部计划内容：MarketDataRelay（含 cache check + fallback + fail-closed）、AuditRecorder（含 secret 脱敏）、ProviderHealthAggregator（内存聚合）、MarketDataCache（stale fail-closed）。40 个自动化测试全绿，既有 34 个回归测试全绿，ruff/py_compile 无错误。未触碰受限模块，未新增真实交易能力，未泄露 secret。
