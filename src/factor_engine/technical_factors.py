"""技术趋势因子计算

实现 ARCHITECTURE.md 5.5 节定义的技术趋势分：
- MA5/MA10/MA20/MA60 均线
- close vs MA 位置关系
- 均线排列（多头/空头）
- 20日新高强度
- 量价突破
- ATR 波动率

所有计算仅使用历史数据，不引入未来信息。
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger


def calc_ma(series: pd.Series, window: int) -> pd.Series:
    """计算简单移动平均"""
    return series.rolling(window=window, min_periods=1).mean()


def calc_ema(series: pd.Series, window: int) -> pd.Series:
    """计算指数移动平均"""
    return series.ewm(span=window, adjust=False).mean()


def calc_atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    """计算平均真实波幅 (ATR)"""
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(window=window, min_periods=1).mean()


def calc_highest(series: pd.Series, window: int) -> pd.Series:
    """计算滚动最高值"""
    return series.rolling(window=window, min_periods=1).max()


def calc_lowest(series: pd.Series, window: int) -> pd.Series:
    """计算滚动最低值"""
    return series.rolling(window=window, min_periods=1).min()


def compute_technical_factors(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算全部技术趋势因子，返回附加因子列的 DataFrame。

    输入 DataFrame 必须包含列：close, high, low, volume
    可选列：trade_date, symbol

    输出新增列：
    - ma5, ma10, ma20, ma60
    - close_above_ma5, close_above_ma10, close_above_ma20
    - ma_bullish_align (ma5 > ma10 > ma20)
    - near_20d_high (close >= highest_20 * 0.95)
    - volume_breakout (volume > volume_ma5 * 1.3)
    - atr_14
    - highest_20, lowest_20
    - volume_ma5, volume_ma20
    """
    if df.empty:
        return df

    result = df.copy()

    # 均线
    result["ma5"] = calc_ma(result["close"], 5)
    result["ma10"] = calc_ma(result["close"], 10)
    result["ma20"] = calc_ma(result["close"], 20)
    result["ma60"] = calc_ma(result["close"], 60)

    # 收盘价与均线位置关系
    result["close_above_ma5"] = result["close"] > result["ma5"]
    result["close_above_ma10"] = result["close"] > result["ma10"]
    result["close_above_ma20"] = result["close"] > result["ma20"]

    # 均线多头排列
    result["ma_bullish_align"] = (
        (result["ma5"] > result["ma10"]) &
        (result["ma10"] > result["ma20"])
    )

    # 20日新高/低
    result["highest_20"] = calc_highest(result["high"], 20)
    result["lowest_20"] = calc_lowest(result["low"], 20)
    result["near_20d_high"] = result["close"] >= result["highest_20"] * 0.95

    # 成交量均线与突破
    result["volume_ma5"] = calc_ma(result["volume"].astype(float), 5)
    result["volume_ma20"] = calc_ma(result["volume"].astype(float), 20)
    result["volume_breakout"] = result["volume"].astype(float) > result["volume_ma5"] * 1.3

    # ATR
    result["atr_14"] = calc_atr(result["high"], result["low"], result["close"], 14)

    return result


def compute_trend_score(df: pd.DataFrame) -> pd.Series:
    """
    计算技术趋势分 (0~100)

    评分规则 (ARCHITECTURE.md 5.5 节)：
    - close > ma5: +15
    - close > ma10: +15
    - close > ma20: +20
    - ma5 > ma10 > ma20 (多头排列): +20
    - close >= highest_20 * 0.95 (近20日新高): +15
    - volume > volume_ma5 * 1.3 (量价突破): +15

    总计满分 100
    """
    score = pd.Series(0, index=df.index, dtype=float)

    if "close_above_ma5" in df.columns:
        score += df["close_above_ma5"].astype(float) * 15
    if "close_above_ma10" in df.columns:
        score += df["close_above_ma10"].astype(float) * 15
    if "close_above_ma20" in df.columns:
        score += df["close_above_ma20"].astype(float) * 20
    if "ma_bullish_align" in df.columns:
        score += df["ma_bullish_align"].astype(float) * 20
    if "near_20d_high" in df.columns:
        score += df["near_20d_high"].astype(float) * 15
    if "volume_breakout" in df.columns:
        score += df["volume_breakout"].astype(float) * 15

    return score


def compute_pullback_signal_factors(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算回踩低吸相关因子：
    - pullback_to_ma10: low <= ma10 * 1.02 且 close > ma10
    - pullback_to_ma20: low <= ma20 * 1.02 且 close > ma20
    """
    result = df.copy()
    if "ma10" in result.columns and "low" in result.columns and "close" in result.columns:
        result["pullback_to_ma10"] = (
            (result["low"] <= result["ma10"] * 1.02) &
            (result["close"] > result["ma10"])
        )
    if "ma20" in result.columns and "low" in result.columns and "close" in result.columns:
        result["pullback_to_ma20"] = (
            (result["low"] <= result["ma20"] * 1.02) &
            (result["close"] > result["ma20"])
        )
    return result
