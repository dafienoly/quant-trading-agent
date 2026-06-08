"""因子评估体系

实现 FACTOR_RESEARCH_GUIDE.md 和 AGENTS.md 3.3 节要求的因子评估指标：
- IC (Information Coefficient): 因子值与下期收益的相关系数
- Rank IC: 因子排名与下期收益排名的Spearman相关系数
- IC_IR (IC Information Ratio): IC均值 / IC标准差
- Turnover: 因子排名换手率
- Coverage: 因子非缺失比例
- Decay Analysis: 因子IC随时间衰减
- Long-Short Return: 多空组合收益

每个因子入库前必须输出上述指标。
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from loguru import logger


def calc_ic(factor: pd.Series, forward_return: pd.Series) -> float:
    """计算IC：因子值与下期收益的Pearson相关系数"""
    valid = factor.notna() & forward_return.notna()
    if valid.sum() < 5:
        return np.nan
    return float(factor[valid].corr(forward_return[valid]))


def calc_rank_ic(factor: pd.Series, forward_return: pd.Series) -> float:
    """计算Rank IC：因子排名与下期收益排名的Spearman相关系数"""
    valid = factor.notna() & forward_return.notna()
    if valid.sum() < 5:
        return np.nan
    factor_rank = factor[valid].rank()
    return_rank = forward_return[valid].rank()
    return float(factor_rank.corr(return_rank))


def calc_ic_series(
    factor_df: pd.DataFrame,
    factor_col: str,
    return_col: str = "forward_return",
    date_col: str = "trade_date",
) -> pd.Series:
    """计算每期IC序列"""
    ic_list = []
    dates = factor_df[date_col].unique() if date_col in factor_df.columns else [0]
    for date in dates:
        if date_col in factor_df.columns:
            subset = factor_df[factor_df[date_col] == date]
        else:
            subset = factor_df
        ic = calc_ic(subset[factor_col], subset[return_col])
        ic_list.append(ic)
    return pd.Series(ic_list, index=dates)


def calc_turnover(factor_df: pd.DataFrame, factor_col: str, date_col: str = "trade_date", top_n: int = 5) -> float:
    """计算因子排名换手率：相邻两期top_n股票集合的变化比例"""
    if date_col not in factor_df.columns:
        return np.nan
    dates = sorted(factor_df[date_col].unique())
    if len(dates) < 2:
        return np.nan

    turnovers = []
    for i in range(1, len(dates)):
        prev = factor_df[factor_df[date_col] == dates[i - 1]]
        curr = factor_df[factor_df[date_col] == dates[i]]
        prev_top = set(prev.nlargest(top_n, factor_col)["symbol"].tolist())
        curr_top = set(curr.nlargest(top_n, factor_col)["symbol"].tolist())
        if prev_top and curr_top:
            turnover = 1 - len(prev_top & curr_top) / len(prev_top | curr_top)
            turnovers.append(turnover)

    return float(np.mean(turnovers)) if turnovers else np.nan


def calc_coverage(factor: pd.Series) -> float:
    """计算因子覆盖率：非缺失比例"""
    if len(factor) == 0:
        return 0.0
    return float(factor.notna().mean())


def calc_decay(
    factor_df: pd.DataFrame,
    factor_col: str,
    return_col: str = "forward_return",
    date_col: str = "trade_date",
    max_lag: int = 5,
) -> Dict[str, float]:
    """计算因子IC衰减：IC随滞后期数的变化"""
    decay = {}
    for lag in range(1, max_lag + 1):
        lagged_return = factor_df.groupby("symbol")[return_col].shift(-lag)
        ic = calc_ic(factor_df[factor_col], lagged_return)
        decay[f"ic_lag_{lag}"] = ic
    return decay


def calc_long_short_return(
    factor_df: pd.DataFrame,
    factor_col: str,
    return_col: str = "forward_return",
    date_col: str = "trade_date",
    n_groups: int = 5,
) -> Dict[str, float]:
    """计算多空组合收益：最高组 - 最低组"""
    if date_col not in factor_df.columns:
        return {"long_short_return": np.nan}

    results = []
    for date in factor_df[date_col].unique():
        subset = factor_df[factor_df[date_col] == date].dropna(subset=[factor_col, return_col])
        if len(subset) < n_groups * 2:
            continue
        subset["group"] = pd.qcut(subset[factor_col], n_groups, labels=False, duplicates="drop")
        long_ret = subset[subset["group"] == n_groups - 1][return_col].mean()
        short_ret = subset[subset["group"] == 0][return_col].mean()
        results.append(long_ret - short_ret)

    return {"long_short_return": float(np.mean(results)) if results else np.nan}


def evaluate_factor(
    factor_df: pd.DataFrame,
    factor_col: str,
    return_col: str = "forward_return",
    date_col: str = "trade_date",
    symbol_col: str = "symbol",
) -> Dict[str, object]:
    """
    完整因子评估，输出 FACTOR_RESEARCH_GUIDE.md 要求的全部指标。

    返回字典包含：
    - factor_name
    - ic_mean, ic_std, ic_ir
    - rank_ic_mean
    - turnover
    - coverage
    - decay_analysis
    - long_short_return
    """
    result = {"factor_name": factor_col}

    # IC 序列
    ic_series = calc_ic_series(factor_df, factor_col, return_col, date_col)
    result["ic_mean"] = float(ic_series.mean()) if not ic_series.empty else np.nan
    result["ic_std"] = float(ic_series.std()) if len(ic_series) > 1 else np.nan
    result["ic_ir"] = (
        result["ic_mean"] / result["ic_std"]
        if result["ic_std"] and result["ic_std"] != 0 and not np.isnan(result["ic_std"])
        else np.nan
    )

    # Rank IC
    rank_ics = []
    for date in factor_df[date_col].unique() if date_col in factor_df.columns else [0]:
        if date_col in factor_df.columns:
            subset = factor_df[factor_df[date_col] == date]
        else:
            subset = factor_df
        ric = calc_rank_ic(subset[factor_col], subset[return_col])
        rank_ics.append(ric)
    result["rank_ic_mean"] = float(np.nanmean(rank_ics)) if rank_ics else np.nan

    # Turnover
    result["turnover"] = calc_turnover(factor_df, factor_col, date_col)

    # Coverage
    result["coverage"] = calc_coverage(factor_df[factor_col])

    # Decay
    result["decay_analysis"] = calc_decay(factor_df, factor_col, return_col, date_col)

    # Long-Short Return
    ls_result = calc_long_short_return(factor_df, factor_col, return_col, date_col)
    result["long_short_return"] = ls_result.get("long_short_return", np.nan)

    logger.info(
        f"Factor evaluation: {factor_col}, "
        f"IC_mean={result['ic_mean']:.4f}, "
        f"Rank_IC={result['rank_ic_mean']:.4f}, "
        f"IC_IR={result['ic_ir']:.4f}, "
        f"coverage={result['coverage']:.2%}"
    )

    return result


def evaluate_all_factors(
    factor_df: pd.DataFrame,
    factor_cols: Optional[List[str]] = None,
    return_col: str = "forward_return",
    date_col: str = "trade_date",
    symbol_col: str = "symbol",
) -> pd.DataFrame:
    """
    批量评估多个因子，返回汇总 DataFrame。
    """
    if factor_cols is None:
        factor_cols = [
            "trend_score", "sentiment_score",
            "policy_score", "fundamental_score",
        ]

    # 计算下期收益
    if return_col not in factor_df.columns:
        if "pct_change" in factor_df.columns and symbol_col in factor_df.columns:
            factor_df = factor_df.copy()
            factor_df[return_col] = factor_df.groupby("symbol")["pct_change"].shift(-1)

    results = []
    for col in factor_cols:
        if col in factor_df.columns:
            eval_result = evaluate_factor(factor_df, col, return_col, date_col)
            results.append(eval_result)

    return pd.DataFrame(results)
