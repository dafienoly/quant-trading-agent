"""Tests for quote health state evaluation."""
from __future__ import annotations

import datetime
from unittest.mock import patch

from src.product_app.data_health_gate import DataHealthGate


def _make_quote(received_at, is_demo=False):
    return {"symbol": "000001.SZ", "price": 10.0, "received_at": received_at}


class TestQuoteHealth:

    def test_healthy_quote(self):
        gate = DataHealthGate()
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        health = gate.get_quote_health(_make_quote(now))
        assert health == gate.QUOTE_HEALTHY, f"expected HEALTHY, got {health}"

    def test_stale_quote(self):
        gate = DataHealthGate()
        old = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=60)).isoformat()
        health = gate.get_quote_health(_make_quote(old))
        assert health == gate.QUOTE_STALE, f"expected STALE, got {health}"

    def test_none_quote_is_unavailable(self):
        gate = DataHealthGate()
        health = gate.get_quote_health(None)
        assert health == gate.QUOTE_UNAVAILABLE, f"expected UNAVAILABLE, got {health}"

    def test_demo_quote(self):
        gate = DataHealthGate()
        health = gate.get_quote_health({"symbol": "DEMO"}, is_demo=True)
        assert health == gate.QUOTE_DEMO, f"expected DEMO, got {health}"

    def test_missing_timestamp_is_stale(self):
        gate = DataHealthGate()
        health = gate.get_quote_health({"symbol": "000001.SZ"})
        assert health == gate.QUOTE_STALE, f"expected STALE, got {health}"

    def test_stale_blocks_signal(self):
        """STALE data must not allow order draft."""
        gate = DataHealthGate()
        decision = gate.evaluate(
            {"data_status": "OK", "provider_delay": 120.0},
            trading_mode="LEVEL_2_HUMAN_CONFIRM",
        )
        assert decision.allow_order_draft is False, "STALE should block orders"
        assert decision.allow_signal is False, "STALE should block signals"

    def test_healthy_allows_research(self):
        gate = DataHealthGate()
        decision = gate.evaluate(
            {"data_status": "OK", "provider_delay": 5.0},
            trading_mode="LEVEL_1_SIGNAL_ONLY",
        )
        assert decision.allow_research is True
        assert decision.allow_signal is True


class TestRefreshStatus:

    def test_idle_on_init(self):
        from src.product_app.service_manager import ServiceManager
        sm = ServiceManager()
        status = sm.get_refresh_status()
        assert status["status"] == "IDLE"

    def test_set_refresh_result(self):
        from src.product_app.service_manager import ServiceManager
        sm = ServiceManager()
        sm._set_refresh_result("SUCCEEDED", [{"symbol": "000001.SZ"}])
        status = sm.get_refresh_status()
        assert status["status"] == "SUCCEEDED"
        assert len(status["data"]) == 1


class TestQuoteHealthConstants:

    def test_constants_exist(self):
        from src.product_app.live_data_service import (
            REFRESH_IDLE, REFRESH_QUEUED, REFRESH_RUNNING,
            REFRESH_SUCCEEDED, REFRESH_FAILED, REFRESH_CANCELLED,
        )
        assert REFRESH_IDLE == "IDLE"
        assert REFRESH_FAILED == "FAILED"
        assert REFRESH_CANCELLED == "CANCELLED"
