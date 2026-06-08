"""组合管理模型

实现 ARCHITECTURE.md 2 节定义的 portfolio_model：
- 仓位分配：根据信号强度和风控约束分配仓位
- 板块约束：单板块不超过60%
- 现金约束：保留20%最低现金
- 单票约束：单票不超过15%

Phase 2 初期实现简化版本，Phase 3 回测时完善。
"""
from __future__ import annotations

from typing import Dict, List, Optional

from loguru import logger

from src.config.settings import (
    MAX_SINGLE_STOCK_POSITION,
    MAX_SECTOR_POSITION,
    MIN_CASH_RATIO,
)


def allocate_position(
    signal_score: float,
    current_positions: Optional[Dict[str, float]] = None,
    sector_exposure: Optional[Dict[str, float]] = None,
    total_capital: float = 100000.0,
    cash_ratio: float = 1.0,
) -> float:
    """
    根据信号强度和风控约束计算建议仓位比例。

    参数：
        signal_score: 信号评分 (0~100)
        current_positions: 当前持仓 {symbol: position_pct}
        sector_exposure: 当前板块暴露 {sector: exposure_pct}
        total_capital: 总资金
        cash_ratio: 当前现金比例

    返回：
        建议仓位比例 (0~MAX_SINGLE_STOCK_POSITION)
    """
    if current_positions is None:
        current_positions = {}
    if sector_exposure is None:
        sector_exposure = {}

    # 现金约束：低于最低现金比例时不建仓
    if cash_ratio < MIN_CASH_RATIO:
        logger.warning(f"现金比例{cash_ratio:.1%}低于最低要求{MIN_CASH_RATIO:.1%}，不建仓")
        return 0.0

    # 基础仓位：根据评分线性映射
    base_position = signal_score / 100 * MAX_SINGLE_STOCK_POSITION

    # 单票约束
    position = min(base_position, MAX_SINGLE_STOCK_POSITION)

    return round(position, 4)


def check_sector_constraint(
    sector: str,
    new_position: float,
    sector_exposure: Dict[str, float],
) -> bool:
    """检查板块约束：单板块不超过60%"""
    current = sector_exposure.get(sector, 0.0)
    if current + new_position > MAX_SECTOR_POSITION:
        logger.warning(
            f"板块{sector}暴露{current:.1%}+{new_position:.1%}="
            f"{current + new_position:.1%}超过限制{MAX_SECTOR_POSITION:.1%}"
        )
        return False
    return True


def check_cash_constraint(cash_ratio: float) -> bool:
    """检查现金约束：保留20%最低现金"""
    if cash_ratio < MIN_CASH_RATIO:
        logger.warning(f"现金比例{cash_ratio:.1%}低于最低要求{MIN_CASH_RATIO:.1%}")
        return False
    return True
