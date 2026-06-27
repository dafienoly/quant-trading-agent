"""Provider 合约层 — 定义数据能力枚举、标准返回模型和 Provider 协议。

本模块是 live closed-loop 的数据契约基础：
- DataCapability: provider 能力枚举
- ProviderResult: 统一返回模型（含 fallback_chain）
- ProviderHealth: provider 诊断结果
- LiveDataProvider: provider 协议（Protocol）
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Protocol

import pandas as pd


class DataCapability(str, Enum):
    """数据能力枚举"""
    REALTIME_QUOTES = "realtime_quotes"
    DAILY_BARS = "daily_bars"
    INDEX_QUOTES = "index_quotes"
    INDEX_BARS = "index_bars"
    ETF_QUOTES = "etf_quotes"
    ETF_BARS = "etf_bars"
    SECTOR_QUOTES = "sector_quotes"
    TRADE_CALENDAR = "trade_calendar"
    FUNDAMENTALS = "fundamentals"
    STOCK_INFO = "stock_info"
    INTRADAY_BARS = "intraday_bars"


class MarketDataType(str, Enum):
    SOURCE_HEALTH = "source_health"
    SOURCE_LIST = "source_list"
    STOCK_QUOTE = "stock_quote"
    INDEX_QUOTE = "index_quote"
    ETF_QUOTE = "etf_quote"
    SECTOR_QUOTE = "sector_quote"
    STOCK_BARS = "stock_bars"
    INDEX_BARS = "index_bars"
    ETF_BARS = "etf_bars"
    TRADE_CALENDAR = "trade_calendar"


class DataUsage(str, Enum):
    DISPLAY = "display"
    ANALYSIS = "analysis"
    SIGNAL = "signal"
    EXECUTION = "execution"


class DataQualityStatus(str, Enum):
    COMPLETE = "complete"
    STALE = "stale"
    INCOMPLETE = "incomplete"
    UNAVAILABLE = "unavailable"
    INCONSISTENT = "inconsistent"
    MOCK = "mock"


class ProviderStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    ERROR = "error"
    CIRCUIT_OPEN = "circuit_open"
    UNKNOWN = "unknown"


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


@dataclass(frozen=True)
class QuoteSnapshot:
    symbol: str
    name: str
    price: float | None
    prev_close: float | None
    open: float | None
    high: float | None
    low: float | None
    volume: float | int | None
    amount: float | None
    change: float | None
    pct_change: float | None
    timestamp: str
    trading_day: str
    currency: str = "CNY"
    timezone: str = "Asia/Shanghai"
    source_volume_unit: str = "share"
    status: str = "NORMAL"

    def to_dict(self) -> dict[str, Any]:
        return _json_value(asdict(self))


@dataclass(frozen=True)
class Bar:
    trade_date: str
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: float | int | None
    amount: float | None
    raw_close: float | None = None
    adjusted_close: float | None = None
    is_suspended: bool = False

    def to_dict(self) -> dict[str, Any]:
        return _json_value(asdict(self))


@dataclass(frozen=True)
class BarSeries:
    symbol: str
    frequency: str
    adjust: str
    bars: list[Bar]
    currency: str = "CNY"
    timezone: str = "Asia/Shanghai"

    def to_dict(self) -> dict[str, Any]:
        return _json_value(asdict(self))


@dataclass(frozen=True)
class DataSourceHealth:
    provider_name: str
    status: ProviderStatus
    capabilities: list[str] = field(default_factory=list)
    last_success_at: str = ""
    last_error_at: str = ""
    latency_ms: float = 0.0
    rate_limit_status: str = "unknown"
    error_summary: str = ""
    field_coverage: dict[str, bool] = field(default_factory=dict)
    fallback_activation_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return _json_value(asdict(self))


@dataclass(frozen=True)
class MarketDataEnvelope:
    request_id: str
    source: str
    provider_name: str
    data_type: MarketDataType
    fetched_at: str
    latency_ms: float
    cached: bool
    stale: bool
    mock: bool
    quality_status: DataQualityStatus
    blocking_for_signal: bool
    payload: Any
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    fallback_used: bool = False
    fallback_reason: str = ""
    cache_status: str = "miss"
    blocking_reason: str = ""
    provider_chain: list[str] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""
    requested_usage: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _json_value(asdict(self))


@dataclass
class ProviderResult:
    """Provider 统一返回模型

    所有 provider 通过 DataProviderHub.fetch_with_fallback() 返回此结构。
    """
    status: str  # "ok" | "failed"
    provider: str
    capability: DataCapability
    data: pd.DataFrame
    messages: list[str] = field(default_factory=list)
    error: str = ""
    elapsed_ms: float = 0.0
    fallback_chain: list[str] = field(default_factory=list)
    request_id: str = ""
    started_at: str = ""
    completed_at: str = ""
    fallback_used: bool = False
    fallback_reason: str = ""


@dataclass
class ProviderHealth:
    """Provider 诊断结果"""
    provider: str
    capability: DataCapability
    status: str  # "OK" | "ERROR" | "CIRCUIT_OPEN"
    latency_ms: float
    row_count: int
    field_coverage: dict[str, bool] = field(default_factory=dict)
    last_success_at: str = ""
    last_error_at: str = ""
    rate_limit_status: str = "unknown"
    error: str = ""
    fallback_activation_count: int = 0


class LiveDataProvider(Protocol):
    """Live data provider 协议

    所有 provider 必须实现此协议，由 DataProviderHub 统一调度。
    """
    name: str

    def get_realtime_quotes(self, symbols: list[str]) -> pd.DataFrame:
        """获取实时行情"""
        ...

    def get_daily_bars(
        self,
        symbols: list[str],
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        """获取历史日线"""
        ...

    def get_fundamentals(self, symbols: list[str]) -> pd.DataFrame:
        """获取基础财务数据"""
        ...
