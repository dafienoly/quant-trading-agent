"""统计显著性检验

实现 M4 审计修复：样本外测试的统计显著性检验。
- t 检验：策略超额收益是否显著大于0
- Bootstrap 检验：通过重采样估计置信区间
- 信息比率检验：IC_IR 是否显著
"""
from __future__ import annotations

import math
from typing import Dict, Optional

import numpy as np
import pandas as pd
from loguru import logger


def t_test_excess_return(
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
    confidence: float = 0.95,
) -> Dict[str, float]:
    """
    t 检验：策略超额收益是否显著大于0。

    返回：
    - t_stat: t统计量
    - p_value: p值（单侧）
    - is_significant: 是否在confidence水平下显著
    - mean_excess: 平均超额收益
    - std_excess: 超额收益标准差
    """
    excess = strategy_returns - benchmark_returns
    excess = excess.dropna()

    if len(excess) < 2:
        return {
            "t_stat": 0.0,
            "p_value": 1.0,
            "is_significant": False,
            "mean_excess": 0.0,
            "std_excess": 0.0,
        }

    n = len(excess)
    mean_excess = float(excess.mean())
    std_excess = float(excess.std())

    if std_excess == 0:
        return {
            "t_stat": 0.0,
            "p_value": 1.0,
            "is_significant": False,
            "mean_excess": mean_excess,
            "std_excess": std_excess,
        }

    t_stat = mean_excess / (std_excess / np.sqrt(n))

    try:
        from scipy import stats as scipy_stats

        p_value = float(1 - scipy_stats.t.cdf(t_stat, df=n - 1))
    except ImportError:
        # 无 scipy 时使用正态近似
        p_value = float(1 - 0.5 * (1 + math.erf(t_stat / math.sqrt(2))))

    alpha = 1 - confidence
    is_significant = p_value < alpha

    return {
        "t_stat": round(t_stat, 4),
        "p_value": round(p_value, 6),
        "is_significant": is_significant,
        "mean_excess": round(mean_excess, 6),
        "std_excess": round(std_excess, 6),
    }


def bootstrap_test(
    returns: pd.Series,
    n_bootstrap: int = 1000,
    confidence: float = 0.95,
) -> Dict[str, float]:
    """
    Bootstrap 检验：通过重采样估计收益的置信区间。

    返回：
    - mean: 样本均值
    - ci_lower: 置信区间下界
    - ci_upper: 置信区间上界
    - is_positive: 置信区间是否完全大于0
    """
    returns = returns.dropna()
    if len(returns) < 10:
        return {"mean": 0.0, "ci_lower": 0.0, "ci_upper": 0.0, "is_positive": False}

    n = len(returns)
    bootstrap_means = []

    for _ in range(n_bootstrap):
        sample = np.random.choice(returns.values, size=n, replace=True)
        bootstrap_means.append(float(np.mean(sample)))

    bootstrap_means = np.array(bootstrap_means)
    alpha = 1 - confidence
    ci_lower = float(np.percentile(bootstrap_means, alpha / 2 * 100))
    ci_upper = float(np.percentile(bootstrap_means, (1 - alpha / 2) * 100))

    return {
        "mean": round(float(returns.mean()), 6),
        "ci_lower": round(ci_lower, 6),
        "ci_upper": round(ci_upper, 6),
        "is_positive": ci_lower > 0,
    }


def significance_test_report(
    strategy_returns: pd.Series,
    benchmark_returns: Optional[pd.Series] = None,
    confidence: float = 0.95,
) -> Dict[str, object]:
    """完整的统计显著性检验报告"""
    result = {}

    # 如果有基准，做超额收益检验
    if benchmark_returns is not None and not benchmark_returns.empty:
        aligned_strategy = strategy_returns.reindex(benchmark_returns.index).dropna()
        aligned_benchmark = benchmark_returns.reindex(aligned_strategy.index).dropna()

        if len(aligned_strategy) > 0 and len(aligned_benchmark) > 0:
            result["t_test"] = t_test_excess_return(
                aligned_strategy, aligned_benchmark, confidence
            )

    # Bootstrap 检验
    result["bootstrap"] = bootstrap_test(strategy_returns, confidence=confidence)

    # 结论
    t_significant = result.get("t_test", {}).get("is_significant", False)
    bootstrap_positive = result.get("bootstrap", {}).get("is_positive", False)

    if t_significant and bootstrap_positive:
        result["conclusion"] = "策略收益统计显著为正，样本外结果可信"
    elif t_significant or bootstrap_positive:
        result["conclusion"] = "策略收益部分指标显著，需进一步验证"
    else:
        result["conclusion"] = "策略收益不显著，可能存在过拟合风险"

    logger.info(f"显著性检验: {result['conclusion']}")
    return result
