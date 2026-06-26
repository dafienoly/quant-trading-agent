from __future__ import annotations

import pytest

from src.product_app.market_data.contracts import ProviderErrorCategory
from src.product_app.market_data.health import ProviderHealthAggregator


class TestProviderHealthAggregator:
    def test_empty_snapshot(self):
        agg = ProviderHealthAggregator()
        snap = agg.snapshot()
        assert snap == {}

    def test_record_success(self):
        agg = ProviderHealthAggregator()
        agg.record_success("eastmoney", 42.5)
        snap = agg.snapshot()
        assert "eastmoney" in snap
        info = snap["eastmoney"]
        assert info["availability"] == pytest.approx(1.0)
        assert info["consecutive_failures"] == 0
        assert info["latency_last_ms"] == 42.5
        assert info["latency_p50_ms"] == 42.5
        assert info["latency_p95_ms"] == 42.5
        assert info["total_success"] == 1
        assert info["total_failures"] == 0
        assert info["fallback_activation_count"] == 0
        assert info["error_category_summary"] == {}
        assert info["circuit_breaker_status"] == "closed"
        assert info["last_success_at"] is not None
        assert info["updated_at"] is not None

    def test_record_failure(self):
        agg = ProviderHealthAggregator()
        agg.record_failure("akshare", ProviderErrorCategory.TIMEOUT, latency_ms=5000.0)
        snap = agg.snapshot()
        assert "akshare" in snap
        info = snap["akshare"]
        assert info["availability"] == pytest.approx(0.0)
        assert info["consecutive_failures"] == 1
        assert info["total_success"] == 0
        assert info["total_failures"] == 1
        assert info["error_category_summary"] == {"TIMEOUT": 1}
        assert info["last_failure_at"] is not None

    def test_multiple_records_calculates_percentiles(self):
        agg = ProviderHealthAggregator()
        latencies = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        for lat in latencies:
            agg.record_success("test_provider", lat)
        snap = agg.snapshot()
        info = snap["test_provider"]
        assert info["total_success"] == 10
        assert info["latency_last_ms"] == 100.0
        assert info["latency_p50_ms"] == pytest.approx(55.0, abs=2.0)
        assert info["latency_p95_ms"] == pytest.approx(95.0, abs=5.0)

    def test_availability_ratio(self):
        agg = ProviderHealthAggregator()
        agg.record_success("p1", 10.0)
        agg.record_success("p1", 10.0)
        agg.record_success("p1", 10.0)
        agg.record_failure("p1", ProviderErrorCategory.TIMEOUT)
        snap = agg.snapshot()
        info = snap["p1"]
        assert info["total_success"] == 3
        assert info["total_failures"] == 1
        assert info["availability"] == pytest.approx(0.75)

    def test_consecutive_failures_reset_on_success(self):
        agg = ProviderHealthAggregator()
        agg.record_failure("p1", ProviderErrorCategory.TIMEOUT)
        agg.record_failure("p1", ProviderErrorCategory.TIMEOUT)
        assert agg.snapshot()["p1"]["consecutive_failures"] == 2
        agg.record_success("p1", 10.0)
        assert agg.snapshot()["p1"]["consecutive_failures"] == 0

    def test_fallback_activation_count(self):
        agg = ProviderHealthAggregator()
        agg.record_success("p1", 10.0, is_fallback=True)
        agg.record_success("p1", 10.0, is_fallback=True)
        agg.record_success("p1", 10.0, is_fallback=False)
        snap = agg.snapshot()
        assert snap["p1"]["fallback_activation_count"] == 2

    def test_error_category_summary(self):
        agg = ProviderHealthAggregator()
        agg.record_failure("p1", ProviderErrorCategory.TIMEOUT)
        agg.record_failure("p1", ProviderErrorCategory.TIMEOUT)
        agg.record_failure("p1", ProviderErrorCategory.AUTH_FAILED)
        snap = agg.snapshot()
        assert snap["p1"]["error_category_summary"] == {"TIMEOUT": 2, "AUTH_FAILED": 1}

    def test_provider_not_recorded_not_in_snapshot(self):
        agg = ProviderHealthAggregator()
        assert "nonexistent" not in agg.snapshot()

    def test_circuit_breaker_passthrough(self):
        agg = ProviderHealthAggregator()
        agg.record_success("p1", 10.0)
        agg.record_failure("p1", ProviderErrorCategory.TIMEOUT)
        info = agg.snapshot()["p1"]
        assert "circuit_breaker_status" in info
