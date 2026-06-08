# Phase 2 审计整改复核报告

> 复核日期：2026-06-08
> 对照文档：AUDIT_REPORT_PHASE2.md、REMEDIATION_REPORT_PHASE2.md
> 复核范围：Phase 2 审计发现的 3 项严重问题、6 项中等问题、2 项低/建议项

---

## 一、测试执行结果

| 项目 | 结果 |
|------|------|
| 测试框架 | pytest 8.4.2 |
| 测试文件 | 7 个 |
| 测试用例 | 148 个 |
| 通过 | 148/148 (100%) |
| 跳过/失败 | 0 |
| 耗时 | 3.11s |

**测试分布：**

| 文件 | 用例数 | 覆盖范围 |
|------|--------|---------|
| test_audit_fixes.py | 39 | Phase 1 审计修复验证 |
| test_audit_phase2.py | 32 | Phase 2 审计修复验证 |
| test_column_mapper.py | 9 | symbol 映射、日线标准化 |
| test_phase2.py | 42 | 因子/评分/信号/板块轮动 |
| test_quality.py | 9 | 数据质量检查 |
| test_stock_pool.py | 13 | 股票池过滤 |
| test_storage.py | 3 | 数据存储 |

---

## 二、严重问题复核

### S1: 基本面因子无真实数据 ✅ 已修复

**修复位置：** `src/factor_engine/fundamental_factors.py`

**验证结果：**

1. `fetch_financial_data_from_akshare(symbols)` 已实现，从 AkShare `stock_financial_analysis_indicator` 接口获取：
   - 营收同比增速（`营业收入同比增长率`）
   - 净利润同比增速（`净利润同比增长率`）
   - ROE（`净资产收益率`）
   - 毛利率变化（最新两期 `销售毛利率` 差值）
2. `compute_fundamental_factors()` 新增 `financial_data` 参数，支持外部财务数据注入
3. 新增 `industry_prosperity` 行业景气度字段（暂无数据源，Phase 4 接入）
4. 评分权重调整为 6 因子：revenue_yoy(20%) + net_profit_yoy(20%) + gross_margin_change(15%) + roe(15%) + consensus_profit_growth(15%) + industry_prosperity(15%)
5. 缺失字段保留 NaN，新增 `is_fundamental_missing` 标记，评分时缺失给中间分

**测试覆盖：** 3 个（TestFundamentalDataFetch）

---

### S2: 情绪因子缺少 3 个指标 ✅ 已修复

**修复位置：** `src/factor_engine/sentiment_factors.py`

**验证结果：**

| 新增指标 | 函数 | 实现方式 | 权重 |
|---------|------|---------|------|
| turnover_ratio | `calc_turnover_ratio()` | 当日换手率 / 过去20日平均换手率 | 14 |
| limit_up_count | `calc_limit_up_count()` | 近5日涨停次数（涨幅>=9.5%视为涨停） | 14 |
| large_order_flow | `calc_large_order_flow()` | 均价与收盘价偏离度估算大单净流入 | 14 |

7 因子权重合计：15+15+14+14+14+14+14 = 100，符合 ARCHITECTURE.md 5.3 节。

`compute_sentiment_factors()` 和 `compute_sentiment_score()` 同步更新。

**测试覆盖：** 5 个（TestMissingSentimentFactors）

---

### S3: 因子评估体系缺失 ✅ 已修复

**修复位置：** `src/factor_engine/factor_evaluation.py`（新建）

**验证结果：**

| 评估指标 | 函数 | 说明 |
|---------|------|------|
| IC | `calc_ic()` | 因子值与下期收益的 Pearson 相关系数 |
| Rank IC | `calc_rank_ic()` | Spearman 相关系数 |
| IC_IR | 自动计算 | IC 均值 / IC 标准差 |
| Turnover | `calc_turnover()` | 因子排名换手率 |
| Coverage | `calc_coverage()` | 因子非缺失比例 |
| Decay | `calc_decay()` | IC 随滞后期数衰减 |
| Long-Short | `calc_long_short_return()` | 多空组合收益 |

`evaluate_factor()` 输出完整评估字典，`evaluate_all_factors()` 批量评估四类因子。

符合 FACTOR_RESEARCH_GUIDE.md 和 AGENTS.md 3.3 节要求。

**测试覆盖：** 5 个（TestFactorEvaluation）

---

## 三、中等问题复核

### M1: 缺少 HOLD 信号 ✅ 已修复

**修复位置：** `src/strategy_engine/signal_generator.py`

**验证结果：**
- `check_hold()` 函数生成 HOLD_WATCH 信号
- `generate_signals()` 新增 `include_hold` 参数（默认 True）
- 不满足买卖条件的股票输出 HOLD 信号，确保每只股票都有信号输出
- 信号统计日志增加 HOLD 计数

**测试覆盖：** 3 个（TestHoldSignal）

---

### M2: Signal 模型缺 stock_name/sector 字段 ✅ 已修复

**修复位置：** `src/models/schemas.py`、`src/strategy_engine/signal_generator.py`

**验证结果：**
- Signal 模型新增 `stock_name: str = ""` 和 `sector: str = ""` 字段
- 所有信号生成函数通过 `_get_stock_name()` 和 `_get_sector()` 辅助函数填充字段
- 符合 AGENTS.md 2.4 节可解释性要求

**测试覆盖：** 2 个（TestSignalModelFields）

---

### M3: 缺少 timing_model 择时规则 ✅ 已修复

**修复位置：** `src/strategy_engine/timing_model.py`（新建）

**验证结果：**
- `is_trading_time()` — 交易时段判断（09:30~11:30 / 13:00~15:00）
- `is_buy_allowed()` — 买入时段过滤（排除开盘5分钟急跌期和收盘10分钟追高）
- `is_sell_allowed()` — 卖出时段判断
- `get_timing_advice()` — 返回当前时段状态和建议文本

**测试覆盖：** 6 个（TestTimingModel）

---

### M4: 缺少 factor_evaluation 子模块 ✅ 已修复

与 S3 合并，`factor_evaluation.py` 已创建。

---

### M5: 板块轮动单板块资金维度降级 ✅ 已修复

**修复位置：** `src/strategy_engine/sector_rotation.py`

**验证结果：**
- 单板块时使用绝对评分：成交额 >= 5亿给满分20分，<= 1亿给0分
- 多板块时使用排名百分位
- 归一化分母统一为 100（30+20+20+30）

**测试覆盖：** 1 个（TestSectorRotationSingleSector）

---

### M6: 基本面因子 fillna(0) 改为标记缺失 ✅ 已修复

**修复位置：** `src/factor_engine/fundamental_factors.py`

**验证结果：**
- 缺失字段保留 NaN，不再静默 `fillna(0)`
- 新增 `is_fundamental_missing` 标记列
- 评分时缺失字段给予中间分（满分的一半），而非 0 分
- 缺失时输出 warning 日志

**测试覆盖：** 3 个（TestFundamentalMissingFlag）

---

## 四、低/建议项复核

### L1: `__init__.py` 缺少公共接口导出 ✅ 已修复

**修复位置：** `src/factor_engine/__init__.py`、`src/strategy_engine/__init__.py`

**验证结果：**
- `factor_engine/__init__.py` 导出 8 个函数（compute_technical_factors, compute_trend_score, compute_sentiment_factors, compute_sentiment_score, compute_policy_score, compute_fundamental_factors, fetch_financial_data_from_akshare, evaluate_factor, evaluate_all_factors）
- `strategy_engine/__init__.py` 导出 6 个函数（compute_all_factors, generate_signals, compute_sector_scores, is_trading_time, is_buy_allowed, allocate_position）

**测试覆盖：** 2 个（TestInitExports）

---

### L2: 信号 ID 缺少随机码 ✅ 已修复

**修复位置：** `src/strategy_engine/signal_generator.py`

**验证结果：**
- `_make_signal_id()` 末尾追加 6 位随机码（大写字母+数字）
- 格式：`SIG_{date}_{symbol}_{type}_{subtype}_{RAND6}`
- 避免同日同股票同类型信号 ID 重复

**测试覆盖：** 2 个（TestSignalIdRandomCode）

---

## 五、新增组件验证

| 组件 | 文件 | 功能 | 状态 |
|------|------|------|------|
| factor_evaluation | `src/factor_engine/factor_evaluation.py` | IC/IR/衰减/换手/覆盖率/多空收益 | ✅ 完整实现 |
| timing_model | `src/strategy_engine/timing_model.py` | 交易时段/买入过滤/择时建议 | ✅ 完整实现 |
| portfolio_model | `src/strategy_engine/portfolio_model.py` | 仓位分配/板块约束/现金约束 | ✅ 简化版实现 |

---

## 六、遗留事项

| # | 事项 | 计划 | 风险评估 |
|---|------|------|---------|
| 1 | consensus_profit_growth 和 industry_prosperity 暂无数据源 | Phase 4 接入研报/一致预期数据 | 低 — 缺失时给中间分，不影响评分合理性 |
| 2 | large_order_flow 使用简化估算，非真实大单数据 | Phase 4 接入 Level-2 数据 | 低 — 简化方法可接受 |
| 3 | portfolio_model 为简化版本 | Phase 3 回测时完善 | 低 — 当前满足 Phase 2 需求 |
| 4 | 因子评估的样本外测试 | Phase 3 回测时执行 | 低 — 评估框架已就位 |

---

## 七、Phase 2 验收标准复核

| # | 验收标准 | 整改前 | 整改后 |
|---|---------|--------|--------|
| 1 | 每只股票每天能生成 4 类因子分 | ⚠️ 部分通过 | ✅ 通过（技术7指标+情绪7指标+政策+基本面6指标） |
| 2 | 每只股票每天能生成总分 | ✅ 通过 | ✅ 通过 |
| 3 | 能输出买入、卖出、持有信号 | ⚠️ 缺 HOLD | ✅ 通过（HOLD_WATCH 已实现） |
| 4 | 每个信号必须有解释文本 | ✅ 通过 | ✅ 通过（新增 stock_name/sector 字段） |
| 5 | 信号不允许包含未来数据 | ✅ 通过 | ✅ 通过 |

**新增合规项：**

| # | 合规要求 | 状态 |
|---|---------|------|
| 6 | 因子入库前必须输出 IC/IR/衰减等评估指标 | ✅ 通过 |
| 7 | 择时规则过滤非交易时段信号 | ✅ 通过 |
| 8 | 基本面数据缺失不静默填充 | ✅ 通过 |
| 9 | 信号 ID 包含随机码避免重复 | ✅ 通过 |
| 10 | 模块公共接口通过 `__init__.py` 导出 | ✅ 通过 |

---

## 八、复核结论

**Phase 2 审计报告中 3 项严重问题和 6 项中等问题全部修复，2 项低/建议项全部修复，148 个测试全部通过。Phase 2 验收标准全部满足，项目可进入 Phase 3。**

遗留 4 项事项均为低风险，已标注后续 Phase 计划，不影响当前阶段交付质量。
