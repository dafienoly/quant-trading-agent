"""交易成本模型

实现 ROADMAP Phase 3 回测基本假设中的交易成本：
- 佣金：买入+卖出双向，默认万3
- 印花税：卖出侧，A股默认千1，港股千1.3
- 滑点：独立 SlippageModel，支持固定比例/固定金额/VWAP偏离
- 最低佣金：5元
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from loguru import logger


# ============================================================
# 滑点模型 (S2 审计修复：抽取独立 SlippageModel)
# ============================================================

class SlippageModel(ABC):
    """滑点模型抽象基类"""

    @abstractmethod
    def calc_buy_fill_price(self, price: float, **kwargs) -> float:
        """计算买入成交价（含滑点）"""

    @abstractmethod
    def calc_sell_fill_price(self, price: float, **kwargs) -> float:
        """计算卖出成交价（含滑点）"""

    @abstractmethod
    def calc_slippage_amount(self, price: float, quantity: int, side: str) -> float:
        """计算滑点金额"""


class FixedRateSlippage(SlippageModel):
    """固定比例滑点模型（默认）"""

    def __init__(self, slippage_rate: float = 0.001):
        self.slippage_rate = slippage_rate

    def calc_buy_fill_price(self, price: float, **kwargs) -> float:
        return round(price * (1 + self.slippage_rate), 4)

    def calc_sell_fill_price(self, price: float, **kwargs) -> float:
        return round(price * (1 - self.slippage_rate), 4)

    def calc_slippage_amount(self, price: float, quantity: int, side: str) -> float:
        return round(price * self.slippage_rate * quantity, 2)


class FixedAmountSlippage(SlippageModel):
    """固定金额滑点模型"""

    def __init__(self, slippage_amount: float = 0.01):
        self.slippage_amount = slippage_amount

    def calc_buy_fill_price(self, price: float, **kwargs) -> float:
        return round(price + self.slippage_amount, 4)

    def calc_sell_fill_price(self, price: float, **kwargs) -> float:
        return round(price - self.slippage_amount, 4)

    def calc_slippage_amount(self, price: float, quantity: int, side: str) -> float:
        return round(self.slippage_amount * quantity, 2)


class NoSlippage(SlippageModel):
    """无滑点模型（用于理想化回测）"""

    def calc_buy_fill_price(self, price: float, **kwargs) -> float:
        return price

    def calc_sell_fill_price(self, price: float, **kwargs) -> float:
        return price

    def calc_slippage_amount(self, price: float, quantity: int, side: str) -> float:
        return 0.0


# ============================================================
# 成交价模式 (L1 审计修复：支持多种成交价模式)
# ============================================================

class FillPriceModel:
    """成交价模型：决定使用开盘价/收盘价/VWAP成交"""

    @staticmethod
    def get_fill_price(
        mode: str,
        open_price: float,
        close_price: float,
        high_price: float = 0.0,
        low_price: float = 0.0,
        volume: float = 0.0,
        amount: float = 0.0,
    ) -> float:
        """
        根据模式获取成交价。

        mode:
        - "next_open": 使用开盘价（默认，模拟次日成交）
        - "close": 使用收盘价
        - "vwap": 使用成交量加权平均价
        """
        if mode == "next_open" or mode == "open":
            return open_price
        elif mode == "close":
            return close_price
        elif mode == "vwap":
            if volume > 0 and amount > 0:
                return round(amount / volume, 4)
            elif high_price > 0 and low_price > 0:
                return round((high_price + low_price + close_price) / 3, 4)
            else:
                return close_price
        else:
            return close_price


# ============================================================
# 交易成本模型
# ============================================================

@dataclass
class CommissionModel:
    """交易成本模型"""

    commission_rate: float = 0.0003  # 佣金费率，万3
    stamp_duty_rate: float = 0.001  # 印花税费率，千1（A股卖出）
    stamp_duty_rate_hk: float = 0.0013  # 港股印花税费率，千1.3
    slippage_model: Optional[SlippageModel] = None  # 滑点模型
    min_commission: float = 5.0  # 最低佣金，5元

    def __post_init__(self):
        if self.slippage_model is None:
            self.slippage_model = FixedRateSlippage()

    def calc_buy_cost(self, price: float, quantity: int, market: str = "SZ") -> dict:
        """计算买入成本"""
        amount = price * quantity
        commission = max(amount * self.commission_rate, self.min_commission)
        fill_price = self.slippage_model.calc_buy_fill_price(price)
        slippage = self.slippage_model.calc_slippage_amount(price, quantity, "BUY")
        stamp_duty = 0.0  # 买入无印花税

        total_cost = commission + slippage + stamp_duty

        return {
            "fill_price": fill_price,
            "amount": round(amount, 2),
            "commission": round(commission, 2),
            "stamp_duty": round(stamp_duty, 2),
            "slippage": round(slippage, 2),
            "total_cost": round(total_cost, 2),
        }

    def calc_sell_cost(self, price: float, quantity: int, market: str = "SZ") -> dict:
        """计算卖出成本"""
        amount = price * quantity
        commission = max(amount * self.commission_rate, self.min_commission)
        fill_price = self.slippage_model.calc_sell_fill_price(price)
        slippage = self.slippage_model.calc_slippage_amount(price, quantity, "SELL")

        # 印花税区分A股/港股 (L4 审计修复)
        if market == "HK":
            stamp_duty = amount * self.stamp_duty_rate_hk
        else:
            stamp_duty = amount * self.stamp_duty_rate

        total_cost = commission + slippage + stamp_duty

        return {
            "fill_price": fill_price,
            "amount": round(amount, 2),
            "commission": round(commission, 2),
            "stamp_duty": round(stamp_duty, 2),
            "slippage": round(slippage, 2),
            "total_cost": round(total_cost, 2),
        }

    def calc_total_round_trip(self, buy_price: float, sell_price: float, quantity: int, market: str = "SZ") -> dict:
        """计算完整往返交易成本"""
        buy = self.calc_buy_cost(buy_price, quantity, market)
        sell = self.calc_sell_cost(sell_price, quantity, market)

        return {
            "buy_cost": buy["total_cost"],
            "sell_cost": sell["total_cost"],
            "total_cost": round(buy["total_cost"] + sell["total_cost"], 2),
            "buy_fill_price": buy["fill_price"],
            "sell_fill_price": sell["fill_price"],
        }
