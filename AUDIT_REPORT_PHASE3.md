# Phase 3 审计与测试报告

> 审计日期：2026-06-08
> 审计范围：Phase 3（回测与评估）
> 对照文档：ROADMAP_AND_CONSTRAINTS.md、AGENTS.md、ARCHITECTURE.md、DATA_CONTRACTS.md、RISK_POLICY.md

---

## 一、测试执行结果

| 项目 | 结果 |
|------|------|
| 测试框架 | pytest 8.4.2 |
| 测试文件 | 8 个 |
| 测试用例 | 190 个 |
| 通过 | 190/190 (100%) |
| 跳过/失败 | 0 |
| 耗时 | 4.56s |

**Phase 3 专项测试：** `test_phase3.py` 含 42 个用例，覆盖交易成本(5)、组合管理(6)、绩效指标(6)、风控检查(5)、回测引擎(8)、样本外测试(3)、市场环境测试(3)、验收标准(6)。

---

## 二、Phase 3 合规性审计

### 严重问题（3 项）

#### S1: 缺少事件驱动回测器（event_backtester）

**位置：** `src/backtest_engine/` 目录

ARCHITECTURE.md 2 节明确定义 backtest_engine 包含：
- `event_backtester` → ❌ 未实现
- `vector_backtester` → ✅ 已实现（engine.py 中的 BacktestEngine）
- `cost_model` → ✅ 已实现（commission_model.py）
- `slippage_model` → ❌ 未实现（滑点逻辑硬编码在 commission_model 中）
- `report_generator` → ✅ 部分实现（performance.py 生成报告）

**问题：** 事件驱动回测器支持逐笔撮合、盘中策略，是 Phase 4 实盘盯盘的前置依赖。当前仅有向量回测器，无法模拟盘中时序。

**违反文档：** ARCHITECTURE.md 2 节

**修复方案：** 实现 `EventBacktester` 类，支持逐日/逐 tick 事件驱动回测

---

#### S2: 滑点模型硬编码，未独立抽象

**位置：** `src/backtest_engine/commission_model.py:55-57`

```python
def apply_slippage(self, price, direction, volume_ratio=0.0):
    slip = price * self.slippage_bps / 10000
    if direction == "buy":
        return price + slip
    return price - slip
```

**问题：** ARCHITECTURE.md 定义 `slippage_model` 为独立子模块，但当前滑点逻辑内嵌在 `CommissionModel` 中。滑点模型应独立，支持：
- 固定滑点（当前实现）
- 百分比滑点
- 成交量冲击滑点（大单冲击成本）
- 市场深度滑点

**违反文档：** ARCHITECTURE.md 2 节

**修复方案：** 抽取 `SlippageModel` 独立类，支持多种滑点策略

---

#### S3: 缺少集成测试、端到端测试和 API 测试

**位置：** `tests/` 目录

当前测试全部为单元测试，缺少：

| 测试层次 | 状态 | 说明 |
|---------|------|------|
| 单元测试 | ✅ 190 个 | 覆盖 Phase 1+2+3 |
| 集成测试 | ❌ 缺失 | 无跨模块集成测试 |
| 端到端测试 | ❌ 缺失 | 无从数据到回测报告的完整流程测试 |
| API 测试 | ❌ 缺失 | 无 FastAPI/Streamlit 服务 |

Phase 3 用户明确要求"包括集成测试、端到端测试、API 测试等"，当前完全缺失。

---

### 中等问题（5 项）

#### M1: 回测引擎未处理涨跌停无法成交逻辑

**位置：** `src/backtest_engine/engine.py:131-145`

```python
def _execute_signal(self, signal, daily_data, portfolio):
    price = daily_data["close"]
    # 直接以收盘价成交，未检查涨跌停
```

**问题：** ROADMAP Phase 3 明确要求"涨跌停/停牌无法成交逻辑"。当前回测引擎：
- 涨停时买入应无法成交（买盘排队）→ 未处理
- 跌停时卖出应无法成交（卖盘排队）→ 未处理
- 停牌日无法成交 → 仅在 risk_check 中检查 is_suspended，但 engine 未使用

AGENTS.md 3.5 节 Backtest Agent 禁止"不处理涨跌停无法成交"和"不处理停牌"。

**违反文档：** ROADMAP Phase 3、AGENTS.md 3.5 节

---

#### M2: 回测报告缺少 AGENTS.md 3.5 节要求的多个指标

**位置：** `src/backtest_engine/performance.py`

AGENTS.md 3.5 节要求 Backtest Agent 必须输出 12 项指标：

| 指标 | 要求 | 实现状态 |
|------|------|---------|
| annual_return | ✅ | ✅ 已实现 |
| max_drawdown | ✅ | ✅ 已实现 |
| sharpe_ratio | ✅ | ✅ 已实现 |
| calmar_ratio | ✅ | ✅ 已实现 |
| win_rate | ✅ | ✅ 已实现 |
| profit_loss_ratio | ✅ | ✅ 已实现 |
| turnover | ✅ | ✅ 已实现 |
| cost_adjusted_return | ✅ | ❌ 未实现（仅有 gross_return） |
| benchmark_return | ✅ | ❌ 未实现 |
| excess_return | ✅ | ❌ 未实现 |
| monthly_return | ✅ | ❌ 未实现 |
| yearly_return | ✅ | ❌ 未实现 |

缺少 5/12 项指标。

---

#### M3: 缺少回测报告 HTML/可视化输出

**位置：** 无对应实现

ARCHITECTURE.md 定义 `report_generator` 子模块，应生成可视化回测报告。当前 `performance.py` 仅返回字典，无 HTML/PDF/图表输出。

Phase 3 用户要求"搭配前后端的实测"，需要可视化报告输出。

---

#### M4: 样本外测试和市场环境测试仅验证框架，未验证策略

**位置：** `src/backtest_engine/engine.py:178-219`

`run_out_of_sample_test` 和 `run_market_regime_test` 方法存在，但仅是框架代码：
- `run_out_of_sample_test` 将数据按比例分割，分别回测
- `run_market_regime_test` 按涨跌分市场环境

但未实际验证策略在不同环境下的表现差异，且缺少统计显著性检验。

---

#### M5: 风控检查与回测引擎未深度集成

**位置：** `src/backtest_engine/risk_check.py` 和 `engine.py`

`RiskCheck` 类实现了完整的风控规则（单票仓位/行业仓位/回撤/日亏损/黑名单），但 `BacktestEngine._execute_signal` 仅调用 `risk_check.check_order()`，未在以下场景集成：
- 每日开盘前检查持仓风险
- 回撤超限时强制减仓
- 风控拒绝后的日志记录和统计

---

### 低/建议（4 项）

#### L1: 回测引擎以收盘价成交，缺少开盘价/ VWAP 成交选项

当前所有交易以当日收盘价成交，实际交易中更常用开盘价或 VWAP。建议支持多种成交价模式。

#### L2: 缺少回测结果持久化存储

回测结果仅返回字典，未保存到文件或数据库。建议保存到 `data/backtest_results/` 目录。

#### L3: portfolio.py 的持仓成本计算未考虑分红除权

`Portfolio` 类的持仓成本计算仅基于买入价格和手续费，未考虑分红除权对成本的影响。

#### L4: commission_model.py 的印花税仅支持 A 股

当前印花税固定为卖出 0.05%，未区分 A 股和港股（港股印花税不同）。

---

## 三、测试框架完整性评估

### 现有测试层次

```
          ┌─────────────┐
          │  E2E 测试    │  ← ❌ 缺失
          ├─────────────┤
          │  集成测试     │  ← ❌ 缺失
          ├─────────────┤
          │  API 测试    │  ← ❌ 缺失
          ├─────────────┤
          │  单元测试     │  ✅ 190 个
          └─────────────┘
```

### 缺失的测试

#### 1. 集成测试（必须补充）

| 测试场景 | 说明 |
|---------|------|
| 数据→因子→评分→信号→回测 | 全流程集成，验证数据质量对回测结果的影响 |
| 信号生成→回测引擎→绩效报告 | 验证信号能正确驱动回测并生成完整报告 |
| 风控检查→回测引擎 | 验证风控拒绝时交易被正确阻止 |
| 成本模型→组合管理→绩效 | 验证交易成本正确计入绩效 |

#### 2. 端到端测试（必须补充）

| 测试场景 | 说明 |
|---------|------|
| 真实数据端到端回测 | 使用 AkShare 获取 002463 半年数据，运行完整回测 |
| 半导体池全量回测 | 对半导体池所有 A 股标的运行回测 |
| 回测报告生成 | 验证 HTML/可视化报告正确生成 |

#### 3. API/前端测试（必须补充）

| 测试场景 | 说明 |
|---------|------|
| FastAPI 回测端点 | POST /api/backtest/run 提交回测任务 |
| FastAPI 报告端点 | GET /api/backtest/report/{id} 获取回测报告 |
| Streamlit 信号看板 | 验证信号展示页面可访问 |

---

## 四、项目偏离评估

### 是否偏离设计目标约束？

**是的，存在多项偏离：**

| 偏离类型 | 具体表现 | 影响等级 |
|----------|---------|---------|
| 架构偏离 | 缺少 event_backtester 和独立 slippage_model | 严重 |
| 回测真实性偏离 | 涨跌停/停牌无法成交未处理 | 严重 |
| 测试框架偏离 | 仅有单元测试，缺少集成/E2E/API 测试 | 严重 |
| 报告完整性偏离 | 缺少 5/12 项 AGENTS.md 要求的指标 | 中等 |
| 可视化偏离 | 缺少 HTML/图表报告输出 | 中等 |

### 功能是否正常可用？

| 功能 | 状态 | 说明 |
|------|------|------|
| 交易成本计算 | ✅ 正常 | 手续费+印花税+滑点计算正确 |
| 组合管理 | ✅ 正常 | 买入/卖出/持仓/现金管理正确 |
| 绩效指标计算 | ⚠️ 部分可用 | 缺 cost_adjusted_return/benchmark_return/excess_return/monthly/yearly |
| 风控检查 | ✅ 正常 | 5 项风控规则完整 |
| 向量回测引擎 | ⚠️ 部分可用 | 核心流程可用，但涨跌停/停牌未处理 |
| 样本外测试 | ⚠️ 框架可用 | 分割逻辑正确，但缺少统计检验 |
| 市场环境测试 | ⚠️ 框架可用 | 分类逻辑正确，但缺少统计检验 |
| 回测报告可视化 | ❌ 不可用 | 无 HTML/图表输出 |

---

## 五、Phase 3 验收标准复核

| # | 验收标准 | 复核结果 | 说明 |
|---|---------|---------|------|
| 1 | 可以运行日频回测 | ✅ 通过 | BacktestEngine.run() 可用 |
| 2 | 交易成本包含手续费+印花税+滑点 | ✅ 通过 | CommissionModel 完整 |
| 3 | 涨跌停/停牌无法成交 | ❌ 未通过 | 未在回测引擎中实现 |
| 4 | 仓位管理 | ✅ 通过 | Portfolio 类完整 |
| 5 | 回测报告包含全部指标 | ⚠️ 部分通过 | 缺 5/12 项指标 |
| 6 | 样本外测试 | ⚠️ 框架通过 | 缺统计检验 |
| 7 | 不同市场环境测试 | ⚠️ 框架通过 | 缺统计检验 |

---

## 六、改进建议（按优先级排序）

### P0 — 必须修复

| # | 问题 | 修复方案 |
|---|------|---------|
| 1 | 涨跌停/停牌无法成交 | 在 `_execute_signal` 中检查 limit_up/limit_down/is_suspended，涨停拒绝买入、跌停拒绝卖出、停牌拒绝所有交易 |
| 2 | 补齐 5 项绩效指标 | 实现 cost_adjusted_return、benchmark_return、excess_return、monthly_return、yearly_return |
| 3 | 补充集成测试 | 实现数据→因子→信号→回测→报告的全流程集成测试 |
| 4 | 补充端到端测试 | 使用 mock/真实数据运行完整回测流程 |

### P1 — Phase 4 之前补齐

| # | 问题 | 修复方案 |
|---|------|---------|
| 5 | 抽取独立 SlippageModel | 支持固定/百分比/冲击成本滑点策略 |
| 6 | 实现 event_backtester | 逐日事件驱动回测，为 Phase 4 实盘做准备 |
| 7 | 回测报告 HTML 输出 | 使用 Jinja2 模板生成可视化回测报告 |
| 8 | 构建 FastAPI 服务 | 提供回测提交/报告查询/信号查询 API |
| 9 | 构建 Streamlit 前端 | 信号看板、回测报告展示、因子热力图 |
| 10 | API 测试 | 使用 httpx + pytest-asyncio 测试 FastAPI 端点 |

### P2 — 中期优化

| # | 问题 | 修复方案 |
|---|------|---------|
| 11 | 支持多种成交价模式 | 收盘价/开盘价/VWAP 可配置 |
| 12 | 回测结果持久化 | 保存到 data/backtest_results/ |
| 13 | 分红除权处理 | 在组合成本计算中考虑除权 |
| 14 | 港股印花税区分 | CommissionModel 支持 A 股/港股不同税率 |
| 15 | 样本外测试统计检验 | 添加 t 检验/Bootstrap 置信区间 |

---

## 七、测试框架建设路线图

Phase 3 应建立完整的测试金字塔：

```
            ┌──────────────────┐
            │   E2E 测试        │  ← 需新建 tests/e2e/
            │  (真实数据全流程)   │
            ├──────────────────┤
            │   API 测试        │  ← 需新建 tests/api/
            │  (FastAPI 端点)    │
            ├──────────────────┤
            │   集成测试         │  ← 需新建 tests/integration/
            │  (跨模块协作)      │
            ├──────────────────┤
            │   单元测试         │  ✅ 190 个
            │  (函数/类级别)      │
            └──────────────────┘
```

### 建议新增的测试文件

| 文件 | 类型 | 覆盖范围 |
|------|------|---------|
| `tests/integration/test_backtest_pipeline.py` | 集成测试 | 信号→回测→报告全流程 |
| `tests/integration/test_risk_integration.py` | 集成测试 | 风控→回测引擎集成 |
| `tests/e2e/test_full_backtest.py` | 端到端 | 使用真实数据的完整回测 |
| `tests/e2e/test_report_generation.py` | 端到端 | 回测报告 HTML 生成 |
| `tests/api/test_backtest_api.py` | API 测试 | FastAPI 回测端点 |

### 前后端实测建议

1. **后端（FastAPI）：**
   - `POST /api/backtest/run` — 提交回测任务（symbols, start_date, end_date, strategy）
   - `GET /api/backtest/report/{task_id}` — 获取回测报告
   - `GET /api/signals/latest` — 获取最新信号
   - `GET /api/factors/daily` — 获取因子评分

2. **前端（Streamlit）：**
   - 信号看板页面 — 当日买卖信号列表
   - 回测报告页面 — 收益曲线、回撤图、月度收益热力图
   - 因子看板页面 — 因子评分排名、板块轮动图

3. **API 测试框架：**
   - 使用 `httpx.AsyncClient` + `pytest-asyncio`
   - FastAPI `TestClient` 同步测试
   - 覆盖全部端点的正常/异常场景
