"""回测风控检查

实现 RISK_POLICY.md 和 AGENTS.md 3.6 Risk Agent 要求的风控约束：
- 单票仓位限制 (默认15%)
- 板块仓位限制 (默认60%)
- 账户回撤限制 (防御线8%, 止损线12%)
- 当日亏损限制 (警告2%, 止损3%)
- 单票亏损限制 (警告5%, 止损8%)
- 最小现金比例 (20%)

Risk Agent 拥有一票否决权。
"""
from __future__ import annotations

from typing import Dict, Optional

from loguru import logger

from src.backtest_engine.portfolio import Portfolio
from src.config.settings import (
    MAX_SINGLE_STOCK_POSITION,
    MAX_SECTOR_POSITION,
    MIN_CASH_RATIO,
    SINGLE_STOCK_LOSS_WARN,
    SINGLE_STOCK_LOSS_STOP,
    DAILY_LOSS_WARN,
    DAILY_LOSS_STOP,
    MAX_DRAWDOWN_DEFENSE,
    MAX_DRAWDOWN_HALT,
)


class BacktestRiskCheck:
    """回测风控检查器"""

    def __init__(
        self,
        max_single_stock_position: float = MAX_SINGLE_STOCK_POSITION,
        max_sector_position: float = MAX_SECTOR_POSITION,
        min_cash_ratio: float = MIN_CASH_RATIO,
        single_stock_loss_warn: float = SINGLE_STOCK_LOSS_WARN,
        single_stock_loss_stop: float = SINGLE_STOCK_LOSS_STOP,
        daily_loss_warn: float = DAILY_LOSS_WARN,
        daily_loss_stop: float = DAILY_LOSS_STOP,
        max_drawdown_defense: float = MAX_DRAWDOWN_DEFENSE,
        max_drawdown_halt: float = MAX_DRAWDOWN_HALT,
    ):
        self.max_single_stock_position = max_single_stock_position
        self.max_sector_position = max_sector_position
        self.min_cash_ratio = min_cash_ratio
        self.single_stock_loss_warn = single_stock_loss_warn
        self.single_stock_loss_stop = single_stock_loss_stop
        self.daily_loss_warn = daily_loss_warn
        self.daily_loss_stop = daily_loss_stop
        self.max_drawdown_defense = max_drawdown_defense
        self.max_drawdown_halt = max_drawdown_halt

        self._prev_total_value: Optional[float] = None
        self._halted = False  # 全局停止交易标志

    def check_buy(
        self,
        portfolio: Portfolio,
        symbol: str,
        price: float,
        quantity: int,
        sector: str = "",
        sector_exposure: Optional[Dict[str, float]] = None,
    ) -> tuple[bool, str]:
        """买入风控检查，返回 (通过, 原因)"""
        if self._halted:
            return False, "风控全局停止交易"

        total_value = portfolio.total_value
        if total_value <= 0:
            return False, "总资产为零"

        # 1. 现金比例检查
        cash_ratio = portfolio.cash_ratio
        buy_amount = price * quantity
        new_cash = portfolio.cash - buy_amount
        new_cash_ratio = new_cash / (total_value) if total_value > 0 else 0
        if new_cash_ratio < self.min_cash_ratio:
            return False, f"买入后现金比例{new_cash_ratio:.1%}低于最低{self.min_cash_ratio:.1%}"

        # 2. 单票仓位检查
        position_value = price * quantity
        existing = portfolio.get_position(symbol)
        if existing:
            position_value += existing.market_value
        position_ratio = position_value / total_value
        if position_ratio > self.max_single_stock_position:
            return False, f"单票仓位{position_ratio:.1%}超过限制{self.max_single_stock_position:.1%}"

        # 3. 板块仓位检查
        if sector and sector_exposure is not None:
            sector_total = sector_exposure.get(sector, 0.0)
            new_sector_ratio = (sector_total + position_value) / total_value
            if new_sector_ratio > self.max_sector_position:
                return False, f"板块仓位{new_sector_ratio:.1%}超过限制{self.max_sector_position:.1%}"

        # 4. 回撤检查
        if self._prev_total_value and self._prev_total_value > 0:
            drawdown = (total_value - self._prev_total_value) / self._prev_total_value
            if drawdown <= self.max_drawdown_halt:
                self._halted = True
                return False, f"回撤{drawdown:.1%}超过止损线{self.max_drawdown_halt:.1%}，停止交易"

        return True, ""

    def check_sell(
        self,
        portfolio: Portfolio,
        symbol: str,
        current_return: float = 0.0,
    ) -> tuple[bool, str, str]:
        """卖出风控检查，返回 (通过, 原因, 建议卖出比例)"""
        # 单票亏损检查
        if current_return <= self.single_stock_loss_stop:
            return True, f"单票亏损{current_return:.1%}超过止损线", "1.0"  # 清仓

        if current_return <= self.single_stock_loss_warn:
            return True, f"单票亏损{current_return:.1%}触发警告", "0.5"  # 减半

        return True, "", "1.0"  # 默认全部卖出

    def update_daily_check(self, portfolio: Portfolio) -> Optional[str]:
        """每日风控检查，返回风控状态"""
        total_value = portfolio.total_value

        # 当日亏损检查
        if self._prev_total_value and self._prev_total_value > 0:
            daily_return = (total_value - self._prev_total_value) / self._prev_total_value

            if daily_return <= self.daily_loss_stop:
                self._halted = True
                return f"当日亏损{daily_return:.1%}超过止损线{self.daily_loss_stop:.1%}，停止交易"

            if daily_return <= self.daily_loss_warn:
                logger.warning(f"当日亏损{daily_return:.1%}触发警告线{self.daily_loss_warn:.1%}")

        # 回撤检查
        if portfolio.initial_capital > 0:
            total_drawdown = (total_value - portfolio.initial_capital) / portfolio.initial_capital
            if total_drawdown <= self.max_drawdown_halt:
                self._halted = True
                return f"总回撤{total_drawdown:.1%}超过止损线{self.max_drawdown_halt:.1%}，停止交易"

        self._prev_total_value = total_value
        return None

    @property
    def is_halted(self) -> bool:
        return self._halted

    def reset(self):
        self._halted = False
        self._prev_total_value = None
