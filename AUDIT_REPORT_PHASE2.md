# Phase 2 审计与测试报告

> 审计日期：2026-06-08
> 审计范围：Phase 2（因子与策略评分）
> 对照文档：ROADMAP_AND_CONSTRAINTS.md、AGENTS.md、ARCHITECTURE.md、DATA_CONTRACTS.md、FACTOR_RESEARCH_GUIDE.md

---

## 一、测试执行结果

| 项目 | 结果 |
|------|------|
| 测试框架 | pytest 8.4.2 |
| 测试文件 | 6 个 |
| 测试用例 | 116 个 |
| 通过 | 116/116 (100%) |
| 跳过/失败 | 0 |
| 耗时 | 4.03s |

**Phase 2 专项测试：** `test_phase2.py` 含 42 个用例，覆盖技术因子(7)、情绪因子(4)、政策因子(3)、基本面因子(3)、总评分(4)、买入信号(5)、卖出信号(6)、信号生成器(4)、板块轮动(2)、验收标准(4)。

---

## 二、Phase 2 合规性审计

### 严重问题（3 项）

#### S1: 基本面因子全部使用中性值 0，无真实数据接入

**位置：** `src/factor_engine/fundamental_factors.py:46-51`

```python
# 缺失则填充中性值0
for col in ["revenue_yoy", "net_profit_yoy", "gross_margin_change", "roe", "consensus_profit_growth"]:
    if col not in result.columns:
        result[col] = 0.0
    else:
        result[col] = result[col].fillna(0.0)
```

**问题：** ARCHITECTURE.md 5.4 节定义了 6 个基本面指标（含 `industry_prosperity`），当前仅实现 5 个且全部默认为 0。`compute_fundamental_factors` 不从任何数据源获取财务数据，仅做字段填充。这意味着：
- 基本面分始终为中间偏低水平（约 33.3 分，5 个指标各 0 分时）
- 总评分中 20% 权重的基本面分无区分度
- BUY_AMBUSH 信号要求 `fundamental_score >= 60`，但无真实数据时几乎不可能满足

**违反文档：** ARCHITECTURE.md 5.4 节、FACTOR_RESEARCH_GUIDE.md 因子数据源要求

**修复方案：** 从 AkShare 接入财务数据（`ak.stock_financial_analysis_indicator`、`ak.stock_profit_sheet` 等）

---

#### S2: 情绪因子缺少 ARCHITECTURE.md 定义的 3 个指标

**位置：** `src/factor_engine/sentiment_factors.py`

ARCHITECTURE.md 5.3 节定义了 7 个情绪资金指标：

| 指标 | ARCHITECTURE 要求 | 实现状态 |
|------|-------------------|---------|
| volume_ratio | ✅ | ✅ 已实现 |
| amount_ratio | ✅ | ✅ 已实现 |
| turnover_ratio | ✅ | ❌ 未实现 |
| relative_strength | ✅ | ✅ 已实现 |
| sector_strength | ✅ | ✅ 已实现 |
| limit_up_count | ✅ | ❌ 未实现 |
| large_order_flow | ✅ | ❌ 未实现 |

**影响：** 情绪资金分权重 30%（四因子中最高），但仅实现 4/7 指标，评分区分度不足。

---

#### S3: 缺少因子评估体系（IC/IR/衰减分析）

**位置：** 无对应实现

FACTOR_RESEARCH_GUIDE.md 要求每个因子入库前必须输出：
- `ic_mean`, `ic_std`, `ic_ir`
- `rank_ic_mean`
- `turnover`, `coverage`
- `decay_analysis`
- `long_short_return`

AGENTS.md 3.3 节 Factor Research Agent 必须输出上述指标。当前完全缺失因子评估模块。

**违反文档：** FACTOR_RESEARCH_GUIDE.md 全文、AGENTS.md 3.3 节

---

### 中等问题（6 项）

#### M1: 信号生成器缺少 HOLD 信号

**位置：** `src/strategy_engine/signal_generator.py:418-466`

ROADMAP Phase 2 验收标准 3 要求"能输出买入、卖出、**持有**信号"，但 `generate_signals` 仅生成 BUY 和 SELL 信号。当股票不满足任何买卖条件时，无 HOLD 信号输出。

**违反文档：** ROADMAP Phase 2 验收标准 3

---

#### M2: 信号缺少 AGENTS.md 2.4 节要求的多个解释字段

**位置：** `src/strategy_engine/signal_generator.py`

AGENTS.md 2.4 节要求每个信号必须输出 13 项信息。当前 Signal 模型缺少：

| 缺失字段 | AGENTS.md 要求 |
|----------|---------------|
| 股票名称 | ✅ 必须 |
| 所属板块 | ✅ 必须 |
| 买入理由/卖出理由 | ✅ 必须（当前 reason 合并了） |
| 仓位建议 | ✅ 有（position_pct） |

Signal 模型有 `reason` 和 `risk_note`，但缺少 `stock_name`、`sector` 独立字段。

---

#### M3: ARCHITECTURE.md 定义了 timing_model 和 portfolio_model 但未实现

**位置：** `src/strategy_engine/` 目录

ARCHITECTURE.md 2 节定义 strategy_engine 包含：
- `stock_pool` → 实际在 `src/stock_pool/`（Phase 1 已知偏离）
- `scoring_model` → ✅ 已实现
- `timing_model` → ❌ 未实现
- `portfolio_model` → ❌ 未实现
- `signal_generator` → ✅ 已实现

`timing_model`（择时规则）和 `portfolio_model`（组合管理）是 Phase 2 应有的组件。

---

#### M4: factor_engine 缺少 factor_evaluation 子模块

**位置：** `src/factor_engine/` 目录

ARCHITECTURE.md 2 节定义 factor_engine 包含 `factor_evaluation` 子模块，当前未实现。这与 S3 问题一致，因子评估体系完全缺失。

---

#### M5: 板块轮动评分资金维度在单板块时自动降级，缺少完整实现

**位置：** `src/strategy_engine/sector_rotation.py:94-100`

```python
if len(result_df) > 1:
    result_df["amount_rank_pct"] = result_df["total_amount"].rank(pct=True)
    result_df["sector_score"] = result_df["sector_score"] + result_df["amount_rank_pct"] * 20
```

单板块时资金维度评分为 0，导致评分偏低。ARCHITECTURE.md 定义资金维度占 20% 权重，但单板块时完全丢失。

---

#### M6: 基本面因子 fillna(0) 违反数据质量原则

**位置：** `src/factor_engine/fundamental_factors.py:50`

```python
result[col] = result[col].fillna(0.0)
```

Phase 1 审计已修复了 volume/amount 的静默填充问题，但基本面因子仍在静默 fillna(0)。缺失数据应标记而非填充为中性值。

---

### 低/建议（4 项）

#### L1: factor_engine 和 strategy_engine 的 `__init__.py` 为空

两个模块的 `__init__.py` 均为空文件，未导出公共接口。建议添加统一导出。

#### L2: 信号 ID 格式不含随机码，可能重复

**位置：** `signal_generator.py:33`

```python
return f"SIG_{trade_date}_{symbol.replace('.', '')}_{signal_type}_{sub_type}"
```

同一股票同日同类型信号会生成相同 ID。DATA_CONTRACTS.md 5 节要求 order_id 格式含随机码，signal_id 也应类似。

#### L3: 测试仅使用随机数据，未使用真实行情数据验证

`test_phase2.py` 使用 `np.random.seed(42)` 生成随机价格数据，未验证因子在真实行情下的计算正确性。

#### L4: 缺少端到端集成测试

当前测试全部为单元测试，缺少从"数据获取 → 因子计算 → 评分 → 信号生成"的端到端集成测试。

---

## 三、测试框架完整性评估

### 现有测试层次

| 层次 | 状态 | 说明 |
|------|------|------|
| 单元测试 | ✅ 已有 | 116 个用例覆盖 Phase 1+2 |
| 集成测试 | ❌ 缺失 | 无跨模块集成测试 |
| 端到端测试 | ❌ 缺失 | 无从数据到信号的完整流程测试 |
| API/前端测试 | ❌ 缺失 | 无 Web 服务或前端界面 |
| 性能测试 | ❌ 缺失 | 无大数据量因子计算性能验证 |

### 缺失的测试类型

#### 1. 集成测试（应补充）

| 测试场景 | 说明 |
|---------|------|
| 数据获取→因子计算 | 验证 AkShare 数据经 column_mapper 后能正确输入因子引擎 |
| 因子计算→评分 | 验证四类因子评分的端到端计算 |
| 评分→信号生成 | 验证评分结果能正确触发买卖信号 |
| 全流程 | fetch_daily_data → compute_all_factors → generate_signals |

#### 2. 端到端测试（应补充）

| 测试场景 | 说明 |
|---------|------|
| 真实数据端到端 | 使用 AkShare 获取 002463 真实行情，计算因子并生成信号 |
| 多股票并发 | 验证半导体池全部股票的因子计算和信号生成 |
| 边界条件 | 停牌日、涨跌停日、上市首日的因子计算 |

#### 3. Web 服务/API 测试（Phase 2 应有但缺失）

ARCHITECTURE.md 10.1 节技术栈建议包含 **FastAPI** 和 **Streamlit**，但当前无任何 Web 服务实现。Phase 2 应至少提供：
- REST API 用于查询因子评分和信号
- 简单的 Web 前端展示信号列表

---

## 四、项目偏离评估

### 是否偏离设计目标约束？

**是的，存在多项偏离：**

| 偏离类型 | 具体表现 | 影响等级 |
|----------|---------|---------|
| 因子完整性偏离 | 情绪因子仅实现 4/7，基本面无真实数据 | 严重 |
| 因子评估缺失 | FACTOR_RESEARCH_GUIDE 要求的 IC/IR/衰减分析完全缺失 | 严重 |
| 信号完整性偏离 | 缺少 HOLD 信号 | 中等 |
| 架构偏离 | timing_model/portfolio_model/factor_evaluation 未实现 | 中等 |
| 测试框架偏离 | 仅有单元测试，缺少集成/端到端/API 测试 | 中等 |

### 功能是否正常可用？

| 功能 | 状态 | 说明 |
|------|------|------|
| 技术趋势因子计算 | ✅ 正常 | MA/ATR/量价突破等计算正确 |
| 情绪资金因子计算 | ⚠️ 部分可用 | 缺少 turnover_ratio/limit_up_count/large_order_flow |
| 政策主题因子计算 | ✅ 正常 | 从 YAML 读取权重，映射正确 |
| 基本面因子计算 | ⚠️ 不可用 | 全部默认 0，无真实数据 |
| 总评分计算 | ⚠️ 部分可用 | 公式正确但基本面分无区分度 |
| 买入信号生成 | ⚠️ 部分可用 | BREAKOUT/PULLBACK 可用，AMBUSH 因基本面数据缺失难以触发 |
| 卖出信号生成 | ✅ 正常 | 止损/趋势破坏/情绪退潮/止盈逻辑正确 |
| 板块轮动评分 | ⚠️ 部分可用 | 单板块时资金维度缺失 |
| 因子评估 | ❌ 不可用 | 完全缺失 |

---

## 五、Phase 2 验收标准复核

| # | 验收标准 | 复核结果 | 说明 |
|---|---------|---------|------|
| 1 | 每只股票每天能生成4类因子分 | ⚠️ 部分通过 | 4类评分均有输出，但基本面分无真实数据 |
| 2 | 每只股票每天能生成总分 | ✅ 通过 | 公式正确，范围 0~100 |
| 3 | 能输出买入、卖出、持有信号 | ⚠️ 部分通过 | 缺少 HOLD 信号 |
| 4 | 每个信号必须有解释文本 | ✅ 通过 | reason + risk_note 均有 |
| 5 | 信号不允许包含未来数据 | ✅ 通过 | rolling/shift(1) 无前瞻 |

---

## 六、改进建议（按优先级排序）

### P0 — 必须修复

| # | 问题 | 修复方案 |
|---|------|---------|
| 1 | 基本面因子无真实数据 | 从 AkShare 接入 `stock_financial_analysis_indicator` 等财务数据接口 |
| 2 | 缺少因子评估体系 | 实现 factor_evaluation 模块，计算 IC/IR/衰减/换手率 |
| 3 | 补充缺失的情绪因子 | 实现 turnover_ratio、limit_up_count、large_order_flow |

### P1 — Phase 3 之前补齐

| # | 问题 | 修复方案 |
|---|------|---------|
| 4 | 补充 HOLD 信号 | 在 generate_signals 中对不满足买卖条件的股票输出 HOLD 信号 |
| 5 | 补充集成测试 | 实现数据→因子→评分→信号的端到端测试 |
| 6 | 补充 timing_model | 实现择时规则（盘中买入时间规则） |
| 7 | 修复基本面 fillna(0) | 缺失时标记 is_fundamental_missing 而非静默填充 |
| 8 | Signal 模型补充字段 | 添加 stock_name、sector 独立字段 |

### P2 — 中期优化

| # | 问题 | 修复方案 |
|---|------|---------|
| 9 | 实现 portfolio_model | 组合管理、仓位分配、板块约束 |
| 10 | 构建 FastAPI 服务 | 提供因子查询和信号查询 API |
| 11 | 构建 Streamlit 前端 | 信号展示、因子看板、板块轮动图 |
| 12 | 信号 ID 添加随机码 | 避免同日同股信号 ID 重复 |
| 13 | 模块 `__init__.py` 统一导出 | 提升代码可导入性 |

---

## 七、测试框架建设建议

Phase 2 应建立完整的测试金字塔，当前仅有底层单元测试：

```
        ┌─────────────┐
        │  E2E 测试    │  ← 缺失：真实数据全流程验证
        ├─────────────┤
        │  集成测试     │  ← 缺失：跨模块协作验证
        ├─────────────┤
        │  API 测试    │  ← 缺失：FastAPI 端点验证
        ├─────────────┤
        │  单元测试     │  ✅ 116 个用例
        └─────────────┘
```

### 建议补充的测试文件

| 文件 | 类型 | 覆盖范围 |
|------|------|---------|
| `tests/integration/test_factor_pipeline.py` | 集成测试 | 数据获取→因子计算→评分全流程 |
| `tests/integration/test_signal_pipeline.py` | 集成测试 | 评分→信号生成→Signal 模型验证 |
| `tests/e2e/test_daily_signal_flow.py` | 端到端 | 使用 mock AkShare 数据的完整日频流程 |
| `tests/api/test_factor_api.py` | API 测试 | FastAPI 因子查询端点 |
| `tests/api/test_signal_api.py` | API 测试 | FastAPI 信号查询端点 |

### 前后端实测建议

1. **后端：** 使用 FastAPI 搭建 REST API，提供 `/factors/daily`、`/signals/latest`、`/sectors/rotation` 端点
2. **前端：** 使用 Streamlit 构建信号看板，展示当日信号列表、因子评分热力图、板块轮动排名
3. **API 测试：** 使用 `httpx` + `pytest-asyncio` 对 FastAPI 端点进行自动化测试
4. **前端测试：** 使用 Playwright 对 Streamlit 页面进行截图对比测试
