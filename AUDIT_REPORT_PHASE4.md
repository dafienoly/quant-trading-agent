# Phase 4 审计与测试报告

> 审计日期：2026-06-08
> 审计范围：Phase 4（实盘盯盘与信号生成）
> 对照文档：ROADMAP_AND_CONSTRAINTS.md、AGENTS.md、ARCHITECTURE.md、RISK_POLICY.md、EXECUTION_POLICY.md、AUDIT_REPORT_PHASE4_RISK_FIRST.md

---

## 一、测试执行结果

| 项目 | 结果 |
|------|------|
| 测试框架 | pytest 8.4.2 |
| 测试文件 | 14 个 |
| 测试用例 | 271 个 |
| 通过 | 271/271 (100%) |
| 跳过/失败 | 0 |

**Phase 4 专项测试：**

| 文件 | 用例数 | 覆盖范围 |
|------|--------|---------|
| test_phase4_risk_engine.py | 7 | RiskDecision 属性 + RuntimeRiskEngine 5 个场景 |
| test_phase4_realtime_health.py | 2 | 过期行情 + 新鲜行情 |
| test_phase4_watchlist_monitor.py | 3 | 风控通过/风控阻断/信号生成异常 |
| test_phase4_signal_service.py | 3 | Kill Switch/回调/结果存储 |
| test_phase4_api.py | 5 | /health + /risk/status + /signals/latest + /backtest/run 拒绝 |

---

## 二、Phase 4 Risk-First 审计修复验证

### M1: /risk/status 端点硬编码 → ✅ 已修复

**修复前：** `/risk/status` 返回硬编码 `risk_pass=True`
**修复后：** API 通过 `create_app(risk_engine=...)` 注入 `RuntimeRiskEngine`，`/risk/status` 调用 `check_realtime_snapshot()` 动态计算

```python
# app.py L19-23
def create_app(risk_engine: RuntimeRiskEngine | None = None, ...):
    _risk_engine = risk_engine or RuntimeRiskEngine()

@app.get("/risk/status")
def risk_status():
    decision = _risk_engine.check_realtime_snapshot(quotes=[], trading_mode=MAX_TRADING_LEVEL)
    return decision.model_dump()
```

**测试覆盖：** `test_risk_endpoint_uses_runtime_risk_engine` — 注入 Kill Switch 后验证返回 `risk_pass=False`

---

### M2: WatchlistMonitor 缺少异常处理 → ✅ 已修复

**修复前：** `generate_signals()` 可能抛异常导致整个监控流程中断
**修复后：** `try-except` 包裹，信号生成失败时返回空信号列表 + 错误信息到 `risk_messages`

```python
# watchlist_monitor.py L25-34
try:
    signals = generate_signals(scored_data, include_hold=False)
except Exception as e:
    logger.warning(f"信号生成失败: {e}")
    return {
        "risk_pass": risk_decision.risk_pass,
        "risk_messages": risk_decision.messages + [f"信号生成异常: {e}"],
        "signals": [],
        "orders": [],
    }
```

**测试覆盖：** `test_watchlist_monitor_handles_signal_generation_error` — mock `generate_signals` 抛 `ValueError`

---

## 三、Phase 4 合规性审计

### 严重问题（1 项）

#### S1: RuntimeRiskEngine 缺少 RISK_POLICY.md 4.1 节的核心风控规则

**位置：** `src/risk_engine/runtime.py`

RISK_POLICY.md 4.1 节定义了 10 项 HARD 限制，当前 `RuntimeRiskEngine` 仅实现了 3 项：

| # | RISK_POLICY 4.1 要求 | 实现状态 |
|---|---------------------|---------|
| 1 | 单日亏损超过限制 | ❌ 未实现 |
| 2 | 单票亏损超过限制 | ❌ 未实现 |
| 3 | 板块集中度超过限制 | ❌ 未实现 |
| 4 | 数据源异常 | ⚠️ 部分实现（仅检查空行情和延迟） |
| 5 | 行情延迟异常 | ✅ 已实现 |
| 6 | 账户资金异常 | ❌ 未实现 |
| 7 | 策略信号冲突 | ❌ 未实现 |
| 8 | 交易接口异常 | ❌ 未实现（Phase 5 范围） |
| 9 | 回测结果不达标 | ❌ 未实现 |
| 10 | 人工禁止交易 | ✅ 已实现（Kill Switch） |

**影响：** RISK_POLICY.md 4.1 节明确"任何时候，风控模块拥有最高优先级"，且 AGENTS.md 3.6 节要求 Risk Agent 检查单票仓位、行业仓位、账户回撤、当日亏损等。当前运行时风控仅覆盖数据层，未覆盖交易层风控。

**修复方案：** 在 `RuntimeRiskEngine` 中新增 `check_portfolio_risk(portfolio)` 方法，接收持仓信息后检查单票亏损/板块集中度/账户回撤/日亏损

---

### 中等问题（4 项）

#### M1: AkShareRealtimeProvider 的涨跌停状态判断不完整

**位置：** `src/data_gateway/realtime_provider.py:49-50`

```python
df.loc[df["pct_change"].astype(float, errors="ignore") >= 9.9, "status"] = "LIMIT_UP"
df.loc[df["pct_change"].astype(float, errors="ignore") <= -9.9, "status"] = "LIMIT_DOWN"
```

**问题：** 统一用 9.9% 判断涨跌停，未区分：
- 创业板/科创板 20% 涨跌停
- ST 股 5% 涨跌停

这与 Phase 1 审计修复的 `column_mapper.py` 涨跌停幅度区分逻辑不一致。

---

#### M2: API 缺少 /signals/latest 的数据注入机制

**位置：** `src/api/app.py:41-45`

```python
@app.get("/signals/latest")
def signals_latest():
    if _signal_service and _signal_service.last_result:
        return _signal_service.last_result
    return {"risk_pass": False, "signals": [], "orders": [], "risk_messages": ["no signal data"]}
```

**问题：** `SignalService` 需要外部定时调用 `run_once()` 来更新 `last_result`，但 API 层没有定时触发机制。在没有外部调度器的情况下，`/signals/latest` 始终返回空数据。

**建议：** 添加后台调度（APScheduler）或在 API 中提供手动触发端点（POST /signals/refresh，仅开发模式）

---

#### M3: Streamlit 面板信号列表始终为空

**位置：** `src/ui_report/dashboard.py:88`

```python
with tab2:
    render_signal_panel([])  # 硬编码空列表
```

**问题：** 信号面板始终传入空列表，无法展示真实信号。需要从 `SignalService.last_result` 或 API 获取信号数据。

---

#### M4: 缺少端到端集成测试

**位置：** `tests/` 目录

当前 Phase 4 测试全部为单元测试，缺少从"实时行情 → 健康门禁 → 风控检查 → 信号生成 → API 返回"的端到端集成测试。

---

### 低/建议（4 项）

#### L1: DataDelayReport.generated_at 与 now 时间基准不一致

**位置：** `src/data_gateway/realtime_health.py`

`build_realtime_health_report` 传入 `now` 参数用于延迟计算，但 `DataDelayReport.generated_at` 使用默认值（当前时间），两者时间基准不一致。

#### L2: agent_orchestrator/__init__.py 为空

未导出 `WatchlistMonitor` 和 `SignalService`。

#### L3: realtime_provider.py 缺少港股实时行情支持

ARCHITECTURE.md 定义港股通标的在可交易范围内，但 `AkShareRealtimeProvider` 仅支持 A 股 `stock_zh_a_spot_em`。

#### L4: 缺少 WebSocket 实时推送

ARCHITECTURE.md 10.1 节建议 WebSocket 推送，当前 API 仅为轮询模式。

---

## 四、风控防线验证

### 四道防线

| 防线 | 机制 | 验证结果 |
|------|------|---------|
| 第一道 | RiskDecision.can_generate_order 在 SIGNAL_ONLY 下为 False | ✅ 代码正确 + 测试覆盖 |
| 第二道 | WatchlistMonitor.orders 永远为空列表 | ✅ 代码硬编码 + 测试覆盖 |
| 第三道 | API 只读，无写入端点 | ✅ 无 POST/PUT/DELETE + /backtest/run 拒绝 |
| 第四道 | 数据健康门禁阻断延迟行情 | ✅ realtime_health.py + 测试覆盖 |

### 安全约束验证

| 约束 | 状态 | 验证方式 |
|------|------|---------|
| MAX_TRADING_LEVEL=LEVEL_1_SIGNAL_ONLY | ✅ | /health 端点返回 + settings.py |
| ENABLE_LIVE_TRADING=false | ✅ | /health 端点返回 + settings.py |
| execution_engine 不可用 | ✅ | 未创建任何执行引擎代码 |
| Kill Switch 机制 | ✅ | RuntimeRiskEngine + 测试覆盖 |
| 创业板/科创板过滤 | ✅ | check_symbol_universe + is_excluded() |

---

## 五、项目偏离评估

### 是否偏离设计目标约束？

| 偏离类型 | 具体表现 | 影响等级 |
|----------|---------|---------|
| 风控规则偏离 | RISK_POLICY 10 项 HARD 限制仅实现 3 项 | 严重 |
| 涨跌停判断偏离 | 实时行情 Provider 未区分 10%/20%/5% 幅度 | 中等 |
| 前端功能偏离 | Streamlit 信号面板硬编码空列表 | 中等 |
| 测试层次偏离 | 仅有单元测试，缺少集成/E2E 测试 | 中等 |

### 功能是否正常可用？

| 功能 | 状态 | 说明 |
|------|------|------|
| 运行时风控引擎 | ⚠️ 部分可用 | 数据层风控完整，交易层风控缺失 |
| 实时行情获取 | ✅ 正常 | AkShare stock_zh_a_spot_em 可用 |
| 数据健康门禁 | ✅ 正常 | 延迟检测/过期检测正确 |
| 只读盯盘监控器 | ✅ 正常 | 信号生成+风控门禁+异常处理完整 |
| 信号生成服务 | ✅ 正常 | 定时触发+风控检查+回调通知 |
| FastAPI 接口 | ⚠️ 部分可用 | 端点正确但 /signals/latest 无数据源 |
| Streamlit 面板 | ⚠️ 部分可用 | 风控状态展示正确，信号列表始终为空 |
| Kill Switch | ✅ 正常 | 一键阻断所有信号生成 |

---

## 六、Phase 4 验收标准复核

| # | 验收标准 | 复核结果 | 说明 |
|---|---------|---------|------|
| 1 | 运行时风控引擎可用 | ⚠️ 部分通过 | 数据层风控完整，交易层风控缺失 |
| 2 | 实时行情数据健康门禁 | ✅ 通过 | 延迟/过期检测正确 |
| 3 | 只读盯盘监控器 | ✅ 通过 | 信号+风控+异常处理完整 |
| 4 | 信号生成服务 | ✅ 通过 | 定时触发+回调通知 |
| 5 | API 只读端点 | ⚠️ 部分通过 | 端点正确但 /signals/latest 无数据注入 |
| 6 | Streamlit 面板 | ⚠️ 部分通过 | 风控展示正确，信号列表为空 |
| 7 | 安全约束全部落地 | ✅ 通过 | 四道防线 + Kill Switch |
| 8 | M1/M2 审计修复 | ✅ 通过 | 已修复并测试 |

---

## 七、改进建议（按优先级排序）

### P0 — 必须修复

| # | 问题 | 修复方案 |
|---|------|---------|
| 1 | RuntimeRiskEngine 缺少交易层风控 | 新增 `check_portfolio_risk(portfolio)` 方法，检查单票亏损/板块集中度/账户回撤/日亏损 |
| 2 | 实时行情涨跌停判断不区分幅度 | 根据 symbol 前缀区分 10%/20%，根据 ST 状态区分 5% |

### P1 — Phase 5 之前补齐

| # | 问题 | 修复方案 |
|---|------|---------|
| 3 | /signals/latest 无数据注入 | 添加 APScheduler 后台调度或手动触发端点 |
| 4 | Streamlit 信号面板硬编码空列表 | 从 SignalService 或 API 获取信号数据 |
| 5 | 补充端到端集成测试 | 实时行情→健康门禁→风控→信号→API 全流程 |
| 6 | 港股实时行情支持 | 使用 AkShare 港股接口 |

### P2 — 中期优化

| # | 问题 | 修复方案 |
|---|------|---------|
| 7 | WebSocket 实时推送 | FastAPI WebSocket 端点 |
| 8 | agent_orchestrator/__init__.py 导出 | 统一导出 WatchlistMonitor/SignalService |
| 9 | DataDelayReport 时间基准一致性 | 传入 generated_at 参数 |

---

## 八、测试框架完整性评估

### 现有测试层次

```
          ┌─────────────┐
          │  E2E 测试    │  ← ❌ 缺失
          ├─────────────┤
          │  集成测试     │  ← ❌ 缺失（Phase 3 有 3 个，Phase 4 无新增）
          ├─────────────┤
          │  API 测试    │  ← ✅ 5 个（FastAPI TestClient）
          ├─────────────┤
          │  单元测试     │  ← ✅ 266 个
          └─────────────┘
```

### 建议新增的测试

| 文件 | 类型 | 覆盖范围 |
|------|------|---------|
| `tests/integration/test_realtime_pipeline.py` | 集成测试 | 实时行情→健康门禁→风控→信号→API |
| `tests/e2e/test_signal_flow.py` | 端到端 | 使用 mock AkShare 数据的完整盯盘流程 |
| `tests/api/test_signal_refresh.py` | API 测试 | 信号刷新端点（如有） |

---

## 九、审计结论

### 总评

Phase 4 Risk-First 基础架构已完整落地，四道安全防线全部有效，M1/M2 审计修复已验证通过。271/271 测试全部通过。核心安全约束（LEVEL_1_SIGNAL_ONLY、can_generate_order 永远 False、orders 永远为空、API 只读）均已正确实现。

### 主要风险

1. **RuntimeRiskEngine 交易层风控缺失**（S1）— RISK_POLICY.md 10 项 HARD 限制仅实现 3 项，这是最严重的偏离
2. **实时行情涨跌停判断不区分幅度**（M1）— 与 Phase 1 修复的 column_mapper 逻辑不一致

### 是否可进入 Phase 5？

**有条件可以。** Phase 5（人工确认交易）需要交易层风控作为前置依赖，S1 必须在 Phase 5 之前修复。M1-M4 可在 Phase 5 开发中同步修复。
