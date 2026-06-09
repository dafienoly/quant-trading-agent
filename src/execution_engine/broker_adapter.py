"""BrokerAdapter 抽象基类与 PaperBroker 模拟交易

EXECUTION_POLICY.md 6: 所有券商接口必须继承 BrokerAdapter 抽象类。
EXECUTION_POLICY.md 9: 模拟交易必须模拟真实流动性约束。
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List

from loguru import logger

from src.models.schemas import AccountInfo, Order, Position, TradeRecord


@dataclass
class OrderResult:
    """订单提交结果"""
    success: bool
    order_id: str = ""
    message: str = ""
    fill_price: float | None = None
    fill_quantity: int | None = None


@dataclass
class CancelResult:
    """撤单结果"""
    success: bool
    message: str = ""


@dataclass
class OrderStatus:
    """订单状态查询结果"""
    order_id: str
    status: str  # CREATED / SENT / FILLED / PARTIALLY_FILLED / REJECTED / CANCELLED
    fill_price: float | None = None
    fill_quantity: int | None = None
    message: str = ""


class BrokerAdapter(ABC):
    """券商接口抽象基类 (EXECUTION_POLICY 6)"""

    @abstractmethod
    def submit_order(self, order: Order) -> OrderResult:
        """提交订单"""

    @abstractmethod
    def cancel_order(self, order_id: str) -> CancelResult:
        """撤销订单"""

    @abstractmethod
    def query_order(self, order_id: str) -> OrderStatus:
        """查询订单状态"""

    @abstractmethod
    def query_positions(self) -> List[Position]:
        """查询持仓"""

    @abstractmethod
    def query_account(self) -> AccountInfo:
        """查询账户信息"""


class PaperBroker(BrokerAdapter):
    """模拟交易接口 (EXECUTION_POLICY 9)

    记录所有操作但不真实成交，模拟流动性约束：
    - 涨停不买、跌停不卖、停牌不成交
    - 模拟成交价使用限价或最新价
    - 同步计算滑点和手续费
    """

    def __init__(
        self,
        initial_cash: float = 1000000.0,
        commission_rate: float = 0.0003,
        stamp_duty_rate: float = 0.001,
        min_commission: float = 5.0,
    ):
        self._cash = initial_cash
        self._initial_cash = initial_cash
        self._commission_rate = commission_rate
        self._stamp_duty_rate = stamp_duty_rate
        self._min_commission = min_commission
        self._positions: dict[str, Position] = {}
        self._orders: dict[str, Order] = {}
        self._trades: list[TradeRecord] = []
        self._pending_orders: dict[str, Order] = {}

    def _calculate_commission(self, amount: float, side: str, market: str = "SZ") -> tuple[float, float]:
        """计算手续费和印花税"""
        commission = max(amount * self._commission_rate, self._min_commission)
        stamp_duty = 0.0
        if side == "SELL":
            stamp_duty_rate = self._stamp_duty_rate
            if market == "HK":
                stamp_duty_rate = 0.0013
            stamp_duty = amount * stamp_duty_rate
        return commission, stamp_duty

    def submit_order(self, order: Order) -> OrderResult:
        """提交模拟订单"""
        self._orders[order.order_id] = order

        # 检查涨停/跌停/停牌（通过 order.market_status 判断，M1 fix）
        market_status = getattr(order, "market_status", "NORMAL") or "NORMAL"
        if market_status == "LIMIT_UP" and order.side == "BUY":
            logger.warning(f"PaperBroker: 涨停股票禁止买入 {order.symbol}")
            return OrderResult(success=False, order_id=order.order_id, message="涨停股票禁止买入")

        if market_status == "LIMIT_DOWN" and order.side == "SELL":
            logger.warning(f"PaperBroker: 跌停股票禁止卖出 {order.symbol}")
            return OrderResult(success=False, order_id=order.order_id, message="跌停股票禁止卖出")

        if market_status == "SUSPENDED":
            logger.warning(f"PaperBroker: 停牌股票禁止交易 {order.symbol}")
            return OrderResult(success=False, order_id=order.order_id, message="停牌股票禁止交易")

        fill_price = order.limit_price
        fill_quantity = order.quantity
        amount = fill_price * fill_quantity
        commission, stamp_duty = self._calculate_commission(amount, order.side, order.market)

        if order.side == "BUY":
            total_cost = amount + commission + stamp_duty
            if total_cost > self._cash:
                return OrderResult(success=False, order_id=order.order_id, message="可用资金不足")
            self._cash -= total_cost
            # 更新持仓
            if order.symbol in self._positions:
                pos = self._positions[order.symbol]
                total_qty = pos.quantity + fill_quantity
                pos.cost_price = (pos.cost_price * pos.quantity + fill_price * fill_quantity) / total_qty
                pos.quantity = total_qty
                # T+1: 当日买入不可卖，available_quantity 不变
            else:
                self._positions[order.symbol] = Position(
                    symbol=order.symbol,
                    market=order.market,
                    name=order.stock_name,
                    quantity=fill_quantity,
                    available_quantity=0,  # T+1: 当日买入不可卖
                    cost_price=fill_price,
                    current_price=fill_price,
                    market_value=amount,
                    sector=order.sector,
                )
        elif order.side == "SELL":
            if order.symbol not in self._positions:
                return OrderResult(success=False, order_id=order.order_id, message="无持仓可卖")
            pos = self._positions[order.symbol]
            if fill_quantity > pos.available_quantity:
                return OrderResult(success=False, order_id=order.order_id, message="可卖数量不足")
            net_amount = amount - commission - stamp_duty
            self._cash += net_amount
            pos.quantity -= fill_quantity
            pos.available_quantity = pos.quantity
            if pos.quantity <= 0:
                del self._positions[order.symbol]

        # 记录成交
        trade = TradeRecord(
            trade_id=f"TRD_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}",
            order_id=order.order_id,
            symbol=order.symbol,
            market=order.market,
            side=order.side,
            price=fill_price,
            quantity=fill_quantity,
            amount=amount,
            commission=commission,
            stamp_duty=stamp_duty,
            net_amount=amount - commission - stamp_duty if order.side == "SELL" else amount + commission + stamp_duty,
            signal_id=order.signal_id,
            risk_check_id=order.risk_check_id,
            strategy_name=order.strategy_name,
            env="paper",
        )
        self._trades.append(trade)

        # 更新订单状态
        order.status = "FILLED"
        order.fill_price = fill_price
        order.fill_quantity = fill_quantity
        order.fill_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        logger.info(f"PaperBroker: 订单成交 {order.order_id} {order.side} {order.symbol} x{fill_quantity}@{fill_price}")
        return OrderResult(
            success=True,
            order_id=order.order_id,
            message="模拟成交",
            fill_price=fill_price,
            fill_quantity=fill_quantity,
        )

    def cancel_order(self, order_id: str) -> CancelResult:
        """撤销模拟订单"""
        if order_id in self._pending_orders:
            self._pending_orders[order_id].status = "CANCELLED"
            del self._pending_orders[order_id]
            return CancelResult(success=True, message="订单已撤销")
        if order_id in self._orders:
            order = self._orders[order_id]
            if order.status in ("FILLED", "REJECTED", "CANCELLED"):
                return CancelResult(success=False, message=f"订单状态为 {order.status}，无法撤销")
            order.status = "CANCELLED"
            return CancelResult(success=True, message="订单已撤销")
        return CancelResult(success=False, message="订单不存在")

    def query_order(self, order_id: str) -> OrderStatus:
        """查询模拟订单状态"""
        if order_id in self._orders:
            order = self._orders[order_id]
            return OrderStatus(
                order_id=order_id,
                status=order.status,
                fill_price=order.fill_price,
                fill_quantity=order.fill_quantity,
            )
        return OrderStatus(order_id=order_id, status="UNKNOWN", message="订单不存在")

    def query_positions(self) -> List[Position]:
        """查询模拟持仓"""
        return list(self._positions.values())

    def query_account(self) -> AccountInfo:
        """查询模拟账户"""
        market_value = sum(p.market_value for p in self._positions.values())
        total_assets = self._cash + market_value
        daily_pnl = total_assets - self._initial_cash
        daily_pnl_pct = daily_pnl / self._initial_cash if self._initial_cash > 0 else 0.0
        return AccountInfo(
            total_assets=total_assets,
            cash=self._cash,
            market_value=market_value,
            available_cash=self._cash,
            daily_pnl=daily_pnl,
            daily_pnl_pct=daily_pnl_pct,
        )

    @property
    def trades(self) -> list[TradeRecord]:
        """获取所有成交记录"""
        return self._trades
