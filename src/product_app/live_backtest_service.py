"""LiveBacktestService — 基于实时数据的快速回测服务。

核心职责：
- 在信号生成前，对实时日线数据运行快速回测以验证信号质量
- 尊重 DataHealthGate 门控：数据 FAILED 时不执行回测
- 优先使用 BacktestEngine，不可用时降级为简化 SMA 交叉策略
- is_demo 始终为 False

规则：
- 快速回测最多 120 个交易日
- 少于 20 个交易日数据时返回 insufficient_data 错误
- data_status=FAILED 时返回空结果
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from loguru import logger

# 尝试导入 BacktestEngine，不可用时使用简化逻辑
_BACKTEST_ENGINE_AVAILABLE = False
try:
    from src.backtest_engine.engine import BacktestEngine
    _BACKTEST_ENGINE_AVAILABLE = True
except Exception:
    logger.info("BacktestEngine 不可用，将使用简化 SMA 交叉回测逻辑")


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

MAX_QUICK_BACKTEST_DAYS = 120
MIN_TRADING_DAYS = 20
RISK_FREE_RATE = 0.03
SMA_SHORT_WINDOW = 5
SMA_LONG_WINDOW = 20


class LiveBacktestService:
    """基于实时数据的快速回测服务。

    在信号生成前对实时日线数据运行快速回测（最近 60-120 交易日），
    验证策略在当前市场环境下的表现，辅助信号质量判断。
    """

    def run_quick_backtest(
        self,
        symbols: list[str],
        start_date: str,
        end_date: str,
        strategy_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """运行快速回测。

        Args:
            symbols: 股票代码列表，如 ["600000.SH", "000001.SZ"]
            start_date: 开始日期 (YYYY-MM-DD 或 YYYYMMDD)
            end_date: 结束日期 (YYYY-MM-DD 或 YYYYMMDD)
            strategy_params: 可选策略参数，如 {"sma_short": 5, "sma_long": 20}

        Returns:
            回测结果字典，包含:
            - status: "ok" | "failed" | "insufficient_data"
            - results: 回测指标（total_return, annualized_return 等）
            - strategy: 使用的策略名称
            - data_status: 数据健康状态
            - is_demo: 始终为 False
        """
        # 获取日线数据
        from src.product_app.live_data_service import LiveDataService

        live_service = LiveDataService()
        bars_result = live_service.get_daily_bars(symbols, start_date, end_date)

        data_status = bars_result.get("data_status", "FAILED")

        # 数据健康门控：FAILED 时不执行回测
        if data_status == "FAILED":
            logger.warning("LiveBacktestService: data_status=FAILED，跳过回测")
            return {
                "status": "failed",
                "results": {},
                "strategy": "",
                "data_status": data_status,
                "is_demo": False,
            }

        daily_bars = bars_result.get("daily_bars", [])
        if not daily_bars or len(daily_bars) < MIN_TRADING_DAYS:
            logger.warning(
                "LiveBacktestService: 数据不足，{} < {} 交易日",
                len(daily_bars), MIN_TRADING_DAYS,
            )
            return {
                "status": "insufficient_data",
                "results": {},
                "strategy": "",
                "data_status": data_status,
                "is_demo": False,
                "detail": f"仅有 {len(daily_bars)} 条数据，至少需要 {MIN_TRADING_DAYS} 交易日",
            }

        # 限制最多 MAX_QUICK_BACKTEST_DAYS 个交易日
        daily_bars = daily_bars[-MAX_QUICK_BACKTEST_DAYS:]

        # 尝试使用 BacktestEngine
        if _BACKTEST_ENGINE_AVAILABLE:
            try:
                result = self._run_with_backtest_engine(
                    daily_bars, strategy_params
                )
                result["data_status"] = data_status
                result["is_demo"] = False
                return result
            except Exception as exc:
                logger.warning(
                    "BacktestEngine 执行失败，降级为简化逻辑: {}", exc
                )

        # 简化 SMA 交叉回测
        result = self._run_simplified_backtest(
            daily_bars, strategy_params
        )
        result["data_status"] = data_status
        result["is_demo"] = False
        return result

    def get_backtest_summary(
        self,
        symbols: list[str],
        start_date: str,
        end_date: str,
    ) -> dict[str, Any]:
        """获取回测结果摘要，包含数据健康信息。

        先通过 LiveDataService 获取日线数据，再运行快速回测，
        最后合并数据健康信息返回。

        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            合并结果字典，包含回测指标和数据健康信息
        """
        from src.product_app.live_data_service import LiveDataService
        from src.product_app.data_health_gate import DataHealthGate

        # 获取日线数据及健康信息
        live_service = LiveDataService()
        bars_result = live_service.get_daily_bars(symbols, start_date, end_date)

        # 评估数据健康
        health_gate = DataHealthGate()
        health_decision = health_gate.evaluate(
            quotes_result={"data_status": "OK"},
            daily_bars_result={"data_status": bars_result.get("data_status", "FAILED")},
            is_demo=False,
            trading_mode="LEVEL_1_SIGNAL_ONLY",
        )

        # 运行快速回测
        backtest_result = self.run_quick_backtest(symbols, start_date, end_date)

        # 合并结果
        return {
            "status": backtest_result["status"],
            "data_status": backtest_result["data_status"],
            "is_demo": False,
            "results": backtest_result.get("results", {}),
            "strategy": backtest_result.get("strategy", ""),
            "health": {
                "data_status": health_decision.data_status,
                "allow_research": health_decision.allow_research,
                "allow_signal": health_decision.allow_signal,
                "allow_order_draft": health_decision.allow_order_draft,
                "risk_level": health_decision.risk_level,
                "messages": health_decision.messages,
            },
            "chosen_provider": bars_result.get("chosen_provider", ""),
            "fallback_chain": bars_result.get("fallback_chain", []),
            "data_quality_report": bars_result.get("data_quality_report", {}),
            "data_missing_report": bars_result.get("data_missing_report", {}),
        }

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _run_with_backtest_engine(
        self,
        daily_bars: list[dict[str, Any]],
        strategy_params: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """使用 BacktestEngine 执行回测。"""
        df = pd.DataFrame(daily_bars)

        # 确保必要列存在
        required_cols = {"trade_date", "close"}
        if not required_cols.issubset(set(df.columns)):
            raise ValueError(
                f"缺少必要列: {required_cols - set(df.columns)}"
            )

        engine = BacktestEngine()
        bt_result = engine.run(df)

        if not bt_result:
            return {
                "status": "failed",
                "results": {},
                "strategy": "backtest_engine",
            }

        return {
            "status": "ok",
            "results": {
                "total_return": bt_result.get("total_return", 0.0),
                "annualized_return": bt_result.get("annual_return", 0.0),
                "max_drawdown": bt_result.get("max_drawdown", 0.0),
                "sharpe_ratio": bt_result.get("sharpe_ratio", 0.0),
                "win_rate": bt_result.get("win_rate", 0.0),
                "trade_count": bt_result.get("trade_count", 0),
            },
            "strategy": "backtest_engine",
        }

    def _run_simplified_backtest(
        self,
        daily_bars: list[dict[str, Any]],
        strategy_params: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """使用简化 SMA 交叉策略执行回测。

        策略逻辑：
        - SMA5 上穿 SMA20 → 买入
        - SMA5 下穿 SMA20 → 卖出
        - 基于 adjusted_close 计算收益
        """
        params = strategy_params or {}
        sma_short = params.get("sma_short", SMA_SHORT_WINDOW)
        sma_long = params.get("sma_long", SMA_LONG_WINDOW)

        df = pd.DataFrame(daily_bars)

        # 确定价格列：优先使用 adjusted_close，其次 close
        price_col = "adjusted_close" if "adjusted_close" in df.columns else "close"
        if price_col not in df.columns:
            return {
                "status": "failed",
                "results": {},
                "strategy": f"sma_crossover_{sma_short}_{sma_long}",
            }

        # 按日期排序
        if "trade_date" in df.columns:
            df = df.sort_values("trade_date").reset_index(drop=True)

        prices = df[price_col].astype(float)

        # 计算 SMA
        sma_s = prices.rolling(window=sma_short, min_periods=sma_short).mean()
        sma_l = prices.rolling(window=sma_long, min_periods=sma_long).mean()

        # 生成交易信号：SMA 短线上穿长线 → 买入(1)，下穿 → 卖出(-1)
        cross = sma_s - sma_l
        signal = pd.Series(0, index=df.index)
        signal[cross > 0] = 1
        signal[cross <= 0] = 0

        # 检测交叉点：signal 从 0→1 为买入，从 1→0 为卖出
        signal_shift = signal.shift(1).fillna(0)
        buy_signals = (signal == 1) & (signal_shift == 0)
        sell_signals = (signal == 0) & (signal_shift == 1)

        # 模拟交易
        trades = self._simulate_trades(prices, buy_signals, sell_signals)

        # 计算指标
        daily_returns = prices.pct_change().dropna()
        total_return = self._calc_total_return(prices)
        annualized_return = self._calc_annualized_return(total_return, len(prices))
        max_drawdown = self._calc_max_drawdown(prices)
        sharpe_ratio = self._calc_sharpe_ratio(daily_returns)
        win_rate = self._calc_win_rate(trades)

        return {
            "status": "ok",
            "results": {
                "total_return": round(total_return, 6),
                "annualized_return": round(annualized_return, 6),
                "max_drawdown": round(max_drawdown, 6),
                "sharpe_ratio": round(sharpe_ratio, 4),
                "win_rate": round(win_rate, 6),
                "trade_count": len(trades),
            },
            "strategy": f"sma_crossover_{sma_short}_{sma_long}",
        }

    @staticmethod
    def _simulate_trades(
        prices: pd.Series,
        buy_signals: pd.Series,
        sell_signals: pd.Series,
    ) -> list[dict[str, Any]]:
        """模拟交易，记录每笔交易的买入/卖出信息。

        Returns:
            交易列表，每笔包含 buy_idx, sell_idx, buy_price, sell_price, return
        """
        trades: list[dict[str, Any]] = []
        holding = False
        buy_idx = None
        buy_price = 0.0

        for i in range(len(prices)):
            if buy_signals.iloc[i] and not holding:
                holding = True
                buy_idx = i
                buy_price = prices.iloc[i]
            elif sell_signals.iloc[i] and holding:
                sell_price = prices.iloc[i]
                trade_return = (sell_price - buy_price) / buy_price if buy_price > 0 else 0.0
                trades.append({
                    "buy_idx": int(buy_idx),
                    "sell_idx": int(i),
                    "buy_price": round(buy_price, 4),
                    "sell_price": round(sell_price, 4),
                    "return": round(trade_return, 6),
                })
                holding = False
                buy_idx = None
                buy_price = 0.0

        return trades

    @staticmethod
    def _calc_total_return(prices: pd.Series) -> float:
        """计算总收益率。"""
        if len(prices) < 2 or prices.iloc[0] == 0:
            return 0.0
        return (prices.iloc[-1] - prices.iloc[0]) / prices.iloc[0]

    @staticmethod
    def _calc_annualized_return(total_return: float, num_days: int) -> float:
        """计算年化收益率。"""
        if num_days <= 0 or total_return <= -1.0:
            return 0.0
        # 252 个交易日为一年
        return (1.0 + total_return) ** (252.0 / num_days) - 1.0

    @staticmethod
    def _calc_max_drawdown(prices: pd.Series) -> float:
        """计算最大回撤。"""
        if len(prices) < 2:
            return 0.0
        cumulative_max = prices.cummax()
        drawdown = (prices - cumulative_max) / cumulative_max
        return float(drawdown.min())

    @staticmethod
    def _calc_sharpe_ratio(daily_returns: pd.Series) -> float:
        """计算年化 Sharpe 比率（无风险利率 3%）。"""
        if len(daily_returns) < 2 or daily_returns.std() == 0:
            return 0.0
        daily_rf = RISK_FREE_RATE / 252.0
        excess_returns = daily_returns - daily_rf
        sharpe = excess_returns.mean() / daily_returns.std() * np.sqrt(252)
        return float(sharpe)

    @staticmethod
    def _calc_win_rate(trades: list[dict[str, Any]]) -> float:
        """计算胜率。"""
        if not trades:
            return 0.0
        wins = sum(1 for t in trades if t["return"] > 0)
        return wins / len(trades)
