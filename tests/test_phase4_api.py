"""Phase 4 API 测试"""
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.risk_engine.models import KillSwitchState, RiskBlockReason
from src.risk_engine.runtime import RuntimeRiskEngine


def test_health_endpoint_reports_signal_only_mode():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["max_trading_level"] == "LEVEL_1_SIGNAL_ONLY"
    assert response.json()["enable_live_trading"] is False


def test_risk_endpoint_uses_runtime_risk_engine():
    engine = RuntimeRiskEngine(
        max_quote_delay_seconds=10,
        kill_switch=KillSwitchState(active=True, reason="test"),
    )
    client = TestClient(create_app(risk_engine=engine))

    response = client.get("/risk/status")

    assert response.status_code == 200
    body = response.json()
    assert body["risk_pass"] is False
    assert RiskBlockReason.KILL_SWITCH in body["reasons"]


def test_risk_endpoint_no_orders_key():
    client = TestClient(create_app())

    response = client.get("/risk/status")

    assert response.status_code == 200
    assert "orders" not in response.json()


def test_signals_latest_returns_empty_when_no_service():
    client = TestClient(create_app())

    response = client.get("/signals/latest")

    assert response.status_code == 200
    assert response.json()["signals"] == []
    assert response.json()["orders"] == []


def test_backtest_run_rejected_via_api():
    client = TestClient(create_app())

    response = client.get("/backtest/run", params={"start_date": "20250101", "end_date": "20251231"})

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
