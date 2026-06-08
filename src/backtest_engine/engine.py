"""回测引擎核心

实现 ROADMAP Phase 3 的日频回测框架：
- 逐日遍历历史数据
- 每日计算因子和信号
- 信号通过风控检查后执行交易
- 涨跌停/停牌无法成交
- 次日开盘价成交
- 记录每日资产和交易

回测流程：
1. 加载历史数据
2. 逐日遍历：
   a. 更新持仓价格
   b. 计算因子和信号
   c. 风控检查
   d. 执行交易
   e. 记录每日资产
3. 生成绩效报告
"""
from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd
from loguru import logger

from src.backtest_engine.commission_model import CommissionModel, FillPriceModel
from src.backtest_engine.portfolio import Portfolio
from src.backtest_engine.performance import PerformanceAnalyzer
from src.backtest_engine.risk_check import BacktestRiskCheck
from src.strategy_engine.scoring_model import compute_all_factors
from src.strategy_engine.signal_generator import generate_signals
from src.stock_pool.semiconductor import SemiconductorPool


class BacktestEngine:
    """日频回测引擎"""

    def __init__(
        self,
        initial_capital: float = 1000000.0,
        commission_model: Optional[CommissionModel] = None,
        risk_check: Optional[BacktestRiskCheck] = None,
        pool: Optional[SemiconductorPool] = None,
        buy_price_mode: str = "next_open",  # next_open / close
        sell_price_mode: str = "next_open",  # next_open / close
    ):
        self.initial_capital = initial_capital
        self.commission_model = commission_model or CommissionModel()
        self.risk_check = risk_check or BacktestRiskCheck()
        self.pool = pool or SemiconductorPool()
        self.buy_price_mode = buy_price_mode
        self.sell_price_mode = sell_price_mode

    def run(
        self,
        data: pd.DataFrame,
        benchmark_data: Optional[pd.DataFrame] = None,
    ) -> dict:
        """
        执行回测。

        参数：
            data: 日线数据，必须包含 symbol, trade_date, open, high, low, close, volume, amount, pct_change
                  以及 is_suspended, is_st, limit_up, limit_down, turnover_rate
            benchmark_data: 基准指数日线数据（可选）

        返回：
            回测结果字典，包含绩效指标、交易记录、每日资产等
        """
        if data.empty:
            logger.error("回测数据为空")
            return {}

        portfolio = Portfolio(
            initial_capital=self.initial_capital,
            commission_model=self.commission_model,
        )
        self.risk_check.reset()

        # 按日期排序
        dates = sorted(data["trade_date"].unique())
        logger.info(f"回测开始: {dates[0]} ~ {dates[-1]}, {len(dates)}个交易日, {len(data)}行数据")
        pending_signals: List = []

        # 预计算基准收益
        benchmark_returns = None
        if benchmark_data is not None and not benchmark_data.empty:
            benchmark_returns = benchmark_data.set_index("trade_date")["pct_change"] / 100

        for i, trade_date in enumerate(dates):
            day_data = data[data["trade_date"] == trade_date].copy()

            # 1. 更新持仓价格
            price_dict = dict(zip(day_data["symbol"], day_data["close"]))
            portfolio.update_all_prices(price_dict)

            # 2. 每日风控检查
            risk_msg = self.risk_check.update_daily_check(portfolio)
            if risk_msg:
                logger.warning(f"[{trade_date}] 风控: {risk_msg}")
                portfolio.record_daily_value(trade_date)
                continue

            # 3. 执行上一交易日产生、需在本交易日成交的信号
            if pending_signals:
                self._execute_signals(pending_signals, day_data, trade_date, portfolio)
                pending_signals = []

            # 4. 计算因子和信号（使用截至当日的数据）
            # 使用最近60个交易日的数据计算因子
            lookback_dates = dates[max(0, i - 60):i + 1]
            lookback_data = data[data["trade_date"].isin(lookback_dates)]

            try:
                scored_data = compute_all_factors(lookback_data, pool=self.pool)
                # 只取当日数据生成信号
                today_scored = scored_data[scored_data["trade_date"] == trade_date]
            except Exception as e:
                logger.warning(f"[{trade_date}] 因子计算失败: {e}")
                portfolio.record_daily_value(trade_date)
                continue

            if today_scored.empty:
                portfolio.record_daily_value(trade_date)
                continue

            # 5. 生成信号
            # 计算持仓收益率
            current_returns = {}
            for symbol, pos in portfolio.positions.items():
                if pos.quantity > 0 and pos.cost_price > 0:
                    current_returns[symbol] = pos.unrealized_pnl_pct

            signals = generate_signals(today_scored, current_returns=current_returns, include_hold=False)

            # 6. 执行交易。默认 next_open/vwap 信号挂起到下一交易日执行。
            same_day_signals = []
            for sig in signals:
                mode = self.buy_price_mode if sig.signal_type == "BUY" else self.sell_price_mode
                if self._uses_next_trade_date(mode):
                    pending_signals.append(sig)
                else:
                    same_day_signals.append(sig)

            self._execute_signals(same_day_signals, day_data, trade_date, portfolio)

            # 7. 记录每日资产
            portfolio.record_daily_value(trade_date)

        # 生成绩效报告
        analyzer = PerformanceAnalyzer(portfolio, benchmark_returns=benchmark_returns)
        result = analyzer.analyze()
        result["trade_records"] = portfolio.get_trade_records_df()
        result["daily_values"] = portfolio.get_daily_values_df()
        result["report_text"] = analyzer.generate_report()

        logger.info(f"回测完成: 年化收益{result['annual_return']:.2%}, 最大回撤{result['max_drawdown']:.2%}")

        return result

    def _execute_signals(
        self,
        signals: list,
        day_data: pd.DataFrame,
        trade_date: str,
        portfolio: Portfolio,
    ):
        """执行信号对应的交易"""
        day_lookup = {row["symbol"]: row for _, row in day_data.iterrows()}

        for sig in signals:
            symbol = sig.symbol

            if sig.signal_type == "BUY":
                row = day_lookup.get(symbol)
                if row is None:
                    continue

                buy_price = self._get_fill_price(self.buy_price_mode, row)
                if buy_price <= 0:
                    continue

                is_suspended, is_limit_up, _ = self._get_trade_status(row)

                # 计算买入数量（按仓位比例）
                position_pct = sig.position_pct
                buy_amount = portfolio.total_value * position_pct
                quantity = int(buy_amount / buy_price / 100) * 100  # 整手
                if quantity <= 0:
                    continue

                # 风控检查
                sector = sig.sector
                sector_exposure = self._calc_sector_exposure(portfolio)
                can_buy, reason = self.risk_check.check_buy(
                    portfolio, symbol, buy_price, quantity,
                    sector=sector, sector_exposure=sector_exposure,
                )
                if not can_buy:
                    logger.debug(f"[{trade_date}] 买入被风控拒绝: {symbol} {reason}")
                    continue

                portfolio.buy(
                    symbol=symbol,
                    price=buy_price,
                    quantity=quantity,
                    trade_date=trade_date,
                    signal_type=sig.signal_type,
                    signal_sub_type=sig.sub_type,
                    reason=sig.reason,
                    is_limit_up=is_limit_up,
                    is_suspended=is_suspended,
                )

            elif sig.signal_type == "SELL":
                pos = portfolio.get_position(symbol)
                if pos is None or pos.quantity <= 0:
                    continue

                row = day_lookup.get(symbol)
                if row is None:
                    continue

                sell_price = self._get_fill_price(self.sell_price_mode, row)
                if sell_price <= 0:
                    continue

                is_suspended, _, is_limit_down = self._get_trade_status(row)

                # 根据信号确定卖出比例
                sell_ratio = sig.position_pct
                quantity = int(pos.quantity * sell_ratio / 100) * 100
                quantity = max(quantity, 100)  # 至少卖1手
                quantity = min(quantity, pos.quantity)

                if quantity <= 0:
                    continue

                portfolio.sell(
                    symbol=symbol,
                    price=sell_price,
                    quantity=quantity,
                    trade_date=trade_date,
                    signal_type=sig.signal_type,
                    signal_sub_type=sig.sub_type,
                    reason=sig.reason,
                    is_limit_down=is_limit_down,
                    is_suspended=is_suspended,
                )

    def _uses_next_trade_date(self, price_mode: str) -> bool:
        """需要下一交易日成交的价格模式。"""
        return price_mode in ("next_open", "vwap")

    def _get_fill_price(self, price_mode: str, row: pd.Series) -> float:
        """从选定交易日行情取成交参考价。"""
        close = row.get("close", 0)
        return FillPriceModel.get_fill_price(
            price_mode,
            open_price=row.get("open", close),
            close_price=close,
            high_price=row.get("high", 0.0),
            low_price=row.get("low", 0.0),
            volume=row.get("volume", 0.0),
            amount=row.get("amount", 0.0),
        )

    def _get_trade_status(self, row: pd.Series) -> tuple[bool, bool, bool]:
        """返回 (停牌, 涨停, 跌停)，用于成交可行性检查。"""
        is_suspended = row.get("is_suspended", False)
        is_st = row.get("is_st", False)
        pct = row.get("pct_change", 0)
        is_limit_up = pct >= 9.5 if not is_st else pct >= 4.5
        is_limit_down = pct <= -9.5 if not is_st else pct <= -4.5
        return is_suspended, is_limit_up, is_limit_down

    def _calc_sector_exposure(self, portfolio: Portfolio) -> Dict[str, float]:
        """计算当前板块暴露"""
        sector_exposure = {}
        for symbol, pos in portfolio.positions.items():
            if pos.quantity <= 0:
                continue
            sector = self.pool.get_sector(symbol.split(".")[0]) or ""
            if sector:
                sector_exposure[sector] = sector_exposure.get(sector, 0.0) + pos.market_value
        return sector_exposure
