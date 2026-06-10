# 开发记录文档 (DEVELOPMENT_LOG.md)

> 本文档记录 quant-trading-agent 项目从 Phase 0 到 Phase 3 的完整开发历程，
> 供第三方团队了解项目背景、架构决策、实现细节和已知问题，便于协作开发。

---

## 一、项目概述

### 1.1 项目名称

quant-trading-agent — A股+港股通量化交易Agent系统

### 1.2 项目目标

构建一个面向 A股主板/中小板 + 港股通的量化交易 Agent 系统，聚焦半导体方向，逐步实现：

1. 量化因子挖掘与评估
2. 历史行情数据接入
3. 回测与组合评估
4. 实盘行情监听与信号生成
5. 人工确认下单
6. 风控约束下的半自动/自动交易

### 1.3 核心原则

> **先研究，后回测；先模拟，后实盘；先人工确认，后自动执行；先风控，后收益。**

- 默认交易模式：`LEVEL_1_SIGNAL_ONLY`（仅生成信号，不下单）
- 禁止创业板(300xxx/301xxx)、科创板(688xxx/689xxx)
- 禁止融资融券
- 单票仓位 ≤15%，板块仓位 ≤60%，现金 ≥20%

### 1.4 技术栈

| 类别 | 技术 |
|------|------|
| 语言 | Python 3.10+ |
| 数据源 | AkShare / AkTools HTTP API |
| 数据处理 | pandas, numpy |
| 数据模型 | pydantic v2 |
| 数据存储 | CSV (raw/cleaned 分离) |
| 配置管理 | pyyaml, python-dotenv |
| 测试 | pytest, pytest-cov |
| 代码规范 | ruff |
| 日志 | loguru |
| 数据库 | duckdb (预留) |

---

## 二、项目架构

### 2.1 系统分层

```
数据层 (data_gateway)
  ↓
特征与因子层 (factor_engine)
  ↓
策略层 (strategy_engine)
  ↓
回测层 (backtest_engine)
  ↓
信号层 (strategy_engine/signal_generator)
  ↓
风控层 (risk_engine)
  ↓
执行层 (execution_engine)
  ↓
报告层 (ui_report)
```

### 2.2 目录结构

```
quant-trading-agent/
├── AGENTS.md                    # Agent 角色定义与开发规则
├── ARCHITECTURE.md              # 系统架构设计
├── ROADMAP_AND_CONSTRAINTS.md   # 路线图与约束
├── DATA_CONTRACTS.md            # 数据接口契约
├── RISK_POLICY.md               # 风控策略
├── EXECUTION_POLICY.md          # 执行策略
├── FACTOR_RESEARCH_GUIDE.md     # 因子研究指南
├── PHASE_COMPLETION_REPORT.md   # 阶段完成报告
├── pyproject.toml               # 项目配置
├── .env.example                 # 环境变量模板
├── .gitignore                   # Git 忽略规则
├── config/
│   └── stock_pool.yaml          # 半导体股票池配置
├── scripts/
│   ├── fetch_daily_data.py      # 数据获取脚本
│   └── run_backtest.py          # 回测运行脚本
├── src/
│   ├── __init__.py
│   ├── data_gateway/            # 数据层
│   │   ├── base.py              # MarketDataProvider 抽象基类
│   │   ├── akshare_provider.py  # AkShare 直接调用实现
│   │   ├── aktools_provider.py  # AkTools HTTP API 实现
│   │   └── column_mapper.py     # 中文列名→标准英文映射
│   ├── factor_engine/           # 因子层
│   │   ├── technical_factors.py # 技术趋势因子
│   │   ├── sentiment_factors.py # 情绪资金因子
│   │   ├── theme_factors.py     # 政策主题因子
│   │   ├── fundamental_factors.py # 基本面因子
│   │   └── factor_evaluation.py # 因子评估 (IC/IR/Decay/LongShort)
│   ├── strategy_engine/         # 策略层
│   │   ├── scoring_model.py     # 四因子加权评分模型
│   │   ├── signal_generator.py  # 信号生成器 (3买+5卖+持有)
│   │   ├── sector_rotation.py   # 板块轮动评分
│   │   ├── timing_model.py      # 交易时段模型
│   │   └── portfolio_model.py   # 仓位分配模型
│   ├── backtest_engine/         # 回测层
│   │   ├── engine.py            # 向量回测引擎
│   │   ├── event_backtester.py  # 事件驱动回测器
│   │   ├── commission_model.py  # 交易成本模型 (佣金/印花税/滑点)
│   │   ├── portfolio.py         # 持仓管理
│   │   ├── performance.py       # 绩效评估 (12项指标)
│   │   ├── risk_check.py        # 回测风控检查
│   │   ├── report_generator.py  # HTML 报告生成器
│   │   ├── significance_test.py # 统计显著性检验
│   │   └── persistence.py       # 回测结果持久化
│   ├── risk_engine/             # 风控层 (待实现)
│   ├── execution_engine/        # 执行层 (待实现)
│   ├── agent_orchestrator/      # Agent 编排 (待实现)
│   ├── ui_report/               # 报告层 (待实现)
│   ├── product_app/             # 产品应用层
│   │   ├── feedback.py          # Bug 报告系统（含自动处理状态）
│   │   ├── bug_fix_agent.py     # BugFix Agent（DeepSeek API 封装）
│   │   ├── bug_watchdog.py      # Bug 文件监控 Hook
│   │   ├── bug_fix_workflow.py  # Bug 修复工作流状态机
│   │   ├── service_manager.py   # 后台作业调度
│   │   ├── health.py            # 健康服务
│   │   ├── config_service.py    # 配置中心
│   │   ├── demo_data.py         # Demo 数据
│   │   └── market_data.py       # 产品行情门面
│   ├── models/
│   │   └── schemas.py           # 数据模型定义
│   ├── config/
│   │   └── settings.py          # 配置管理
│   ├── stock_pool/
│   │   ├── mainboard_filter.py  # 主板股票过滤器
│   │   └── semiconductor.py     # 半导体主题池
│   └── utils/
│       ├── calendar.py          # 交易日历
│       ├── quality.py           # 数据质量检查
│       └── storage.py           # CSV 存储管理
└── tests/
    ├── test_column_mapper.py    # 列映射测试
    ├── test_stock_pool.py       # 股票池测试
    ├── test_quality.py          # 数据质量测试
    ├── test_storage.py          # 存储测试
    ├── test_phase2.py           # Phase 2 测试
    ├── test_phase3.py           # Phase 3 测试
    ├── test_audit_fixes.py      # Phase 1 审计修复测试
    ├── test_audit_phase2.py     # Phase 2 审计修复测试
    ├── test_audit_phase3.py     # Phase 3 审计修复测试
    └── test_bug_auto_fix.py     # Phase 5.6 BUG自动处理测试
```

### 2.3 9 个 Agent 角色

| Agent | 职责 | 实现状态 |
|-------|------|---------|
| Architect Agent | 架构设计、代码审查、技术决策 | ✅ 规则定义 |
| Data Agent | 数据获取、清洗、质量检查 | ✅ Phase 1 |
| Factor Research Agent | 因子挖掘、评估、入库 | ✅ Phase 2 |
| Strategy Agent | 评分、信号生成、板块轮动 | ✅ Phase 2 |
| Backtest Agent | 回测执行、绩效评估、显著性检验 | ✅ Phase 3 |
| Risk Agent | 风控检查、仓位约束、回撤控制 | ✅ Phase 3 (回测内) |
| Execution Agent | 订单执行、交易时段控制 | ✅ Phase 5 |
| Report Agent | 报告生成、可视化 | ✅ Phase 3 (回测内) |
| BugFix Agent | Bug 自动分析、修复方案生成、自动修复 | ✅ Phase 5.6 |

---

## 三、开发历程

### Phase 0: 项目骨架与约束文档

**完成日期：** 2026-06-08

**交付内容：**

1. 7 份核心文档：
   - `AGENTS.md` — Agent 角色定义、总原则、代码修改规则
   - `ARCHITECTURE.md` — 8 层系统架构、技术栈
   - `ROADMAP_AND_CONSTRAINTS.md` — 6 阶段路线图 + 约束
   - `DATA_CONTRACTS.md` — 数据接口规范
   - `RISK_POLICY.md` — 仓位限制、止损回撤、Kill Switch
   - `EXECUTION_POLICY.md` — 订单生命周期、交易模式
   - `FACTOR_RESEARCH_GUIDE.md` — 因子定义标准、评估体系

2. 项目骨架：
   - `pyproject.toml` — Python 项目配置
   - `.env.example` — 环境变量模板
   - `.gitignore` — Git 忽略规则
   - `src/` 10 个子模块 + `tests/` + `config/` + `data/` + `scripts/` + `logs/`

**关键决策：**

- 默认交易模式设为 `LEVEL_1_SIGNAL_ONLY`，禁止自动下单
- 数据源抽象为 `MarketDataProvider` 基类，支持 AkShare/AkTools 双实现
- 排除创业板/科创板在架构层面硬编码，不可配置绕过

---

### Phase 1: 数据层与股票池

**完成日期：** 2026-06-08

**交付内容：**

- 12 个源代码文件，4 个测试文件 (35 个测试用例)
- 测试通过率：35/35 (100%)

**核心实现：**

| 模块 | 关键功能 |
|------|---------|
| `column_mapper.py` | AkShare 中文列名→标准英文映射，symbol 格式转换，涨跌停价计算，ST 检测 |
| `akshare_provider.py` | AkShare 直接调用 Provider，内置 0.5s rate limiting |
| `aktools_provider.py` | AkTools HTTP API Provider (httpx 客户端) |
| `mainboard_filter.py` | 主板/中小板过滤，排除创业板/科创板/ST |
| `semiconductor.py` | 半导体主题池，6 个子板块 21 只股票 |
| `quality.py` | 数据质量检查：完整性/价格异常/涨跌停/停牌/连续缺失 |
| `calendar.py` | 交易日历管理，支持缓存/区间查询 |

**Phase 1 审计整改 (AUDIT_REPORT.md)：**

| 审计发现 | 严重程度 | 整改结果 |
|---------|---------|---------|
| S1: 涨跌停价计算统一用10%，未区分创业板20%/ST 5% | 严重 | ✅ 已修复 |
| S2: 缺少 is_st 字段标记 | 严重 | ✅ 已修复 |
| S3: pre_close 计算逻辑有误 | 严重 | ✅ 已修复 |
| S4: 缺少 is_data_missing 标记 | 严重 | ✅ 已修复 |
| S5: 股票池过滤缺少成交量和上市日期条件 | 严重 | ✅ 已修复 |
| M1~M8: 中等问题 | 中等 | ✅ 6已修复/2部分修复 |
| L1~L4: 低/建议 | 低 | ⬜ 4项中期优化 |

整改后测试：74/74 (100%)

---

### Phase 2: 因子与策略评分

**完成日期：** 2026-06-08

**交付内容：**

- 7 个源代码文件，1 个测试文件 (42 个测试用例)
- 整改后测试：148/148 (100%)

**四因子评分模型：**

```
total_score = 0.25 × policy_score + 0.30 × sentiment_score
            + 0.20 × fundamental_score + 0.25 × trend_score
```

| 因子类别 | 权重 | 核心因子 |
|---------|------|---------|
| 政策主题分 (policy_score) | 0.25 | 板块政策权重 (stock_pool.yaml) |
| 情绪资金分 (sentiment_score) | 0.30 | 量比/额比/相对强度/板块强度 |
| 基本面分 (fundamental_score) | 0.20 | 营收增速/利润增速/毛利率变化/ROE/一致预期 |
| 技术趋势分 (trend_score) | 0.25 | MA排列/20日新高/量价突破/ATR |

**信号体系：**

| 信号类型 | 条件摘要 | 仓位 |
|---------|---------|------|
| BUY_BREAKOUT | 总分>80 + 近20日新高 + 量比>1.5 | 10% |
| BUY_PULLBACK | 总分>75 + 站稳MA20 + 回踩MA10 + 缩量 | 10% |
| BUY_AMBUSH | 政策分>=90 + 基本面>=60 + 站稳均线 | 8% |
| SELL_STOP_LOSS | 浮亏>=8% | 清仓 |
| SELL_TREND_BREAK | 跌破MA20 + 放量破位 | 减仓50% |
| SELL_SENTIMENT_FADE | 板块强度<-2 + 跌幅>3% | 减仓50% |
| SELL_TAKE_PROFIT | 浮盈>=15% + 跌破MA5 | 全仓止盈 |

**Phase 2 审计整改 (AUDIT_REPORT_PHASE2.md)：**

| 审计发现 | 严重程度 | 整改结果 |
|---------|---------|---------|
| S1: 基本面因子全部硬编码为0 | 严重 | ✅ 已修复，接入 AkShare 财务数据 |
| S2: 情绪因子缺少横截面排名模式 | 严重 | ✅ 已修复 |
| S3: 因子评估模块未实现 | 严重 | ✅ 已修复，新增 factor_evaluation.py |
| M1~M6: 中等问题 | 中等 | ✅ 全部修复 |
| L1~L2: 低/建议 | 低 | ✅ 全部修复 |

---

### Phase 3: 回测与评估

**完成日期：** 2026-06-08

**交付内容：**

- 10 个源代码文件，2 个测试文件 (100 个测试用例)
- 整改后测试：248/248 (100%)

**核心实现：**

| 模块 | 关键功能 |
|------|---------|
| `engine.py` | 向量回测引擎：逐日遍历/因子计算/信号生成/涨跌停停牌/风控集成 |
| `event_backtester.py` | 事件驱动回测器：MarketEvent→SignalEvent→OrderEvent→FillEvent |
| `commission_model.py` | 交易成本：佣金万3/印花税千1/港股千1.3/SlippageModel/FillPriceModel |
| `portfolio.py` | 持仓管理：买入/卖出/涨跌停/停牌检查/每日资产记录 |
| `performance.py` | 绩效评估：12项指标 (年化收益/最大回撤/夏普/Calmar/胜率/盈亏比/换手率/扣费收益/基准收益/超额收益/月度/年度) |
| `risk_check.py` | 回测风控：9项约束 (单票15%/板块60%/现金20%/亏损/回撤) |
| `report_generator.py` | HTML报告：Chart.js 净值/回撤曲线/月度收益表 |
| `significance_test.py` | 统计显著性：t检验/Bootstrap/显著性报告 |
| `persistence.py` | 回测结果持久化：保存/加载/列出运行记录 |

**SlippageModel 继承体系：**

```python
class SlippageModel(ABC):           # 抽象基类
    def calc_buy_fill_price(...)
    def calc_sell_fill_price(...)
    def calc_slippage_amount(...)

class FixedRateSlippage(SlippageModel)    # 固定比例滑点 (默认0.1%)
class FixedAmountSlippage(SlippageModel)  # 固定金额滑点
class NoSlippage(SlippageModel)           # 无滑点 (仅用于对比测试)
```

**FillPriceModel 成交价模式：**

| 模式 | 说明 |
|------|------|
| `next_open` | 下一日开盘价成交 (默认) |
| `next_close` | 下一日收盘价成交 |
| `vwap` | 成交量加权平均价 |

**Phase 3 审计整改 (AUDIT_REPORT_PHASE3.md)：**

| 审计发现 | 严重程度 | 整改结果 |
|---------|---------|---------|
| S1: 缺少事件驱动回测器 | 严重 | ✅ 新建 event_backtester.py |
| S2: 滑点模型硬编码未独立抽象 | 严重 | ✅ 新建 SlippageModel 继承体系 |
| S3: 缺少集成测试和端到端测试 | 严重 | ✅ 新增 3 个集成测试 |
| M1: 回测引擎未处理涨跌停无法成交 | 中等 | ✅ 已修复 |
| M2: 回测报告缺少5项绩效指标 | 中等 | ✅ 已修复，12项指标全部实现 |
| M3: 缺少回测报告HTML/可视化输出 | 中等 | ✅ 新建 report_generator.py |
| M4: 样本外测试缺少统计显著性检验 | 中等 | ✅ 新建 significance_test.py |
| M5: 风控检查与回测引擎未深度集成 | 中等 | ✅ 已修复 |
| L1: 缺少多种成交价模式 | 低 | ✅ 新建 FillPriceModel |
| L2: 缺少回测结果持久化存储 | 低 | ✅ 新建 persistence.py |
| L3: 持仓成本未考虑分红除权 | 低 | ⬜ 暂缓至 Phase 4+ |
| L4: 印花税仅支持A股 | 低 | ✅ 新增港股印花税率 0.0013 |

---

## 四、数据流

### 4.1 数据获取流程

```
用户执行 scripts/fetch_daily_data.py
  │
  ├─ 加载交易日历 (TradeCalendar)
  │    └─ provider.get_trade_dates() → 缓存到 data/cleaned/_trade_calendar.csv
  │
  ├─ 确定股票列表
  │    ├─ --symbols 模式: 用户指定
  │    ├─ --pool semiconductor: SemiconductorPool → config/stock_pool.yaml
  │    └─ --pool all: provider.get_stock_list() → filter_tradeable()
  │
  ├─ 获取日线数据 (Provider.get_daily_bars)
  │    ├─ AkShareProvider: ak.stock_zh_a_hist() → column_mapper.map_daily_bars()
  │    └─ AkToolsProvider: HTTP GET /api/public/stock_zh_a_hist → column_mapper
  │
  ├─ 按 symbol 分组保存
  │    ├─ data/raw/{code}_daily_raw.csv
  │    └─ data/cleaned/{code}_daily_cleaned.csv
  │
  └─ 数据质量检查 → data/cleaned/{code}_quality.json
```

### 4.2 回测执行流程

```
用户执行 scripts/run_backtest.py
  │
  ├─ 加载配置 (初始资金/成本模型/风控参数)
  │
  ├─ 加载行情数据 (DataFrame)
  │
  ├─ 向量回测引擎 (BacktestEngine)
  │    ├─ 逐日遍历行情数据
  │    ├─ 计算因子 (compute_all_factors)
  │    ├─ 生成信号 (generate_signals)
  │    ├─ 涨跌停/停牌检查
  │    ├─ 风控检查 (BacktestRiskCheck.update_daily_check)
  │    ├─ 执行买入/卖出 (Portfolio.buy/sell)
  │    └─ 记录每日资产
  │
  ├─ 绩效评估 (PerformanceAnalyzer)
  │    ├─ 12项指标计算
  │    └─ 月度/年度收益
  │
  ├─ 统计显著性检验 (significance_test)
  │    ├─ t检验 (超额收益)
  │    └─ Bootstrap 检验
  │
  ├─ 生成 HTML 报告 (report_generator)
  │
  └─ 持久化结果 (persistence)
       └─ data/backtest_results/{timestamp}/
```

### 4.3 事件驱动回测流程

```
EventBacktester.run()
  │
  ├─ MarketEvent (逐日遍历)
  │    └─ 传入当日行情数据
  │
  ├─ SignalEvent (信号生成)
  │    ├─ compute_all_factors()
  │    ├─ generate_signals()
  │    └─ on_signal_handler 回调
  │
  ├─ OrderEvent (订单生成)
  │    ├─ 信号→订单转换
  │    ├─ 涨跌停/停牌检查
  │    └─ 风控检查
  │
  └─ FillEvent (成交确认)
       ├─ FillPriceModel 计算成交价
       ├─ SlippageModel 计算滑点
       ├─ CommissionModel 计算佣金/印花税
       └─ on_fill_handler 回调
```

---

## 五、关键设计决策

### 5.1 数据源可插拔

`MarketDataProvider` 抽象基类定义 5 个接口方法，AkShare/AkTools 两种实现可切换：

```python
class MarketDataProvider(ABC):
    def get_daily_bars(self, symbol, start_date, end_date) -> pd.DataFrame
    def get_stock_list(self) -> pd.DataFrame
    def get_trade_dates(self, start_date, end_date) -> list[str]
    def get_index_daily(self, index_code, start_date, end_date) -> pd.DataFrame
    def get_intraday_bars(self, symbol, date) -> pd.DataFrame
```

### 5.2 涨跌停价区分计算

```python
def _calc_limit_prices(pre_close, symbol_raw, is_st):
    if is_st:          # ST 股：5%
        rate = 0.05
    elif 300/301/688/689:  # 创业板/科创板：20%
        rate = 0.20
    else:              # 主板/中小板：10%
        rate = 0.10
```

### 5.3 滑点模型独立抽象

从 `CommissionModel` 中提取 `SlippageModel` 为独立继承体系，支持：
- `FixedRateSlippage` — 固定比例 (默认 0.1%)
- `FixedAmountSlippage` — 固定金额
- `NoSlippage` — 无滑点 (对比测试用)

### 5.4 港股印花税差异化

A股印花税 0.1%（卖出），港股印花税 0.13%（买卖双向），在 `CommissionModel` 中通过 `stamp_duty_rate_hk` 参数区分。

### 5.5 因子评估体系

```python
# factor_evaluation.py 支持的评估指标
- IC (Information Coefficient)
- Rank IC
- IC_IR (IC Information Ratio)
- Turnover (因子换手率)
- Coverage (因子覆盖率)
- Decay (因子衰减)
- Long-Short Return (多空收益)
```

---

## 六、测试体系

### 6.1 测试统计

| Phase | 测试文件 | 测试用例数 | 通过率 |
|-------|---------|-----------|--------|
| Phase 1 基础 | 4 个文件 | 35 | 100% |
| Phase 1 审计 | 1 个文件 | 39 | 100% |
| Phase 2 | 1 个文件 | 42 | 100% |
| Phase 2 审计 | 1 个文件 | 32 | 100% |
| Phase 3 | 1 个文件 | 42 | 100% |
| Phase 3 审计 | 1 个文件 | 58 | 100% |
| Phase 4 Risk-First | 4 个文件 | 11 | 100% |
| Phase 5.6 BUG自动处理 | 1 个文件 | 21 | 100% |
| **合计** | **14 个文件** | **283** | **100%** |

### 6.2 运行测试

```bash
# 安装依赖
pip install -e ".[dev]"

# 运行全部测试
pytest tests/ -v

# 运行特定 Phase 测试
pytest tests/test_phase3.py -v
pytest tests/test_audit_phase3.py -v

# 运行带覆盖率
pytest tests/ --cov=src --cov-report=html
```

---

## 七、已知问题与限制

| # | 问题 | 严重程度 | 处理计划 |
|---|------|----------|---------|
| 1 | 港股日线数据暂不支持通过 AkShare stock_zh_a_hist 获取 | 中 | Phase 4 使用港股专用接口 |
| 2 | 回测使用当日收盘价成交，非实际撮合 | 中 | Phase 4 引入分钟线后优化 |
| 3 | 基本面数据获取可能因 AkShare 接口变动而失败 | 中 | 增加异常处理和备用数据源 |
| 4 | 分红除权未处理 (L3 暂缓) | 低 | Phase 4+，需除权因子数据源 |
| 5 | adj_factor 字段暂未填充 | 低 | 当前使用前复权价格 |
| 6 | 换手率计算为简化版本 | 低 | Phase 3 后续优化 |
| 7 | E2E 测试和 API 测试待 Phase 4 补充 | 中 | Phase 4 实现 FastAPI 后补充 |
| 8 | AkShare 免费数据源有反爬限制 | 中 | Provider 内置 0.5s rate limiting |

---

## 八、Phase 4 开发计划

### 8.1 目标

实盘盯盘与信号生成

### 8.0 架构复核裁决（2026-06-08）

本次复核结论：

1. Phase 3 可以进入 Phase 4，但不是无条件放行。
2. 已补充 `BACKTEST_POLICY.md`，明确日频信号默认必须在下一交易日成交，禁止前视偏差。
3. 已修复 `BacktestEngine` 与 `EventBacktester` 的 `next_open`/`vwap` 同日成交问题。
4. 已修复 `factor_evaluation.evaluate_all_factors()` 缺少 `forward_return` 时的 `symbol_col` 未定义问题。
5. 已修复 Rank IC 与统计显著性检验对未声明 `scipy` 的硬依赖。
6. 全量测试结果：`251 passed in 23.39s`。

Phase 4 开发顺序调整为：

1. 先实现 `risk_engine` 运行时风控骨架和只读 Kill Switch 状态。
2. 再实现实时行情 Provider、行情延迟报告和数据健康门禁。
3. 再实现信号生成服务，交易模式保持 `LEVEL_1_SIGNAL_ONLY`。
4. 最后实现 API/UI/通知层。

### 8.2 核心任务

1. **FastAPI 后端服务**
   - 实时行情推送 (WebSocket)
   - 信号生成 API
   - 回测触发 API
   - 持仓查询 API

2. **Streamlit 前端**
   - 实时盯盘面板
   - 信号列表与详情
   - 回测配置与结果展示
   - 风控状态监控

3. **实时数据集成**
   - 分钟级行情接入
   - 实时因子计算
   - 实时信号触发

4. **信号仪表盘**
   - 当日信号汇总
   - 历史信号追踪
   - 信号准确率统计

### 8.3 技术选型 (待确认)

| 类别 | 候选方案 |
|------|---------|
| Web 框架 | FastAPI |
| 前端框架 | Streamlit |
| 实时通信 | WebSocket |
| 任务队列 | Celery / asyncio |
| 缓存 | Redis |
| 数据库 | SQLite / DuckDB |

---

## 九、协作开发指南

### 9.1 环境搭建

```bash
# 1. 克隆仓库
git clone git@github.com:dafienoly/quant-trading-agent.git
cd quant-trading-agent

# 2. 创建虚拟环境
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 3. 安装依赖
pip install -e ".[dev]"

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 填入必要配置

# 5. 运行测试验证
pytest tests/ -v
```

### 9.2 代码规范

- 使用 `ruff` 进行代码格式化和 lint
- 行宽限制 100 字符
- 目标 Python 版本 3.10+
- 所有核心逻辑必须有单元测试
- 信号和因子必须有解释文本

### 9.3 开发规则 (AGENTS.md 摘要)

1. **不允许直接跳过验证** — 任何策略必须经过：单元测试→数据完整性检查→回测→样本外测试→模拟盘→风险评估→人工确认
2. **不允许默认自动下单** — 默认 `LEVEL_1_SIGNAL_ONLY`
3. **不允许绕过风控** — 风控模块不可被注释/删除/绕过
4. **不允许使用未来数据** — 禁止 `shift(-1)` 或前瞻函数
5. **不允许硬编码密钥** — 使用 `.env` 管理敏感配置
6. **每个信号必须有解释** — Signal 必须包含 reason + risk_note

### 9.4 Git 工作流

```bash
# 主分支: main (稳定版本)
# 开发分支: develop (日常开发)
# 功能分支: feature/xxx (新功能)

# 创建功能分支
git checkout -b feature/phase4-fastapi

# 提交代码
git add <files>
git commit -m "feat: add FastAPI signal endpoint"

# 推送并创建 PR
git push -u origin feature/phase4-fastapi
```

### 9.5 关键文档索引

| 文档 | 说明 |
|------|------|
| `AGENTS.md` | Agent 角色定义与开发规则 (必读) |
| `ARCHITECTURE.md` | 系统架构设计 (必读) |
| `ROADMAP_AND_CONSTRAINTS.md` | 路线图与约束 (必读) |
| `DATA_CONTRACTS.md` | 数据接口契约 |
| `RISK_POLICY.md` | 风控策略 |
| `EXECUTION_POLICY.md` | 执行策略 |
| `FACTOR_RESEARCH_GUIDE.md` | 因子研究指南 |
| `PHASE_COMPLETION_REPORT.md` | 各阶段完成报告 |
| `AUDIT_REPORT.md` | Phase 1 审计报告 |
| `AUDIT_REPORT_PHASE2.md` | Phase 2 审计报告 |
| `AUDIT_REPORT_PHASE3.md` | Phase 3 审计报告 |
| `REMEDIATION_REPORT.md` | Phase 1 整改报告 |
| `REMEDIATION_REPORT_PHASE2.md` | Phase 2 整改报告 |
| `REMEDIATION_REPORT_PHASE3.md` | Phase 3 整改报告 |

---

## 十、版本历史

| 版本 | 日期 | Phase | 说明 |
|------|------|-------|------|
| v0.1.0 | 2026-06-08 | Phase 0 | 项目骨架与约束文档 |
| v0.2.0 | 2026-06-08 | Phase 1 | 数据层与股票池 |
| v0.2.1 | 2026-06-08 | Phase 1 审计 | 审计整改 (74/74 测试通过) |
| v0.3.0 | 2026-06-08 | Phase 2 | 因子与策略评分 |
| v0.3.1 | 2026-06-08 | Phase 2 审计 | 审计整改 (148/148 测试通过) |
| v0.4.0 | 2026-06-08 | Phase 3 | 回测与评估 |
| v0.4.1 | 2026-06-08 | Phase 3 审计 | 审计整改 (248/248 测试通过) |
| v0.5.0 | 2026-06-08 | Phase 4 Risk-First | 运行时风控+数据健康门禁+只读监控器+API (262/262 测试通过) |
| v0.5.6 | 2026-06-10 | Phase 5.5 产品补强 | AkShare/AkTools 产品行情门面、实时行情 API、后台 quote_refresh 快照、9 Tab Dashboard 交互补强 (17 项聚焦测试通过) |
| v0.6.0 | 2026-06-10 | Phase 5.6 BUG自动处理 | BugFixAgent(DeepSeek API)+BugWatchdog(文件监控)+BugFixWorkflow(状态机)+4 API端点+面板审批 (21 项集成测试通过) |

---

## 十一、2026-06-10 产品实时行情与 Dashboard 补强

### 11.1 背景

Phase 5.5 已具备一键启动与产品 Demo，但用户侧核心体验仍需要从“静态 Demo 表格”升级为“可选择数据源、可触发实时刷新、可落盘后台快照”的产品闭环。本次修改保持默认 `LEVEL_1_SIGNAL_ONLY`，不引入任何真实自动下单能力。

### 11.2 完成内容

1. 新增 `src/product_app/market_data.py`，统一产品侧 AkShare/AkTools provider 构建、symbols 规范化、Demo fallback、自动 feedback Bug 生成。
2. `/product/quotes` 接入统一行情门面，支持 `provider=akshare|aktools`、`allow_demo`、`force_live` 参数。
3. `ServiceManager.quote_refresh` 不再只写 `source=demo`，改为写入 `runtime/state/latest_quotes.json`，包含 `status/provider/is_demo/symbols/quotes/messages/updated_at`。
4. Streamlit 产品 Dashboard 的 `Realtime Market` Tab 增加数据源选择、实时刷新、后台快照启动、后台作业状态展示。
5. Dashboard 保留人工确认安全边界：不暴露批量买入确认，不启用 LEVEL_3 自动交易。
6. 新增聚焦测试：
   - `tests/test_product_market_data.py`
   - `tests/test_product_realtime_api.py`
   - `tests/test_product_service_manager_quotes.py`
   - `tests/test_realtime_provider.py`
   - `tests/test_product_dashboard_source.py`

### 11.3 后续 Agent 必须遵守的开发准则

1. 修改 `src/data_gateway/realtime_provider.py` 或 `src/data_gateway/aktools_provider.py` 时，必须确认 volume 内部单位仍为股，并保留 `data_source/updated_at/data_version/currency/timezone`。
2. 修改 `/product/quotes`、`product_app.market_data` 或 `ServiceManager.quote_refresh` 时，必须同时验证 API 与后台 `latest_quotes.json` 快照。
3. Dashboard 新增交易相关控件时，必须保持 LEVEL_3 不默认暴露，买入订单不允许批量确认。
4. AkShare/AkTools 失败时不得静默吞错，必须生成 `feedback/bugs/open` 下的 Bug 清单；允许 Demo fallback，但 UI/API 必须显式标注 `is_demo=true` 或 `fallback_demo`。
5. 触碰本次范围后必须运行：

```bash
.venv\Scripts\python.exe -m pytest tests/test_phase4_api.py tests/test_phase4_realtime_health.py tests/test_realtime_provider.py tests/test_product_market_data.py tests/test_product_realtime_api.py tests/test_product_service_manager_quotes.py tests/test_product_dashboard_source.py -q --basetemp=runtime\pytest-tmp
.venv\Scripts\python.exe -m ruff check src\product_app\market_data.py src\product_app\service_manager.py src\api\product_routes.py src\data_gateway\realtime_provider.py src\data_gateway\aktools_provider.py src\ui_report\product_dashboard.py tests\test_realtime_provider.py tests\test_product_market_data.py tests\test_product_realtime_api.py tests\test_product_service_manager_quotes.py tests\test_product_dashboard_source.py
.venv\Scripts\python.exe -m py_compile src\product_app\market_data.py src\product_app\service_manager.py src\api\product_routes.py src\data_gateway\realtime_provider.py src\data_gateway\aktools_provider.py src\ui_report\product_dashboard.py
```

### 11.4 本次验证记录

| 验证项 | 结果 |
|---|---|
| 聚焦 pytest | 17 passed |
| ruff touched scope | All checks passed |
| py_compile touched scope | passed |
| API smoke | `/product/quotes` 返回 HTTP 200，Demo fallback 状态显式 |
| Streamlit smoke | `http://127.0.0.1:8771` 返回 HTTP 200 |
| Browser smoke | Realtime Market Tab、数据源选择、刷新、后台快照按钮可见，quote_refresh 状态可见 |

---

## 十二、2026-06-10 Phase 5.6 BUG 自动处理系统

### 12.1 背景

项目仍处于开发期，Bug 频繁产生且阻塞正常流程。原有的 Bug 收集系统（`feedback.py`）仅实现了提交、去重和状态管理，Bug 提交后需要人工逐个分析、定位、修复。Phase 5.6 将"Bug 收集"升级为"Bug 自动处理"，引入 AI Agent 作为 Bug 处理工程师。

### 12.2 LLM 引擎选型

| 资源 | 优势 | 劣势 | 结论 |
|------|------|------|------|
| Claude Code + DeepSeek | Claude 擅长代码理解和修复 | Claude Code 需要交互式环境，不适合后台自动化 | 不采用 |
| DeepSeek API | 成本极低（约 0.001 元/千 token）、代码能力强、适合批量自动化 | 长上下文理解略弱于 Claude | **采用** |

### 12.3 完成内容

1. **BugFixAgent** (`src/product_app/bug_fix_agent.py`)：封装 DeepSeek API 调用
   - `analyze()` — 读取 Bug 报告 + 项目上下文 → 调用 DeepSeek API → 生成根因分析
   - `propose_fix()` — 基于分析结果 → 调用 DeepSeek API → 生成修复方案（含代码 diff）
   - `execute_fix()` — 应用代码 diff → 运行 pytest → 验证通过则提交，失败则回滚
   - `_call_deepseek()` — OpenAI 兼容接口调用，3 次重试 + 指数退避（2s/4s/8s）
   - `_build_context()` — 根据 Bug 组件收集相关源码上下文（最多 3 文件，每文件 200 行）
   - `_is_blocked_module()` — 拦截对 risk_engine/trading_log/backtest_report 的修改

2. **BugWatchdog** (`src/product_app/bug_watchdog.py`)：文件监控 Hook
   - 基于 watchdog 库监控 `feedback/bugs/open/` 目录新文件事件
   - watchdog 未安装时自动降级为 30 秒轮询模式
   - 2 秒防抖机制，避免重复触发
   - 启动时自动处理已有 Bug 文件

3. **BugFixWorkflow** (`src/product_app/bug_fix_workflow.py`)：状态机编排
   - 状态流转：open → analyzing → proposed → approved → fixing → verified → fixed
   - 分支状态：blocked（受限模块）、rejected（审批拒绝）、fix_failed（修复失败）
   - `process_bug()` — 编排完整分析+方案生成流程
   - `approve_fix()` — 审批通过后自动执行修复
   - `reject_fix()` — 审批拒绝，可重新触发分析
   - `_execute_and_verify()` — 执行修复 + pytest 验证 + git stash/commit

4. **FeedbackService 扩展** (`src/product_app/feedback.py`)：
   - BugReport 新增 6 字段：analysis_report/fix_proposal/approval_status/approval_comment/fix_result/git_commit_hash
   - 新增 8 个状态常量：analyzing/proposed/approved/rejected/fixing/fix_failed/verified/blocked
   - 新增 `feedback/bugs/analysis/` 目录

5. **ServiceManager 扩展** (`src/product_app/service_manager.py`)：
   - 新增 `bug_fix_agent` 作业类型
   - 启动时创建 BugWatchdog 并注册回调
   - 停止时自动关闭 BugWatchdog

6. **API 端点** (`src/api/product_routes.py`)：
   - `GET /product/feedback/{bug_id}/analysis` — 获取分析报告
   - `POST /product/feedback/{bug_id}/approve` — 审批修复方案
   - `POST /product/feedback/{bug_id}/reject` — 拒绝修复方案
   - `GET /product/feedback/{bug_id}/fix-status` — 获取修复进度

7. **产品面板** (`src/ui_report/product_dashboard.py`)：
   - 状态机步骤指示器（7 步水平进度条）
   - 分析报告和修复方案展开显示
   - Approve/Reject 操作按钮
   - 修复执行结果展示

8. **依赖更新** (`pyproject.toml`)：
   - 新增 `openai>=1.0`（DeepSeek API 调用）
   - 新增 `watchdog>=3.0`（文件系统监控）

9. **集成测试** (`tests/test_bug_auto_fix.py`)：
   - 21 个测试用例：BugFixAgent(8) + BugWatchdog(3) + BugFixWorkflow(6) + API端点(4)

### 12.4 安全约束

1. 修复方案必须经过人工审批才能执行（与 AGENTS.md 2.1 原则一致）
2. 禁止修改风控模块、交易日志、回测报告（与 AGENTS.md 4.2 一致）
3. 修复执行前自动创建 git stash 作为回滚点
4. 修复后必须运行 pytest 验证，测试不通过则自动回滚
5. DeepSeek API Key 从环境变量读取，不硬编码

### 12.5 后续 Agent 必须遵守的开发准则

1. 修改 `bug_fix_agent.py` 时，不得移除 `_is_blocked_module()` 检查或绕过审批流程
2. 修改 `bug_fix_workflow.py` 状态机时，必须保持人工审批门禁（proposed → approved 不可跳过）
3. 新增 Bug 状态时，必须同步更新 `VALID_TRANSITIONS` 和 `_status_to_dir()` 映射
4. 修改 DeepSeek API 调用逻辑时，必须保持重试机制和错误处理
5. 触碰本次范围后必须运行：

```bash
.venv\Scripts\python.exe -m pytest tests/test_bug_auto_fix.py -v
```

### 12.6 本次验证记录

| 验证项 | 结果 |
|---|---|
| 集成测试 | 21 passed |
| checklist 验证 | 30/30 项全部通过 |
| AGENTS.md 合规 | 人工确认原则 ✅ / 禁止修改风控 ✅ / 禁止硬编码密钥 ✅ |
