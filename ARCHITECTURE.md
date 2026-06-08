# ARCHITECTURE.md

## 1. 系统概览

本项目是一个面向 A股、港股的量化交易 Agent 系统。

系统由以下核心层组成：

```
数据层
 ↓
特征与因子层
 ↓
策略层
 ↓
回测层
 ↓
信号层
 ↓
风控层
 ↓
执行层
 ↓
报告层
```

核心目标：

1. 数据可插拔
2. 策略可扩展
3. 风控可强制
4. 回测可复现
5. 实盘可追踪
6. 信号可解释
7. 下单可控制

---

## 2. 总体架构

```
quant-trading-agent
├── data_gateway
│   ├── market_data
│   ├── fundamental_data
│   ├── news_data
│   ├── announcement_data
│   └── calendar_data
│
├── data_storage
│   ├── raw
│   ├── cleaned
│   ├── feature_store
│   └── signal_store
│
├── factor_engine
│   ├── technical_factors
│   ├── fundamental_factors
│   ├── sentiment_factors
│   ├── theme_factors
│   └── factor_evaluation
│
├── strategy_engine
│   ├── stock_pool
│   ├── scoring_model
│   ├── timing_model
│   ├── portfolio_model
│   └── signal_generator
│
├── backtest_engine
│   ├── event_backtester
│   ├── vector_backtester
│   ├── cost_model
│   ├── slippage_model
│   └── report_generator
│
├── risk_engine
│   ├── position_risk
│   ├── sector_risk
│   ├── drawdown_risk
│   ├── liquidity_risk
│   ├── trading_permission
│   └── kill_switch
│
├── execution_engine
│   ├── paper_trading
│   ├── order_router
│   ├── broker_adapter
│   ├── order_checker
│   └── trade_recorder
│
├── agent_orchestrator
│   ├── research_agent
│   ├── data_agent
│   ├── strategy_agent
│   ├── risk_agent
│   ├── execution_agent
│   └── report_agent
│
└── ui_report
    ├── daily_plan
    ├── intraday_alert
    ├── portfolio_report
    └── backtest_report
```

---

## 3. 数据层设计

### 3.1 数据源分层

数据源必须可插拔，禁止策略直接依赖某一个数据供应商。

统一接口：

```python
class MarketDataProvider:
    def get_daily_bars(self, symbols, start_date, end_date):
        pass

    def get_intraday_bars(self, symbols, interval):
        pass

    def get_realtime_quotes(self, symbols):
        pass

    def get_limit_status(self, symbols):
        pass

    def get_suspend_status(self, symbols):
        pass
```

**初期免费数据源：**

- AkShare
- Tushare free
- Eastmoney public data
- Sina quote
- Yahoo Finance for HK/US reference

**后续可替换付费数据源：**

- Tushare Pro
- Wind
- Choice
- 聚宽
- 米筐
- 掘金
- 富途 OpenAPI
- 券商 Level2

---

### 3.2 数据标准化

所有行情数据必须统一成以下结构：

**日线数据结构：**

| 字段 | 类型 | 说明 |
|------|------|------|
| symbol | str | 股票代码 |
| market | str | 市场 |
| trade_date | str | 交易日期 |
| open | float | 开盘价 |
| high | float | 最高价 |
| low | float | 最低价 |
| close | float | 收盘价 |
| pre_close | float | 前收盘价 |
| volume | int | 成交量（股） |
| amount | float | 成交额（元） |
| turnover_rate | float | 换手率(%) |
| adj_factor | float | 复权因子 |
| limit_up | float | 涨停价 |
| limit_down | float | 跌停价 |
| is_suspended | bool | 是否停牌 |
| is_st | bool | 是否ST |

**分钟数据结构：**

| 字段 | 类型 | 说明 |
|------|------|------|
| symbol | str | 股票代码 |
| market | str | 市场 |
| datetime | str | 时间戳 |
| open | float | 开盘价 |
| high | float | 最高价 |
| low | float | 最低价 |
| close | float | 收盘价 |
| volume | int | 成交量 |
| amount | float | 成交额 |

**实时行情结构：**

| 字段 | 类型 | 说明 |
|------|------|------|
| symbol | str | 股票代码 |
| market | str | 市场 |
| datetime | str | 时间戳 |
| last_price | float | 最新价 |
| bid_price_1 | float | 买一价 |
| ask_price_1 | float | 卖一价 |
| bid_volume_1 | int | 买一量 |
| ask_volume_1 | int | 卖一量 |
| volume | int | 成交量 |
| amount | float | 成交额 |
| pct_change | float | 涨跌幅 |
| status | str | 状态 |

---

## 4. 股票池设计

### 4.1 基础股票池

由于用户当前不能买创业板和科创板，初始股票池必须排除：

- `300xxx` 创业板
- `301xxx` 创业板
- `688xxx` 科创板
- `689xxx` 科创板

允许：

- `000xxx` 深主板
- `001xxx` 深主板
- `002xxx` 中小板
- `600xxx` 沪主板
- `601xxx` 沪主板
- `603xxx` 沪主板
- `605xxx` 沪主板
- 港股通标的

---

### 4.2 半导体主题股票池

**PCB/CCL：**

- 002463 沪电股份
- 002916 深南电路
- 600183 生益科技
- 603228 景旺电子

**先进封装/封测：**

- 600584 长电科技
- 002156 通富微电
- 002185 华天科技
- 000021 深科技

**设备/材料：**

- 002371 北方华创
- 002409 雅克科技
- 603650 彤程新材
- 600206 有研新材
- 603690 至纯科技
- 600641 万业企业

**光模块/CPO：**

- 002281 光迅科技
- 000988 华工科技
- 603083 剑桥科技
- 600487 亨通光电

**存储/HBM：**

- 603986 兆易创新
- 000021 深科技
- 600667 太极实业

**港股：**

- 00981 中芯国际

---

## 5. 因子层设计

### 5.1 总评分模型

策略总评分：

```
total_score = (
    0.25 * policy_score
  + 0.30 * sentiment_score
  + 0.20 * fundamental_score
  + 0.25 * trend_score
)
```

四类因子：

- `policy_score`: 政策主题分
- `sentiment_score`: 情绪资金分
- `fundamental_score`: 基本面分
- `trend_score`: 技术趋势分

---

### 5.2 政策主题分

政策主题分是半静态因子，由人工维护或 LLM 辅助更新。

```python
THEME_POLICY_WEIGHT = {
    "semiconductor_equipment": 100,
    "semiconductor_material": 95,
    "advanced_packaging": 95,
    "pcb_ccl": 90,
    "memory_hbm": 85,
    "optical_module_cpo": 80,
    "chip_design": 65,
    "traditional_packaging": 60,
}
```

每只股票可以绑定多个主题，取最高分或加权平均。

---

### 5.3 情绪资金分

核心指标：

- `volume_ratio`
- `amount_ratio`
- `turnover_ratio`
- `relative_strength`
- `sector_strength`
- `limit_up_count`
- `large_order_flow`

简化公式：

```
sentiment_score = (
    25 * rank(volume_ratio)
  + 25 * rank(amount_ratio)
  + 25 * rank(relative_strength)
  + 25 * rank(sector_strength)
)
```

---

### 5.4 基本面分

核心指标：

- `revenue_yoy`
- `net_profit_yoy`
- `gross_margin_change`
- `roe`
- `consensus_profit_growth`
- `industry_prosperity`

简化公式：

```
fundamental_score = (
    0.25 * rank(revenue_yoy)
  + 0.25 * rank(net_profit_yoy)
  + 0.20 * rank(gross_margin_change)
  + 0.15 * rank(roe)
  + 0.15 * rank(consensus_profit_growth)
)
```

---

### 5.5 技术趋势分

核心指标：

- `close > ma5`
- `close > ma10`
- `close > ma20`
- `ma5 > ma10 > ma20`
- `near_20d_high`
- `volume_breakout`
- `pullback_to_ma10`
- `atr_volatility`

简化公式：

```python
trend_score = 0
if close > ma5:
    trend_score += 15
if close > ma10:
    trend_score += 15
if close > ma20:
    trend_score += 20
if ma5 > ma10 > ma20:
    trend_score += 20
if close >= highest_20 * 0.95:
    trend_score += 15
if volume > volume_ma5 * 1.3:
    trend_score += 15
```

---

## 6. 策略层设计

### 6.1 买入信号

**趋势突破买入**

```python
buy_breakout = (
    total_score > 80
    and close > highest_20 * 0.98
    and close > ma5
    and close > ma10
    and volume > volume_ma5 * 1.5
    and sector_strength > 0
    and pct_change < 7
)
```

**回踩低吸买入**

```python
buy_pullback = (
    total_score > 75
    and close > ma20
    and low <= ma10 * 1.02
    and close > ma10
    and volume < volume_ma5 * 1.2
    and sector_strength >= -1
)
```

**材料设备埋伏买入**

```python
buy_ambush = (
    policy_score >= 90
    and fundamental_score >= 60
    and close > ma20
    and close > ma60
    and volume > volume_ma20 * 1.2
    and total_score > 68
)
```

---

### 6.2 卖出信号

**止损**

```python
sell_stop_loss = (
    current_return <= -0.05
    and close < ma10
)
```

**趋势破坏**

```python
sell_trend_break = (
    close < ma20
    and volume > volume_ma5 * 1.2
)
```

**情绪退潮**

```python
sell_sentiment_fade = (
    sector_strength < -2
    and pct_change < -3
    and volume > volume_ma5
)
```

**止盈**

```python
sell_take_profit = (
    current_return >= 0.15
    and close < ma5
)
```

---

## 7. 风控层设计

### 7.1 单票限制

- 单只股票最大仓位：15%
- 单只埋伏仓最大仓位：8%
- 单只光模块/存储弹性仓最大仓位：10%
- 单只亏损超过 5%：减半
- 单只亏损超过 8%：清仓或强制人工确认

---

### 7.2 板块限制

- 半导体总仓位最大：60%
- PCB/CCL 最大仓位：25%
- 封测/先进封装最大仓位：20%
- 设备/材料最大仓位：20%
- 光模块最大仓位：15%
- 存储最大仓位：15%
- 港股半导体最大仓位：20%
- 现金最低比例：20%

---

### 7.3 账户限制

- 单日账户亏损超过 2%：停止开新仓
- 单日账户亏损超过 3%：只允许减仓，不允许买入
- 账户最大回撤超过 8%：进入防守模式
- 账户最大回撤超过 12%：停止实盘交易，转入复盘模式

---

## 8. 执行层设计

### 8.1 执行流程

```
Signal Generator
       ↓
Risk Engine
       ↓
Order Checker
       ↓
Human Confirmation
       ↓
Broker Adapter
       ↓
Trade Recorder
```

真实交易前必须经过：

1. 信号通过
2. 风控通过
3. 订单检查通过
4. 用户确认通过

---

### 8.2 订单结构

| 字段 | 类型 | 说明 |
|------|------|------|
| order_id | str | 订单ID |
| symbol | str | 股票代码 |
| market | str | 市场 |
| side | str | 买卖方向 |
| price_type | str | 价格类型 |
| limit_price | float | 限价 |
| quantity | int | 数量 |
| strategy_name | str | 策略名称 |
| signal_id | str | 信号ID |
| risk_check_id | str | 风控检查ID |
| status | str | 状态 |
| created_at | str | 创建时间 |
| updated_at | str | 更新时间 |

---

## 9. 报告层设计

### 9.1 每日盘前报告

必须包括：

- 市场状态
- 外围市场
- 政策新闻
- 半导体细分方向热度
- 今日候选股
- 持仓风险
- 买入计划
- 卖出计划
- 禁止交易列表

---

### 9.2 盘中提醒

必须包括：

- 股票代码
- 股票名称
- 触发信号
- 触发价格
- 建议动作
- 建议仓位
- 止损位
- 止盈位
- 触发原因
- 风险提示

---

### 9.3 盘后复盘

必须包括：

- 今日收益
- 组合收益
- 基准收益
- 超额收益
- 最大回撤
- 触发信号统计
- 成交统计
- 未成交原因
- 策略表现
- 明日计划

---

## 10. 技术栈建议

### 10.1 初期

- Python
- Pandas
- NumPy
- DuckDB
- SQLite
- AkShare
- Tushare
- FastAPI
- APScheduler
- Streamlit
- Plotly
- Loguru
- Pydantic

### 10.2 中期

- PostgreSQL
- Redis
- ClickHouse
- Qlib
- Backtrader
- VectorBT
- Airflow / Prefect
- Docker
- Grafana
- Prometheus

### 10.3 后期

- Kafka
- Ray
- Polars
- TimescaleDB
- Kubernetes
- 券商交易 API
- 富途 OpenAPI
- 自建监控系统

---

## 11. MVP 版本边界

**第一版不做：**

1. 全自动下单
2. 高频交易
3. Level2 深度盘口
4. 大模型直接决定买卖
5. 复杂多因子优化器
6. 实时新闻情绪驱动下单
7. 杠杆交易
8. 融资融券
9. 期权期货
10. 多账户管理

**第一版只做：**

1. 股票池管理
2. 日线数据获取
3. 基础因子计算
4. 策略评分
5. 回测
6. 持仓导入
7. 每日买卖建议
8. 人工确认交易
