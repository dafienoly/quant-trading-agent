"""东方财富直连 HTTP 数据提供者 — AkShare/AkTools 不可用时的主要降级方案。

实现 LiveDataProvider 协议，通过东方财富公开 API 直接获取：
- A 股实时行情
- 日线行情
- 基础财务数据（PE、PB 等）
"""
from __future__ import annotations

import time
from typing import Any

import httpx
import pandas as pd
from loguru import logger

from src.data_gateway.realtime_provider import map_a_share_realtime_quotes, normalize_quote_symbol
from src.data_gateway.live_data_mapper import normalize_trade_date


# ---------------------------------------------------------------------------
# 东方财富 API 字段映射
# ---------------------------------------------------------------------------

# 实时行情：东方财富 f 编号 → 内部列名
_EM_REALTIME_FIELD_MAP: dict[str, str] = {
    "f2": "最新价",
    "f3": "涨跌幅",
    "f4": "涨跌额",
    "f5": "成交量",
    "f6": "成交额",
    "f7": "振幅",
    "f8": "换手率",
    "f9": "市盈率-动态",
    "f10": "量比",
    "f12": "代码",
    "f14": "名称",
    "f15": "最高",
    "f16": "最低",
    "f17": "今开",
    "f18": "昨收",
}

# 实时行情请求字段列表
_EM_REALTIME_FIELDS = ",".join(_EM_REALTIME_FIELD_MAP.keys())

# 日线行情 fields1
_EM_KLINE_FIELDS1 = "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13"
# 日线行情 fields2
_EM_KLINE_FIELDS2 = "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"

# 财务数据字段映射
_EM_FUNDAMENTAL_FIELD_MAP: dict[str, str] = {
    "f9": "pe_ttm",           # 市盈率(动)
    "f23": "pb",              # 市净率
    "f20": "total_market_cap", # 总市值
    "f115": "circulating_market_cap",  # 流通市值
    "f116": "revenue",        # 营业收入(部分场景可用)
    "f117": "net_profit",     # 净利润(部分场景可用)
    "f162": "roe",            # ROE(加权)
}
_EM_FUNDAMENTAL_FIELDS = ",".join(_EM_FUNDAMENTAL_FIELD_MAP.keys())


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _symbol_to_secid(symbol: str) -> str:
    """将标准 symbol (如 600000.SH / 000001.SZ) 转换为东方财富 secid 格式。

    东方财富 secid 格式: 市场编号.股票代码
    - 沪市: 1.600000
    - 深市: 0.000001
    """
    raw = str(symbol).strip().upper()
    if "." in raw:
        code, suffix = raw.split(".", 1)
    else:
        code = raw
        suffix = "SH" if raw.startswith(("5", "6", "9")) else "SZ"

    if suffix in ("SH", "SSE"):
        return f"1.{code}"
    if suffix in ("SZ", "SZSE"):
        return f"0.{code}"
    # 北交所
    if suffix in ("BJ", "BSE"):
        return f"0.{code}"
    # 默认按代码判断
    if code.startswith(("5", "6", "9")):
        return f"1.{code}"
    return f"0.{code}"


def _secid_to_symbol(secid: str) -> str:
    """将东方财富 secid (如 1.600000 / 0.000001) 转换为标准 symbol 格式。"""
    parts = str(secid).strip().split(".")
    if len(parts) != 2:
        return secid
    market_id, code = parts
    code = code.zfill(6)
    if market_id == "1":
        return f"{code}.SH"
    return f"{code}.SZ"


# ---------------------------------------------------------------------------
# EastmoneyProvider
# ---------------------------------------------------------------------------

class EastmoneyProvider:
    """东方财富直连 HTTP 数据提供者。

    实现 LiveDataProvider 协议，作为 AkShare/AkTools 不可用时的降级方案。
    """

    name = "eastmoney"

    # 实时行情 API
    _REALTIME_URL = "https://push2.eastmoney.com/api/qt/clist/get"
    # 日线行情 API
    _KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    # 财务数据 API
    _FUNDAMENTAL_URL = "https://push2.eastmoney.com/api/qt/stock/get"

    # A 股筛选参数：沪市主板 + 深市主板 + 中小板
    _A_SHARE_FS = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048"

    def __init__(self, timeout_seconds: float = 8.0, request_interval: float = 0.8):
        self._timeout = timeout_seconds
        self._request_interval = request_interval
        self._last_request_time = 0.0
        self._client = httpx.Client(timeout=timeout_seconds)

    # ------------------------------------------------------------------
    # 速率限制
    # ------------------------------------------------------------------

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self._request_interval:
            time.sleep(self._request_interval - elapsed)
        self._last_request_time = time.time()

    # ------------------------------------------------------------------
    # 实时行情
    # ------------------------------------------------------------------

    def get_realtime_quotes(self, symbols: list[str]) -> pd.DataFrame:
        """获取 A 股实时行情快照。

        一次性拉取全市场 A 股数据，然后按 symbols 过滤。
        """
        if not symbols:
            return pd.DataFrame()

        normalized = [normalize_quote_symbol(s) for s in symbols if str(s).strip()]
        if not normalized:
            return pd.DataFrame()

        # 仅支持 A 股，过滤掉港股等
        a_symbols = [s for s in normalized if not s.endswith(".HK")]
        if not a_symbols:
            return pd.DataFrame()

        try:
            self._rate_limit()
            raw = self._fetch_all_a_share_realtime()
            if raw is None or raw.empty:
                logger.warning("Eastmoney realtime: API returned empty data")
                return pd.DataFrame()

            # 使用 realtime_provider 的映射函数
            df = map_a_share_realtime_quotes(raw, a_symbols, data_source="eastmoney")
            return df

        except Exception as exc:
            logger.error(f"Eastmoney realtime quotes failed: {exc}")
            return pd.DataFrame()

    def _fetch_all_a_share_realtime(self) -> pd.DataFrame:
        """从东方财富拉取全市场 A 股实时行情，返回中文列名 DataFrame。"""
        params = {
            "pn": "1",
            "pz": "5000",
            "po": "1",
            "np": "1",
            "fltt": "2",
            "invt": "2",
            "fid": "f3",
            "fs": self._A_SHARE_FS,
            "fields": _EM_REALTIME_FIELDS,
        }

        resp = self._client.get(self._REALTIME_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

        diff = data.get("data", {}).get("diff")
        if not diff:
            return pd.DataFrame()

        # diff 是字典列表，每个字典的 key 是 f 编号
        raw_df = pd.DataFrame(diff)

        # 将 f 编号列重命名为中文列名（与 AkShare 返回格式一致）
        rename_map = {}
        for f_code, cn_name in _EM_REALTIME_FIELD_MAP.items():
            if f_code in raw_df.columns:
                rename_map[f_code] = cn_name
        raw_df = raw_df.rename(columns=rename_map)

        # 确保代码列为字符串并补零
        if "代码" in raw_df.columns:
            raw_df["代码"] = raw_df["代码"].astype(str).str.zfill(6)

        return raw_df

    # ------------------------------------------------------------------
    # 日线行情
    # ------------------------------------------------------------------

    def get_daily_bars(
        self,
        symbols: list[str],
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        """获取日线行情数据。

        逐个 symbol 请求东方财富 kline API。
        """
        if not symbols:
            return pd.DataFrame()

        # 日期格式转换：去掉横线，东方财富需要 YYYYMMDD
        beg = start_date.replace("-", "")
        end = end_date.replace("-", "")

        # 复权类型映射
        fqt_map = {"qfq": "1", "hfq": "2", "": "0"}
        fqt = fqt_map.get(adjust, "1")

        all_frames: list[pd.DataFrame] = []

        for symbol in symbols:
            try:
                self._rate_limit()
                df = self._fetch_kline(symbol, beg, end, fqt)
                if df is not None and not df.empty:
                    all_frames.append(df)
                    logger.debug(f"Eastmoney kline: {symbol} got {len(df)} rows")
                else:
                    logger.warning(f"Eastmoney kline: {symbol} returned empty")
            except Exception as exc:
                logger.error(f"Eastmoney kline: {symbol} failed: {exc}")

        if not all_frames:
            return pd.DataFrame()

        return pd.concat(all_frames, ignore_index=True)

    def _fetch_kline(
        self, symbol: str, beg: str, end: str, fqt: str
    ) -> pd.DataFrame | None:
        """拉取单个 symbol 的日线数据。"""
        secid = _symbol_to_secid(symbol)
        params = {
            "secid": secid,
            "fields1": _EM_KLINE_FIELDS1,
            "fields2": _EM_KLINE_FIELDS2,
            "klt": "101",   # 日线
            "fqt": fqt,
            "beg": beg,
            "end": end,
        }

        resp = self._client.get(self._KLINE_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

        klines = data.get("data", {}).get("klines")
        if not klines:
            return None

        # klines 是逗号分隔字符串列表:
        # date,open,close,high,low,volume,amount,amplitude,pct_change,change,turnover
        rows = []
        for line in klines:
            parts = line.split(",")
            if len(parts) < 11:
                continue
            rows.append({
                "trade_date": parts[0],
                "open": parts[1],
                "close": parts[2],
                "high": parts[3],
                "low": parts[4],
                "volume": parts[5],
                "amount": parts[6],
                "amplitude": parts[7],
                "pct_change": parts[8],
                "change": parts[9],
                "turnover_rate": parts[10],
            })

        if not rows:
            return None

        df = pd.DataFrame(rows)
        df["symbol"] = symbol

        # 日期格式统一为 YYYY-MM-DD
        df["trade_date"] = df["trade_date"].apply(normalize_trade_date)

        # 数值转换
        numeric_cols = [
            "open", "close", "high", "low", "volume", "amount",
            "amplitude", "pct_change", "change", "turnover_rate",
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # 东方财富 volume 单位为手，转换为股
        if "volume" in df.columns:
            df["volume"] = df["volume"] * 100

        # 计算 pre_close
        if "pct_change" in df.columns and "close" in df.columns:
            pct = df["pct_change"]
            df["pre_close"] = (df["close"] / (1 + pct / 100)).round(2)

        return df

    # ------------------------------------------------------------------
    # 财务数据
    # ------------------------------------------------------------------

    def get_fundamentals(self, symbols: list[str]) -> pd.DataFrame:
        """获取基础财务数据（PE、PB、ROE 等）。

        逐个 symbol 请求东方财富 stock get API。
        缺失字段保留 NaN，不静默填 0。
        """
        if not symbols:
            return pd.DataFrame()

        all_frames: list[pd.DataFrame] = []

        for symbol in symbols:
            try:
                self._rate_limit()
                df = self._fetch_fundamental(symbol)
                if df is not None and not df.empty:
                    all_frames.append(df)
                    logger.debug(f"Eastmoney fundamentals: {symbol} OK")
                else:
                    logger.warning(f"Eastmoney fundamentals: {symbol} returned empty")
            except Exception as exc:
                logger.error(f"Eastmoney fundamentals: {symbol} failed: {exc}")

        if not all_frames:
            return pd.DataFrame()

        result = pd.concat(all_frames, ignore_index=True)

        # 确保标准列存在，缺失保留 NaN
        standard_cols = [
            "symbol", "pe_ttm", "pb", "roe", "revenue", "net_profit",
            "market_cap", "total_market_cap", "circulating_market_cap",
        ]
        for col in standard_cols:
            if col not in result.columns:
                result[col] = pd.NA

        # 数值转换 — 缺失保留 NaN
        for col in ["pe_ttm", "pb", "roe", "revenue", "net_profit",
                     "market_cap", "total_market_cap", "circulating_market_cap"]:
            if col in result.columns:
                result[col] = pd.to_numeric(result[col], errors="coerce")

        return result

    def _fetch_fundamental(self, symbol: str) -> pd.DataFrame | None:
        """拉取单个 symbol 的基础财务数据。"""
        secid = _symbol_to_secid(symbol)
        params = {
            "secid": secid,
            "fields": _EM_FUNDAMENTAL_FIELDS,
        }

        resp = self._client.get(self._FUNDAMENTAL_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

        stock_data = data.get("data")
        if not stock_data:
            return None

        row: dict[str, Any] = {"symbol": symbol}

        for f_code, col_name in _EM_FUNDAMENTAL_FIELD_MAP.items():
            value = stock_data.get(f_code)
            # 东方财富对无效值返回 "-" 或 None
            if value is None or value == "-":
                row[col_name] = pd.NA
            else:
                row[col_name] = value

        # 总市值作为 market_cap
        if "total_market_cap" in row and pd.notna(row.get("total_market_cap")):
            row["market_cap"] = row["total_market_cap"]
        else:
            row["market_cap"] = pd.NA

        return pd.DataFrame([row])

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def close(self) -> None:
        self._client.close()

    def __del__(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass
