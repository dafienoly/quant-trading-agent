from __future__ import annotations

from typing import Optional

import pandas as pd


# AkShare stock_zh_a_hist 返回的中文列名 → 标准英文列名
DAILY_BAR_COLUMN_MAP = {
    "日期": "trade_date",
    "股票代码": "symbol_raw",
    "开盘": "open",
    "收盘": "close",
    "最高": "high",
    "最低": "low",
    "成交量": "volume",
    "成交额": "amount",
    "振幅": "amplitude",
    "涨跌幅": "pct_change",
    "涨跌额": "change_amount",
    "换手率": "turnover_rate",
}

# AkShare index_zh_a_hist 返回的中文列名 → 标准英文列名
INDEX_DAILY_COLUMN_MAP = {
    "日期": "trade_date",
    "开盘": "open",
    "收盘": "close",
    "最高": "high",
    "最低": "low",
    "成交量": "volume",
    "成交额": "amount",
    "振幅": "amplitude",
    "涨跌幅": "pct_change",
    "涨跌额": "change_amount",
    "换手率": "turnover_rate",
}

# AkShare stock_info_a_code_name 返回的列名
STOCK_LIST_COLUMN_MAP = {
    "code": "symbol_raw",
    "name": "name",
}

# 标准日线输出列顺序
DAILY_BAR_COLUMNS = [
    "symbol",
    "market",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "pre_close",
    "volume",
    "amount",
    "turnover_rate",
    "adj_factor",
    "limit_up",
    "limit_down",
    "is_suspended",
    "is_st",
    "is_data_missing",
    "pct_change",
]


def symbol_to_market(symbol_raw: str) -> str:
    if len(symbol_raw) == 5:
        return "HK"
    if symbol_raw.startswith(("6", "9")):
        return "SH"
    if symbol_raw.startswith(("0", "2", "3")):
        return "SZ"
    return "UNKNOWN"


def to_standard_symbol(symbol_raw: str) -> str:
    market = symbol_to_market(symbol_raw)
    return f"{symbol_raw}.{market}"


def _calc_limit_prices(pre_close: float, symbol_raw: str, is_st: bool) -> tuple[float, float]:
    """计算涨跌停价，根据股票类型区分幅度"""
    code = symbol_raw.split(".")[0] if "." in symbol_raw else symbol_raw
    if is_st:
        rate = 0.05
    elif code.startswith(("300", "301", "688", "689")):
        rate = 0.20
    else:
        rate = 0.10
    limit_up = round(pre_close * (1 + rate), 2)
    limit_down = round(pre_close * (1 - rate), 2)
    return limit_up, limit_down


def _detect_is_st(name: Optional[str]) -> bool:
    """从股票名称检测是否为ST股"""
    if not name:
        return False
    upper = str(name).upper()
    return "ST" in upper or "退" in upper


def map_daily_bars(df: pd.DataFrame, stock_name: Optional[str] = None) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=DAILY_BAR_COLUMNS)

    result = df.rename(columns=DAILY_BAR_COLUMN_MAP)

    symbol_raw_col = None
    if "symbol_raw" in result.columns:
        symbol_raw_col = result["symbol_raw"]
        result["market"] = symbol_raw_col.apply(symbol_to_market)
        result["symbol"] = symbol_raw_col.apply(to_standard_symbol)
        result = result.drop(columns=["symbol_raw"])

    result["trade_date"] = pd.to_datetime(result["trade_date"]).dt.strftime("%Y%m%d")

    # 关键字段转换为数值，NaN保留不做静默填充
    result["volume"] = pd.to_numeric(result.get("volume"), errors="coerce")
    result["amount"] = pd.to_numeric(result.get("amount"), errors="coerce")
    result["turnover_rate"] = pd.to_numeric(result.get("turnover_rate"), errors="coerce")

    for col in ["open", "high", "low", "close"]:
        result[col] = pd.to_numeric(result[col], errors="coerce")

    # 标记是否有关键字段缺失（在数值转换之后检查）
    result["is_data_missing"] = (
        result["open"].isna() | result["high"].isna() |
        result["low"].isna() | result["close"].isna() |
        result["volume"].isna() | result["amount"].isna()
    )
    # 使用Nullable整数类型保持NaN
    result["volume"] = result["volume"].astype("Int64")

    # 计算 pre_close: close / (1 + pct_change/100)
    if "pct_change" in result.columns:
        pct = pd.to_numeric(result["pct_change"], errors="coerce")
        result["pre_close"] = (result["close"] / (1 + pct / 100)).round(2)
    else:
        result["pre_close"] = None

    # 识别ST状态并计算正确的涨跌停价
    if "name" in result.columns:
        result["is_st"] = result["name"].apply(_detect_is_st)
    elif stock_name is not None and symbol_raw_col is not None:
        # 如果提供了股票名称，用于ST检测
        result["is_st"] = _detect_is_st(stock_name)
    else:
        result["is_st"] = False

    # 根据symbol前缀和is_st计算正确的涨跌停幅度
    if symbol_raw_col is not None:
        # 逐行计算涨跌停价
        limit_up_list = []
        limit_down_list = []
        for pc, sym, st in zip(result["pre_close"], symbol_raw_col, result["is_st"]):
            if pd.isna(pc):
                limit_up_list.append(None)
                limit_down_list.append(None)
            else:
                lu, ld = _calc_limit_prices(pc, str(sym), bool(st))
                limit_up_list.append(lu)
                limit_down_list.append(ld)
        result["limit_up"] = limit_up_list
        result["limit_down"] = limit_down_list
    else:
        # 默认回退到10%
        result["limit_up"] = (result["pre_close"] * 1.10).round(2)
        result["limit_down"] = (result["pre_close"] * 0.90).round(2)

    result["adj_factor"] = None
    # 仅当volume有值且为0时标记为停牌，volume缺失不认为是停牌
    result["is_suspended"] = result["volume"].fillna(-1) == 0

    # 确保所有标准列存在
    for col in DAILY_BAR_COLUMNS:
        if col not in result.columns:
            result[col] = None

    return result[DAILY_BAR_COLUMNS]


def map_index_daily_bars(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["trade_date", "open", "high", "low", "close", "volume", "amount", "pct_change"])

    result = df.rename(columns=INDEX_DAILY_COLUMN_MAP)
    result["trade_date"] = pd.to_datetime(result["trade_date"]).dt.strftime("%Y%m%d")

    for col in ["open", "high", "low", "close", "volume", "amount"]:
        if col in result.columns:
            result[col] = pd.to_numeric(result[col], errors="coerce")

    return result


def map_stock_list(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["symbol", "name", "market", "board_type"])

    result = df.rename(columns=STOCK_LIST_COLUMN_MAP)
    result["market"] = result["symbol_raw"].apply(symbol_to_market)
    result["symbol"] = result["symbol_raw"].apply(to_standard_symbol)

    def _board_type(symbol_raw: str) -> str:
        if symbol_raw.startswith(("300", "301")):
            return "chinext"
        if symbol_raw.startswith(("688", "689")):
            return "star"
        if symbol_raw.startswith("002"):
            return "sme"
        return "mainboard"

    result["board_type"] = result["symbol_raw"].apply(_board_type)
    result = result.drop(columns=["symbol_raw"])
    return result[["symbol", "name", "market", "board_type"]]
