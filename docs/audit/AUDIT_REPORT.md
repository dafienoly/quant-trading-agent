# Phase 1 & Phase 2 审计与测试报告

> 审计日期：2026-06-08
> 审计范围：Phase 1（数据层与股票池）、Phase 2（因子与策略评分）
> 对照文档：ROADMAP_AND_CONSTRAINTS.md、AGENTS.md、ARCHITECTURE.md、DATA_CONTRACTS.md、EXECUTION_POLICY.md、FACTOR_RESEARCH_GUIDE.md、RISK_POLICY.md

---

## 一、测试执行结果

| 项目 | 结果 |
|------|------|
| 测试框架 | pytest 8.4.2 |
| 测试文件 | 4 个 |
| 测试用例 | 35 个 |
| 通过 | 35/35 (100%) |
| 跳过/失败 | 0 |
| 耗时 | 2.94s |

**测试分布：**

| 文件 | 用例数 | 覆盖范围 |
|------|--------|---------|
| test_column_mapper.py | 9 | symbol 映射、日线标准化、pre_close 计算、停牌检测 |
| test_stock_pool.py | 13 | 主板判断、排除判断、港股、ST 检测、半导体池 |
| test_quality.py | 9 | 完整性检查、价格有效性、涨跌停检测、连续性 |
| test_storage.py | 3 | 保存加载、不存在处理、日期过滤 |

**测试盲区：**

- ❌ TradeCalendar 单元测试缺失
- ❌ Provider 集成测试缺失（需 mock AkShare API）
- ❌ fetch_daily_data.py 脚本测试缺失
- ❌ 涨跌停幅度区分测试缺失（创业板20%/ST5%）
- ❌ is_st 字段获取测试缺失

---

## 二、Phase 1 审计发现

### 严重问题（5 项）

#### S1: 涨跌停价计算统一用 10%，未区分创业板 20%/ST 5%

**位置：** `src/data_gateway/column_mapper.py:108-109`

```python
# 当前实现 — 统一 10%
result["limit_up"] = (result["pre_close"] * 1.10).round(2)
result["limit_down"] = (result["pre_close"] * 0.90).round(2)
```

**问题：** 创业板(300xxx/301xxx)和科创板(688xxx/689xxx)涨跌停幅度为 20%，ST 股为 5%。当前统一按 10% 计算，将导致：
- 创业板/科创板股票的涨跌停价偏低，回测中可能错误判断为涨停无法买入
- ST 股的涨跌停价偏高，回测中可能错误允许交易

**违反文档：** DATA_CONTRACTS.md 2.4 节、RISK_POLICY.md 4.1 节

**修复方案：** 根据 symbol 前缀和 is_st 字段区分涨跌停幅度

```python
def _calc_limit(pre_close, symbol_raw, is_st):
    code = symbol_raw.split(".")[0] if "." in symbol_raw else symbol_raw
    if is_st:
        rate = 0.05
    elif code.startswith(("300", "301", "688", "689")):
        rate = 0.20
    else:
        rate = 0.10
    return round(pre_close * (1 + rate), 2), round(pre_close * (1 - rate), 2)
```

---

#### S2: is_st 硬编码为 False，未从数据源获取

**位置：** `src/data_gateway/column_mapper.py:113`

```python
result["is_st"] = False  # 始终为 False
```

**问题：** ST 标记是风控的关键输入。RISK_POLICY.md 4.2 节明确将 ST 股列入黑名单，禁止买入。is_st 始终为 False 意味着：
- 无法在数据层面识别 ST 股票
- 风控模块无法自动拦截 ST 股交易
- 涨跌停价计算无法区分 ST 5% 幅度

**违反文档：** DATA_CONTRACTS.md 1.1 节、AGENTS.md 3.2 节、RISK_POLICY.md 4.2 节

**修复方案：**
1. 在 `map_daily_bars` 中增加股票名称参数，通过名称匹配 ST
2. 或在 `AkShareProvider.get_daily_bars` 中先获取股票信息，合并 ST 状态
3. 或在 `map_stock_list` 中保留 ST 标记，后续关联

---

#### S3: filter_tradeable() 未集成成交额/上市日期/停牌过滤

**位置：** `src/stock_pool/mainboard_filter.py:68-72`

```python
def filter_tradeable(stock_list, min_amount=1e8) -> pd.DataFrame:
    result = filter_mainboard(stock_list)
    return result  # 仅调用了 filter_mainboard，未调用 filter_by_volume
```

**问题：** ROADMAP Phase 1 股票池规则明确要求排除：
- 上市不足 120 个交易日的股票 — **未实现**
- 日成交额低于 1 亿元的股票 — `filter_by_volume` 已实现但未集成
- 停牌股票 — **未实现**

`filter_by_volume` 函数已存在（第 59-65 行）但 `filter_tradeable` 未调用它。

**违反文档：** ROADMAP Phase 1 股票池规则、RISK_POLICY.md 4.1 节

**修复方案：**
1. 在 `filter_tradeable` 中调用 `filter_by_volume`
2. 新增上市日期过滤（需获取 list_date 字段）
3. 新增停牌过滤（需获取 is_suspended 状态）

---

#### S4: volume/amount 静默 fillna(0)，违反禁止静默填充规则

**位置：** `src/data_gateway/column_mapper.py:93-94`

```python
result["volume"] = pd.to_numeric(result.get("volume", 0), errors="coerce").fillna(0).astype(int)
result["amount"] = pd.to_numeric(result.get("amount", 0), errors="coerce").fillna(0.0)
```

**问题：** DATA_CONTRACTS.md 2.1 节规定"非关键字段缺失时，必须保留 NaN，不得静默填充"。AGENTS.md 3.2 节禁止"静默使用缺失数据"。volume 和 amount 是关键字段，缺失时填充为 0 会：
- 将缺失数据伪装成零成交（与停牌混淆）
- 导致 is_suspended 判断错误（volume=0 被判定为停牌）
- 影响后续因子计算（成交量比率等）

**违反文档：** DATA_CONTRACTS.md 2.1 节、AGENTS.md 3.2 节

**修复方案：**
1. 关键字段缺失时保留 NaN
2. 新增 `is_data_missing` 标记列
3. 在质量报告中统计缺失行数

---

#### S5: 缺少 IntradayBar/RealtimeQuote/Order 模型定义

**位置：** `src/models/schemas.py`

**问题：** DATA_CONTRACTS.md 定义了完整的数据契约，但当前仅实现了 DailyBar、StockInfo、DataQualityReport、Signal 四个模型。缺失：

| 模型 | DATA_CONTRACTS 章节 | Phase 需求 |
|------|---------------------|-----------|
| IntradayBar | 1.2 节 | Phase 4 实盘盯盘 |
| RealtimeQuote | 1.3 节 | Phase 4 实盘盯盘 |
| Order | 5 节 | Phase 5 人工确认交易 |

**违反文档：** DATA_CONTRACTS.md 1.2/1.3/5 节

**修复方案：** 在 schemas.py 中补充模型定义，字段严格对照 DATA_CONTRACTS.md

---

### 中等问题（8 项）

#### M1: StockInfo 缺少 5 个字段

**位置：** `src/models/schemas.py:29-35`

当前 StockInfo 仅有 symbol, name, market, board_type, is_st, list_date。缺少：

| 缺失字段 | DATA_CONTRACTS 要求 |
|----------|---------------------|
| industry_sw | 申万一级行业 |
| industry_sw_detail | 申万二级行业 |
| total_shares | 总股本 |
| float_shares | 流通股本 |
| is_hs300 | 是否沪深300成分 |

**违反文档：** DATA_CONTRACTS.md 1.4 节

---

#### M2: MarketDataProvider 缺少 3 个接口方法

**位置：** `src/data_gateway/base.py`

DATA_CONTRACTS.md 定义了 4 个 Provider 接口，当前 MarketDataProvider 仅覆盖：

| 接口 | 状态 |
|------|------|
| DailyBarProvider | ✅ 已实现 |
| IntradayBarProvider | ❌ 未实现 |
| RealtimeQuoteProvider | ❌ 仅抛 NotImplementedError |
| ReferenceDataProvider | ❌ get_stock_list 字段不全 |

**违反文档：** DATA_CONTRACTS.md 1.2/1.3/1.4 节

---

#### M3: cleaned 数据无 data_version 列

**位置：** `src/utils/storage.py:28-34`

DATA_CONTRACTS.md 6 节要求"cleaned 保留清洗后数据，新增 data_version 列"。当前 `save_cleaned_data` 直接保存 DataFrame，未添加版本信息。

---

#### M4: raw 数据按 symbol 分文件，未按日期分区

**位置：** `src/utils/storage.py:19-25`

DATA_CONTRACTS.md 6 节要求"raw 保留原始数据，按日期分区"。当前按 `{code}_daily_raw.csv` 分文件，未按日期分区。

---

#### M5: 数据更新不自动触发质量报告

**位置：** `src/utils/storage.py`

DATA_CONTRACTS.md 6 节要求"数据更新必须触发 data_quality_report 自动生成"。当前质量报告需在 `fetch_daily_data.py` 中手动调用 `generate_quality_report()`，存储层无自动触发机制。

---

#### M6: 缺少 data_missing_report 和 data_delay_report

**位置：** 无对应实现

AGENTS.md 3.2 节要求 Data Agent 必须输出：
- ✅ data_quality_report — 已实现
- ❌ data_missing_report — 未实现
- ❌ data_delay_report — 未实现

---

#### M7: 缺少 config/settings.py 配置管理模块

**位置：** `src/config/` 为空目录

.env.example 定义了风控参数、交易模式、回测参数等配置，但无代码加载和验证这些配置。python-dotenv 已声明依赖但未集成。

**违反文档：** EXECUTION_POLICY.md 2 节

---

#### M8: memory_hbm 板块缺少 000021（深科技）

**位置：** `config/stock_pool.yaml:76-83`

ARCHITECTURE.md 4.2 节定义存储/HBM 板块包含 603986、000021、600667 三只股票，但 stock_pool.yaml 中 memory_hbm 仅有 603986 和 600667，缺少 000021（深科技）。

注：000021 已在 advanced_packaging 板块中存在，属于跨板块重复。需确认是否应同时出现在两个板块。

---

### 低/建议（4 项）

#### L1: stock_pool 模块位置偏离 ARCHITECTURE.md 设计

ARCHITECTURE.md 定义 stock_pool 在 `strategy_engine/stock_pool/` 下，实际在 `src/stock_pool/`。

**建议：** 可保持当前位置，但需更新 ARCHITECTURE.md 以反映实际结构。

#### L2: calendar/quality/storage 模块位置偏离

ARCHITECTURE.md 定义 calendar_data 在 `data_gateway/calendar_data/` 下，实际在 `src/utils/`。

**建议：** 同 L1，可保持但需更新文档。

#### L3: 使用 CSV 存储而非 DuckDB

pyproject.toml 声明了 `duckdb>=0.9` 依赖，但实际使用 CSV 文件存储。

**建议：** 初期 CSV 可接受，中期需迁移到 DuckDB 以提升查询性能。

#### L4: 缺少 data_storage 独立子模块

ARCHITECTURE.md 定义了 `data_storage` 子模块（raw/cleaned/feature_store/signal_store），当前存储逻辑散布在 `src/utils/storage.py`。

**建议：** 可在后续 Phase 补齐独立模块。

---

## 三、Phase 2 状态评估

**Phase 2（因子与策略评分）完全未实现。**

| 模块 | 状态 |
|------|------|
| factor_engine/ | 空壳（仅 `__init__.py`） |
| strategy_engine/ | 空壳（仅 `__init__.py`） |

ROADMAP Phase 2 要求的 8 项任务均未开始：

| # | 任务 | 状态 |
|---|------|------|
| 1 | 实现政策主题分 (policy_score) | ❌ |
| 2 | 实现情绪资金分 (sentiment_score) | ❌ |
| 3 | 实现基本面分 (fundamental_score) | ❌ |
| 4 | 实现技术趋势分 (trend_score) | ❌ |
| 5 | 实现总评分 (total_score) | ❌ |
| 6 | 实现买入信号 (BREAKOUT/PULLBACK/AMBUSH) | ❌ |
| 7 | 实现卖出信号 (STOP_LOSS/TREND_BREAK/SENTIMENT_FADE/TAKE_PROFIT) | ❌ |
| 8 | 实现板块轮动评分 | ❌ |

---

## 四、项目偏离评估

### 是否偏离设计目标约束？

**是的，存在多项偏离：**

| 偏离类型 | 具体表现 | 影响等级 |
|----------|---------|---------|
| 数据契约偏离 | DATA_CONTRACTS 定义 4 个 Provider，仅实现 1 个 | 严重 |
| 风控合规偏离 | 涨跌停计算不准确，ST 标记缺失 | 严重 |
| 股票池规则偏离 | 过滤不完整，可能纳入不应交易的股票 | 严重 |
| 数据质量偏离 | 静默 fillna(0) 违反禁止项 | 严重 |
| 架构偏离 | 模块位置与 ARCHITECTURE.md 不一致 | 低 |
| 配置管理偏离 | .env 配置无代码加载 | 中等 |

### 功能是否正常可用？

| 功能 | 状态 | 说明 |
|------|------|------|
| 日线数据获取 | ✅ 正常 | AkShare/AkTools 双通道可用 |
| 交易日历 | ✅ 正常 | 支持缓存/区间查询/前后交易日 |
| 基础股票池过滤 | ✅ 正常 | 主板/中小板/港股/ST 过滤可用 |
| 数据质量报告 | ✅ 正常 | 完整性/价格/涨跌停/停牌检查可用 |
| 数据存储 | ✅ 正常 | raw/cleaned 分离存储可用 |
| 涨跌停价计算 | ⚠️ 不准确 | 统一 10%，未区分 20%/5% |
| ST 标记 | ⚠️ 不可用 | 始终为 False |
| 完整股票池过滤 | ⚠️ 不完整 | 缺成交额/上市日期/停牌过滤 |

---

## 五、改进建议（按优先级排序）

### P0 — 必须在 Phase 2 之前修复

| # | 问题 | 修复位置 | 修复方案 |
|---|------|---------|---------|
| 1 | 涨跌停价计算不准确 | `column_mapper.py:108-109` | 根据 symbol 前缀区分 10%/20%，根据 is_st 区分 5% |
| 2 | is_st 硬编码 False | `column_mapper.py:113` | 从股票名称匹配 ST 或从 AkShare 获取 |
| 3 | filter_tradeable 不完整 | `mainboard_filter.py:68-72` | 集成 filter_by_volume + 上市日期过滤 + 停牌过滤 |
| 4 | volume/amount 静默填充 | `column_mapper.py:93-94` | 缺失时保留 NaN，新增 is_data_missing 标记 |

### P1 — Phase 2 开发中补齐

| # | 问题 | 修复位置 |
|---|------|---------|
| 5 | 补齐 IntradayBar/RealtimeQuote/Order 模型 | `schemas.py` |
| 6 | 补齐 StockInfo 缺失字段 | `schemas.py` |
| 7 | 补齐 MarketDataProvider 缺失接口 | `base.py` |
| 8 | 实现 config/settings.py | `src/config/settings.py` |
| 9 | 补齐 data_missing_report 和 data_delay_report | `src/utils/` |
| 10 | 补齐 memory_hbm 中的 000021 | `config/stock_pool.yaml` |

### P2 — 中期优化

| # | 问题 | 修复位置 |
|---|------|---------|
| 11 | cleaned 数据添加 data_version 列 | `storage.py` |
| 12 | raw 数据改为按日期分区 | `storage.py` |
| 13 | 存储迁移到 DuckDB | `storage.py` |
| 14 | 数据更新自动触发质量报告 | `storage.py` |
| 15 | 更新 ARCHITECTURE.md 反映实际模块位置 | `ARCHITECTURE.md` |

---

## 六、Phase 1 验收标准复核

| # | 验收标准 | 状态 | 说明 |
|---|---------|------|------|
| 1 | 可以拉取指定股票日线数据 | ✅ 通过 | AkShare/AkTools 双通道 |
| 2 | 可以拉取指数数据 | ✅ 通过 | 上证/沪深300/创业板指 |
| 3 | 可以生成可交易股票池 | ⚠️ 部分通过 | 过滤不完整，缺成交额/上市日期/停牌 |
| 4 | 可以输出数据质量报告 | ✅ 通过 | DataQualityReport 完整 |
| 5 | 可以识别停牌、ST、涨跌停 | ⚠️ 部分通过 | 停牌识别依赖 volume=0（与缺失混淆）；ST 硬编码 False；涨跌停幅度不区分 |

**Phase 1 验收结论：** 基本功能可用，但存在 5 项严重问题和 8 项中等问题需修复后方可进入 Phase 2。
