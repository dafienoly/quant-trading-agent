"""持仓管理

实现回测中的持仓/资金/交易记录管理：
- 持仓跟踪：每只股票的持仓数量、成本价、当前价
- 资金管理：可用现金、总资产
- 交易记录：每笔买入/卖出的完整记录
- 涨跌停/停牌检查：涨停无法买入，跌停无法卖出，停牌无法交易
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd
from loguru import logger

from src.backtest_engine.commission_model import CommissionModel


@dataclass
class Position:
    """单只股票持仓"""
    symbol: str
    quantity: int = 0
    cost_price: float = 0.0  # 含成本的买入均价
    current_price: float = 0.0
    stop_loss_price: float = 0.0
    take_profit_price: float = 0.0

    @property
    def market_value(self) -> float:
        return self.current_price * self.quantity

    @property
    def cost_value(self) -> float:
        return self.cost_price * self.quantity

    @property
    def unrealized_pnl(self) -> float:
        return (self.current_price - self.cost_price) * self.quantity

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.cost_price == 0:
            return 0.0
        return (self.current_price - self.cost_price) / self.cost_price


@dataclass
class TradeRecord:
    """交易记录"""
    trade_date: str
    symbol: str
    side: str  # BUY / SELL
    quantity: int
    price: float  # 原始价格
    fill_price: float  # 含滑点的成交价
    amount: float
    commission: float
    stamp_duty: float
    slippage: float
    total_cost: float
    signal_type: str = ""
    signal_sub_type: str = ""
    reason: str = ""


class Portfolio:
    """回测持仓管理器"""

    def __init__(
        self,
        initial_capital: float = 1000000.0,
        commission_model: Optional[CommissionModel] = None,
    ):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.commission_model = commission_model or CommissionModel()
        self.positions: Dict[str, Position] = {}
        self.trade_records: List[TradeRecord] = []
        self.daily_values: List[dict] = []

    @property
    def total_market_value(self) -> float:
        return sum(p.market_value for p in self.positions.values())

    @property
    def total_value(self) -> float:
        return self.cash + self.total_market_value

    @property
    def cash_ratio(self) -> float:
        total = self.total_value
        return self.cash / total if total > 0 else 0.0

    def get_position(self, symbol: str) -> Optional[Position]:
        return self.positions.get(symbol)

    def has_position(self, symbol: str) -> bool:
        return symbol in self.positions and self.positions[symbol].quantity > 0

    def update_price(self, symbol: str, price: float):
        """更新持仓股票的当前价格"""
        if symbol in self.positions:
            self.positions[symbol].current_price = price

    def update_all_prices(self, price_dict: Dict[str, float]):
        """批量更新当前价格"""
        for symbol, price in price_dict.items():
            self.update_price(symbol, price)

    def can_buy(
        self,
        symbol: str,
        price: float,
        quantity: int,
        is_limit_up: bool = False,
        is_suspended: bool = False,
    ) -> tuple[bool, str]:
        """检查是否可以买入"""
        if is_suspended:
            return False, "停牌无法买入"
        if is_limit_up:
            return False, "涨停无法买入"

        cost_info = self.commission_model.calc_buy_cost(price, quantity)
        total_needed = cost_info["amount"] + cost_info["total_cost"]

        if total_needed > self.cash:
            return False, f"资金不足: 需要{total_needed:.0f}, 可用{self.cash:.0f}"

        return True, ""

    def can_sell(
        self,
        symbol: str,
        quantity: int,
        is_limit_down: bool = False,
        is_suspended: bool = False,
    ) -> tuple[bool, str]:
        """检查是否可以卖出"""
        if is_suspended:
            return False, "停牌无法卖出"
        if is_limit_down:
            return False, "跌停无法卖出"

        pos = self.get_position(symbol)
        if pos is None or pos.quantity < quantity:
            return False, f"持仓不足: 持有{pos.quantity if pos else 0}, 欲卖{quantity}"

        return True, ""

    def buy(
        self,
        symbol: str,
        price: float,
        quantity: int,
        trade_date: str,
        signal_type: str = "",
        signal_sub_type: str = "",
        reason: str = "",
        is_limit_up: bool = False,
        is_suspended: bool = False,
    ) -> Optional[TradeRecord]:
        """执行买入"""
        can, msg = self.can_buy(symbol, price, quantity, is_limit_up, is_suspended)
        if not can:
            logger.debug(f"买入被拒: {symbol} {msg}")
            return None

        cost_info = self.commission_model.calc_buy_cost(price, quantity)
        fill_price = cost_info["fill_price"]
        total_deduct = cost_info["amount"] + cost_info["total_cost"]

        self.cash -= total_deduct

        if symbol in self.positions:
            pos = self.positions[symbol]
            # 加仓：更新成本价
            total_cost = pos.cost_value + fill_price * quantity
            pos.quantity += quantity
            pos.cost_price = total_cost / pos.quantity
            pos.current_price = price
        else:
            self.positions[symbol] = Position(
                symbol=symbol,
                quantity=quantity,
                cost_price=fill_price,
                current_price=price,
            )

        record = TradeRecord(
            trade_date=trade_date,
            symbol=symbol,
            side="BUY",
            quantity=quantity,
            price=price,
            fill_price=fill_price,
            amount=cost_info["amount"],
            commission=cost_info["commission"],
            stamp_duty=cost_info["stamp_duty"],
            slippage=cost_info["slippage"],
            total_cost=cost_info["total_cost"],
            signal_type=signal_type,
            signal_sub_type=signal_sub_type,
            reason=reason,
        )
        self.trade_records.append(record)
        logger.debug(f"买入: {symbol} {quantity}股 @ {fill_price:.2f}, 成本{cost_info['total_cost']:.2f}")
        return record

    def sell(
        self,
        symbol: str,
        price: float,
        quantity: int,
        trade_date: str,
        signal_type: str = "",
        signal_sub_type: str = "",
        reason: str = "",
        is_limit_down: bool = False,
        is_suspended: bool = False,
    ) -> Optional[TradeRecord]:
        """执行卖出"""
        can, msg = self.can_sell(symbol, quantity, is_limit_down, is_suspended)
        if not can:
            logger.debug(f"卖出被拒: {symbol} {msg}")
            return None

        cost_info = self.commission_model.calc_sell_cost(price, quantity)
        fill_price = cost_info["fill_price"]
        total_receive = cost_info["amount"] - cost_info["total_cost"]

        self.cash += total_receive

        pos = self.positions[symbol]
        pos.quantity -= quantity
        pos.current_price = price

        if pos.quantity <= 0:
            del self.positions[symbol]

        record = TradeRecord(
            trade_date=trade_date,
            symbol=symbol,
            side="SELL",
            quantity=quantity,
            price=price,
            fill_price=fill_price,
            amount=cost_info["amount"],
            commission=cost_info["commission"],
            stamp_duty=cost_info["stamp_duty"],
            slippage=cost_info["slippage"],
            total_cost=cost_info["total_cost"],
            signal_type=signal_type,
            signal_sub_type=signal_sub_type,
            reason=reason,
        )
        self.trade_records.append(record)
        logger.debug(f"卖出: {symbol} {quantity}股 @ {fill_price:.2f}, 成本{cost_info['total_cost']:.2f}")
        return record

    def record_daily_value(self, trade_date: str):
        """记录每日资产值"""
        self.daily_values.append({
            "trade_date": trade_date,
            "cash": round(self.cash, 2),
            "market_value": round(self.total_market_value, 2),
            "total_value": round(self.total_value, 2),
            "position_count": len([p for p in self.positions.values() if p.quantity > 0]),
            "cash_ratio": round(self.cash_ratio, 4),
        })

    def get_trade_records_df(self) -> pd.DataFrame:
        if not self.trade_records:
            return pd.DataFrame()
        return pd.DataFrame([vars(r) for r in self.trade_records])

    def get_daily_values_df(self) -> pd.DataFrame:
        if not self.daily_values:
            return pd.DataFrame()
        return pd.DataFrame(self.daily_values)

    def get_positions_df(self) -> pd.DataFrame:
        if not self.positions:
            return pd.DataFrame()
        rows = []
        for pos in self.positions.values():
            if pos.quantity > 0:
                rows.append({
                    "symbol": pos.symbol,
                    "quantity": pos.quantity,
                    "cost_price": pos.cost_price,
                    "current_price": pos.current_price,
                    "market_value": pos.market_value,
                    "unrealized_pnl": pos.unrealized_pnl,
                    "unrealized_pnl_pct": pos.unrealized_pnl_pct,
                })
        return pd.DataFrame(rows)
