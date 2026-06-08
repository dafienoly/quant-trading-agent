from __future__ import annotations

import time
from typing import Dict, List, Optional

import akshare as ak
import pandas as pd
from loguru import logger

from src.data_gateway.base import MarketDataProvider
from src.data_gateway.column_mapper import (
    map_daily_bars,
    map_index_daily_bars,
    map_stock_list,
)


class AkShareProvider(MarketDataProvider):

    def __init__(self, request_interval: float = 0.5):
        self._request_interval = request_interval
        self._last_request_time = 0.0
        self._stock_name_cache: Dict[str, str] = {}

    def _rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self._request_interval:
            time.sleep(self._request_interval - elapsed)
        self._last_request_time = time.time()

    def _build_stock_name_cache(self):
        """构建股票代码→名称缓存，用于ST检测"""
        if self._stock_name_cache:
            return
        try:
            self._rate_limit()
            stock_list = self.get_stock_list()
            if not stock_list.empty:
                for _, row in stock_list.iterrows():
                    code = row["symbol"].split(".")[0] if "." in row["symbol"] else row["symbol"]
                    self._stock_name_cache[code] = row.get("name", "")
                logger.info(f"Stock name cache built: {len(self._stock_name_cache)} entries")
        except Exception as e:
            logger.warning(f"Failed to build stock name cache: {e}")

    def get_daily_bars(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        self._build_stock_name_cache()
        all_frames = []
        for symbol in symbols:
            code = symbol.split(".")[0] if "." in symbol else symbol
            try:
                self._rate_limit()
                logger.info(f"Fetching daily bars: {code} ({start_date}~{end_date})")
                df = ak.stock_zh_a_hist(
                    symbol=code,
                    period="daily",
                    start_date=start_date,
                    end_date=end_date,
                    adjust=adjust,
                )
                if df is not None and not df.empty:
                    stock_name = self._stock_name_cache.get(code, None)
                    mapped = map_daily_bars(df, stock_name=stock_name)
                    all_frames.append(mapped)
                    logger.debug(f"  Got {len(mapped)} rows for {code}")
                else:
                    logger.warning(f"  No data returned for {code}")
            except Exception as e:
                logger.error(f"  Failed to fetch {code}: {e}")

        if not all_frames:
            return pd.DataFrame()
        return pd.concat(all_frames, ignore_index=True)

    def get_index_daily_bars(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        code = symbol.split(".")[0] if "." in symbol else symbol
        try:
            self._rate_limit()
            logger.info(f"Fetching index bars: {code} ({start_date}~{end_date})")
            df = ak.index_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_date,
                end_date=end_date,
            )
            if df is not None and not df.empty:
                return map_index_daily_bars(df)
            logger.warning(f"No index data for {code}")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Failed to fetch index {code}: {e}")
            return pd.DataFrame()

    def get_stock_list(self) -> pd.DataFrame:
        try:
            self._rate_limit()
            logger.info("Fetching A-share stock list")
            df = ak.stock_info_a_code_name()
            if df is not None and not df.empty:
                return map_stock_list(df)
            logger.warning("Empty stock list returned")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Failed to fetch stock list: {e}")
            return pd.DataFrame()

    def get_trade_dates(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        try:
            self._rate_limit()
            logger.info("Fetching trade calendar")
            df = ak.tool_trade_date_hist_sina()
            if df is None or df.empty:
                return pd.DataFrame()

            dates = pd.to_datetime(df["trade_date"])
            if start_date:
                dates = dates[dates >= pd.to_datetime(start_date)]
            if end_date:
                dates = dates[dates <= pd.to_datetime(end_date)]

            return pd.DataFrame({"trade_date": dates.dt.strftime("%Y%m%d")})
        except Exception as e:
            logger.error(f"Failed to fetch trade dates: {e}")
            return pd.DataFrame()

    def get_realtime_quotes(self, symbols: List[str]) -> pd.DataFrame:
        raise NotImplementedError("Realtime quotes will be implemented in Phase 4")
