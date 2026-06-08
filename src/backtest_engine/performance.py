"""绩效评估分析器

实现 ROADMAP Phase 3 和 AGENTS.md 3.5 Backtest Agent 要求的全部指标：
- annual_return: 年化收益
- max_drawdown: 最大回撤
- sharpe_ratio: 夏普比率
- calmar_ratio: Calmar比率
- win_rate: 胜率
- profit_loss_ratio: 盈亏比
- turnover: 换手率
- cost_adjusted_return: 扣费后收益
- benchmark_return: 基准收益
- excess_return: 超额收益
- monthly_return: 月度收益
- yearly_return: 年度收益
- total_trades: 交易次数
- total_commission: 总手续费
- total_stamp_duty: 总印花税
- total_slippage: 总滑点
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from loguru import logger

from src.backtest_engine.portfolio import Portfolio


# 默认无风险利率
DEFAULT_RISK_FREE_RATE = 0.02  # 2% 年化


class PerformanceAnalyzer:
    """绩效评估分析器"""

    def __init__(
        self,
        portfolio: Portfolio,
        risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
        benchmark_returns: Optional[pd.Series] = None,
    ):
        self.portfolio = portfolio
        self.risk_free_rate = risk_free_rate
        self.benchmark_returns = benchmark_returns

    def analyze(self) -> dict:
        """执行完整绩效分析，返回所有指标"""
        daily_df = self.portfolio.get_daily_values_df()
        if daily_df.empty:
            return self._empty_result()

        # 计算日收益率
        daily_df["daily_return"] = daily_df["total_value"].pct_change()
        daily_df = daily_df.dropna(subset=["daily_return"])

        if daily_df.empty:
            return self._empty_result()

        result = {}

        # 基础指标
        result["initial_capital"] = self.portfolio.initial_capital
        result["final_value"] = daily_df["total_value"].iloc[-1]
        result["total_return"] = (result["final_value"] / result["initial_capital"]) - 1
        result["total_trades"] = len(self.portfolio.trade_records)

        # 年化收益
        trading_days = len(daily_df)
        years = trading_days / 242  # A股约242个交易日
        if years > 0:
            result["annual_return"] = (1 + result["total_return"]) ** (1 / years) - 1
        else:
            result["annual_return"] = 0.0

        # 最大回撤
        result["max_drawdown"] = self._calc_max_drawdown(daily_df["total_value"])

        # 夏普比率
        result["sharpe_ratio"] = self._calc_sharpe(daily_df["daily_return"])

        # Calmar比率
        result["calmar_ratio"] = (
            result["annual_return"] / abs(result["max_drawdown"])
            if result["max_drawdown"] != 0
            else 0.0
        )

        # 胜率和盈亏比
        win_rate, pl_ratio = self._calc_win_loss_stats()
        result["win_rate"] = win_rate
        result["profit_loss_ratio"] = pl_ratio

        # 换手率
        result["turnover"] = self._calc_turnover(daily_df)

        # 交易成本
        costs = self._calc_total_costs()
        result["total_commission"] = costs["commission"]
        result["total_stamp_duty"] = costs["stamp_duty"]
        result["total_slippage"] = costs["slippage"]
        result["total_cost"] = costs["total"]

        # 扣费后收益 = 总收益 - 总成本/初始资金
        if result["initial_capital"] > 0:
            result["cost_adjusted_return"] = result["total_return"] - costs["total"] / result["initial_capital"]
        else:
            result["cost_adjusted_return"] = result["total_return"]

        # 基准收益
        result["benchmark_return"] = self._calc_benchmark_return(daily_df)
        result["excess_return"] = result["total_return"] - result["benchmark_return"]

        # 月度收益
        result["monthly_return"] = self._calc_monthly_return(daily_df)

        # 年度收益
        result["yearly_return"] = self._calc_yearly_return(daily_df)

        return result

    def _empty_result(self) -> dict:
        return {
            "initial_capital": self.portfolio.initial_capital,
            "final_value": self.portfolio.initial_capital,
            "total_return": 0.0,
            "annual_return": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "calmar_ratio": 0.0,
            "win_rate": 0.0,
            "profit_loss_ratio": 0.0,
            "turnover": 0.0,
            "total_trades": 0,
            "total_commission": 0.0,
            "total_stamp_duty": 0.0,
            "total_slippage": 0.0,
            "total_cost": 0.0,
            "cost_adjusted_return": 0.0,
            "benchmark_return": 0.0,
            "excess_return": 0.0,
            "monthly_return": {},
            "yearly_return": {},
        }

    def _calc_max_drawdown(self, values: pd.Series) -> float:
        """计算最大回撤"""
        cummax = values.cummax()
        drawdown = (values - cummax) / cummax
        return float(drawdown.min())

    def _calc_sharpe(self, daily_returns: pd.Series) -> float:
        """计算夏普比率"""
        if len(daily_returns) < 2 or daily_returns.std() == 0:
            return 0.0
        excess_daily = daily_returns - self.risk_free_rate / 242
        return float(excess_daily.mean() / daily_returns.std() * np.sqrt(242))

    def _calc_win_loss_stats(self) -> tuple[float, float]:
        """计算胜率和盈亏比"""
        trades = self.portfolio.trade_records
        if not trades:
            return 0.0, 0.0

        # 配对买卖交易
        buy_sell_pairs = []
        holdings: Dict[str, dict] = {}

        for t in trades:
            if t.side == "BUY":
                if t.symbol not in holdings:
                    holdings[t.symbol] = {"buy_price": t.fill_price, "buy_date": t.trade_date}
            elif t.side == "SELL" and t.symbol in holdings:
                buy_price = holdings[t.symbol]["buy_price"]
                pnl_pct = (t.fill_price - buy_price) / buy_price
                buy_sell_pairs.append(pnl_pct)
                del holdings[t.symbol]

        if not buy_sell_pairs:
            return 0.0, 0.0

        wins = [p for p in buy_sell_pairs if p > 0]
        losses = [p for p in buy_sell_pairs if p <= 0]
        win_rate = len(wins) / len(buy_sell_pairs)

        avg_win = np.mean(wins) if wins else 0.0
        avg_loss = abs(np.mean(losses)) if losses else 1.0
        pl_ratio = avg_win / avg_loss if avg_loss > 0 else 0.0

        return win_rate, pl_ratio

    def _calc_turnover(self, daily_df: pd.DataFrame) -> float:
        """计算换手率"""
        trades = self.portfolio.trade_records
        if not trades:
            return 0.0

        total_buy_amount = sum(t.amount for t in trades if t.side == "BUY")
        avg_capital = daily_df["total_value"].mean()
        if avg_capital == 0:
            return 0.0

        trading_days = len(daily_df)
        return float(total_buy_amount / avg_capital / trading_days * 242)

    def _calc_total_costs(self) -> dict:
        """计算总交易成本"""
        trades = self.portfolio.trade_records
        return {
            "commission": sum(t.commission for t in trades),
            "stamp_duty": sum(t.stamp_duty for t in trades),
            "slippage": sum(t.slippage for t in trades),
            "total": sum(t.total_cost for t in trades),
        }

    def _calc_benchmark_return(self, daily_df: pd.DataFrame) -> float:
        """计算基准收益（使用复合收益）"""
        if self.benchmark_returns is not None and not self.benchmark_returns.empty:
            # 使用复合收益: (1+r1)*(1+r2)*...*(1+rn) - 1
            return float((1 + self.benchmark_returns).prod() - 1)
        # 无基准时返回0
        return 0.0

    def _calc_monthly_return(self, daily_df: pd.DataFrame) -> dict:
        """计算月度收益"""
        if "trade_date" not in daily_df.columns:
            return {}
        df = daily_df.copy()
        df["month"] = df["trade_date"].str[:6]
        monthly = df.groupby("month")["daily_return"].apply(lambda x: (1 + x).prod() - 1)
        return monthly.to_dict()

    def _calc_yearly_return(self, daily_df: pd.DataFrame) -> dict:
        """计算年度收益"""
        if "trade_date" not in daily_df.columns:
            return {}
        df = daily_df.copy()
        df["year"] = df["trade_date"].str[:4]
        yearly = df.groupby("year")["daily_return"].apply(lambda x: (1 + x).prod() - 1)
        return yearly.to_dict()

    def generate_report(self) -> str:
        """生成文本格式回测报告"""
        result = self.analyze()
        lines = [
            "=" * 60,
            "回测报告",
            "=" * 60,
            f"初始资金: {result['initial_capital']:,.0f}",
            f"最终资产: {result['final_value']:,.2f}",
            f"总收益率: {result['total_return']:.2%}",
            f"年化收益: {result['annual_return']:.2%}",
            "-" * 60,
            f"最大回撤: {result['max_drawdown']:.2%}",
            f"夏普比率: {result['sharpe_ratio']:.2f}",
            f"Calmar比率: {result['calmar_ratio']:.2f}",
            "-" * 60,
            f"胜率: {result['win_rate']:.2%}",
            f"盈亏比: {result['profit_loss_ratio']:.2f}",
            f"换手率: {result['turnover']:.2%}",
            "-" * 60,
            f"交易次数: {result['total_trades']}",
            f"总佣金: {result['total_commission']:,.2f}",
            f"总印花税: {result['total_stamp_duty']:,.2f}",
            f"总滑点: {result['total_slippage']:,.2f}",
            f"总交易成本: {result['total_cost']:,.2f}",
            "-" * 60,
            f"基准收益: {result['benchmark_return']:.2%}",
            f"超额收益: {result['excess_return']:.2%}",
            "=" * 60,
        ]

        # 月度收益
        if result["monthly_return"]:
            lines.append("月度收益:")
            for month, ret in sorted(result["monthly_return"].items()):
                lines.append(f"  {month}: {ret:.2%}")

        # 年度收益
        if result["yearly_return"]:
            lines.append("年度收益:")
            for year, ret in sorted(result["yearly_return"].items()):
                lines.append(f"  {year}: {ret:.2%}")

        return "\n".join(lines)
