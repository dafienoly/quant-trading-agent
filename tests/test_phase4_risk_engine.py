"""Phase 4 风控引擎测试"""
from src.risk_engine.models import KillSwitchState, RiskBlockReason, RiskDecision, RiskLevel
from src.risk_engine.runtime import RuntimeRiskEngine


def test_risk_decision_defaults_to_blocked_when_not_passed():
    decision = RiskDecision(risk_pass=False, level=RiskLevel.BLOCK)

    assert decision.risk_pass is False
    assert decision.level == RiskLevel.BLOCK
    assert decision.can_generate_order is False


def test_signal_mode_never_allows_order_generation():
    decision = RiskDecision(
        risk_pass=True,
        level=RiskLevel.OK,
        trading_mode="LEVEL_1_SIGNAL_ONLY",
    )

    assert decision.can_generate_signal is True
    assert decision.can_generate_order is False


def test_runtime_risk_blocks_stale_quotes():
    engine = RuntimeRiskEngine(max_quote_delay_seconds=10)

    decision = engine.check_realtime_snapshot(
        quotes=[{"symbol": "002463.SZ", "delay_seconds": 12, "status": "NORMAL"}],
        trading_mode="LEVEL_1_SIGNAL_ONLY",
    )

    assert decision.risk_pass is False
    assert RiskBlockReason.DATA_DELAY in decision.reasons


def test_runtime_risk_blocks_manual_kill_switch():
    engine = RuntimeRiskEngine(kill_switch=KillSwitchState(active=True, reason="manual stop"))

    decision = engine.check_realtime_snapshot(
        quotes=[{"symbol": "002463.SZ", "delay_seconds": 1, "status": "NORMAL"}],
        trading_mode="LEVEL_1_SIGNAL_ONLY",
    )

    assert decision.risk_pass is False
    assert RiskBlockReason.KILL_SWITCH in decision.reasons


def test_runtime_risk_rejects_chinext_symbol():
    engine = RuntimeRiskEngine()

    decision = engine.check_symbol_universe(["300001.SZ"])

    assert decision.risk_pass is False
    assert RiskBlockReason.DISALLOWED_BOARD in decision.reasons


def test_runtime_risk_blocks_empty_quotes():
    engine = RuntimeRiskEngine()

    decision = engine.check_realtime_snapshot(quotes=[], trading_mode="LEVEL_1_SIGNAL_ONLY")

    assert decision.risk_pass is False
    assert RiskBlockReason.EMPTY_QUOTES in decision.reasons


def test_warn_level_allows_signal_but_not_order():
    decision = RiskDecision(risk_pass=True, level=RiskLevel.WARN, trading_mode="LEVEL_1_SIGNAL_ONLY")

    assert decision.can_generate_signal is True
    assert decision.can_generate_order is False
