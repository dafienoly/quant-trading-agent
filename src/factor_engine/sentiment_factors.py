"""情绪资金因子计算

实现 ARCHITECTURE.md 5.3 节定义的情绪资金分（7个指标）：
- volume_ratio: 量比（当日成交量 / 过去5日平均成交量）
- amount_ratio: 额比（当日成交额 / 过去5日平均成交额）
- turnover_ratio: 换手率比（当日换手率 / 过去20日平均换手率）
- relative_strength: 相对强度（个股涨幅 vs 指数涨幅）
- sector_strength: 板块强度（个股涨幅 vs 板块平均涨幅）
- limit_up_count: 近5日涨停次数
- large_order_flow: 大单净流入占比

情绪资金分公式：
sentiment_score = 15*rank(volume_ratio) + 15*rank(amount_ratio)
                + 14*rank(turnover_ratio) + 14*rank(relative_strength)
                + 14*rank(sector_strength) + 14*rank(limit_up_count)
                + 14*rank(large_order_flow)

rank 为横截面排名百分位（0~1），单只股票时使用绝对评分。
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger


def calc_volume_ratio(volume: pd.Series, window: int = 5) -> pd.Series:
    """计算量比：当日成交量 / 过去window日平均成交量"""
    vol_ma = volume.rolling(window=window, min_periods=1).mean().shift(1)
    result = volume / vol_ma.replace(0, np.nan)
    return result


def calc_amount_ratio(amount: pd.Series, window: int = 5) -> pd.Series:
    """计算额比：当日成交额 / 过去window日平均成交额"""
    amt_ma = amount.rolling(window=window, min_periods=1).mean().shift(1)
    result = amount / amt_ma.replace(0, np.nan)
    return result


def calc_turnover_ratio(turnover_rate: pd.Series, window: int = 20) -> pd.Series:
    """计算换手率比：当日换手率 / 过去window日平均换手率"""
    tr_ma = turnover_rate.rolling(window=window, min_periods=1).mean().shift(1)
    result = turnover_rate / tr_ma.replace(0, np.nan)
    return result


def calc_relative_strength(
    stock_pct_change: pd.Series,
    benchmark_pct_change: pd.Series,
) -> pd.Series:
    """计算相对强度：个股涨跌幅 - 基准涨跌幅"""
    return stock_pct_change - benchmark_pct_change


def calc_sector_strength(
    stock_pct_change: pd.Series,
    sector_pct_change: pd.Series,
) -> pd.Series:
    """计算板块强度：个股涨跌幅 - 板块平均涨跌幅"""
    return stock_pct_change - sector_pct_change


def calc_limit_up_count(pct_change: pd.Series, window: int = 5, threshold: float = 9.5) -> pd.Series:
    """计算近window日涨停次数（涨幅>=threshold视为涨停）"""
    is_limit_up = (pct_change >= threshold).astype(float)
    return is_limit_up.rolling(window=window, min_periods=1).sum()


def calc_large_order_flow(
    volume: pd.Series,
    amount: pd.Series,
    close: pd.Series,
    window: int = 5,
) -> pd.Series:
    """
    估算大单净流入占比（简化版本）。

    使用成交额/成交量与均价的偏离度估算大单活跃度：
    - 当均价（amount/volume）接近收盘价上方时，大单偏买入
    - 当均价接近收盘价下方时，大单偏卖出

    返回 -1~1 的值，正数表示大单净流入，负数表示净流出。
    """
    avg_price = amount / volume.replace(0, np.nan)
    # 偏离度 = (均价 - 收盘价) / 收盘价
    deviation = (avg_price - close) / close.replace(0, np.nan)
    # 标准化到 -1~1
    result = deviation.clip(-0.02, 0.02) / 0.02
    return result


def cross_section_rank(series: pd.Series) -> pd.Series:
    """
    横截面排名百分位（0~1）
    对一组股票的同日因子值进行排名
    """
    if len(series) <= 1:
        return pd.Series(0.5, index=series.index)
    return series.rank(pct=True, na_option="keep")


def compute_sentiment_factors(
    df: pd.DataFrame,
    benchmark_pct: Optional[pd.Series] = None,
    sector_pct: Optional[pd.Series] = None,
) -> pd.DataFrame:
    """
    计算情绪资金因子，返回附加因子列的 DataFrame。

    输入必须包含：volume, amount, pct_change
    可选列：turnover_rate, close, benchmark_pct_change, sector_pct_change

    输出新增列：
    - volume_ratio, amount_ratio, turnover_ratio
    - relative_strength, sector_strength
    - limit_up_count, large_order_flow
    """
    if df.empty:
        return df

    result = df.copy()

    # 量比和额比
    result["volume_ratio"] = calc_volume_ratio(result["volume"].astype(float))
    result["amount_ratio"] = calc_amount_ratio(result["amount"].astype(float))

    # 换手率比
    if "turnover_rate" in result.columns:
        result["turnover_ratio"] = calc_turnover_ratio(result["turnover_rate"].astype(float))
    else:
        result["turnover_ratio"] = np.nan

    # 相对强度
    if benchmark_pct is not None:
        result["relative_strength"] = calc_relative_strength(
            result["pct_change"], benchmark_pct
        )
    elif "benchmark_pct_change" in result.columns:
        result["relative_strength"] = calc_relative_strength(
            result["pct_change"], result["benchmark_pct_change"]
        )
    else:
        result["relative_strength"] = result["pct_change"]

    # 板块强度
    if sector_pct is not None:
        result["sector_strength"] = calc_sector_strength(
            result["pct_change"], sector_pct
        )
    elif "sector_pct_change" in result.columns:
        result["sector_strength"] = calc_sector_strength(
            result["pct_change"], result["sector_pct_change"]
        )
    else:
        result["sector_strength"] = result["pct_change"]

    # 近5日涨停次数
    result["limit_up_count"] = calc_limit_up_count(result["pct_change"])

    # 大单净流入占比
    if "close" in result.columns:
        result["large_order_flow"] = calc_large_order_flow(
            result["volume"].astype(float),
            result["amount"].astype(float),
            result["close"],
        )
    else:
        result["large_order_flow"] = np.nan

    return result


def compute_sentiment_score(
    df: pd.DataFrame,
    is_cross_section: bool = False,
) -> pd.Series:
    """
    计算情绪资金分 (0~100)

    7因子评分（ARCHITECTURE.md 5.3 节）：
    横截面模式 (is_cross_section=True)：
      每个因子 14~15 分，合计 100 分

    时间序列模式 (is_cross_section=False，默认)：
      使用绝对评分，将因子值映射到对应分值
    """
    score = pd.Series(0.0, index=df.index)

    if is_cross_section:
        weights = {
            "volume_ratio": 15,
            "amount_ratio": 15,
            "turnover_ratio": 14,
            "relative_strength": 14,
            "sector_strength": 14,
            "limit_up_count": 14,
            "large_order_flow": 14,
        }
        for col, weight in weights.items():
            if col in df.columns:
                ranked = cross_section_rank(df[col].fillna(0))
                score += ranked * weight
    else:
        # 绝对评分模式
        if "volume_ratio" in df.columns:
            score += np.clip((df["volume_ratio"].fillna(1) - 0.5) / 1.5 * 15, 0, 15)

        if "amount_ratio" in df.columns:
            score += np.clip((df["amount_ratio"].fillna(1) - 0.5) / 1.5 * 15, 0, 15)

        if "turnover_ratio" in df.columns:
            # 换手率比 0.5~2.0 映射到 0~14
            score += np.clip((df["turnover_ratio"].fillna(1) - 0.5) / 1.5 * 14, 0, 14)

        if "relative_strength" in df.columns:
            score += np.clip((df["relative_strength"].fillna(0) + 5) / 10 * 14, 0, 14)

        if "sector_strength" in df.columns:
            score += np.clip((df["sector_strength"].fillna(0) + 5) / 10 * 14, 0, 14)

        if "limit_up_count" in df.columns:
            # 0~3次涨停 映射到 0~14
            score += np.clip(df["limit_up_count"].fillna(0) / 3 * 14, 0, 14)

        if "large_order_flow" in df.columns:
            # -1~1 映射到 0~14
            score += np.clip((df["large_order_flow"].fillna(0) + 1) / 2 * 14, 0, 14)

    return score
