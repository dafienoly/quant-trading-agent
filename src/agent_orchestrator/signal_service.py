"""信号生成服务

定时触发因子计算和信号生成，结合运行时风控决策。
核心约束：LEVEL_1_SIGNAL_ONLY 模式下只生成信号提醒，不生成订单。
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable

import pandas as pd
from loguru import logger

from src.agent_orchestrator.watchlist_monitor import WatchlistMonitor
from src.data_gateway.realtime_health import build_realtime_health_report
from src.risk_engine.models import RiskDecision
from src.risk_engine.runtime import RuntimeRiskEngine
from src.strategy_engine.scoring_model import compute_all_factors


class SignalService:
    def __init__(
        self,
        risk_engine: RuntimeRiskEngine | None = None,
        monitor: WatchlistMonitor | None = None,
        max_quote_delay_seconds: float = 10.0,
    ):
        self.risk_engine = risk_engine or RuntimeRiskEngine(
            max_quote_delay_seconds=max_quote_delay_seconds,
        )
        self.monitor = monitor or WatchlistMonitor()
        self._last_result: dict | None = None

    def run_once(
        self,
        scored_data: pd.DataFrame,
        quotes: list[dict] | None = None,
        on_alert: Callable[[dict], None] | None = None,
    ) -> dict:
        """执行一次信号生成周期

        Args:
            scored_data: 已计算因子的数据
            quotes: 实时行情快照 (用于风控检查)
            on_alert: 信号回调函数

        Returns:
            包含 risk_pass, signals, orders 的结果字典
        """
        now = datetime.now()

        # 1. 数据健康检查
        if quotes:
            health = build_realtime_health_report(
                provider="realtime",
                quotes=quotes,
                now=now,
                max_delay_seconds=self.risk_engine.max_quote_delay_seconds,
            )
            if not health.is_acceptable:
                logger.warning(f"数据健康检查未通过: {len(health.delayed_symbols)} 延迟")

        # 2. 运行时风控检查
        risk_decision = self.risk_engine.check_realtime_snapshot(
            quotes=quotes or [],
        )

        # 3. 生成信号
        result = self.monitor.generate_alerts(scored_data, risk_decision)
        self._last_result = result

        # 4. 回调通知
        if on_alert and result["signals"]:
            try:
                on_alert(result)
            except Exception as e:
                logger.warning(f"信号回调异常: {e}")

        logger.info(
            f"信号生成完成: risk_pass={result['risk_pass']}, "
            f"signals={len(result['signals'])}, orders={len(result['orders'])}"
        )

        return result

    @property
    def last_result(self) -> dict | None:
        return self._last_result
