"""Tests for V16.0b signal observation with health gating."""
from __future__ import annotations

from src.product_app.data_health_gate import DataHealthGate


def test_signal_blocked_when_all_providers_fail():
    gate = DataHealthGate()
    decision = gate.evaluate({"data_status": "FAILED"})
    assert decision.allow_signal is False
    assert decision.allow_research is False


def test_signal_blocked_on_demo():
    gate = DataHealthGate()
    decision = gate.evaluate({"data_status": "OK"}, is_demo=True)
    assert decision.allow_signal is False
    assert decision.allow_order_draft is False


def test_signal_allowed_on_healthy():
    gate = DataHealthGate()
    decision = gate.evaluate({"data_status": "OK", "provider_delay": 5.0})
    assert decision.allow_signal is True
    assert decision.allow_research is True


def test_stale_quote_health():
    gate = DataHealthGate()
    health = gate.get_quote_health({"symbol": "TEST"}, _now=None)
    # no timestamp → STALE
    assert health == gate.QUOTE_STALE


def test_demo_quote_health():
    gate = DataHealthGate()
    health = gate.get_quote_health({"symbol": "DEMO"}, is_demo=True)
    assert health == gate.QUOTE_DEMO
