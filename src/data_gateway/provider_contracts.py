"""Provider 合约层 — 定义数据能力枚举、标准返回模型和 Provider 协议。

本模块是 live closed-loop 的数据契约基础：
- DataCapability: provider 能力枚举
- ProviderResult: 统一返回模型（含 fallback_chain）
- ProviderHealth: provider 诊断结果
- LiveDataProvider: provider 协议（Protocol）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

import pandas as pd


class DataCapability(str, Enum):
    """数据能力枚举"""
    REALTIME_QUOTES = "realtime_quotes"
    DAILY_BARS = "daily_bars"
    FUNDAMENTALS = "fundamentals"
    STOCK_INFO = "stock_info"
    INTRADAY_BARS = "intraday_bars"


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
    error: str = ""


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
