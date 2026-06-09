# 数据契约 (DATA_CONTRACTS.md)

> 本文档定义量化交易系统中所有数据的标准格式、接口规范和质量要求。
> 任何数据 Agent、策略或模块必须遵守本契约，禁止自行定义非标准数据字段。

---

## 1. 数据源接口契约

所有行情数据提供者必须实现统一抽象接口，保证数据源可插拔。

### 1.1 日线行情接口

```python
class DailyBarProvider:
    def get_daily_bars(
        self,
        symbols: List[str],
        start_date: str,      # YYYYMMDD
        end_date: str         # YYYYMMDD
    ) -> pd.DataFrame:
        """
        返回字段必须包含：
        - symbol: str           股票代码（如 002463.SZ）
        - market: str           市场 (SH/SZ/HK)
        - trade_date: str       YYYYMMDD
        - open: float
        - high: float
        - low: float
        - close: float
        - pre_close: float
        - volume: int           股
        - amount: float         元
        - turnover_rate: float  换手率(%)
        - adj_factor: float     复权因子（前复权基准为最新交易日）
        - limit_up: float       涨停价
        - limit_down: float     跌停价
        - is_suspended: bool    是否停牌
        - is_st: bool           是否ST
        """
```

### 1.2 分钟线接口

```python
class IntradayBarProvider:
    def get_intraday_bars(
        self,
        symbols: List[str],
        interval: str,         # "1m", "5m", "15m", "30m", "60m"
        start_datetime: str,   # "YYYYMMDD HH:MM:SS"
        end_datetime: str
    ) -> pd.DataFrame:
        """
        返回字段：
        - symbol
        - market
        - datetime
        - open
        - high
        - low
        - close
        - volume
        - amount
        """
```

### 1.3 实时行情接口

```python
class RealtimeQuoteProvider:
    def get_realtime_quotes(self, symbols: List[str]) -> pd.DataFrame:
        """
        返回字段：
        - symbol
        - market
        - datetime
        - last_price
        - bid_price_1 .. bid_price_5
        - ask_price_1 .. ask_price_5
        - bid_volume_1 .. bid_volume_5
        - ask_volume_1 .. ask_volume_5
        - volume
        - amount
        - pct_change
        - status: str  "NORMAL","LIMIT_UP","LIMIT_DOWN","SUSPENDED","UNKNOWN"
        """
```

### 1.4 基础信息接口

```python
class ReferenceDataProvider:
    def get_stock_info(self, symbols: List[str]) -> pd.DataFrame:
        """
        字段：
        - symbol
        - name
        - market
        - industry_sw          申万一级行业
        - industry_sw_detail   申万二级行业
        - list_date
        - total_shares
        - float_shares
        - is_st
        - is_hs300
        - board_type           主板/中小板/创业板/科创板
        """
```

---

## 2. 数据质量契约

### 2.1 数据完整性要求

- 日线数据缺失率不得超过 1%（按交易日计算）。
- 若单只股票连续缺失超过 3 个交易日，必须标记并在报告中高亮。
- 关键字段（open, high, low, close, volume）不允许为 NaN。
- 非关键字段缺失时，必须保留 NaN，不得静默填充。

### 2.2 复权与价格对齐

- 所有价格统一使用 **前复权**。
- 复权因子 `adj_factor` 必须以最新交易日为基准（即当天 adj_factor = 1）。
- 若使用不复权价格，必须在字段名显式标识为 `_raw`。

### 2.3 交易日历

- 统一使用中国 A 股交易日历（含调休日处理）。
- 港股交易日历单独维护，两者对齐时以 A 股交易日为主，港股独立存储。
- 节假日、非交易日返回的 DataFrame 行数应为 0，不得抛出异常。

### 2.4 停牌处理

- `is_suspended = True` 时，行情数据仍保留最后成交价，但 `volume = 0`。
- 回测系统中，停牌期间禁止生成任何交易。
- 数据清洗阶段必须标记停牌区间。

---

## 3. 因子数据契约

因子计算结果统一存储于因子特征表，字段命名遵循以下规则：

```
{factor_name}__{window}__{type}
示例：close_ma5, volume_ratio_20d, rsi_14d
```

### 3.1 因子表结构

- `symbol`
- `trade_date`
- `factor_value`
- `factor_name`
- `factor_version`   每次计算引擎更新时递增
- `created_at`

### 3.2 因子计算数据源

- 所有因子必须从清洗后的日线或分钟线计算，不允许直接从 `raw` 表读取。
- 因子计算过程中，不得使用未来信息（包括但不限于：当日收盘价用于计算当日开盘因子、财务公告日期前使用公告数据等）。

---

## 4. 信号数据契约

策略产生的交易信号必须序列化至如下结构：

```python
class Signal(BaseModel):
    signal_id: str
    symbol: str
    trade_date: str
    strategy: str
    signal_type: str          # BUY / SELL / HOLD
    sub_type: str             # BREAKOUT / PULLBACK / AMBUSH / STOP_LOSS ...
    score: float              # 触发时总评分
    price_trigger: float      # 信号触发参考价
    reason: str               # 人类可读的理由（不超过200字）
    stop_loss_price: float
    take_profit_price: float
    position_pct: float       # 建议仓位比例
    risk_note: str
    created_at: str
```

---

## 5. 订单契约

遵循 `ARCHITECTURE.md` 中订单结构。额外约束：

- `order_id` 必须全局唯一，格式 `ORD_{YYYYMMDD}_{6位随机码}`
- `side` 枚举：`BUY`, `SELL`
- `price_type` 枚举：`LIMIT`, `MARKET`
- 所有订单必须关联 `signal_id` 和 `risk_check_id`
- 订单状态流转：`CREATED -> RISK_CHECKED -> CONFIRMED -> SENT -> FILLED / REJECTED / CANCELLED`

---

## 6. 数据版本与溯源

- `data_storage/raw` 保留原始数据，按日期分区。
- `data_storage/cleaned` 保留清洗后数据，新增 `data_version` 列。
- 所有数据加载必须记录日志，包括：来源、日期范围、行数、耗时。
- 数据更新必须触发 `data_quality_report` 自动生成。

---

## 7. 多市场与港股通

- 港股代码统一为5位数字（如 `00981`），市场标记 `HK`。
- 港股行情货币为港元，需在数据落库时增加 `currency` 字段。
- 所有涉及港股价格的比较、组合计算，必须经过汇率换算（汇率取当日央行中间价或 Wind 收盘价）。

---

## 8. 禁止事项

1. 策略/因子直接调用某个具体数据源 API（必须通过 Gateway）。
2. 对缺失价格进行前向填充（ffill）而不打标。
3. 将未经验证的外部数据直接送入策略引擎。
4. 在数据更新过程中覆盖历史清洗数据而不保留版本。
5. 使用未记录来源的研报/新闻数据生成信号。
