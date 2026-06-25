# Phase 4 Risk-First Readiness Implementation Plan

> 本文档记录 Phase 4 Risk-First 准备工作的实施计划和完成情况。
> 基于 Leader 的架构复核裁决和 `docs/superpowers/plans/2026-06-08-phase4-risk-first-readiness.md`。

---

## 一、Leader 架构复核裁决摘要

### 1.1 核心意见

1. **Phase 3 可以进入 Phase 4，但不是无条件放行**
2. **新增 `BACKTEST_POLICY.md`** — 日频收盘信号默认必须在下一交易日成交，禁止前视偏差
3. **回测引擎修复** — `next_open`/`vwap` 模式现在真正延迟到下一交易日执行
4. **因子评估修复** — `evaluate_all_factors()` 缺少 `forward_return` 时的 `symbol_col` 未定义问题
5. **依赖修复** — Rank IC 与统计显著性检验对未声明 `scipy` 的硬依赖
6. **Phase 4 开发顺序调整** — 风控优先：risk_engine → 数据健康 → 信号 → API/UI

### 1.2 架构裁决

| 裁决项 | 内容 |
|--------|------|
| Phase 4 必须先落地运行时 `risk_engine` | `execution_engine` 保持不可用 |
| 交易模式保持 `LEVEL_1_SIGNAL_ONLY` | `can_generate_order` 永远为 False |
| API 只提供只读端点 | 不提供任何写入/下单接口 |
| 数据健康门禁 | 行情延迟超过阈值时阻断信号生成 |

---

## 二、实施计划 (6 个 Task)

### Task 1: Runtime Risk Models ✅

**目标：** 定义运行时风控决策模型

**交付物：**
- `src/risk_engine/models.py`

**核心模型：**

| 模型 | 说明 |
|------|------|
| `RiskLevel` | OK / WARN / BLOCK 三级 |
| `RiskBlockReason` | DATA_DELAY / EMPTY_QUOTES / UNKNOWN_SYMBOL / DISALLOWED_BOARD / KILL_SWITCH / INVALID_TRADING_MODE / LIVE_TRADING_DISABLED |
| `KillSwitchState` | active / reason / activated_at |
| `RiskDecision` | risk_pass / level / trading_mode / reasons / messages / evidence + can_generate_signal / can_generate_order 属性 |

**关键约束：**
- `RiskDecision.can_generate_order` 在 `LEVEL_1_SIGNAL_ONLY` 模式下永远为 False
- 只有 `LEVEL_2_HUMAN_CONFIRM` 和 `LEVEL_3_AUTO` 模式才允许生成订单

**测试：** 2 个测试用例通过

---

### Task 2: Runtime Risk Engine ✅

**目标：** 实现运行时风控检查逻辑

**交付物：**
- `src/risk_engine/runtime.py`

**核心功能：**

| 方法 | 说明 |
|------|------|
| `check_realtime_snapshot(quotes, trading_mode)` | 检查实时行情快照：延迟/空值/Kill Switch |
| `check_symbol_universe(symbols)` | 检查股票池范围：排除创业板/科创板 |

**检查逻辑：**
1. Kill Switch 激活 → BLOCK
2. 行情数据为空 → BLOCK (EMPTY_QUOTES)
3. 行情延迟超过阈值 → BLOCK (DATA_DELAY)
4. 股票池包含创业板/科创板 → BLOCK (DISALLOWED_BOARD)

**测试：** 3 个测试用例通过

---

### Task 3: Realtime Data Health Gate ✅

**目标：** 将实时行情获取元数据转换为 DataDelayReport

**交付物：**
- `src/data_gateway/realtime_health.py`

**核心功能：**

| 函数 | 说明 |
|------|------|
| `build_realtime_health_report(provider, quotes, now, max_delay_seconds)` | 构建数据延迟报告 |

**输出模型：** `DataDelayReport`（已在 schemas.py 中定义）

| 字段 | 说明 |
|------|------|
| provider | 数据源名称 |
| total_symbols | 总股票数 |
| avg_latency_seconds | 平均延迟 |
| max_latency_seconds | 最大延迟 |
| delayed_symbols | 延迟股票列表 |
| is_acceptable | 是否可接受 |

**测试：** 2 个测试用例通过

---

### Task 4: Read-Only Watchlist Monitor ✅

**目标：** 结合策略信号和运行时风控，生成只读提醒

**交付物：**
- `src/agent_orchestrator/watchlist_monitor.py`

**核心功能：**

| 方法 | 说明 |
|------|------|
| `generate_alerts(scored_data, risk_decision)` | 生成信号提醒 |

**核心约束：**
- 风控不通过时，返回空信号列表
- 风控通过时，调用 `generate_signals()` 生成信号
- **永远不生成 Order 对象**，`orders` 永远为空列表

**输出格式：**
```python
{
    "risk_pass": bool,
    "risk_messages": list[str],
    "signals": list[dict],  # Signal.model_dump()
    "orders": [],           # 永远为空
}
```

**测试：** 2 个测试用例通过

---

### Task 5: Read-Only Phase 4 API ✅

**目标：** 提供只读 HTTP API

**交付物：**
- `src/api/app.py`
- `src/api/__init__.py`

**端点：**

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查，返回 max_trading_level 和 enable_live_trading |
| `/risk/status` | GET | 风控状态，返回 RiskDecision |

**核心约束：**
- 不提供任何 POST/PUT/DELETE 端点
- 不提供任何下单/写入接口
- `/health` 返回 `max_trading_level: "LEVEL_1_SIGNAL_ONLY"` 和 `enable_live_trading: false`

**测试：** 2 个测试用例通过

---

### Task 6: Final Phase 4 Gate Verification ✅

**目标：** 全量回归测试 + lint 检查

**验证结果：**

| 检查项 | 结果 |
|--------|------|
| Phase 4 专项测试 | 11/11 通过 |
| 全量回归测试 | 262/262 通过 |
| ruff lint | 无新增错误 |

---

## 三、交付物总览

### 3.1 新增源码文件 (5 个)

| # | 文件 | 行数 | 说明 |
|---|------|------|------|
| 1 | `src/risk_engine/models.py` | 58 | 运行时风控模型 |
| 2 | `src/risk_engine/runtime.py` | 68 | 运行时风控引擎 |
| 3 | `src/data_gateway/realtime_health.py` | 50 | 实时数据健康门禁 |
| 4 | `src/agent_orchestrator/watchlist_monitor.py` | 38 | 只读盯盘监控器 |
| 5 | `src/api/app.py` | 35 | 只读 API |

### 3.2 新增测试文件 (4 个)

| # | 文件 | 测试数 |
|---|------|--------|
| 1 | `tests/test_phase4_risk_engine.py` | 5 |
| 2 | `tests/test_phase4_realtime_health.py` | 2 |
| 3 | `tests/test_phase4_watchlist_monitor.py` | 2 |
| 4 | `tests/test_phase4_api.py` | 2 |

### 3.3 更新文件 (2 个)

| # | 文件 | 变更 |
|---|------|------|
| 1 | `PHASE_COMPLETION_REPORT.md` | Phase 4 状态更新为 Risk-First 基础已完成 |
| 2 | `DEVELOPMENT_LOG.md` | 测试统计和版本历史更新 |

---

## 四、风控防线验证

### 4.1 第一道防线：RiskDecision.can_generate_order

```python
# LEVEL_1_SIGNAL_ONLY 模式下
decision = RiskDecision(risk_pass=True, level=RiskLevel.OK, trading_mode="LEVEL_1_SIGNAL_ONLY")
assert decision.can_generate_signal is True   # 可以生成信号
assert decision.can_generate_order is False   # 不能生成订单
```

### 4.2 第二道防线：WatchlistMonitor.orders 永远为空

```python
monitor = WatchlistMonitor()
result = monitor.generate_alerts(scored_data, risk_decision)
assert result["orders"] == []  # 永远为空
```

### 4.3 第三道防线：API 只读

```python
# /health 返回
{"max_trading_level": "LEVEL_1_SIGNAL_ONLY", "enable_live_trading": False}

# 无任何 POST/PUT/DELETE 端点
```

### 4.4 第四道防线：数据健康门禁

```python
# 行情延迟超过阈值 → is_acceptable = False → 风控 BLOCK
report = build_realtime_health_report(provider, quotes, now, max_delay_seconds=10)
if not report.is_acceptable:
    # 阻断信号生成
```

---

## 五、后续工作 (Phase 4 完整开发)

Risk-First 基础已就绪，后续可按以下顺序继续开发：

1. **实时行情 Provider** — 接入 AkShare 实时行情接口
2. **信号生成服务** — 定时触发因子计算和信号生成
3. **WebSocket 推送** — 实时推送信号和风控状态
4. **Streamlit 前端** — 盯盘面板、信号列表、风控监控
5. **回测触发 API** — 通过 API 触发回测任务
6. **通知服务** — 信号提醒（邮件/钉钉/微信）
