from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

import pandas as pd
from loguru import logger


MAINBOARD_PREFIXES = ("000", "001", "002", "600", "601", "603", "605")
EXCLUDED_PREFIXES = ("300", "301", "688", "689")
HK_PATTERN_LEN = 5
MIN_TRADING_DAYS = 120  # 上市最少交易日


def is_mainboard(symbol: str) -> bool:
    code = symbol.split(".")[0] if "." in symbol else symbol
    if len(code) == HK_PATTERN_LEN and code.isdigit():
        return True
    return code.startswith(MAINBOARD_PREFIXES)


def is_excluded(symbol: str) -> bool:
    code = symbol.split(".")[0] if "." in symbol else symbol
    if code.startswith(EXCLUDED_PREFIXES):
        return True
    return False


def is_st(name: str) -> bool:
    if not name:
        return False
    upper = name.upper()
    return "ST" in upper or "退" in name


def filter_mainboard(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    code_col = "symbol" if "symbol" in df.columns else "code"
    name_col = "name" if "name" in df.columns else None

    mask_mainboard = df[code_col].apply(is_mainboard)
    mask_not_excluded = ~df[code_col].apply(is_excluded)

    if name_col:
        mask_not_st = ~df[name_col].apply(is_st)
    else:
        mask_not_st = pd.Series([True] * len(df), index=df.index)

    filtered = df[mask_mainboard & mask_not_excluded & mask_not_st].copy()

    logger.info(
        f"Mainboard filter: {len(df)} -> {len(filtered)} stocks "
        f"(excluded {len(df) - len(filtered)})"
    )
    return filtered


def filter_by_volume(df: pd.DataFrame, min_amount: float = 1e8) -> pd.DataFrame:
    if df.empty or "amount" not in df.columns:
        return df

    filtered = df[df["amount"] >= min_amount].copy()
    logger.info(f"Volume filter (amount >= {min_amount/1e8:.0f}亿): {len(df)} -> {len(filtered)}")
    return filtered


def filter_by_listing_date(
    df: pd.DataFrame,
    min_trading_days: int = MIN_TRADING_DAYS,
    ref_date: str | None = None,
) -> pd.DataFrame:
    """过滤上市不足 min_trading_days 个自然日的股票"""
    if df.empty or "list_date" not in df.columns:
        return df

    if ref_date is None:
        ref_date = datetime.now().strftime("%Y%m%d")

    try:
        ref_dt = datetime.strptime(ref_date, "%Y%m%d")
    except ValueError:
        logger.warning(f"Invalid ref_date: {ref_date}, skipping listing date filter")
        return df

    def _is_listed_long_enough(list_date_str):
        if pd.isna(list_date_str) or not list_date_str:
            return True  # 无上市日期不过滤
        try:
            # list_date 可能是 "YYYYMMDD" 或 "YYYY-MM-DD" 格式
            list_date_str = str(list_date_str).replace("-", "").strip()
            list_dt = datetime.strptime(list_date_str, "%Y%m%d")
            return (ref_dt - list_dt).days >= min_trading_days
        except (ValueError, TypeError):
            return True  # 解析失败不过滤

    mask = df["list_date"].apply(_is_listed_long_enough)
    filtered = df[mask].copy()
    excluded = len(df) - len(filtered)
    if excluded > 0:
        logger.info(
            f"Listing date filter (>= {min_trading_days} days): "
            f"{len(df)} -> {len(filtered)} (excluded {excluded})"
        )
    return filtered


def filter_by_suspension(df: pd.DataFrame) -> pd.DataFrame:
    """过滤停牌股票"""
    if df.empty:
        return df
    if "is_suspended" not in df.columns:
        return df
    filtered = df[~df["is_suspended"]].copy()
    excluded = len(df) - len(filtered)
    if excluded > 0:
        logger.info(f"Suspension filter: {len(df)} -> {len(filtered)} (excluded {excluded})")
    return filtered


def filter_tradeable(
    stock_list: pd.DataFrame,
    min_amount: float = 1e8,
    min_trading_days: int = MIN_TRADING_DAYS,
) -> pd.DataFrame:
    """综合过滤可交易股票：主板 + 排除ST/创业板/科创板 + 成交额 + 上市日期 + 停牌"""
    result = filter_mainboard(stock_list)

    # 过滤上市不足规定天数的股票
    if "list_date" in result.columns:
        result = filter_by_listing_date(result, min_trading_days=min_trading_days)

    # 过滤日成交额不足的股票
    if "amount" in result.columns:
        result = filter_by_volume(result, min_amount=min_amount)

    # 过滤停牌股票
    if "is_suspended" in result.columns:
        result = filter_by_suspension(result)

    return result
