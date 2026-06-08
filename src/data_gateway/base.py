from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

import pandas as pd


class MarketDataProvider(ABC):
    """行情数据统一抽象接口 (DATA_CONTRACTS 1.1~1.4)"""

    @abstractmethod
    def get_daily_bars(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        """获取日线行情数据 (DailyBarProvider)，返回标准格式 DataFrame"""

    @abstractmethod
    def get_index_daily_bars(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """获取指数日线行情数据"""

    def get_intraday_bars(
        self,
        symbols: List[str],
        interval: str,
        start_datetime: str,
        end_datetime: str,
    ) -> pd.DataFrame:
        """获取分钟线行情数据 (IntradayBarProvider, Phase 4 实现)"""
        raise NotImplementedError("Intraday bars will be implemented in Phase 4")

    def get_realtime_quotes(self, symbols: List[str]) -> pd.DataFrame:
        """获取实时行情 (RealtimeQuoteProvider, Phase 4 实现)"""
        raise NotImplementedError("Realtime quotes will be implemented in Phase 4")

    @abstractmethod
    def get_stock_list(self) -> pd.DataFrame:
        """获取全量 A 股股票列表 (ReferenceDataProvider)"""

    @abstractmethod
    def get_trade_dates(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """获取交易日历"""

    def get_stock_info(self, symbols: List[str]) -> pd.DataFrame:
        """获取股票基础信息 (ReferenceDataProvider 1.4, Phase 2 实现)"""
        raise NotImplementedError("Stock info will be implemented in Phase 2")

    def get_limit_status(self, symbols: List[str]) -> pd.DataFrame:
        """获取涨跌停状态 (Phase 4 实现)"""
        raise NotImplementedError("Limit status will be implemented in Phase 4")

    def get_suspend_status(self, symbols: List[str]) -> pd.DataFrame:
        """获取停牌状态 (Phase 4 实现)"""
        raise NotImplementedError("Suspend status will be implemented in Phase 4")
