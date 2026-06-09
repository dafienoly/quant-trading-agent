"""订单检查器 (EXECUTION_POLICY 4-5)

在订单发送前执行最终检查：
- 价格合理性
- 数量合规（100股整数倍、不超可用资金/持仓）
- 交易时段
- 资金充足性
- 黑名单检查
- 创业板/科创板禁止买入
"""
from __future__ import annotations

import math
from datetime import datetime, time

from loguru import logger

from src.models.schemas import AccountInfo, Order, OrderDraft, Position
from src.stock_pool.mainboard_filter import is_excluded


# A股交易时段 (EXECUTION_POLICY 7)
A_SHARE_MORNING_OPEN = time(9, 30)
A_SHARE_MORNING_CLOSE = time(11, 30)
A_SHARE_AFTERNOON_OPEN = time(13, 0)
A_SHARE_AFTERNOON_CLOSE = time(15, 0)

# 尾盘禁止开新仓 (EXECUTION_POLICY 7)
A_SHARE_NO_NEW_BUY_START = time(14, 55)

# 港股交易时段
HK_MORNING_OPEN = time(9, 30)
HK_MORNING_CLOSE = time(12, 0)
HK_AFTERNOON_OPEN = time(13, 0)
HK_AFTERNOON_CLOSE = time(16, 0)


class OrderCheckResult:
    """订单检查结果"""

    def __init__(self, passed: bool, reason: str = "", adjusted_quantity: int | None = None):
        self.passed = passed
        self.reason = reason
        self.adjusted_quantity = adjusted_quantity


def is_trading_hours(market: str = "SZ", now: datetime | None = None) -> bool:
    """检查当前是否在交易时段 (EXECUTION_POLICY 7)"""
    if now is None:
        now = datetime.now()
    t = now.time()

    if market == "HK":
        return (HK_MORNING_OPEN <= t <= HK_MORNING_CLOSE or
                HK_AFTERNOON_OPEN <= t <= HK_AFTERNOON_CLOSE)
    else:
        return (A_SHARE_MORNING_OPEN <= t <= A_SHARE_MORNING_CLOSE or
                A_SHARE_AFTERNOON_OPEN <= t <= A_SHARE_AFTERNOON_CLOSE)


def is_no_new_buy_period(market: str = "SZ", now: datetime | None = None) -> bool:
    """检查是否在尾盘禁止开新仓时段"""
    if market == "HK":
        return False  # 港股无此限制
    if now is None:
        now = datetime.now()
    t = now.time()
    return A_SHARE_NO_NEW_BUY_START <= t <= A_SHARE_AFTERNOON_CLOSE


def calculate_buy_quantity(
    available_cash: float,
    price: float,
    position_pct: float,
    commission_rate: float = 0.0003,
    lot_size: int = 100,
) -> int:
    """计算买入数量 (EXECUTION_POLICY 4.1)

    quantity = floor(可用资金 * 仓位比例 / (limit_price * (1 + 手续费率)))
    quantity = min(quantity, 单票最大仓位限制换算数量)
    quantity = 100 的整数倍（A股）
    """
    max_amount = available_cash * position_pct
    price_with_cost = price * (1 + commission_rate)
    if price_with_cost <= 0:
        return 0
    raw_quantity = max_amount / price_with_cost
    lot_quantity = math.floor(raw_quantity / lot_size) * lot_size
    return max(lot_quantity, 0)


class OrderChecker:
    """订单检查器 (EXECUTION_POLICY 4-5)"""

    def __init__(
        self,
        commission_rate: float = 0.0003,
        lot_size: int = 100,
        min_quantity: int = 100,
        blacklist: set[str] | None = None,
    ):
        self._commission_rate = commission_rate
        self._lot_size = lot_size
        self._min_quantity = min_quantity
        self._blacklist = blacklist or set()

    def check_order(
        self,
        draft: OrderDraft,
        account: AccountInfo,
        positions: list[Position],
        now: datetime | None = None,
    ) -> OrderCheckResult:
        """执行订单检查，返回检查结果"""
        # 1. 创业板/科创板禁止买入 (EXECUTION_POLICY 10.5)
        if draft.side == "BUY" and is_excluded(draft.symbol):
            return OrderCheckResult(passed=False, reason=f"禁止买入创业板/科创板股票: {draft.symbol}")

        # 1.5 ST 股检测 (L1 fix: 审计要求增加 ST 股风险提示)
        if draft.side == "BUY" and draft.stock_name and "ST" in draft.stock_name.upper():
            return OrderCheckResult(passed=False, reason=f"禁止买入ST股票: {draft.symbol} ({draft.stock_name})")

        # 2. 黑名单检查 (RISK_POLICY 4.2)
        code = draft.symbol.split(".")[0] if "." in draft.symbol else draft.symbol
        if code in self._blacklist or draft.symbol in self._blacklist:
            return OrderCheckResult(passed=False, reason=f"黑名单股票: {draft.symbol}")

        # 3. 交易时段检查 (EXECUTION_POLICY 7)
        if not is_trading_hours(draft.market, now):
            return OrderCheckResult(passed=False, reason="非交易时段")

        # 4. 尾盘禁止开新仓 (EXECUTION_POLICY 7)
        if draft.side == "BUY" and is_no_new_buy_period(draft.market, now):
            return OrderCheckResult(passed=False, reason="尾盘禁止开新仓买入")

        # 5. 价格合理性检查
        if draft.limit_price <= 0:
            return OrderCheckResult(passed=False, reason="价格必须大于0")

        # 6. 数量检查
        if draft.quantity <= 0:
            return OrderCheckResult(passed=False, reason="数量必须大于0")

        if draft.quantity % self._lot_size != 0:
            return OrderCheckResult(passed=False, reason=f"数量必须是{self._lot_size}的整数倍")

        if draft.quantity < self._min_quantity:
            return OrderCheckResult(passed=False, reason=f"数量不得小于{self._min_quantity}股")

        # 7. 买入资金检查 (EXECUTION_POLICY 4.1)
        if draft.side == "BUY":
            cost = draft.limit_price * draft.quantity * (1 + self._commission_rate)
            if cost > account.available_cash:
                # 尝试调整数量
                adjusted = calculate_buy_quantity(
                    account.available_cash, draft.limit_price, 1.0, self._commission_rate, self._lot_size
                )
                if adjusted < self._min_quantity:
                    return OrderCheckResult(passed=False, reason="可用资金不足，调整后数量小于最低限制")
                return OrderCheckResult(
                    passed=True,
                    reason=f"数量已调整: {draft.quantity} -> {adjusted}（资金不足）",
                    adjusted_quantity=adjusted,
                )

        # 8. 卖出持仓检查 (EXECUTION_POLICY 4.2)
        if draft.side == "SELL":
            pos = next((p for p in positions if p.symbol == draft.symbol), None)
            if pos is None:
                return OrderCheckResult(passed=False, reason="无持仓可卖")
            if draft.quantity > pos.available_quantity:
                return OrderCheckResult(passed=False, reason=f"可卖数量不足: 可卖{pos.available_quantity}股")

        logger.info(f"OrderChecker: 订单检查通过 {draft.symbol} {draft.side} x{draft.quantity}")
        return OrderCheckResult(passed=True)
