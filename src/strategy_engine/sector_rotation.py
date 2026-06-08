"""板块轮动评分

计算半导体各子板块的强弱排名，用于：
1. 确定当前最强/最弱板块
2. 辅助买入信号中的板块强度判断
3. 生成盘前报告中的板块分析

评分维度：
- 板块平均涨跌幅（动量）
- 板块成交额变化（资金流向）
- 板块内上涨股票占比（广度）
- 板块政策权重（主题热度）
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from loguru import logger

from src.stock_pool.semiconductor import SemiconductorPool


def compute_sector_scores(
    df: pd.DataFrame,
    pool: Optional[SemiconductorPool] = None,
) -> pd.DataFrame:
    """
    计算各子板块的轮动评分。

    输入 DataFrame 必须包含：symbol, pct_change, amount
    可选列：close, volume

    输出 DataFrame 列：
    - sector_key, sector_name
    - avg_pct_change: 板块平均涨跌幅
    - total_amount: 板块总成交额
    - advance_ratio: 上涨股票占比
    - policy_weight: 政策权重
    - sector_score: 综合评分 (0~100)
    """
    if df.empty:
        return pd.DataFrame()

    if pool is None:
        pool = SemiconductorPool()

    weights = pool.get_policy_weights()
    sector_data = pool.get_stocks_by_sector()

    # 为每只股票添加板块标记
    df_with_sector = df.copy()
    codes = df_with_sector["symbol"].apply(lambda s: s.split(".")[0] if "." in str(s) else str(s))
    df_with_sector["sector_key"] = codes.apply(lambda c: pool.get_sector(c) or "")

    # 按板块聚合
    results = []
    for sector_key, sector_info in sector_data.items():
        sector_stocks = df_with_sector[df_with_sector["sector_key"] == sector_key]
        if sector_stocks.empty:
            continue

        avg_pct = sector_stocks["pct_change"].mean() if "pct_change" in sector_stocks.columns else 0
        total_amount = sector_stocks["amount"].sum() if "amount" in sector_stocks.columns else 0
        advance_count = (sector_stocks["pct_change"] > 0).sum() if "pct_change" in sector_stocks.columns else 0
        advance_ratio = advance_count / len(sector_stocks) if len(sector_stocks) > 0 else 0
        policy_weight = float(weights.get(sector_key, 50))

        # 综合评分：
        # - 动量(30%): avg_pct_change -5~+5 → 0~30
        # - 资金(20%): 成交额排名百分位 × 20
        # - 广度(20%): advance_ratio × 20
        # - 政策(30%): policy_weight / 100 × 30
        momentum_score = np.clip((avg_pct + 5) / 10 * 30, 0, 30)
        breadth_score = advance_ratio * 20
        policy_score = policy_weight / 100 * 30

        sector_score = momentum_score + breadth_score + policy_score

        results.append({
            "sector_key": sector_key,
            "sector_name": sector_info.get("name", sector_key),
            "stock_count": len(sector_stocks),
            "avg_pct_change": round(avg_pct, 2),
            "total_amount": total_amount,
            "advance_ratio": round(advance_ratio, 2),
            "policy_weight": policy_weight,
            "sector_score": round(sector_score, 2),
        })

    result_df = pd.DataFrame(results)
    if not result_df.empty:
        # 资金维度评分
        if len(result_df) > 1:
            # 多板块：使用排名百分位
            result_df["amount_rank_pct"] = result_df["total_amount"].rank(pct=True)
            result_df["sector_score"] = result_df["sector_score"] + result_df["amount_rank_pct"] * 20
        else:
            # 单板块：使用绝对评分，成交额 >= 5亿给满分20，<= 1亿给0分
            amount_abs_score = np.clip(result_df["total_amount"].iloc[0] / 5e8 * 20, 0, 20)
            result_df["sector_score"] = result_df["sector_score"] + amount_abs_score
            result_df["amount_rank_pct"] = amount_abs_score / 20  # 归一化记录

        # 归一化到 0~100
        max_possible = 30 + 20 + 20 + 30  # 100
        result_df["sector_score"] = (result_df["sector_score"] / max_possible * 100).round(2)
        result_df = result_df.sort_values("sector_score", ascending=False).reset_index(drop=True)

    return result_df
