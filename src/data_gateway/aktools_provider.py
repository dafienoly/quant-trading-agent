from __future__ import annotations

import os
from typing import List, Optional

import httpx
import pandas as pd
from loguru import logger

from src.data_gateway.base import MarketDataProvider
from src.data_gateway.column_mapper import (
    map_daily_bars,
    map_index_daily_bars,
    map_stock_list,
)

DEFAULT_AKTOOLS_URL = os.getenv("AKTOOLS_BASE_URL", "http://127.0.0.1:8080")


class AkToolsProvider(MarketDataProvider):
    name = "aktools"

    def __init__(self, base_url: str = DEFAULT_AKTOOLS_URL, timeout: float = 30.0):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    def _get(self, endpoint: str, params: dict | None = None) -> pd.DataFrame:
        url = f"{self._base_url}/api/public/{endpoint}"
        logger.info(f"AkTools HTTP GET: {url} params={params}")
        resp = self._client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        if data is None or (isinstance(data, list) and len(data) == 0):
            return pd.DataFrame()
        return pd.DataFrame(data)

    def get_daily_bars(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        # 尝试获取股票名称缓存用于ST检测
        if not hasattr(self, '_stock_name_cache'):
            self._stock_name_cache = {}
            try:
                stock_list = self.get_stock_list()
                if not stock_list.empty:
                    for _, row in stock_list.iterrows():
                        code = row["symbol"].split(".")[0] if "." in row["symbol"] else row["symbol"]
                        self._stock_name_cache[code] = row.get("name", "")
                    logger.info(f"Stock name cache built: {len(self._stock_name_cache)} entries")
            except Exception as e:
                logger.warning(f"Failed to build stock name cache: {e}")

        all_frames = []
        for symbol in symbols:
            code = symbol.split(".")[0] if "." in symbol else symbol
            try:
                df = self._get("stock_zh_a_hist", {
                    "symbol": code,
                    "period": "daily",
                    "start_date": start_date,
                    "end_date": end_date,
                    "adjust": adjust,
                })
                if not df.empty:
                    stock_name = self._stock_name_cache.get(code, None)
                    mapped = map_daily_bars(df, stock_name=stock_name)
                    all_frames.append(mapped)
                    logger.debug(f"  Got {len(mapped)} rows for {code}")
                else:
                    logger.warning(f"  No data for {code}")
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
            df = self._get("index_zh_a_hist", {
                "symbol": code,
                "period": "daily",
                "start_date": start_date,
                "end_date": end_date,
            })
            if not df.empty:
                return map_index_daily_bars(df)
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Failed to fetch index {code}: {e}")
            return pd.DataFrame()

    def get_stock_list(self) -> pd.DataFrame:
        try:
            df = self._get("stock_info_a_code_name")
            if not df.empty:
                return map_stock_list(df)
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
            df = self._get("tool_trade_date_hist_sina")
            if df.empty:
                return pd.DataFrame()

            col = "trade_date" if "trade_date" in df.columns else df.columns[0]
            dates = pd.to_datetime(df[col])
            if start_date:
                dates = dates[dates >= pd.to_datetime(start_date)]
            if end_date:
                dates = dates[dates <= pd.to_datetime(end_date)]

            return pd.DataFrame({"trade_date": dates.dt.strftime("%Y%m%d")})
        except Exception as e:
            logger.error(f"Failed to fetch trade dates: {e}")
            return pd.DataFrame()

    def get_realtime_quotes(self, symbols: List[str]) -> pd.DataFrame:
        from src.data_gateway.realtime_provider import (
            _is_hk_symbol,
            map_a_share_realtime_quotes,
            map_hk_realtime_quotes,
            normalize_quote_symbol,
        )

        normalized = [normalize_quote_symbol(s) for s in symbols if str(s).strip()]
        a_symbols = [s for s in normalized if not _is_hk_symbol(s)]
        hk_symbols = [s for s in normalized if _is_hk_symbol(s)]
        frames: list[pd.DataFrame] = []

        if a_symbols:
            try:
                raw = self._get("stock_zh_a_spot_em")
                if not raw.empty:
                    frames.append(
                        map_a_share_realtime_quotes(raw, a_symbols, data_source="aktools")
                    )
            except Exception as e:
                logger.error(f"Failed to fetch AkTools A-share realtime quotes: {e}")

        if hk_symbols:
            try:
                raw = self._get("stock_hk_spot_em")
                if not raw.empty:
                    frames.append(map_hk_realtime_quotes(raw, hk_symbols, data_source="aktools"))
            except Exception as e:
                logger.error(f"Failed to fetch AkTools HK realtime quotes: {e}")

        frames = [frame for frame in frames if frame is not None and not frame.empty]
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)

    def close(self):
        self._client.close()

    def __del__(self):
        try:
            self._client.close()
        except Exception:
            pass
