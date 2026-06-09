"""AkShare 实时行情实现

通过 AkShare 的 stock_zh_a_spot_em 接口获取 A 股实时行情快照。
通过 AkShare 的 stock_hk_spot_em 接口获取港股实时行情快照。
"""
from __future__ import annotations

import time
from typing import List

import akshare as ak
import pandas as pd
from loguru import logger

from src.data_gateway.base import MarketDataProvider


def _is_hk_symbol(symbol: str) -> bool:
    """判断是否为港股代码（5位纯数字）"""
    code = symbol.split(".")[0] if "." in symbol else symbol
    return len(code) == 5 and code.isdigit()


def _map_realtime_quotes(raw: pd.DataFrame, symbols: List[str]) -> pd.DataFrame:
    """将 AkShare 实时行情原始数据映射为标准格式"""
    symbol_set = set(s.split(".")[0] for s in symbols)

    col_map = {
        "代码": "code",
        "名称": "name",
        "最新价": "last_price",
        "涨跌幅": "pct_change",
        "涨跌额": "change",
        "成交量": "volume",
        "成交额": "amount",
        "今开": "open",
        "最高": "high",
        "最低": "low",
        "昨收": "pre_close",
        "量比": "volume_ratio",
        "换手率": "turnover_rate",
        "市盈率-动态": "pe_ttm",
    }

    df = raw.rename(columns=col_map)

    if "code" in df.columns:
        df = df[df["code"].isin(symbol_set)]

    now_str = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    df["datetime"] = now_str
    df["delay_seconds"] = 0.0
    df["status"] = "NORMAL"

    if "pct_change" in df.columns:
        pct = df["pct_change"].astype(float, errors="ignore")
        # 根据代码前缀区分涨跌停幅度
        # 创业板(300/301)、科创板(688/689): 20%
        # ST 股: 5%
        # 主板/中小板: 10%
        chinext_mask = df["code"].str.startswith(("300", "301"))
        star_mask = df["code"].str.startswith(("688", "689"))
        st_mask = df["name"].str.contains("ST", na=False, case=False)

        # 主板 10% 涨跌停
        mainboard_mask = ~(chinext_mask | star_mask | st_mask)
        df.loc[mainboard_mask & (pct >= 9.9), "status"] = "LIMIT_UP"
        df.loc[mainboard_mask & (pct <= -9.9), "status"] = "LIMIT_DOWN"

        # 创业板/科创板 20% 涨跌停
        gem_star_mask = chinext_mask | star_mask
        df.loc[gem_star_mask & (pct >= 19.9), "status"] = "LIMIT_UP"
        df.loc[gem_star_mask & (pct <= -19.9), "status"] = "LIMIT_DOWN"

        # ST 股 5% 涨跌停
        df.loc[st_mask & (pct >= 4.9), "status"] = "LIMIT_UP"
        df.loc[st_mask & (pct <= -4.9), "status"] = "LIMIT_DOWN"

    df["symbol"] = df["code"] + ".SZ"
    mask_sh = df["code"].str.startswith(("6",))
    df.loc[mask_sh, "symbol"] = df.loc[mask_sh, "code"] + ".SH"

    return df


def _map_hk_quotes(raw: pd.DataFrame, symbols: List[str]) -> pd.DataFrame:
    """将 AkShare 港股实时行情原始数据映射为标准格式"""
    symbol_set = set(s.split(".")[0] for s in symbols)

    col_map = {
        "代码": "code",
        "名称": "name",
        "最新价": "last_price",
        "涨跌幅": "pct_change",
        "涨跌额": "change",
        "成交量": "volume",
        "成交额": "amount",
        "今开": "open",
        "最高": "high",
        "最低": "low",
        "昨收": "pre_close",
    }

    df = raw.rename(columns=col_map)

    if "code" in df.columns:
        df = df[df["code"].isin(symbol_set)]

    now_str = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    df["datetime"] = now_str
    df["delay_seconds"] = 0.0
    df["status"] = "NORMAL"
    df["symbol"] = df["code"] + ".HK"

    return df


class AkShareRealtimeProvider:
    """AkShare 实时行情 Provider

    使用 stock_zh_a_spot_em 获取 A 股实时快照，
    使用 stock_hk_spot_em 获取港股实时快照，然后过滤目标股票。
    """

    def __init__(self, request_interval: float = 2.0):
        self._request_interval = request_interval
        self._last_request_time = 0.0

    def _rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self._request_interval:
            time.sleep(self._request_interval - elapsed)
        self._last_request_time = time.time()

    def get_realtime_quotes(self, symbols: List[str]) -> pd.DataFrame:
        a_symbols = [s for s in symbols if not _is_hk_symbol(s)]
        hk_symbols = [s for s in symbols if _is_hk_symbol(s)]

        results: list[pd.DataFrame] = []

        # A 股行情
        if a_symbols:
            try:
                self._rate_limit()
                logger.info(f"Fetching A-share realtime quotes for {len(a_symbols)} symbols")
                raw = ak.stock_zh_a_spot_em()
                if raw is not None and not raw.empty:
                    results.append(_map_realtime_quotes(raw, a_symbols))
                else:
                    logger.warning("Empty A-share realtime data returned")
            except Exception as e:
                logger.error(f"Failed to fetch A-share realtime quotes: {e}")

        # 港股行情
        if hk_symbols:
            try:
                self._rate_limit()
                logger.info(f"Fetching HK realtime quotes for {len(hk_symbols)} symbols")
                raw = ak.stock_hk_spot_em()
                if raw is not None and not raw.empty:
                    results.append(_map_hk_quotes(raw, hk_symbols))
                else:
                    logger.warning("Empty HK realtime data returned")
            except Exception as e:
                logger.error(f"Failed to fetch HK realtime quotes: {e}")

        if not results:
            return pd.DataFrame()
        return pd.concat(results, ignore_index=True)
