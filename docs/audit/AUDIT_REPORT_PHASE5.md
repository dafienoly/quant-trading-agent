# Phase 5 审计报告 (AUDIT_REPORT_PHASE5.md)

> 审计日期: 2026-06-09
> 审计范围: Phase 5 人工确认交易 — 执行引擎、订单检查、模拟交易、成交记录、API 订单管理、Streamlit 订单确认面板
> 审计依据: PHASE_COMPLETION_REPORT.md / EXECUTION_POLICY.md / RISK_POLICY.md / DATA_CONTRACTS.md / AGENTS.md
> 测试结果: **363/363 通过** (含 35 个新增 E2E/集成/API 测试)

---

## 一、审计总评

| 维度 | 评级 | 说明 |
|------|------|------|
| 功能完整性 | **B+** | 核心功能完整，但卖出数量获取、订单修改、超时取消缺失 |
| 文档合规性 | **A-** | EXECUTION_POLICY 合规度高，USER_GUIDE 已补充 |
| 安全约束 | **A** | 默认 LEVEL_1、禁止一键确认、风控不可绕过 |
| 测试覆盖 | **B+** | 单元测试充分，E2E/API 测试已补充，但缺少前端测试 |
| 可交付性 | **B** | 使用文档已补充，但缺少 README.md 和启动入口脚本 |

**结论: 有条件可交付** — 需修复 S1/S2 后方可交付客户

---

## 二、测试结果

### 2.1 测试套件运行结果

```
363 passed, 1 warning in 25.16s
```

| 测试文件 | 测试数 | 覆盖范围 |
|---------|--------|---------|
| test_phase5_execution.py | 14 | ExecutionService 生命周期 + API 端点 |
| test_phase5_order_checker.py | 14 | 订单检查器全部规则 |
| test_phase5_paper_broker.py | 11 | 模拟交易全部场景 |
| test_phase5_e2e.py (新增) | 35 | 完整 E2E/集成/API 测试 |
| test_phase4_*.py | 20 | Phase 4 风控/信号/监控 |
| test_phase3*.py | 100 | 回测引擎 |
| test_phase2*.py | 81 | 因子/策略 |
| test_audit_fixes.py | 39 | Phase 1 审计修复 |
| test_*.py (基础) | 49 | 数据层/股票池 |

### 2.2 新增 E2E/集成/API 测试覆盖

| 测试类 | 测试数 | 场景 |
|--------|--------|------|
| TestFullE2ELifecycle | 2 | Signal→Draft→Risk→Order→Confirm→Execute→TradeRecord 完整链路 |
| TestLevel3AutoExecution | 3 | LEVEL_3 自动执行、无待确认状态 |
| TestRiskBlockPreventsOrder | 3 | BLOCK 阻断、WARN 允许 |
| TestKillSwitchBlocksAll | 2 | Kill Switch 阻断订单创建和 API |
| TestPortfolioRiskIntegration | 3 | 仓位超限、日亏损止损、回撤停止 |
| TestAPIFullLifecycle | 3 | API 确认→账户→持仓链路 |
| TestAPILevel1RejectsConfirm | 2 | LEVEL_1 模式拒绝确认 |
| TestOrderCheckerIntegration | 4 | 非交易时段、创业板、资金调整、科创板 |
| TestSellOrderPositionCheck | 3 | 买入→卖出、超卖、无持仓 |
| TestTradeRecorderIntegration | 6 | 成交记录、日摘要、信号链路追溯 |
| TestAPIEdgeCases | 4 | 重复确认、不存在订单、撤销 |

---

## 三、代码审计发现

### S1 [严重] signal_to_draft() 卖出订单数量始终为 0

**位置**: `src/execution_engine/execution_service.py` L96-97

```python
else:
    # 卖出：从持仓获取数量，默认全仓
    quantity = 0  # 需要从持仓获取
```

**问题**: 卖出信号转换草稿时，quantity 硬编码为 0，未从持仓中获取实际可卖数量。OrderChecker 的 `check_order()` 会因 `quantity <= 0` 直接拒绝（L138-139），导致**所有卖出订单无法创建**。

**EXECUTION_POLICY 4.2 要求**: "quantity 不得超过当前可卖持仓"

**影响**: LEVEL_2/LEVEL_3 模式下，止损、止盈、趋势破位等所有卖出信号均无法生成有效订单草稿，卖出功能完全失效。

**修复建议**:
```python
else:
    # 卖出：从持仓获取可卖数量
    positions = self._broker.query_positions()
    pos = next((p for p in positions if p.symbol == signal.symbol), None)
    if pos is None:
        logger.warning(f"ExecutionService: 无持仓可卖 {signal.symbol}")
        return None
    quantity = pos.available_quantity
```

### S2 [严重] 缺少项目 README.md 和统一启动入口

**问题**: 项目根目录无 README.md，无统一启动脚本。客户无法快速了解项目、安装依赖和启动系统。

**影响**: 不满足交付要求 — "必须有相应的使用说明文档，能跑通完整使用流程"。

**修复建议**: 创建 README.md 包含项目简介、快速开始、使用流程；创建 `scripts/start.py` 或 Makefile 统一启动 API + Dashboard。

### M1 [中等] PaperBroker 涨跌停检测依赖 risk_note 字符串匹配

**位置**: `src/execution_engine/broker_adapter.py` L112-122

```python
if "LIMIT_UP" in (order.risk_note or "") and order.side == "BUY":
    return OrderResult(success=False, ...)
if "LIMIT_DOWN" in (order.risk_note or "") and order.side == "SELL":
    return OrderResult(success=False, ...)
if "SUSPENDED" in (order.risk_note or ""):
    return OrderResult(success=False, ...)
```

**问题**: 涨跌停/停牌检测通过 `risk_note` 字段字符串匹配实现，而非通过行情数据中的 `status` 字段。这导致：
1. 如果信号生成时未在 risk_note 中写入 LIMIT_UP/LIMIT_DOWN/SUSPENDED，PaperBroker 不会拒绝
2. risk_note 是自由文本字段，字符串匹配不可靠（如 "LIMIT_UP_REACHED" 也会匹配）
3. 与 realtime_provider.py 中已计算的 status 字段（NORMAL/LIMIT_UP/LIMIT_DOWN/SUSPENDED）脱节

**EXECUTION_POLICY 9 要求**: "模拟交易必须模拟真实的流动性约束：涨停不买、跌停不卖、停牌不成交"

**修复建议**: Order 模型增加 `market_status` 字段，PaperBroker 根据 `market_status` 判断涨跌停/停牌。

### M2 [中等] ExecutionService 未集成 TradeRecorder

**位置**: `src/execution_engine/execution_service.py`

**问题**: ExecutionService 有 `_on_trade_callback` 回调机制，但未在 `__init__` 中自动创建 TradeRecorder 并绑定回调。成交记录需要外部手动调用 `TradeRecorder.record_from_order()`。

**EXECUTION_POLICY 1.5 要求**: "每一笔订单必须有完整的日志链路，从信号 ID -> 风控 ID -> 订单 ID -> 成交记录"

**影响**: 如果使用者忘记手动绑定，成交记录将丢失，违反可追溯性要求。

**修复建议**: ExecutionService 构造函数中默认创建 TradeRecorder 并绑定回调。

### M3 [中等] API /account 和 /positions 直接访问 _broker 私有属性

**位置**: `src/api/app.py` L140, L148

```python
account = _execution_service._broker.query_account()
positions = _execution_service._broker.query_positions()
```

**问题**: API 端点直接访问 ExecutionService 的私有属性 `_broker`，违反封装原则。如果 ExecutionService 内部实现变更（如移除 _broker），API 将崩溃。

**修复建议**: 在 ExecutionService 上添加 `query_account()` 和 `query_positions()` 公共方法。

### M4 [中等] check_portfolio_risk() trading_mode 硬编码

**位置**: `src/risk_engine/runtime.py` L231

```python
trading_mode="LEVEL_1_SIGNAL_ONLY",
```

**问题**: `check_portfolio_risk()` 返回的 RiskDecision 中 trading_mode 硬编码为 LEVEL_1_SIGNAL_ONLY，未使用实际传入的交易模式。这导致 `can_generate_order` 属性在 LEVEL_2/LEVEL_3 模式下也返回 False。

**影响**: 如果 ExecutionService 使用 `check_portfolio_risk()` 的返回值来决定是否创建订单，LEVEL_2/LEVEL_3 模式下订单创建会被错误阻断。

**修复建议**: `check_portfolio_risk()` 接受 trading_mode 参数，或从 settings 读取。

### L1 [低] OrderChecker 未检查 ST 股票

**位置**: `src/execution_engine/order_checker.py`

**问题**: OrderChecker 检查了创业板/科创板禁止买入（通过 `is_excluded()`），但未单独检查 ST 股票。EXECUTION_POLICY 10.5 要求"禁止对创业板、科创板、ST 股生成任何买入订单"。

**说明**: `is_excluded()` 当前仅排除 300/301/688/689 前缀，不排除 ST。RISK_POLICY 4.2 要求 ST 股进入黑名单，但 OrderChecker 的黑名单需要手动配置。

**修复建议**: 在 OrderChecker 中增加 ST 股检测逻辑，或在默认黑名单中自动加入 ST 股。

### L2 [低] PaperBroker 模拟 T+0 而非 T+1

**位置**: `src/execution_engine/broker_adapter.py` L140

```python
pos.available_quantity = pos.quantity  # 模拟T+0
```

**问题**: A股实行 T+1 交易制度，当日买入的股票次日才可卖出。PaperBroker 将 available_quantity 设为 quantity，模拟的是 T+0。

**影响**: 模拟交易中可以当日买入后立即卖出，与真实交易不符。

**修复建议**: 买入时 `available_quantity = 0`，次日更新为 quantity。

### L3 [低] 缺少 EXECUTION_POLICY 5 要求的「修改价格/数量」功能

**位置**: `src/execution_engine/execution_service.py` + `src/api/app.py`

**问题**: EXECUTION_POLICY 5 要求确认界面提供「确认」「拒绝」「修改价格/数量」三个动作。当前只实现了确认和拒绝，缺少修改功能。

**影响**: 用户无法在确认前调整订单的价格或数量，只能拒绝后重新生成。

### L4 [低] 缺少订单超时自动取消

**位置**: `src/execution_engine/execution_service.py`

**问题**: EXECUTION_POLICY 5 要求"确认有效期：当日有效，收盘后未确认自动取消"。当前未实现自动取消逻辑。

### L5 [低] /risk/status 端点传入空行情列表

**位置**: `src/api/app.py` L39-41

```python
decision = _risk_engine.check_realtime_snapshot(
    quotes=[], trading_mode=MAX_TRADING_LEVEL,
)
```

**问题**: /risk/status 端点始终传入空行情列表，导致 EMPTY_QUOTES 阻断。虽然这符合"失败即安全"原则，但使得该端点在正常运行时也显示风控阻断，用户可能困惑。

**修复建议**: 集成 RealtimeProvider，传入实际行情数据；或在无行情时返回特殊状态而非 BLOCK。

---

## 四、EXECUTION_POLICY 合规性检查

| # | EXECUTION_POLICY 要求 | 状态 | 备注 |
|---|----------------------|------|------|
| 1 | 未确认不下单 | ✅ | LEVEL_2 必须逐笔确认 |
| 2 | 风控不通过不下单 | ✅ | create_order() 检查 risk_decision |
| 3 | 非交易时间不下单 | ✅ | OrderChecker.is_trading_hours() |
| 4 | 不超可用资金/持仓 | ⚠️ | 买入资金检查OK，卖出数量 S1 缺陷 |
| 5 | 可追溯 | ⚠️ | TradeRecorder 存在但未自动集成 M2 |
| 6 | LEVEL_1 不生成订单 | ✅ | signal_to_draft() 返回 None |
| 7 | 订单生命周期完整 | ✅ | CREATED→RISK_CHECKED→CONFIRMED→SENT→FILLED/REJECTED |
| 8 | 人工确认逐笔操作 | ✅ | 禁止一键确认 |
| 9 | 确认界面展示完整信息 | ✅ | Dashboard 展示全部字段 |
| 10 | 修改价格/数量 | ❌ | L3 缺失 |
| 11 | 订单超时自动取消 | ❌ | L4 缺失 |
| 12 | BrokerAdapter 抽象 | ✅ | ABC + PaperBroker |
| 13 | 交易时段控制 | ✅ | A股/港股时段 + 尾盘禁止 |
| 14 | 模拟交易流动性约束 | ⚠️ | M1 涨跌停检测依赖字符串匹配 |
| 15 | 禁止创业板/科创板买入 | ✅ | OrderChecker + is_excluded() |
| 16 | 禁止 ST 股买入 | ⚠️ | L1 未单独检查 |

---

## 五、RISK_POLICY 合规性检查

| # | RISK_POLICY 要求 | 状态 | 备注 |
|---|-----------------|------|------|
| 1 | 风控优先于收益 | ✅ | RiskDecision 一票否决 |
| 2 | 失败即安全 | ✅ | 默认阻断 |
| 3 | 单票仓位 15% | ✅ | check_portfolio_risk() |
| 4 | 板块集中度 60% | ✅ | check_portfolio_risk() |
| 5 | 现金最低 20% | ✅ | check_portfolio_risk() |
| 6 | 单票亏损 -5%/-8% | ✅ | WARN/STOP |
| 7 | 日亏损 -2%/-3% | ✅ | STOP_NEW/REDUCE_ONLY |
| 8 | 回撤 -8%/-12% | ✅ | DEFENSE/HALT |
| 9 | Kill Switch | ✅ | KillSwitchState |
| 10 | 黑名单 | ✅ | OrderChecker blacklist |
| 11 | 涨停不买/跌停不卖 | ⚠️ | M1 依赖 risk_note |
| 12 | 交易权限分级 | ✅ | LEVEL_0~3 |
| 13 | 风控检查流程10步 | ⚠️ | 部分步骤分散在不同模块 |

---

## 六、Phase 4 遗留问题验证

| 问题 | 状态 | 验证结果 |
|------|------|---------|
| M1: /risk/status 硬编码 | ✅ 已修复 | 集成 RuntimeRiskEngine 注入 |
| M2: WatchlistMonitor 异常处理 | ✅ 已修复 | try-except 包裹 |
| S1: RuntimeRiskEngine 交易层风控 | ✅ 已修复 | check_portfolio_risk() 实现 RISK_POLICY 2-4 节 |
| realtime_provider 涨跌停检测 | ✅ 已修复 | 区分 10%/20%/5% 涨跌停 |

---

## 七、可交付性评估

### 7.1 已满足的交付要求

| # | 交付要求 | 状态 |
|---|---------|------|
| 1 | 完整订单生命周期 | ✅ |
| 2 | LEVEL_1/LEVEL_2/LEVEL_3 模式 | ✅ |
| 3 | 人工确认逐笔操作 | ✅ |
| 4 | 风控不可绕过 | ✅ |
| 5 | 模拟交易 | ✅ |
| 6 | API 订单管理端点 | ✅ |
| 7 | Streamlit 订单确认面板 | ✅ |
| 8 | 成交记录可追溯 | ✅ |
| 9 | 使用说明文档 | ✅ USER_GUIDE.md 已创建 |
| 10 | E2E/API/集成测试 | ✅ 363 测试通过 |

### 7.2 未满足的交付要求

| # | 缺失项 | 严重程度 | 影响 |
|---|--------|---------|------|
| 1 | README.md | S2 | 客户无法快速上手 |
| 2 | 卖出订单无法创建 | S1 | 止损/止盈功能失效 |
| 3 | 统一启动脚本 | M | 需要手动启动多个服务 |

---

## 八、修复优先级

### 必须修复 (交付阻塞)

| # | 问题 | 修复方案 | 预估工作量 |
|---|------|---------|-----------|
| S1 | 卖出订单 quantity=0 | signal_to_draft() 从持仓获取可卖数量 | 小 |
| S2 | 缺少 README.md | 创建项目 README + 快速开始 | 小 |

### 建议修复 (交付后)

| # | 问题 | 修复方案 | 预估工作量 |
|---|------|---------|-----------|
| M1 | PaperBroker 涨跌停检测 | Order 增加 market_status 字段 | 中 |
| M2 | TradeRecorder 未自动集成 | ExecutionService 默认绑定 | 小 |
| M3 | API 访问私有属性 | 添加公共方法 | 小 |
| M4 | trading_mode 硬编码 | 参数化 | 小 |
| L1 | ST 股检查 | OrderChecker 增加 ST 检测 | 小 |
| L2 | T+0 模拟 | available_quantity 延迟更新 | 中 |
| L3 | 修改价格/数量 | 新增 modify_order() | 中 |
| L4 | 订单超时取消 | 定时任务清理 | 中 |
| L5 | /risk/status 空行情 | 集成 RealtimeProvider | 中 |

---

## 九、交付建议

**当前状态: 有条件可交付**

1. **修复 S1 + S2 后可交付** — 这两个问题修复工作量小，但影响大
2. M1~M4 建议在交付后第一轮迭代中修复
3. L1~L5 可在 Phase 6 开发中逐步完善

**交付清单**:

| 交付物 | 状态 |
|--------|------|
| 源代码 (src/) | ✅ |
| 测试套件 (tests/, 363 cases) | ✅ |
| 使用说明 (docs/USER_GUIDE.md) | ✅ |
| 项目 README | ❌ 待创建 (S2) |
| 配置模板 (.env.example) | ✅ |
| 策略文档 (docs/policy/) | ✅ |
| 设计文档 (docs/design/) | ✅ |
| 审计报告 (docs/audit/) | ✅ |

---

## 十、审计检查清单确认

### A. 代码安全

- [x] 无硬编码密钥/Token/密码
- [x] `.env` 在 `.gitignore` 中
- [x] 无 eval/exec 动态代码执行
- [x] 无 SQL 注入风险
- [x] 无命令注入风险

### B. 数据完整性

- [x] 不使用未来数据
- [x] 原始数据保留不覆盖
- [x] 数据变更有版本记录
- [x] 缺失数据有明确标记而非静默填充

### C. 风控合规

- [x] 默认交易模式为 LEVEL_1_SIGNAL_ONLY
- [x] 风控模块未被绕过或删除
- [x] Kill Switch 机制完整
- [x] 创业板/科创板过滤有效
- [ ] ST 股过滤 (L1 待修复)

### D. 测试覆盖

- [x] 核心逻辑有单元测试
- [x] 测试可独立运行 (`pytest tests/`)
- [x] 无跳过的测试
- [x] 边界条件和异常场景有覆盖
- [x] E2E/集成/API 测试已补充

### E. 文档完整性

- [x] 接口有 docstring 或注释
- [x] 配置文件有示例 (.env.example)
- [x] 运行方式有说明 (USER_GUIDE.md)
- [x] 已知问题有记录
- [ ] 项目 README (S2 待创建)
