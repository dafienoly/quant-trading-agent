"""策略总评分模型

实现 ARCHITECTURE.md 5.1 节定义的总评分：

total_score = 0.25 * policy_score
            + 0.30 * sentiment_score
            + 0.20 * fundamental_score
            + 0.25 * trend_score

总评分范围 0~100。
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger

from src.factor_engine.technical_factors import compute_technical_factors, compute_trend_score
from src.factor_engine.sentiment_factors import compute_sentiment_factors, compute_sentiment_score
from src.factor_engine.theme_factors import compute_policy_score_for_df
from src.factor_engine.fundamental_factors import compute_fundamental_factors, compute_fundamental_score
from src.stock_pool.semiconductor import SemiconductorPool


# 权重常量（ARCHITECTURE.md 5.1 节）
WEIGHT_POLICY = 0.25
WEIGHT_SENTIMENT = 0.30
WEIGHT_FUNDAMENTAL = 0.20
WEIGHT_TREND = 0.25


def compute_all_factors(
    df: pd.DataFrame,
    pool: Optional[SemiconductorPool] = None,
    benchmark_pct: Optional[pd.Series] = None,
    sector_pct: Optional[pd.Series] = None,
) -> pd.DataFrame:
    """
    计算全部四类因子并合并到 DataFrame。

    输入 DataFrame 必须包含：symbol, close, high, low, volume, amount, pct_change
    输出新增列：所有技术因子 + 情绪因子 + 政策主题分 + 基本面分 + 四类评分 + 总评分
    """
    if df.empty:
        return df

    result = df.copy()

    # 1. 技术趋势因子
    result = compute_technical_factors(result)
    result["trend_score"] = compute_trend_score(result)

    # 2. 情绪资金因子
    result = compute_sentiment_factors(result, benchmark_pct=benchmark_pct, sector_pct=sector_pct)
    result["sentiment_score"] = compute_sentiment_score(result)

    # 3. 政策主题因子
    result = compute_policy_score_for_df(result, pool=pool)

    # 4. 基本面因子
    result = compute_fundamental_factors(result)
    result["fundamental_score"] = compute_fundamental_score(result)

    # 5. 总评分
    result["total_score"] = (
        WEIGHT_POLICY * result["policy_score"]
        + WEIGHT_SENTIMENT * result["sentiment_score"]
        + WEIGHT_FUNDAMENTAL * result["fundamental_score"]
        + WEIGHT_TREND * result["trend_score"]
    )

    return result


def compute_total_score_only(
    policy_score: float | pd.Series,
    sentiment_score: float | pd.Series,
    fundamental_score: float | pd.Series,
    trend_score: float | pd.Series,
) -> float | pd.Series:
    """单独计算总评分，用于已知四类评分的场景"""
    return (
        WEIGHT_POLICY * policy_score
        + WEIGHT_SENTIMENT * sentiment_score
        + WEIGHT_FUNDAMENTAL * fundamental_score
        + WEIGHT_TREND * trend_score
    )
