from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class DailyBar(BaseModel):
    symbol: str
    market: str
    trade_date: str  # YYYYMMDD
    open: float
    high: float
    low: float
    close: float
    pre_close: Optional[float] = None
    volume: Optional[int] = None  # 股，可为None（数据缺失）
    amount: Optional[float] = None  # 元，可为None（数据缺失）
    turnover_rate: Optional[float] = None  # %
    adj_factor: Optional[float] = None
    limit_up: Optional[float] = None
    limit_down: Optional[float] = None
    is_suspended: bool = False
    is_st: bool = False
    is_data_missing: bool = False
    pct_change: Optional[float] = None


class StockInfo(BaseModel):
    symbol: str
    name: str
    market: str
    board_type: str  # mainboard / sme / chinext / star
    is_st: bool = False
    list_date: Optional[str] = None
    industry_sw: Optional[str] = None  # 申万一级行业
    industry_sw_detail: Optional[str] = None  # 申万二级行业
    total_shares: Optional[float] = None  # 总股本
    float_shares: Optional[float] = None  # 流通股本
    is_hs300: bool = False  # 是否沪深300成分


class IntradayBar(BaseModel):
    """分钟线数据结构 (DATA_CONTRACTS 1.2)"""
    symbol: str
    market: str
    datetime: str  # YYYYMMDD HH:MM:SS
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float


class RealtimeQuote(BaseModel):
    """实时行情数据结构 (DATA_CONTRACTS 1.3)"""
    symbol: str
    market: str
    datetime: str
    last_price: float
    bid_price_1: Optional[float] = None
    bid_price_2: Optional[float] = None
    bid_price_3: Optional[float] = None
    bid_price_4: Optional[float] = None
    bid_price_5: Optional[float] = None
    ask_price_1: Optional[float] = None
    ask_price_2: Optional[float] = None
    ask_price_3: Optional[float] = None
    ask_price_4: Optional[float] = None
    ask_price_5: Optional[float] = None
    bid_volume_1: Optional[int] = None
    bid_volume_2: Optional[int] = None
    bid_volume_3: Optional[int] = None
    bid_volume_4: Optional[int] = None
    bid_volume_5: Optional[int] = None
    ask_volume_1: Optional[int] = None
    ask_volume_2: Optional[int] = None
    ask_volume_3: Optional[int] = None
    ask_volume_4: Optional[int] = None
    ask_volume_5: Optional[int] = None
    volume: int = 0
    amount: float = 0.0
    pct_change: Optional[float] = None
    status: str = "UNKNOWN"  # NORMAL / LIMIT_UP / LIMIT_DOWN / SUSPENDED / UNKNOWN


class Order(BaseModel):
    """订单数据结构 (DATA_CONTRACTS 5, EXECUTION_POLICY 3)"""
    order_id: str  # 格式 ORD_{YYYYMMDD}_{6位随机码}
    symbol: str
    market: str
    side: str  # BUY / SELL
    price_type: str  # LIMIT / MARKET
    limit_price: float
    quantity: int
    strategy_name: str
    signal_id: str
    risk_check_id: str
    status: str = "CREATED"  # CREATED / RISK_CHECKED / CONFIRMED / SENT / FILLED / PARTIALLY_FILLED / REJECTED / CANCELLED
    created_at: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    updated_at: Optional[str] = None
    # Phase 5: EXECUTION_POLICY 4.1 订单必须包含
    stock_name: str = ""
    sector: str = ""
    stop_loss_price: float = 0.0
    take_profit_price: float = 0.0
    position_pct: float = 0.0  # 建议仓位比例
    risk_note: str = ""
    market_status: str = "NORMAL"  # NORMAL / LIMIT_UP / LIMIT_DOWN / SUSPENDED (M1 fix)
    confirmed_by: Optional[str] = None  # 确认人
    confirmed_at: Optional[str] = None  # 确认时间
    fill_price: Optional[float] = None  # 成交价
    fill_quantity: Optional[int] = None  # 成交数量
    fill_at: Optional[str] = None  # 成交时间
    reject_reason: Optional[str] = None  # 拒绝原因


class OrderDraft(BaseModel):
    """订单草稿 (EXECUTION_POLICY 3)

    从信号生成，尚未经过风控检查和人工确认。
    """
    symbol: str
    market: str = "SZ"
    side: str  # BUY / SELL
    price_type: str = "LIMIT"
    limit_price: float
    quantity: int
    strategy_name: str
    signal_id: str
    stock_name: str = ""
    sector: str = ""
    stop_loss_price: float = 0.0
    take_profit_price: float = 0.0
    position_pct: float = 0.0
    risk_note: str = ""


class TradeRecord(BaseModel):
    """成交记录 (EXECUTION_POLICY 1.5 可追溯)"""
    trade_id: str
    order_id: str
    symbol: str
    market: str
    side: str
    price: float
    quantity: int
    amount: float  # 成交金额
    commission: float = 0.0  # 手续费
    stamp_duty: float = 0.0  # 印花税
    net_amount: float = 0.0  # 净金额
    signal_id: str = ""
    risk_check_id: str = ""
    strategy_name: str = ""
    env: str = "paper"  # paper / live
    traded_at: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class AccountInfo(BaseModel):
    """账户信息 (EXECUTION_POLICY 6)"""
    total_assets: float = 0.0
    cash: float = 0.0
    market_value: float = 0.0
    available_cash: float = 0.0
    daily_pnl: float = 0.0
    daily_pnl_pct: float = 0.0


class Position(BaseModel):
    """持仓信息 (EXECUTION_POLICY 6)"""
    symbol: str
    market: str = "SZ"
    name: str = ""
    quantity: int = 0
    available_quantity: int = 0  # 可卖数量
    cost_price: float = 0.0
    current_price: float = 0.0
    market_value: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    sector: str = ""


class DataQualityReport(BaseModel):
    symbol: str
    start_date: str
    end_date: str
    total_rows: int
    missing_open: int = 0
    missing_high: int = 0
    missing_low: int = 0
    missing_close: int = 0
    missing_volume: int = 0
    max_consecutive_missing: int = 0
    invalid_price_rows: int = 0  # high < low or price <= 0
    limit_up_days: int = 0
    limit_down_days: int = 0
    suspended_days: int = 0
    completeness_pct: float = Field(default=0.0, description="数据完整率 %")
    issues: list[str] = Field(default_factory=list)

    @property
    def is_acceptable(self) -> bool:
        if self.total_rows == 0:
            return False
        if self.completeness_pct < 99.0:
            return False
        if self.invalid_price_rows > 0:
            return False
        return True


class DataMissingReport(BaseModel):
    """数据缺失报告 (AGENTS.md 3.2)"""
    generated_at: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    total_symbols: int = 0
    symbols_with_missing: int = 0
    missing_details: list[dict] = Field(default_factory=list)
    summary: str = ""


class DataDelayReport(BaseModel):
    """数据延迟报告 (AGENTS.md 3.2)"""
    generated_at: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    provider: str = ""
    total_symbols: int = 0
    avg_latency_seconds: float = 0.0
    max_latency_seconds: float = 0.0
    delayed_symbols: list[dict] = Field(default_factory=list)
    is_acceptable: bool = True  # 延迟是否在可接受范围内


class Signal(BaseModel):
    """信号数据结构 (AGENTS.md 2.4 可解释性要求)"""
    signal_id: str
    symbol: str
    stock_name: str = ""  # AGENTS.md 2.4: 股票名称
    sector: str = ""  # AGENTS.md 2.4: 所属板块
    trade_date: str
    strategy: str
    signal_type: str  # BUY / SELL / HOLD
    sub_type: str  # BREAKOUT / PULLBACK / AMBUSH / STOP_LOSS / HOLD_WATCH ...
    score: float
    price_trigger: float
    reason: str
    stop_loss_price: float
    take_profit_price: float
    position_pct: float
    risk_note: str
    created_at: str
