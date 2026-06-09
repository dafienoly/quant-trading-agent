"""Phase 4 只读监控器测试"""
from unittest.mock import patch

import pandas as pd

from src.agent_orchestrator.watchlist_monitor import WatchlistMonitor
from src.risk_engine.models import RiskDecision, RiskLevel


def test_watchlist_monitor_returns_alerts_without_orders():
    monitor = WatchlistMonitor()
    scored = pd.DataFrame([
        {
            "symbol": "002463.SZ",
            "name": "沪电股份",
            "sector_key": "pcb_ccl",
            "trade_date": "20260608",
            "open": 10.0,
            "high": 11.0,
            "low": 9.8,
            "close": 10.8,
            "volume": 300000.0,
            "amount": 3240000.0,
            "pct_change": 3.0,
            "ma5": 10.0,
            "ma10": 9.9,
            "ma20": 9.6,
            "ma60": 9.2,
            "highest_20": 11.0,
            "volume_ma5": 100000.0,
            "volume_ma20": 120000.0,
            "sector_strength": 1.0,
            "policy_score": 95.0,
            "fundamental_score": 80.0,
            "total_score": 85.0,
        }
    ])
    risk = RiskDecision(risk_pass=True, level=RiskLevel.OK)

    result = monitor.generate_alerts(scored, risk)

    assert result["risk_pass"] is True
    assert len(result["signals"]) >= 1
    assert result["orders"] == []


def test_watchlist_monitor_blocks_signals_when_runtime_risk_fails():
    monitor = WatchlistMonitor()
    scored = pd.DataFrame([{"symbol": "002463.SZ", "trade_date": "20260608"}])
    risk = RiskDecision(risk_pass=False, level=RiskLevel.BLOCK, messages=["data delay"])

    result = monitor.generate_alerts(scored, risk)

    assert result["signals"] == []
    assert result["orders"] == []
    assert result["risk_messages"] == ["data delay"]


def test_watchlist_monitor_handles_signal_generation_error():
    monitor = WatchlistMonitor()
    scored = pd.DataFrame([{"symbol": "002463.SZ", "trade_date": "20260608"}])
    risk = RiskDecision(risk_pass=True, level=RiskLevel.OK)

    with patch("src.agent_orchestrator.watchlist_monitor.generate_signals", side_effect=ValueError("missing column")):
        result = monitor.generate_alerts(scored, risk)

    assert result["signals"] == []
    assert result["orders"] == []
    assert any("信号生成异常" in msg for msg in result["risk_messages"])
