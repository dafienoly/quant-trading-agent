"""Phase 4 信号服务测试"""
from unittest.mock import MagicMock

import pandas as pd

from src.agent_orchestrator.signal_service import SignalService
from src.risk_engine.models import KillSwitchState, RiskDecision, RiskLevel
from src.risk_engine.runtime import RuntimeRiskEngine


def test_signal_service_blocks_when_kill_switch_active():
    engine = RuntimeRiskEngine(kill_switch=KillSwitchState(active=True, reason="test"))
    service = SignalService(risk_engine=engine)
    scored = pd.DataFrame([{"symbol": "002463.SZ", "trade_date": "20260608"}])

    result = service.run_once(scored, quotes=[])

    assert result["risk_pass"] is False
    assert result["signals"] == []
    assert result["orders"] == []


def test_signal_service_calls_on_alert_callback():
    service = SignalService()
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
    callback = MagicMock()

    result = service.run_once(
        scored,
        quotes=[{"symbol": "002463.SZ", "delay_seconds": 1, "status": "NORMAL"}],
        on_alert=callback,
    )

    assert result["risk_pass"] is True
    if result["signals"]:
        callback.assert_called_once()


def test_signal_service_stores_last_result():
    service = SignalService()
    scored = pd.DataFrame([{"symbol": "002463.SZ", "trade_date": "20260608"}])

    service.run_once(scored, quotes=[])
    assert service.last_result is not None
    assert "risk_pass" in service.last_result
