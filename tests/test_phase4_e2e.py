"""Phase 4 审计整改 — 端到端集成测试 (M4)

覆盖完整流程：实时行情 → 健康门禁 → 风控检查 → 信号生成 → API 返回
"""
from datetime import datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.data_gateway.realtime_health import build_realtime_health_report
from src.risk_engine.models import KillSwitchState, RiskBlockReason, RiskLevel
from src.risk_engine.runtime import RuntimeRiskEngine


def test_e2e_healthy_pipeline():
    """端到端：正常行情 → 健康门禁通过 → 风控通过 → API 返回正常"""
    # 1. 构造新鲜行情
    now = datetime(2026, 6, 9, 10, 0, 5)
    quotes = [
        {"symbol": "002463.SZ", "datetime": "2026-06-09 10:00:00", "last_price": 10.0, "delay_seconds": 5.0, "status": "NORMAL"},
    ]

    # 2. 健康门禁
    health_report = build_realtime_health_report(
        provider="mock", quotes=quotes, now=now, max_delay_seconds=10,
    )
    assert health_report.is_acceptable is True

    # 3. 风控检查（直接调用引擎，传入行情数据）
    engine = RuntimeRiskEngine(max_quote_delay_seconds=10)
    risk_decision = engine.check_realtime_snapshot(quotes=quotes, trading_mode="LEVEL_1_SIGNAL_ONLY")
    assert risk_decision.risk_pass is True
    assert risk_decision.can_generate_signal is True

    # 4. API 层风控状态（/risk/status 返回 Kill Switch 状态）
    client = TestClient(create_app(risk_engine=engine))
    response = client.get("/risk/status")
    assert response.status_code == 200
    assert response.json()["risk_pass"] is True  # Kill Switch 未激活


def test_e2e_stale_data_blocks_pipeline():
    """端到端：延迟行情 → 健康门禁阻断 → 风控阻断"""
    now = datetime(2026, 6, 9, 10, 0, 20)
    quotes = [
        {"symbol": "002463.SZ", "datetime": "2026-06-09 10:00:00", "last_price": 10.0, "delay_seconds": 20.0, "status": "NORMAL"},
    ]

    # 健康门禁
    health_report = build_realtime_health_report(
        provider="mock", quotes=quotes, now=now, max_delay_seconds=10,
    )
    assert health_report.is_acceptable is False

    # 风控检查
    engine = RuntimeRiskEngine(max_quote_delay_seconds=10)
    risk_decision = engine.check_realtime_snapshot(quotes=quotes, trading_mode="LEVEL_1_SIGNAL_ONLY")
    assert risk_decision.risk_pass is False
    assert RiskBlockReason.DATA_DELAY in risk_decision.reasons


def test_e2e_kill_switch_blocks_everything():
    """端到端：Kill Switch 激活 → 风控阻断 → 信号不可生成"""
    engine = RuntimeRiskEngine(kill_switch=KillSwitchState(active=True, reason="emergency"))
    risk_decision = engine.check_realtime_snapshot(
        quotes=[{"symbol": "002463.SZ", "delay_seconds": 1, "status": "NORMAL"}],
        trading_mode="LEVEL_1_SIGNAL_ONLY",
    )
    assert risk_decision.risk_pass is False
    assert risk_decision.can_generate_signal is False

    client = TestClient(create_app(risk_engine=engine))
    response = client.get("/risk/status")
    assert response.json()["risk_pass"] is False
    assert response.json()["kill_switch_active"] is True


def test_e2e_portfolio_risk_blocks_signals():
    """端到端：持仓风控阻断 → 信号不可生成"""
    engine = RuntimeRiskEngine()
    portfolio = {
        "total_assets": 1000000.0,
        "cash": 100000.0,
        "daily_pnl_pct": -0.035,
        "drawdown_pct": 0.0,
        "holdings": [
            {"symbol": "002463.SZ", "sector": "PCB", "position_pct": 0.10, "pnl_pct": -0.01},
        ],
    }

    decision = engine.check_portfolio_risk(portfolio)
    assert decision.risk_pass is False
    assert decision.can_generate_signal is False


def test_e2e_signals_refresh_endpoint():
    """端到端：POST /signals/refresh 触发信号刷新"""
    new_result = {"risk_pass": True, "signals": [{"signal_type": "BUY", "symbol": "002463.SZ"}], "orders": []}
    mock_service = MagicMock()
    mock_service.last_result = None
    mock_service.run_once.return_value = new_result

    client = TestClient(create_app(signal_service=mock_service))

    # 刷新前：无数据
    response = client.get("/signals/latest")
    assert response.json()["signals"] == []

    # 刷新
    response = client.post("/signals/refresh")
    assert response.status_code == 200
    assert response.json()["signals"][0]["symbol"] == "002463.SZ"

    # 模拟 run_once 更新 last_result
    mock_service.last_result = new_result
    response = client.get("/signals/latest")
    assert response.json()["signals"][0]["symbol"] == "002463.SZ"


def test_e2e_signals_refresh_no_service():
    """端到端：无 SignalService 时 /signals/refresh 返回错误"""
    client = TestClient(create_app())

    response = client.post("/signals/refresh")
    assert response.status_code == 200
    assert response.json()["status"] == "error"
