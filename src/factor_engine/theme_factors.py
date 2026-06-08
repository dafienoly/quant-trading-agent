"""政策主题因子计算

实现 ARCHITECTURE.md 5.2 节定义的政策主题分：
- 半静态因子，由人工维护或 LLM 辅助更新
- 从 stock_pool.yaml 的 sector_policy_weight 读取板块权重
- 每只股票绑定一个或多个主题，取最高分或加权平均

板块政策权重（默认值）：
- semiconductor_equipment: 100
- semiconductor_material: 95
- advanced_packaging: 95
- pcb_ccl: 90
- memory_hbm: 85
- optical_module_cpo: 80
- chip_design: 65
- traditional_packaging: 60
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import yaml
from loguru import logger

from src.stock_pool.semiconductor import SemiconductorPool


def compute_policy_score(
    symbols: List[str],
    pool: Optional[SemiconductorPool] = None,
) -> pd.DataFrame:
    """
    计算政策主题分。

    每只股票根据所属板块获取政策权重分，映射到 0~100。
    不在任何板块的股票得分为 0。

    参数：
        symbols: 股票代码列表（如 ["002463.SZ", "600584.SH"]）
        pool: SemiconductorPool 实例，为 None 时使用默认配置

    返回：
        DataFrame 列：symbol, sector_key, policy_score
    """
    if pool is None:
        pool = SemiconductorPool()

    weights = pool.get_policy_weights()
    rows = []

    for symbol in symbols:
        code = symbol.split(".")[0] if "." in symbol else symbol
        sector_key = pool.get_sector(code)

        if sector_key and sector_key in weights:
            policy_score = float(weights[sector_key])
        else:
            policy_score = 0.0

        rows.append({
            "symbol": symbol,
            "sector_key": sector_key or "",
            "policy_score": policy_score,
        })

    return pd.DataFrame(rows)


def compute_policy_score_for_df(
    df: pd.DataFrame,
    pool: Optional[SemiconductorPool] = None,
) -> pd.DataFrame:
    """
    为 DataFrame 中的股票计算政策主题分，合并回原 DataFrame。

    输入 DataFrame 必须包含 symbol 列。
    输出新增列：sector_key, policy_score
    """
    if df.empty:
        return df

    result = df.copy()
    symbols = result["symbol"].unique().tolist()
    policy_df = compute_policy_score(symbols, pool=pool)

    # 合并
    result = result.merge(
        policy_df[["symbol", "sector_key", "policy_score"]],
        on="symbol",
        how="left",
    )
    result["policy_score"] = result["policy_score"].fillna(0.0)
    result["sector_key"] = result["sector_key"].fillna("")

    return result
