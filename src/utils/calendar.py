from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional

import pandas as pd
from loguru import logger

from src.data_gateway.base import MarketDataProvider

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "cleaned"
CALENDAR_CACHE = CACHE_DIR / "_trade_calendar.csv"


class TradeCalendar:

    def __init__(self, provider: MarketDataProvider):
        self._provider = provider
        self._trade_dates: set[str] = set()
        self._sorted_dates: list[str] = []
        self._loaded = False

    def load(self, force_refresh: bool = False):
        if self._loaded and not force_refresh:
            return

        if CALENDAR_CACHE.exists() and not force_refresh:
            logger.info(f"Loading trade calendar from cache: {CALENDAR_CACHE}")
            df = pd.read_csv(CALENDAR_CACHE, dtype=str)
        else:
            logger.info("Fetching trade calendar from provider")
            df = self._provider.get_trade_dates()
            if df.empty:
                logger.error("Failed to load trade calendar")
                return
            CALENDAR_CACHE.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(CALENDAR_CACHE, index=False)

        self._sorted_dates = sorted(df["trade_date"].tolist())
        self._trade_dates = set(self._sorted_dates)
        self._loaded = True
        logger.info(f"Trade calendar loaded: {len(self._sorted_dates)} dates "
                     f"({self._sorted_dates[0]}~{self._sorted_dates[-1]})")

    def is_trading_date(self, date_str: str) -> bool:
        self.load()
        return date_str in self._trade_dates

    def get_trade_dates_between(
        self, start_date: str, end_date: str
    ) -> List[str]:
        self.load()
        return [d for d in self._sorted_dates if start_date <= d <= end_date]

    def get_recent_trading_dates(self, n: int, before: Optional[str] = None) -> List[str]:
        self.load()
        if before is None:
            before = datetime.now().strftime("%Y%m%d")
        candidates = [d for d in self._sorted_dates if d <= before]
        return candidates[-n:]

    def get_next_trading_date(self, after: str) -> Optional[str]:
        self.load()
        for d in self._sorted_dates:
            if d > after:
                return d
        return None

    def get_prev_trading_date(self, before: str) -> Optional[str]:
        self.load()
        candidates = [d for d in self._sorted_dates if d < before]
        return candidates[-1] if candidates else None
