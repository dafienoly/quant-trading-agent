"""只读盯盘监控器

结合实时行情、策略信号和运行时风控决策，生成可解释的提醒。
核心约束：永远不生成 Order 对象，只输出 Signal 级别的提醒。
"""
from __future__ import annotations

import pandas as pd
from loguru import logger

from src.risk_engine.models import RiskDecision
from src.strategy_engine.signal_generator import generate_signals


class WatchlistMonitor:
    def generate_alerts(self, scored_data: pd.DataFrame, risk_decision: RiskDecision) -> dict:
        if not risk_decision.can_generate_signal:
            return {
                "risk_pass": risk_decision.risk_pass,
                "risk_messages": risk_decision.messages,
                "signals": [],
                "orders": [],
            }

        try:
            signals = generate_signals(scored_data, include_hold=False)
        except Exception as e:
            logger.warning(f"信号生成失败: {e}")
            return {
                "risk_pass": risk_decision.risk_pass,
                "risk_messages": risk_decision.messages + [f"信号生成异常: {e}"],
                "signals": [],
                "orders": [],
            }

        return {
            "risk_pass": risk_decision.risk_pass,
            "risk_messages": risk_decision.messages,
            "signals": [signal.model_dump() for signal in signals],
            "orders": [],
        }
