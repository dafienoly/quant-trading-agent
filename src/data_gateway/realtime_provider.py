"""Realtime quote providers backed by AkShare-compatible interfaces."""

from __future__ import annotations

import time
from typing import Iterable

import akshare as ak
import pandas as pd
from loguru import logger


A_SHARE_COLUMNS = {
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

HK_COLUMNS = {
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

NUMERIC_COLUMNS = (
    "last_price",
    "pct_change",
    "change",
    "volume",
    "amount",
    "open",
    "high",
    "low",
    "pre_close",
    "volume_ratio",
    "turnover_rate",
    "pe_ttm",
)


def normalize_quote_symbol(symbol: str) -> str:
    """Return an uppercase exchange-qualified symbol for A-share/HK quote inputs."""
    raw = str(symbol).strip().upper()
    if not raw:
        return raw
    if "." in raw:
        code, suffix = raw.split(".", 1)
        return f"{code}.{suffix}"
    if len(raw) == 5 and raw.isdigit():
        return f"{raw}.HK"
    if raw.startswith(("5", "6", "9")):
        return f"{raw}.SH"
    return f"{raw}.SZ"


def _code(symbol: str) -> str:
    return normalize_quote_symbol(symbol).split(".", 1)[0]


def _is_hk_symbol(symbol: str) -> bool:
    return normalize_quote_symbol(symbol).endswith(".HK")


def _symbol_market(code: str, *, hk: bool = False) -> str:
    if hk:
        return "HK"
    if str(code).startswith(("5", "6", "9")):
        return "SH"
    return "SZ"


def _with_exchange(code: str, *, hk: bool = False) -> str:
    return f"{code}.{_symbol_market(code, hk=hk)}"


def _coerce_numeric(df: pd.DataFrame) -> pd.DataFrame:
    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _prepare_raw(raw: pd.DataFrame, col_map: dict[str, str], symbols: Iterable[str]) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame()

    symbol_codes = {_code(s) for s in symbols}
    df = raw.rename(columns=col_map).copy()
    if "code" not in df.columns:
        return pd.DataFrame()

    df["code"] = df["code"].astype(str).str.zfill(5)
    a_share_mask = df["code"].str.len() == 6
    df.loc[a_share_mask, "code"] = df.loc[a_share_mask, "code"].str[-6:]
    df = df[df["code"].isin(symbol_codes)]
    if df.empty:
        return pd.DataFrame()

    return _coerce_numeric(df)


def _mark_a_share_status(df: pd.DataFrame) -> pd.DataFrame:
    df["status"] = "NORMAL"
    if "pct_change" not in df.columns:
        return df

    pct = pd.to_numeric(df["pct_change"], errors="coerce")
    names = df["name"].astype(str) if "name" in df.columns else pd.Series("", index=df.index)

    chinext_mask = df["code"].str.startswith(("300", "301"))
    star_mask = df["code"].str.startswith(("688", "689"))
    st_mask = names.str.contains("ST", na=False, case=False)
    mainboard_mask = ~(chinext_mask | star_mask | st_mask)

    df.loc[mainboard_mask & (pct >= 9.9), "status"] = "LIMIT_UP"
    df.loc[mainboard_mask & (pct <= -9.9), "status"] = "LIMIT_DOWN"

    gem_star_mask = chinext_mask | star_mask
    df.loc[gem_star_mask & (pct >= 19.9), "status"] = "LIMIT_UP"
    df.loc[gem_star_mask & (pct <= -19.9), "status"] = "LIMIT_DOWN"

    df.loc[st_mask & (pct >= 4.9), "status"] = "LIMIT_UP"
    df.loc[st_mask & (pct <= -4.9), "status"] = "LIMIT_DOWN"
    return df


def map_a_share_realtime_quotes(
    raw: pd.DataFrame,
    symbols: list[str],
    *,
    data_source: str = "akshare",
) -> pd.DataFrame:
    """Map AkShare/Eastmoney A-share realtime snapshots to the internal quote shape."""
    df = _prepare_raw(raw, A_SHARE_COLUMNS, symbols)
    if df.empty:
        return df

    df["market"] = df["code"].map(lambda c: _symbol_market(c))
    df["symbol"] = df["code"].map(lambda c: _with_exchange(c))
    df["datetime"] = pd.Timestamp.now(tz="Asia/Shanghai").isoformat()
    df["delay_seconds"] = 0.0
    df["source_volume_unit"] = "lot"
    df["volume"] = pd.to_numeric(df.get("volume", 0), errors="coerce").fillna(0).astype("int64") * 100
    df["currency"] = "CNY"
    df["timezone"] = "Asia/Shanghai"
    df["data_source"] = data_source
    df["updated_at"] = df["datetime"]
    df["data_version"] = "realtime-v1"
    df = _mark_a_share_status(df)
    return df


def map_hk_realtime_quotes(
    raw: pd.DataFrame,
    symbols: list[str],
    *,
    data_source: str = "akshare",
) -> pd.DataFrame:
    """Map AkShare HK realtime snapshots to the internal quote shape."""
    df = _prepare_raw(raw, HK_COLUMNS, symbols)
    if df.empty:
        return df

    df["market"] = "HK"
    df["symbol"] = df["code"].map(lambda c: _with_exchange(c, hk=True))
    df["datetime"] = pd.Timestamp.now(tz="Asia/Hong_Kong").isoformat()
    df["delay_seconds"] = 0.0
    df["status"] = "NORMAL"
    df["source_volume_unit"] = "share"
    df["volume"] = pd.to_numeric(df.get("volume", 0), errors="coerce").fillna(0).astype("int64")
    df["currency"] = "HKD"
    df["timezone"] = "Asia/Hong_Kong"
    df["data_source"] = data_source
    df["updated_at"] = df["datetime"]
    df["data_version"] = "realtime-v1"
    return df


class AkShareRealtimeProvider:
    """Fetch realtime A-share and HK quote snapshots through AkShare.

    Features:
    - Rate limiting between API calls to avoid anti-scraping blocks
    - Retry with exponential backoff (up to 3 attempts) on empty results
    - Per-symbol degradation: if bulk fetch fails, falls back to individual symbol queries
    """
    name = "akshare_realtime"

    _MAX_RETRIES = 3
    _RETRY_BASE_DELAY = 1.5       # seconds — base for exponential backoff
    _SYMBOL_INTERVAL = 0.5         # seconds — delay between individual symbol fallback calls

    def __init__(self, request_interval: float = 2.0):
        self._request_interval = request_interval
        self._last_request_time = 0.0

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self._request_interval:
            time.sleep(self._request_interval - elapsed)
        self._last_request_time = time.time()

    def _retry_with_backoff(self, fn, description: str, symbols: list[str]) -> pd.DataFrame:
        """Call *fn* up to _MAX_RETRIES times with exponential backoff.

        Returns the first non-empty DataFrame, or an empty DataFrame after exhausting
        retries.
        """
        for attempt in range(1, self._MAX_RETRIES + 1):
            try:
                self._rate_limit()
                logger.info(f"{description} (attempt {attempt}/{self._MAX_RETRIES}) — {len(symbols)} symbols")
                result = fn()
                if result is not None and not result.empty:
                    return result
                if attempt < self._MAX_RETRIES:
                    delay = self._RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    logger.warning(
                        f"{description} returned empty on attempt {attempt}, "
                        f"retrying in {delay:.1f}s …"
                    )
                    time.sleep(delay)
            except Exception as exc:
                if attempt < self._MAX_RETRIES:
                    delay = self._RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    logger.warning(
                        f"{description} failed on attempt {attempt}: {exc}, "
                        f"retrying in {delay:.1f}s …"
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"{description} failed after {self._MAX_RETRIES} attempts: {exc}")
        return pd.DataFrame()

    def _fetch_a_shares_bulk(self, a_symbols: list[str]) -> pd.DataFrame:
        """Primary path: fetch all A-shares in one bulk call."""
        return self._retry_with_backoff(
            lambda: map_a_share_realtime_quotes(ak.stock_zh_a_spot_em(), a_symbols),
            "A-share bulk realtime",
            a_symbols,
        )

    def _fetch_a_shares_per_symbol(self, a_symbols: list[str]) -> pd.DataFrame:
        """Fallback path: fetch A-share quotes one symbol at a time.

        Used when the bulk ``stock_zh_a_spot_em()`` call consistently returns empty
        (often due to AkShare anti-scraping or API changes).  Each symbol is fetched
        via ``stock_zh_a_spot_em()`` filtered to that symbol, with a small inter-symbol
        delay.
        """
        frames: list[pd.DataFrame] = []
        for i, sym in enumerate(a_symbols):
            try:
                if i > 0:
                    time.sleep(self._SYMBOL_INTERVAL)
                # stock_zh_a_spot_em returns all stocks; we filter in map_a_share_realtime_quotes
                raw = ak.stock_zh_a_spot_em()
                df = map_a_share_realtime_quotes(raw, [sym])
                if not df.empty:
                    frames.append(df)
                    logger.debug(f"Per-symbol fallback: {sym} OK")
                else:
                    logger.warning(f"Per-symbol fallback: {sym} returned empty after filtering")
            except Exception as exc:
                logger.warning(f"Per-symbol fallback: {sym} failed: {exc}")
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def get_realtime_quotes(self, symbols: list[str]) -> pd.DataFrame:
        normalized = [normalize_quote_symbol(s) for s in symbols if str(s).strip()]
        a_symbols = [s for s in normalized if not _is_hk_symbol(s)]
        hk_symbols = [s for s in normalized if _is_hk_symbol(s)]
        frames: list[pd.DataFrame] = []

        if a_symbols:
            # Try bulk fetch first, fall back to per-symbol on persistent empty
            df = self._fetch_a_shares_bulk(a_symbols)
            if df.empty and len(a_symbols) > 1:
                logger.warning(
                    f"Bulk A-share fetch returned empty after retries; "
                    f"falling back to per-symbol fetch for {len(a_symbols)} symbols"
                )
                df = self._fetch_a_shares_per_symbol(a_symbols)
            if not df.empty:
                frames.append(df)

        if hk_symbols:
            df = self._retry_with_backoff(
                lambda: map_hk_realtime_quotes(ak.stock_hk_spot_em(), hk_symbols),
                "HK realtime",
                hk_symbols,
            )
            if not df.empty:
                frames.append(df)

        frames = [frame for frame in frames if frame is not None and not frame.empty]
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)


def get_realtime_quotes(symbols: list[str]) -> pd.DataFrame:
    """Backward-compatible convenience wrapper used by product routes."""
    return AkShareRealtimeProvider().get_realtime_quotes(symbols)
