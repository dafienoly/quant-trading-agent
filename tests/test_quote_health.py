"""Tests for quote health state evaluation."""
from __future__ import annotations

import datetime
from unittest.mock import patch

from src.product_app.data_health_gate import DataHealthGate


def _make_quote(received_at=None, price=10.0):
    return {"symbol": "000001.SZ", "price": price, "received_at": received_at}


class TestQuoteHealth:

    @patch.object(DataHealthGate, "STALE_THRESHOLD_SECONDS", 30.0)
    def test_healthy_quote(self):
        gate = DataHealthGate()
        fixed_now = datetime.datetime(2026, 6, 23, 10, 0, 0, tzinfo=datetime.timezone.utc)
        health = gate.get_quote_health(_make_quote(fixed_now.isoformat()), _now=fixed_now)
        assert health == gate.QUOTE_HEALTHY, f"expected HEALTHY, got {health}"

    @patch.object(DataHealthGate, "STALE_THRESHOLD_SECONDS", 30.0)
    def test_stale_quote(self):
        gate = DataHealthGate()
        fixed_now = datetime.datetime(2026, 6, 23, 10, 0, 0, tzinfo=datetime.timezone.utc)
        old_ts = (fixed_now - datetime.timedelta(seconds=60)).isoformat()
        health = gate.get_quote_health(_make_quote(old_ts), _now=fixed_now)
        assert health == gate.QUOTE_STALE, f"expected STALE, got {health}"

    def test_none_quote_is_unavailable(self):
        gate = DataHealthGate()
        health = gate.get_quote_health(None)
        assert health == gate.QUOTE_UNAVAILABLE

    def test_demo_quote(self):
        gate = DataHealthGate()
        health = gate.get_quote_health({"symbol": "DEMO"}, is_demo=True)
        assert health == gate.QUOTE_DEMO

    def test_missing_timestamp_is_stale(self):
        gate = DataHealthGate()
        health = gate.get_quote_health({"symbol": "000001.SZ"})
        assert health == gate.QUOTE_STALE

    def test_stale_blocks_signal(self):
        gate = DataHealthGate()
        decision = gate.evaluate(
            {"data_status": "OK", "provider_delay": 120.0},
            trading_mode="LEVEL_2_HUMAN_CONFIRM",
        )
        assert decision.allow_order_draft is False
        assert decision.allow_signal is False

    def test_healthy_allows_research(self):
        gate = DataHealthGate()
        decision = gate.evaluate(
            {"data_status": "OK", "provider_delay": 5.0},
            trading_mode="LEVEL_1_SIGNAL_ONLY",
        )
        assert decision.allow_research is True
        assert decision.allow_signal is True

    def test_demo_data_rejected_when_allow_demo_false(self):
        gate = DataHealthGate()
        decision = gate.evaluate(
            {"data_status": "OK"}, is_demo=True,
        )
        assert decision.allow_signal is False
        assert decision.allow_order_draft is False

    def test_all_providers_failed_fail_closed(self):
        gate = DataHealthGate()
        decision = gate.evaluate({"data_status": "FAILED"})
        assert decision.allow_research is False
        assert decision.allow_signal is False
        assert decision.allow_order_draft is False

    def test_demo_quote_signal_blocked(self):
        gate = DataHealthGate()
        health = gate.get_quote_health({"symbol": "DEMO"}, is_demo=True)
        assert health == gate.QUOTE_DEMO
        decision = gate.evaluate({"data_status": "OK"}, is_demo=True)
        assert decision.allow_signal is False
        assert decision.allow_order_draft is False


class TestRefreshStatus:

    def test_idle_on_init(self):
        from src.product_app.service_manager import ServiceManager
        sm = ServiceManager()
        assert sm.get_refresh_status()["status"] == "IDLE"

    def test_set_refresh_result(self):
        from src.product_app.service_manager import ServiceManager
        sm = ServiceManager()
        sm._set_refresh_result("SUCCEEDED", [{"symbol": "000001.SZ"}])
        assert sm.get_refresh_status()["status"] == "SUCCEEDED"


class TestQuoteHealthConstants:

    def test_constants_exist(self):
        from src.product_app.live_data_service import (
            REFRESH_IDLE, REFRESH_FAILED, REFRESH_CANCELLED,
        )
        assert REFRESH_IDLE == "IDLE"
        assert REFRESH_FAILED == "FAILED"
        assert REFRESH_CANCELLED == "CANCELLED"
