"""V16.2 市场数据 Relay 专用 Provider 与本地缓存。

该模块只补充现有 LiveDataService 尚未统一覆盖的指数、ETF、行业板块和
交易日历能力。ManualFixtureProvider 仅用于显式测试模式。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import akshare as ak
import pandas as pd

from src.data_gateway.realtime_provider import normalize_quote_symbol


_SPOT_COLUMN_MAP = {
    "代码": "code",
    "基金代码": "code",
    "板块代码": "code",
    "名称": "name",
    "基金简称": "name",
    "板块名称": "name",
    "最新价": "last_price",
    "昨收": "pre_close",
    "今开": "open",
    "开盘": "open",
    "最高": "high",
    "最低": "low",
    "成交量": "volume",
    "成交额": "amount",
    "涨跌额": "change",
    "涨跌幅": "pct_change",
}

_BAR_COLUMN_MAP = {
    "日期": "trade_date",
    "开盘": "open",
    "最高": "high",
    "最低": "low",
    "收盘": "close",
    "成交量": "volume",
    "成交额": "amount",
}


def _code(value: str) -> str:
    return str(value).strip().upper().split(".", 1)[0]


def _market_suffix(code: str) -> str:
    return "SH" if code.startswith(("5", "6", "9")) else "SZ"


def _map_spot(
    raw: pd.DataFrame,
    symbols: list[str],
    *,
    data_source: str,
    sector: bool = False,
    volume_multiplier: int = 100,
) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame()
    frame = raw.rename(columns=_SPOT_COLUMN_MAP).copy()
    if "code" not in frame.columns:
        return pd.DataFrame()
    frame["code"] = frame["code"].astype(str).str.strip()
    requested_map = {
        _code(symbol): normalize_quote_symbol(symbol)
        for symbol in symbols
        if str(symbol).strip() and not sector
    }
    requested = (
        set(requested_map)
        if not sector
        else {_code(symbol) for symbol in symbols if str(symbol).strip()}
    )
    if requested:
        name_series = frame.get("name", pd.Series("", index=frame.index)).astype(str)
        frame = frame[frame["code"].isin(requested) | name_series.isin(requested)]
    if frame.empty:
        return pd.DataFrame()

    numeric = (
        "last_price",
        "pre_close",
        "open",
        "high",
        "low",
        "volume",
        "amount",
        "change",
        "pct_change",
    )
    for column in numeric:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        else:
            frame[column] = None
    frame["volume"] = frame["volume"] * volume_multiplier
    if "name" not in frame.columns:
        frame["name"] = ""

    if sector:
        frame["symbol"] = frame["code"]
    else:
        frame["symbol"] = frame["code"].map(
            lambda item: requested_map.get(
                item,
                normalize_quote_symbol(
                    f"{item}.{_market_suffix(item)}" if "." not in item else item
                ),
            )
        )
    now = pd.Timestamp.now(tz="Asia/Shanghai")
    frame["datetime"] = now.isoformat()
    frame["trading_day"] = now.strftime("%Y%m%d")
    frame["currency"] = "CNY"
    frame["timezone"] = "Asia/Shanghai"
    frame["source_volume_unit"] = "lot" if volume_multiplier == 100 else "share"
    frame["status"] = "NORMAL"
    frame["data_source"] = data_source
    frame["updated_at"] = frame["datetime"]
    return frame[
        [
            "symbol",
            "name",
            "last_price",
            "pre_close",
            "open",
            "high",
            "low",
            "volume",
            "amount",
            "change",
            "pct_change",
            "datetime",
            "trading_day",
            "currency",
            "timezone",
            "source_volume_unit",
            "status",
            "data_source",
            "updated_at",
        ]
    ]


def _map_bars(raw: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame()
    frame = raw.rename(columns=_BAR_COLUMN_MAP).copy()
    required = ("trade_date", "open", "high", "low", "close", "volume", "amount")
    if any(column not in frame.columns for column in required):
        return pd.DataFrame()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y%m%d")
    for column in required[1:]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["symbol"] = normalize_quote_symbol(symbol)
    frame["raw_close"] = frame["close"]
    frame["adjusted_close"] = frame["close"]
    frame["is_suspended"] = frame["volume"].fillna(-1).eq(0)
    return frame[
        [
            "symbol",
            "trade_date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "amount",
            "raw_close",
            "adjusted_close",
            "is_suspended",
        ]
    ]


class AkShareMarketRelayProvider:
    """AkShare 的指数、ETF、行业和交易日历只读适配器。"""

    name = "akshare"

    def get_index_realtime_quotes(self, symbols: list[str]) -> pd.DataFrame:
        return _map_spot(
            ak.stock_zh_index_spot_em(),
            symbols,
            data_source=self.name,
        )

    def get_etf_realtime_quotes(self, symbols: list[str]) -> pd.DataFrame:
        return _map_spot(
            ak.fund_etf_spot_em(),
            symbols,
            data_source=self.name,
        )

    def get_sector_quotes(self, symbols: list[str]) -> pd.DataFrame:
        return _map_spot(
            ak.stock_board_industry_spot_em(),
            symbols,
            data_source=self.name,
            sector=True,
        )

    def get_index_daily_bars(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str = "",
    ) -> pd.DataFrame:
        del adjust
        raw = ak.index_zh_a_hist(
            symbol=_code(symbol),
            period="daily",
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
        )
        return _map_bars(raw, symbol)

    def get_etf_daily_bars(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        raw = ak.fund_etf_hist_em(
            symbol=_code(symbol),
            period="daily",
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
            adjust=adjust,
        )
        return _map_bars(raw, symbol)

    def get_trade_dates(
        self,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        raw = ak.tool_trade_date_hist_sina()
        if raw is None or raw.empty or "trade_date" not in raw.columns:
            return pd.DataFrame()
        dates = pd.to_datetime(raw["trade_date"])
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        dates = dates[(dates >= start) & (dates <= end)]
        return pd.DataFrame({"trade_date": dates.dt.strftime("%Y%m%d")})


class LocalCacheProvider:
    """JSON 文件缓存，只能作为 Relay 的明确 fallback。"""

    name = "local_cache"

    def __init__(self, root: Path | str = "runtime/cache/market-relay") -> None:
        self.root = Path(root)

    @staticmethod
    def make_key(data_type: str, identity: str) -> str:
        digest = hashlib.sha256(f"{data_type}:{identity}".encode()).hexdigest()
        return f"{data_type}-{digest[:24]}"

    def write(self, key: str, envelope: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        destination = self.root / f"{key}.json"
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(envelope, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(destination)

    def read(self, key: str) -> dict[str, Any] | None:
        path = self.root / f"{key}.json"
        if not path.exists():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None


class ManualFixtureProvider:
    """确定性测试 Provider；禁止在非 test_mode 中启用。"""

    name = "manual_fixture"

    def __init__(
        self,
        fixtures: dict[str, pd.DataFrame],
        *,
        test_mode: bool = False,
    ) -> None:
        if not test_mode:
            raise RuntimeError("ManualFixtureProvider 只能在显式 test_mode 中使用")
        self._fixtures = fixtures

    def _get(self, name: str) -> pd.DataFrame:
        frame = self._fixtures.get(name)
        return frame.copy() if isinstance(frame, pd.DataFrame) else pd.DataFrame()

    def get_index_realtime_quotes(self, symbols: list[str]) -> pd.DataFrame:
        del symbols
        return self._get("index_quotes")

    def get_etf_realtime_quotes(self, symbols: list[str]) -> pd.DataFrame:
        del symbols
        return self._get("etf_quotes")

    def get_sector_quotes(self, symbols: list[str]) -> pd.DataFrame:
        del symbols
        return self._get("sector_quotes")

    def get_index_daily_bars(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str = "",
    ) -> pd.DataFrame:
        del symbol, start_date, end_date, adjust
        return self._get("index_bars")

    def get_etf_daily_bars(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        del symbol, start_date, end_date, adjust
        return self._get("etf_bars")

    def get_trade_dates(self, start_date: str, end_date: str) -> pd.DataFrame:
        del start_date, end_date
        return self._get("trade_calendar")
