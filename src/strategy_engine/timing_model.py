"""择时模型

实现 ARCHITECTURE.md 2 节定义的 timing_model：
- 交易时段控制：仅允许在交易时间内生成买入信号
- 择时规则：避免尾盘追高、开盘急跌买入等
- 信号时间窗口过滤

EXECUTION_POLICY.md 定义交易时段：
- 上午：09:30 ~ 11:30
- 下午：13:00 ~ 15:00
"""
from __future__ import annotations

from datetime import datetime, time
from typing import Optional

from loguru import logger


# 交易时段定义
MORNING_OPEN = time(9, 30)
MORNING_CLOSE = time(11, 30)
AFTERNOON_OPEN = time(13, 0)
AFTERNOON_CLOSE = time(15, 0)

# 择时窗口
NO_BUY_BEFORE = time(9, 35)   # 开盘前5分钟不买入
NO_BUY_AFTER = time(14, 50)   # 收盘前10分钟不买入
AVOID_OPEN_RUSH_END = time(9, 45)  # 开盘急跌期结束


def is_trading_time(dt: Optional[datetime] = None) -> bool:
    """判断当前是否在交易时段内"""
    if dt is None:
        dt = datetime.now()
    t = dt.time()
    return (MORNING_OPEN <= t <= MORNING_CLOSE) or (AFTERNOON_OPEN <= t <= AFTERNOON_CLOSE)


def is_buy_allowed(dt: Optional[datetime] = None) -> bool:
    """判断当前是否允许买入（排除开盘急跌和尾盘追高）"""
    if dt is None:
        dt = datetime.now()
    t = dt.time()

    # 非交易时段不允许买入
    if not is_trading_time(dt):
        return False

    # 开盘前5分钟不买入（避免急跌）
    if MORNING_OPEN <= t < NO_BUY_BEFORE:
        return False

    # 尾盘10分钟不买入（避免追高）
    if NO_BUY_AFTER <= t <= AFTERNOON_CLOSE:
        return False

    return True


def is_sell_allowed(dt: Optional[datetime] = None) -> bool:
    """判断当前是否允许卖出（止损随时允许，止盈需在交易时段）"""
    return is_trading_time(dt)


def get_timing_advice(dt: Optional[datetime] = None) -> dict:
    """获取当前择时建议"""
    if dt is None:
        dt = datetime.now()

    return {
        "is_trading_time": is_trading_time(dt),
        "is_buy_allowed": is_buy_allowed(dt),
        "is_sell_allowed": is_sell_allowed(dt),
        "current_time": dt.strftime("%H:%M:%S"),
        "advice": _get_advice_text(dt),
    }


def _get_advice_text(dt: datetime) -> str:
    t = dt.time()
    if not is_trading_time(dt):
        return "非交易时段，等待开盘"
    if MORNING_OPEN <= t < AVOID_OPEN_RUSH_END:
        return "开盘急跌期，建议观望"
    if NO_BUY_AFTER <= t <= AFTERNOON_CLOSE:
        return "尾盘时段，不建议新建仓位"
    return "正常交易时段，可执行信号"
