"""事件驱动回测器

实现 S1 审计修复：将回测引擎重构为事件驱动架构，
支持 on_bar / on_signal / on_fill 事件回调，
使回测逻辑可扩展、可测试、可复现。

事件流：
  MarketEvent → SignalEvent → OrderEvent → FillEvent

与 BacktestEngine 的区别：
- BacktestEngine: 简单逐日遍历，信号→交易一步到位
- EventBacktester: 事件驱动，信号→订单→成交三步分离，
  支持自定义事件处理器和中间件
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List, Optional

import pandas as pd
from loguru import logger

from src.backtest_engine.commission_model import CommissionModel, FillPriceModel
from src.backtest_engine.portfolio import Portfolio
from src.backtest_engine.risk_check import BacktestRiskCheck
from src.strategy_engine.scoring_model import compute_all_factors
from src.strategy_engine.signal_generator import generate_signals
from src.stock_pool.semiconductor import SemiconductorPool


class EventType(Enum):
    MARKET = "MARKET"
    SIGNAL = "SIGNAL"
    ORDER = "ORDER"
    FILL = "FILL"


@dataclass
class MarketEvent:
    """市场数据事件"""
    trade_date: str
    bar_data: pd.DataFrame  # 当日全部股票行情


@dataclass
class SignalEvent:
    """信号事件"""
    trade_date: str
    signals: list  # Signal 对象列表


@dataclass
class OrderEvent:
    """订单事件"""
    trade_date: str
    symbol: str
    side: str  # BUY / SELL
    quantity: int
    price: float  # 目标价格
    signal_type: str = ""
    signal_sub_type: str = ""
    reason: str = ""


@dataclass
class FillEvent:
    """成交事件"""
    trade_date: str
    symbol: str
    side: str
    quantity: int
    fill_price: float
    commission: float
    stamp_duty: float
    slippage: float
    total_cost: float
    signal_type: str = ""
    signal_sub_type: str = ""
    reason: str = ""


class EventBacktester:
    """事件驱动回测器"""

    def __init__(
        self,
        initial_capital: float = 1000000.0,
        commission_model: Optional[CommissionModel] = None,
        risk_check: Optional[BacktestRiskCheck] = None,
        pool: Optional[SemiconductorPool] = None,
        fill_price_mode: str = "next_open",
        on_signal_handler: Optional[Callable] = None,
        on_fill_handler: Optional[Callable] = None,
    ):
        self.initial_capital = initial_capital
        self.commission_model = commission_model or CommissionModel()
        self.risk_check = risk_check or BacktestRiskCheck()
        self.pool = pool or SemiconductorPool()
        self.fill_price_mode = fill_price_mode
        self.on_signal_handler = on_signal_handler
        self.on_fill_handler = on_fill_handler

        self.portfolio = Portfolio(
            initial_capital=initial_capital,
            commission_model=self.commission_model,
        )
        self.events: List = []  # 事件日志

    def run(self, data: pd.DataFrame, benchmark_data: Optional[pd.DataFrame] = None) -> dict:
        """执行事件驱动回测"""
        if data.empty:
            return {}

        self.risk_check.reset()
        dates = sorted(data["trade_date"].unique())
        logger.info(f"事件驱动回测: {dates[0]}~{dates[-1]}, {len(dates)}交易日")
        pending_signals: List = []

        for i, trade_date in enumerate(dates):
            # Step 1: 生成 MarketEvent
            day_data = data[data["trade_date"] == trade_date].copy()
            market_event = MarketEvent(trade_date=trade_date, bar_data=day_data)
            self.events.append(market_event)

            # Step 2: 更新持仓价格
            price_dict = dict(zip(day_data["symbol"], day_data["close"]))
            self.portfolio.update_all_prices(price_dict)

            # Step 3: 风控每日检查
            risk_msg = self.risk_check.update_daily_check(self.portfolio)
            if risk_msg:
                logger.warning(f"[{trade_date}] 风控: {risk_msg}")
                self.portfolio.record_daily_value(trade_date)
                continue

            # Step 4: 执行上一交易日产生、需在本交易日成交的信号
            if pending_signals:
                self._execute_signal_events(pending_signals, day_data, trade_date)
                pending_signals = []

            # Step 5: 计算因子和信号 → SignalEvent
            lookback_dates = dates[max(0, i - 60):i + 1]
            lookback_data = data[data["trade_date"].isin(lookback_dates)]

            try:
                scored_data = compute_all_factors(lookback_data, pool=self.pool)
                today_scored = scored_data[scored_data["trade_date"] == trade_date]
            except Exception as e:
                logger.warning(f"[{trade_date}] 因子计算失败: {e}")
                self.portfolio.record_daily_value(trade_date)
                continue

            if today_scored.empty:
                self.portfolio.record_daily_value(trade_date)
                continue

            current_returns = {}
            for symbol, pos in self.portfolio.positions.items():
                if pos.quantity > 0 and pos.cost_price > 0:
                    current_returns[symbol] = pos.unrealized_pnl_pct

            signals = generate_signals(today_scored, current_returns=current_returns, include_hold=False)
            signal_event = SignalEvent(trade_date=trade_date, signals=signals)
            self.events.append(signal_event)

            # 信号回调
            if self.on_signal_handler:
                self.on_signal_handler(signal_event)

            # Step 6: 信号→订单→成交。默认 next_open/vwap 信号挂起到下一交易日执行。
            same_day_signals = []
            for sig in signals:
                if self._uses_next_trade_date(self.fill_price_mode):
                    pending_signals.append(sig)
                else:
                    same_day_signals.append(sig)

            self._execute_signal_events(same_day_signals, day_data, trade_date)

            self.portfolio.record_daily_value(trade_date)

        # 生成绩效
        from src.backtest_engine.performance import PerformanceAnalyzer
        benchmark_returns = None
        if benchmark_data is not None and not benchmark_data.empty:
            benchmark_returns = benchmark_data.set_index("trade_date")["pct_change"] / 100

        analyzer = PerformanceAnalyzer(self.portfolio, benchmark_returns=benchmark_returns)
        result = analyzer.analyze()
        result["trade_records"] = self.portfolio.get_trade_records_df()
        result["daily_values"] = self.portfolio.get_daily_values_df()
        result["report_text"] = analyzer.generate_report()
        result["events"] = self.events

        return result

    def _execute_signal_events(self, signals: list, day_data: pd.DataFrame, trade_date: str):
        """将信号转换为订单并在当前交易日成交。"""
        for sig in signals:
            order = self._signal_to_order(sig, day_data, trade_date)
            if order is None:
                continue

            fill = self._order_to_fill(order, day_data)
            if fill is not None:
                self.events.append(fill)
                if self.on_fill_handler:
                    self.on_fill_handler(fill)

    def _signal_to_order(self, sig, day_data: pd.DataFrame, trade_date: str) -> Optional[OrderEvent]:
        """信号转订单"""
        symbol = sig.symbol
        row = day_data[day_data["symbol"] == symbol]
        if row.empty:
            return None
        row = row.iloc[0]

        close = row.get("close", 0)
        open_price = row.get("open", close)
        is_suspended = row.get("is_suspended", False)
        pct = row.get("pct_change", 0)
        is_st = row.get("is_st", False)
        is_limit_up = pct >= (4.5 if is_st else 9.5)
        is_limit_down = pct <= (-4.5 if is_st else -9.5)

        if sig.signal_type == "BUY":
            if is_suspended or is_limit_up:
                return None

            fill_price = FillPriceModel.get_fill_price(
                self.fill_price_mode, open_price, close,
                row.get("high", 0), row.get("low", 0),
                row.get("volume", 0), row.get("amount", 0),
            )
            if fill_price <= 0:
                return None

            buy_amount = self.portfolio.total_value * sig.position_pct
            quantity = int(buy_amount / fill_price / 100) * 100
            if quantity <= 0:
                return None

            # 风控检查
            sector = sig.sector
            sector_exposure = self._calc_sector_exposure()
            can_buy, reason = self.risk_check.check_buy(
                self.portfolio, symbol, fill_price, quantity,
                sector=sector, sector_exposure=sector_exposure,
            )
            if not can_buy:
                return None

            return OrderEvent(
                trade_date=trade_date,
                symbol=symbol,
                side="BUY",
                quantity=quantity,
                price=fill_price,
                signal_type=sig.signal_type,
                signal_sub_type=sig.sub_type,
                reason=sig.reason,
            )

        elif sig.signal_type == "SELL":
            pos = self.portfolio.get_position(symbol)
            if pos is None or pos.quantity <= 0:
                return None

            if is_suspended or is_limit_down:
                return None

            fill_price = FillPriceModel.get_fill_price(
                self.fill_price_mode, open_price, close,
                row.get("high", 0), row.get("low", 0),
                row.get("volume", 0), row.get("amount", 0),
            )
            if fill_price <= 0:
                return None

            sell_ratio = sig.position_pct
            quantity = int(pos.quantity * sell_ratio / 100) * 100
            quantity = max(quantity, 100)
            quantity = min(quantity, pos.quantity)

            return OrderEvent(
                trade_date=trade_date,
                symbol=symbol,
                side="SELL",
                quantity=quantity,
                price=fill_price,
                signal_type=sig.signal_type,
                signal_sub_type=sig.sub_type,
                reason=sig.reason,
            )

        return None

    def _uses_next_trade_date(self, price_mode: str) -> bool:
        """需要下一交易日成交的价格模式。"""
        return price_mode in ("next_open", "vwap")

    def _order_to_fill(self, order: OrderEvent, day_data: pd.DataFrame) -> Optional[FillEvent]:
        """订单转成交"""
        symbol = order.symbol

        if order.side == "BUY":
            record = self.portfolio.buy(
                symbol=symbol,
                price=order.price,
                quantity=order.quantity,
                trade_date=order.trade_date,
                signal_type=order.signal_type,
                signal_sub_type=order.signal_sub_type,
                reason=order.reason,
            )
            if record is None:
                return None
            return FillEvent(
                trade_date=order.trade_date,
                symbol=symbol,
                side="BUY",
                quantity=record.quantity,
                fill_price=record.fill_price,
                commission=record.commission,
                stamp_duty=record.stamp_duty,
                slippage=record.slippage,
                total_cost=record.total_cost,
                signal_type=order.signal_type,
                signal_sub_type=order.signal_sub_type,
                reason=order.reason,
            )

        elif order.side == "SELL":
            record = self.portfolio.sell(
                symbol=symbol,
                price=order.price,
                quantity=order.quantity,
                trade_date=order.trade_date,
                signal_type=order.signal_type,
                signal_sub_type=order.signal_sub_type,
                reason=order.reason,
            )
            if record is None:
                return None
            return FillEvent(
                trade_date=order.trade_date,
                symbol=symbol,
                side="SELL",
                quantity=record.quantity,
                fill_price=record.fill_price,
                commission=record.commission,
                stamp_duty=record.stamp_duty,
                slippage=record.slippage,
                total_cost=record.total_cost,
                signal_type=order.signal_type,
                signal_sub_type=order.signal_sub_type,
                reason=order.reason,
            )

        return None

    def _calc_sector_exposure(self) -> Dict[str, float]:
        sector_exposure = {}
        for symbol, pos in self.portfolio.positions.items():
            if pos.quantity <= 0:
                continue
            sector = self.pool.get_sector(symbol.split(".")[0]) or ""
            if sector:
                sector_exposure[sector] = sector_exposure.get(sector, 0.0) + pos.market_value
        return sector_exposure
