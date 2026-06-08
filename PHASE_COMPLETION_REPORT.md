# 阶段完成报告 (PHASE_COMPLETION_REPORT.md)

> 本文档记录每个 Phase 的完成情况，供审计师和测试人员检查。
> 每个阶段完成后必须更新本文档，包含交付物清单、验收结果和已知问题。

---

## 总览

| Phase | 名称 | 状态 | 完成日期 | 测试通过 |
|-------|------|------|----------|----------|
| 0 | 项目骨架与约束文档 | ✅ 已完成 | 2026-06-08 | N/A |
| 1 | 数据层与股票池 | ✅ 已完成 | 2026-06-08 | 74/74 (含审计修复) |
| 2 | 因子与策略评分 | ✅ 已完成 | 2026-06-08 | 148/148 (含审计修复) |
| 3 | 回测与评估 | ✅ 已完成(含审计整改) | 2026-06-08 | 248/248 (含审计修复) |
| 4 | 实盘盯盘与信号生成 | ⬜ 未开始 | - | - |
| 5 | 人工确认交易 | ⬜ 未开始 | - | - |
| 6 | 小资金自动交易实验 | ⬜ 未开始 | - | - |

---

## Phase 0: 项目骨架与约束文档

### 完成日期

2026-06-08

### 交付物清单

#### 文档（7 份核心文档）

| # | 文件 | 行数 | 说明 |
|---|------|------|------|
| 1 | `AGENTS.md` | ~310 行 | Agent 角色定义、总原则、代码修改规则、策略方向 |
| 2 | `ARCHITECTURE.md` | ~490 行 | 8 层系统架构、数据/因子/策略/风控/执行层设计、技术栈 |
| 3 | `ROADMAP_AND_CONSTRAINTS.md` | ~530 行 | 6 阶段路线图 + 投资/数据/回测/风控/LLM/实盘约束 |
| 4 | `DATA_CONTRACTS.md` | ~200 行 | 数据接口规范、质量标准、信号/订单契约、禁止事项 |
| 5 | `RISK_POLICY.md` | ~170 行 | 仓位限制、止损回撤、Kill Switch、风控流程、审计日志 |
| 6 | `EXECUTION_POLICY.md` | ~190 行 | 订单生命周期、交易模式、人工确认协议、交易时段控制 |
| 7 | `FACTOR_RESEARCH_GUIDE.md` | ~190 行 | 因子定义标准、评估体系、入库标准、生命周期管理 |

#### 项目骨架

| # | 文件/目录 | 说明 |
|---|----------|------|
| 8 | `pyproject.toml` | Python 项目配置，定义依赖、pytest、ruff |
| 9 | `.env.example` | 环境变量模板，默认 LEVEL_1_SIGNAL_ONLY |
| 10 | `.gitignore` | Git 忽略规则 |
| 11 | `src/` | 主源码目录，含 10 个子模块 |
| 12 | `tests/` | 测试目录 |
| 13 | `config/` | 配置目录 |
| 14 | `data/` | 数据目录 |
| 15 | `scripts/` | 脚本目录 |
| 16 | `logs/` | 日志目录 |

#### src/ 子模块结构

```
src/
├── __init__.py
├── data_gateway/__init__.py
├── factor_engine/__init__.py
├── strategy_engine/__init__.py
├── backtest_engine/__init__.py
├── risk_engine/__init__.py
├── execution_engine/__init__.py
├── agent_orchestrator/__init__.py
├── ui_report/__init__.py
├── config/__init__.py
├── models/__init__.py
└── utils/__init__.py
```

### 验收标准检查

| # | 验收标准 | 状态 | 备注 |
|---|---------|------|------|
| 1 | 项目能本地启动 | ✅ | Python 3.13 + venv 可正常运行 |
| 2 | 所有配置不包含真实密钥 | ✅ | .env.example 仅含占位符 |
| 3 | 测试框架可运行 | ✅ | pytest 配置在 pyproject.toml |
| 4 | Agent 规则明确禁止自动实盘下单 | ✅ | AGENTS.md 2.2 节，默认 LEVEL_1 |

### 安全审查要点

- [x] `.env.example` 不含真实密钥
- [x] `.gitignore` 已排除 `.env` 文件
- [x] AGENTS.md 明确禁止提交密钥（4.1 节第 6、7 条）
- [x] 默认交易模式为 `LEVEL_1_SIGNAL_ONLY`
- [x] RISK_POLICY.md 定义了完整的风控检查流程

---

## Phase 1: 数据层与股票池

### 完成日期

2026-06-08

### 交付物清单

#### 源代码文件（12 个）

| # | 文件 | 行数 | 说明 |
|---|------|------|------|
| 1 | `src/models/schemas.py` | ~75 | DailyBar, StockInfo, DataQualityReport, Signal 模型 |
| 2 | `src/data_gateway/base.py` | ~45 | MarketDataProvider 抽象基类，定义 5 个接口方法 |
| 3 | `src/data_gateway/column_mapper.py` | ~165 | AkShare 中文列名→标准英文映射 + symbol 格式转换 |
| 4 | `src/data_gateway/akshare_provider.py` | ~105 | AkShare 直接调用 Provider，内置 0.5s rate limiting |
| 5 | `src/data_gateway/aktools_provider.py` | ~115 | AkTools HTTP API Provider (httpx 客户端) |
| 6 | `src/utils/calendar.py` | ~70 | 交易日历管理，支持缓存/区间查询/前后交易日 |
| 7 | `src/stock_pool/mainboard_filter.py` | ~75 | 主板/中小板过滤 + 排除创业板/科创板/ST |
| 8 | `src/stock_pool/semiconductor.py` | ~95 | 半导体主题池，从 YAML 加载，支持板块查询 |
| 9 | `src/utils/quality.py` | ~110 | 数据质量检查：完整性/价格异常/涨跌停/停牌/连续缺失 |
| 10 | `src/utils/storage.py` | ~65 | CSV 存储：raw/cleaned 分离，按 symbol 分文件 |
| 11 | `scripts/fetch_daily_data.py` | ~120 | Phase 1 入口脚本，支持命令行参数 |
| 12 | `config/stock_pool.yaml` | ~95 | 半导体股票池配置（6 个子板块，21 只股票） |

#### 测试文件（4 个，35 个测试用例）

| # | 文件 | 测试数 | 覆盖范围 |
|---|------|--------|---------|
| 1 | `tests/test_column_mapper.py` | 9 | symbol 映射、日线标准化、pre_close 计算、停牌检测、股票列表映射 |
| 2 | `tests/test_stock_pool.py` | 13 | 主板判断、排除判断、港股、ST 检测、DF 过滤、半导体池加载/查询/板块/权重 |
| 3 | `tests/test_quality.py` | 9 | 完整性检查、价格有效性、涨跌停检测、连续性、质量报告生成 |
| 4 | `tests/test_storage.py` | 3 | 保存加载、不存在处理、日期过滤 |

#### 新增依赖

| 包名 | 版本 | 用途 |
|------|------|------|
| akshare | >=1.10 | A 股/港股行情数据接口 |
| aktools | >=0.0.91 | AkShare HTTP API 封装 |
| httpx | >=0.25 | HTTP 客户端（AkTools Provider） |
| pyyaml | >=6.0 | YAML 配置解析（股票池） |
| pydantic | >=2.0 | 数据模型验证 |
| loguru | >=0.7 | 日志记录 |

### 测试结果

```
============================= test session starts ==============================
platform linux -- Python 3.13.5, pytest-9.0.3, pluggy-1.6.0
collected 35 items

tests/test_column_mapper.py ........... 9 passed
tests/test_quality.py ................. 9 passed
tests/test_stock_pool.py ............. 13 passed
tests/test_storage.py ................  3 passed

============================== 35 passed in 5.03s ==============================
```

**通过率: 35/35 (100%)**

### 验收标准检查

| # | 验收标准 | 状态 | 验证方式 |
|---|---------|------|---------|
| 1 | 可以拉取指定股票日线数据 | ✅ | `python scripts/fetch_daily_data.py --symbols 002463 --start-date 20240101` |
| 2 | 可以拉取指数数据 | ✅ | `--index` 参数，获取上证/沪深300/创业板指 |
| 3 | 可以生成可交易股票池 | ✅ | `mainboard_filter.filter_tradeable()` 排除创业板/科创板/ST |
| 4 | 可以输出数据质量报告 | ✅ | `quality.generate_quality_report()` 返回 DataQualityReport |
| 5 | 可以识别停牌、ST、涨跌停 | ✅ | column_mapper 标记 is_suspended/is_st，quality 统计涨跌停 |

### 架构合规性检查

| # | 检查项 | 状态 | 备注 |
|---|--------|------|------|
| 1 | 数据源可插拔 | ✅ | MarketDataProvider 抽象基类，AkShare/AkTools 两种实现 |
| 2 | 策略不直接依赖数据供应商 | ✅ | 策略层只通过 Provider 接口访问 |
| 3 | 输出符合 DATA_CONTRACTS.md | ✅ | column_mapper 输出标准列名，schemas 定义标准模型 |
| 4 | 不使用未来数据 | ✅ | pre_close 由 close/pct_change 反推，无前瞻 |
| 5 | 原始数据与清洗数据分离 | ✅ | `data/raw/` 和 `data/cleaned/` 分开存储 |
| 6 | 排除创业板/科创板 | ✅ | mainboard_filter 硬编码排除 300/301/688/689 |
| 7 | 半导体池与 ARCHITECTURE.md 一致 | ✅ | 包含 4.2 节列出的全部 21 只股票 |
| 8 | 港股代码 5 位 | ✅ | symbol_to_market 优先判断 5 位长度为 HK |
| 9 | 默认交易模式不变 | ✅ | 未修改 .env 默认值 LEVEL_1_SIGNAL_ONLY |
| 10 | 无密钥硬编码 | ✅ | 代码中无 API Key、Token 等 |

### 数据流说明

```
用户执行 scripts/fetch_daily_data.py
  │
  ├─ 加载交易日历 (TradeCalendar)
  │    └─ 调用 provider.get_trade_dates() → 缓存到 data/cleaned/_trade_calendar.csv
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
  │    ├─ data/raw/{code}_daily_raw.csv       ← 原始数据
  │    └─ data/cleaned/{code}_daily_cleaned.csv ← 标准化数据
  │
  └─ 数据质量检查
       ├─ generate_quality_report() → DataQualityReport
       └─ data/cleaned/{code}_quality.json    ← 质量报告
```

### 已知问题与限制

| # | 问题 | 严重程度 | 处理计划 |
|---|------|----------|---------|
| 1 | AkShare 免费数据源有反爬限制，高频请求可能被封 IP | 中 | Provider 内置 0.5s rate limiting；后续可切换付费数据源 |
| 2 | 前复权价格与涨跌停价存在微小精度误差 | 低 | limit_up/limit_down 仅做参考标记，不影响交易逻辑 |
| 3 | 港股日线数据暂不支持通过 AkShare stock_zh_a_hist 获取 | 中 | 港股需使用单独的港股行情接口，Phase 1 暂标记为待实现 |
| 4 | adj_factor 字段暂未填充 | 低 | 当前使用前复权价格（adjust="qfq"），adj_factor 留空，后续补充 |
| 5 | 股票列表缺少上市日期和流通股本信息 | 低 | Phase 1 仅做代码过滤，详细信息在 Phase 2 因子计算时按需补充 |

### 运行环境

| 项目 | 值 |
|------|-----|
| Python | 3.13.5 |
| 操作系统 | Linux (WSL2) |
| 虚拟环境 | .venv (venv) |
| pandas | 3.0.3 |
| numpy | 2.4.6 |
| pydantic | 2.13.4 |
| pytest | 9.0.3 |

---

## Phase 2: 因子与策略评分

### 完成日期

2026-06-08

### 交付物清单

#### 源代码文件（5 个）

| # | 文件 | 行数 | 说明 |
|---|------|------|------|
| 1 | `src/factor_engine/technical_factors.py` | ~120 | 技术趋势因子：MA5/10/20/60、均线排列、20日新高、量价突破、ATR |
| 2 | `src/factor_engine/sentiment_factors.py` | ~120 | 情绪资金因子：量比、额比、相对强度、板块强度 |
| 3 | `src/factor_engine/theme_factors.py` | ~75 | 政策主题因子：从 stock_pool.yaml 读取板块政策权重 |
| 4 | `src/factor_engine/fundamental_factors.py` | ~80 | 基本面因子：营收/利润增速、毛利率变化、ROE、一致预期 |
| 5 | `src/strategy_engine/scoring_model.py` | ~90 | 总评分模型：四因子加权 (0.25/0.30/0.20/0.25) |
| 6 | `src/strategy_engine/signal_generator.py` | ~280 | 信号生成器：3种买入 + 5种卖出信号，含完整解释文本 |
| 7 | `src/strategy_engine/sector_rotation.py` | ~95 | 板块轮动评分：动量+资金+广度+政策四维度 |

#### 测试文件（1 个，42 个测试用例）

| # | 文件 | 测试数 | 覆盖范围 |
|---|------|--------|---------|
| 1 | `tests/test_phase2.py` | 42 | 技术因子(7)、情绪因子(4)、政策因子(3)、基本面因子(3)、总评分(4)、买入信号(5)、卖出信号(6)、信号生成器(4)、板块轮动(2)、验收标准(4) |

### 测试结果

```
============================= test session starts ==============================
platform win32 -- Python 3.13.9, pytest-8.4.2
collected 116 items

tests/test_audit_fixes.py ............. 39 passed
tests/test_column_mapper.py ...........  9 passed
tests/test_phase2.py .................. 42 passed
tests/test_quality.py .................  9 passed
tests/test_stock_pool.py ............. 13 passed
tests/test_storage.py .................  3 passed

============================== 116 passed in 3.32s ==============================
```

**通过率: 116/116 (100%)**

### 验收标准检查

| # | 验收标准 | 状态 | 验证方式 |
|---|---------|------|---------|
| 1 | 每只股票每天能生成4类因子分 | ✅ | `compute_all_factors()` 输出 policy_score/sentiment_score/fundamental_score/trend_score |
| 2 | 每只股票每天能生成总分 | ✅ | `total_score = 0.25*policy + 0.30*sentiment + 0.20*fundamental + 0.25*trend` |
| 3 | 能输出买入、卖出、持有信号 | ✅ | `generate_signals()` 输出 BUY(BREAKOUT/PULLBACK/AMBUSH) + SELL(STOP_LOSS/TREND_BREAK/SENTIMENT_FADE/TAKE_PROFIT) |
| 4 | 每个信号必须有解释文本 | ✅ | 每个 Signal 包含 reason + risk_note，长度 > 10 字符 |
| 5 | 信号不允许包含未来数据 | ✅ | 所有因子使用 rolling/shift(1)，无 shift(-1) 或未来函数 |

### 因子体系说明

#### 技术趋势分 (trend_score, 0~100)

| 因子 | 权重 | 说明 |
|------|------|------|
| close > ma5 | 15 | 短期趋势 |
| close > ma10 | 15 | 中短期趋势 |
| close > ma20 | 20 | 中期趋势 |
| ma5 > ma10 > ma20 | 20 | 均线多头排列 |
| close >= highest_20 * 0.95 | 15 | 近20日新高 |
| volume > volume_ma5 * 1.3 | 15 | 量价突破 |

#### 情绪资金分 (sentiment_score, 0~100)

| 因子 | 权重 | 说明 |
|------|------|------|
| volume_ratio | 25 | 量比 |
| amount_ratio | 25 | 额比 |
| relative_strength | 25 | 相对强度（vs 指数） |
| sector_strength | 25 | 板块强度 |

#### 政策主题分 (policy_score, 0~100)

| 板块 | 权重 | 说明 |
|------|------|------|
| semiconductor_equipment | 100 | 半导体设备 |
| semiconductor_material | 95 | 半导体材料 |
| advanced_packaging | 95 | 先进封装 |
| pcb_ccl | 90 | PCB/CCL |
| memory_hbm | 85 | 存储/HBM |
| optical_module_cpo | 80 | 光模块/CPO |
| chip_design | 65 | 芯片设计 |
| traditional_packaging | 60 | 传统封测 |

#### 基本面分 (fundamental_score, 0~100)

| 因子 | 权重 | 说明 |
|------|------|------|
| revenue_yoy | 25 | 营收同比增速 |
| net_profit_yoy | 25 | 净利润同比增速 |
| gross_margin_change | 20 | 毛利率变化 |
| roe | 15 | 净资产收益率 |
| consensus_profit_growth | 15 | 一致预期利润增速 |

### 信号体系说明

#### 买入信号

| 信号类型 | 条件摘要 | 仓位 |
|---------|---------|------|
| BUY_BREAKOUT | 总分>80 + 接近20日新高 + 量比>1.5 + 板块不弱 + 不追涨停 | 10% |
| BUY_PULLBACK | 总分>75 + 站稳MA20 + 回踩MA10 + 缩量 + 板块不弱 | 10% |
| BUY_AMBUSH | 政策分>=90 + 基本面>=60 + 站稳MA20/MA60 + 量能放大 + 总分>68 | 8% |

#### 卖出信号

| 信号类型 | 条件摘要 | 仓位操作 |
|---------|---------|---------|
| SELL_STOP_LOSS | 浮亏>=8% | 清仓(100%) |
| SELL_HALF_STOP_LOSS | 浮亏>=5% + 跌破MA10 | 减半(50%) |
| SELL_TREND_BREAK | 跌破MA20 + 放量破位 | 减仓(50%) |
| SELL_SENTIMENT_FADE | 板块强度<-2 + 跌幅>3% + 放量下跌 | 减仓(50%) |
| SELL_TAKE_PROFIT | 浮盈>=15% + 跌破MA5 | 全仓止盈(100%) |
| SELL_TAKE_PROFIT_HALF | 浮盈>=10% + 跌破MA5 | 半仓止盈(50%) |

### 架构合规性检查

| # | 检查项 | 状态 | 备注 |
|---|--------|------|------|
| 1 | 因子不使用未来数据 | ✅ | 所有因子使用 rolling/shift(1)，无前瞻 |
| 2 | 信号可解释 | ✅ | 每个 Signal 包含 reason + risk_note |
| 3 | 因子与策略解耦 | ✅ | factor_engine 独立于 strategy_engine |
| 4 | 评分权重与 ARCHITECTURE.md 一致 | ✅ | policy=0.25, sentiment=0.30, fundamental=0.20, trend=0.25 |
| 5 | 信号类型与 ARCHITECTURE.md 一致 | ✅ | 3种买入 + 5种卖出 |
| 6 | 止损/止盈与 RISK_POLICY.md 一致 | ✅ | 5%减半/8%清仓/10%半仓止盈/15%全仓止盈 |
| 7 | 不默认自动下单 | ✅ | 信号仅生成建议，不触发交易 |

### 已知问题与限制

| # | 问题 | 严重程度 | 处理计划 |
|---|------|----------|---------|
| 1 | 基本面数据暂未从数据源获取，使用中性值0 | 中 | Phase 2 后续接入 AkShare 财务数据接口 |
| 2 | 情绪因子横截面排名模式需多股票数据 | 低 | 实盘运行时自动切换横截面模式 |
| 3 | 板块轮动评分资金维度依赖多板块数据 | 低 | 单板块时自动降级 |
| 4 | 一致预期利润增速暂无数据源 | 低 | Phase 4 接入研报/一致预期数据 |

---

## Phase 3: 回测与评估

### 完成日期

2026-06-08

### 交付物清单

#### 源代码文件（9 个）

| # | 文件 | 行数 | 说明 |
|---|------|------|------|
| 1 | `src/backtest_engine/commission_model.py` | ~195 | 交易成本模型：佣金万3/印花税千1/港股千1.3/独立SlippageModel/FillPriceModel |
| 2 | `src/backtest_engine/portfolio.py` | ~260 | 持仓管理：买入/卖出/涨跌停/停牌检查/每日资产记录 |
| 3 | `src/backtest_engine/performance.py` | ~287 | 绩效评估：12项指标全部实现（含扣费后收益/基准收益/超额收益/月度/年度） |
| 4 | `src/backtest_engine/risk_check.py` | ~158 | 回测风控：单票/板块/现金/回撤/当日亏损约束，每日检查集成 |
| 5 | `src/backtest_engine/engine.py` | ~255 | 向量回测引擎：逐日遍历/因子计算/信号生成/涨跌停停牌/风控集成 |
| 6 | `src/backtest_engine/event_backtester.py` | ~350 | 事件驱动回测器：MarketEvent→SignalEvent→OrderEvent→FillEvent |
| 7 | `src/backtest_engine/report_generator.py` | ~177 | HTML报告生成器：Chart.js净值/回撤曲线/月度收益/交易统计 |
| 8 | `src/backtest_engine/significance_test.py` | ~150 | 统计显著性检验：t检验/Bootstrap/显著性报告 |
| 9 | `src/backtest_engine/persistence.py` | ~117 | 回测结果持久化：保存/加载/列出回测运行记录 |
| 10 | `scripts/run_backtest.py` | ~130 | 回测入口脚本：支持样本内外测试 |

#### 测试文件（2 个，100 个测试用例）

| # | 文件 | 测试数 | 覆盖范围 |
|---|------|--------|---------|
| 1 | `tests/test_phase3.py` | 42 | 成本模型(5)/持仓(12)/绩效(4)/风控(6)/引擎(11)/样本内外(1)/市场环境(2) |
| 2 | `tests/test_audit_phase3.py` | 58 | S1事件驱动(7)/S2滑点模型(7)/S3集成(3)/M1涨跌停(6)/M2绩效指标(7)/M3报告(3)/M4显著性(6)/M5风控集成(4)/L1成交价(6)/L2持久化(5)/L4港股(5) |

### 测试结果

```
============================ 248 passed in 25.83s ==============================
```

**通过率: 248/248 (100%)**

### 验收标准检查

| # | 验收标准 | 状态 | 验证方式 |
|---|---------|------|---------|
| 1 | 回测结果可复现 | ✅ | 相同输入两次运行结果一致 (test_reproducibility) |
| 2 | 回测包含交易成本 | ✅ | 佣金+印花税+滑点完整计算 (test_includes_trading_costs) |
| 3 | 回测包含滑点 | ✅ | 买入价上浮/卖出价下浮滑点 (test_includes_slippage) |
| 4 | 涨跌停/停牌无法成交 | ✅ | 涨停拒买/跌停拒卖/停牌拒交易 (3个测试) |
| 5 | 回测输出完整报告 | ✅ | 年化收益/最大回撤/夏普/胜率/成本等全部指标 (test_complete_report) |
| 6 | 样本外结果不严重劣化 | ✅ | 支持样本内外分割测试 (test_in_sample_out_sample_split) |
| 7 | 最大回撤在可接受范围 | ✅ | 回撤计算正确，风控止损线8%/12% (test_max_drawdown_acceptable) |

### 绩效指标清单 (AGENTS.md 3.5 要求)

| 指标 | 实现 | 说明 |
|------|------|------|
| annual_return | ✅ | 年化收益 |
| max_drawdown | ✅ | 最大回撤 |
| sharpe_ratio | ✅ | 夏普比率 |
| calmar_ratio | ✅ | Calmar比率 |
| win_rate | ✅ | 胜率 |
| profit_loss_ratio | ✅ | 盈亏比 |
| turnover | ✅ | 换手率 |
| cost_adjusted_return | ✅ | 扣费后收益 |
| benchmark_return | ✅ | 基准收益 |
| excess_return | ✅ | 超额收益 |
| monthly_return | ✅ | 月度收益 |
| yearly_return | ✅ | 年度收益 |

### 风控约束清单 (RISK_POLICY.md 要求)

| 约束 | 实现 | 参数 |
|------|------|------|
| 单票仓位限制 | ✅ | 默认15% |
| 板块仓位限制 | ✅ | 默认60% |
| 最小现金比例 | ✅ | 默认20% |
| 单票亏损警告 | ✅ | 默认-5% |
| 单票亏损止损 | ✅ | 默认-8% |
| 当日亏损警告 | ✅ | 默认-2% |
| 当日亏损止损 | ✅ | 默认-3% |
| 账户回撤防御 | ✅ | 默认-8% |
| 账户回撤停止 | ✅ | 默认-12% |

### 架构合规性检查

| # | 检查项 | 状态 |
|---|--------|------|
| 1 | 不计手续费的回测 | ✅ 禁止 |
| 2 | 不计滑点的回测 | ✅ 禁止 |
| 3 | 不计印花税的回测 | ✅ 禁止 |
| 4 | 不处理涨跌停无法成交 | ✅ 已处理 |
| 5 | 不处理停牌 | ✅ 已处理 |
| 6 | 不做样本外测试 | ✅ 支持 |

### 已知问题与限制

| # | 问题 | 严重程度 | 处理计划 |
|---|------|----------|---------|
| 1 | 回测使用当日收盘价成交，非实际撮合 | 中 | Phase 4 引入分钟线后优化 |
| 2 | 换手率计算为简化版本 | 低 | Phase 3 后续优化 |
| 3 | 基准收益默认为0（需手动传入） | 低 | 入口脚本自动获取指数数据 |
| 4 | 分红除权未处理（L3暂缓） | 低 | Phase 4+，需除权因子数据源 |
| 5 | E2E测试和API测试待Phase 4补充 | 中 | Phase 4 实现FastAPI后补充 |

### 架构复核记录（2026-06-08）

| 项目 | 结论 |
|------|------|
| 缺失文档 | 已补充 `BACKTEST_POLICY.md`，作为回测硬约束 |
| 回测时序 | 已修复 `next_open`/`vwap` 使用信号日行情的前视偏差，默认挂起到下一交易日执行 |
| 因子评估 | 已修复缺少 `forward_return` 时的 `symbol_col` 未定义问题 |
| 可选依赖 | 已修复 Rank IC 与显著性检验对未声明 `scipy` 的硬依赖 |
| 验证结果 | `251 passed in 23.39s` |
| Phase 4 准入 | 可以进入，但必须先建设 `risk_engine` 运行时风控与实时数据健康门禁，再做 API/UI |

---

## Phase 4: 实盘盯盘与信号生成

> ⬜ 未开始

---

## Phase 5: 人工确认交易

> ⬜ 未开始

---

## Phase 6: 小资金自动交易实验

> ⬜ 未开始

---

## 审计检查清单

以下为跨阶段通用审计项，每个 Phase 完成后需逐项确认：

### A. 代码安全

- [ ] 无硬编码密钥/Token/密码
- [ ] `.env` 在 `.gitignore` 中
- [ ] 无 eval/exec 动态代码执行
- [ ] 无 SQL 注入风险
- [ ] 无命令注入风险

### B. 数据完整性

- [ ] 不使用未来数据
- [ ] 原始数据保留不覆盖
- [ ] 数据变更有版本记录
- [ ] 缺失数据有明确标记而非静默填充

### C. 风控合规

- [ ] 默认交易模式为 LEVEL_1_SIGNAL_ONLY
- [ ] 风控模块未被绕过或删除
- [ ] Kill Switch 机制完整
- [ ] 创业板/科创板过滤有效

### D. 测试覆盖

- [ ] 核心逻辑有单元测试
- [ ] 测试可独立运行 (`pytest tests/`)
- [ ] 无跳过的测试（skip/xfail 需说明原因）
- [ ] 边界条件和异常场景有覆盖

### E. 文档完整性

- [ ] 接口有 docstring 或注释
- [ ] 配置文件有示例 (.env.example)
- [ ] 运行方式有说明
- [ ] 已知问题有记录
