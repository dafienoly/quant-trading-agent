from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.product_app.market_data.cache import CachedEntry, MarketDataCache
from src.product_app.market_data.contracts import (
    DataQualityMetadata,
    FreshnessPolicy,
    QualityStatus,
)
from src.product_app.market_data.quality import CallerContext


def _make_quality(status: QualityStatus = QualityStatus.OK) -> DataQualityMetadata:
    now = datetime.now(timezone.utc)
    return DataQualityMetadata(
        source_provider="test",
        source_priority=1,
        as_of=now,
        received_at=now,
        freshness_seconds=0.0,
        is_stale=False,
        is_realtime=True,
        is_demo=False,
        is_mock=False,
        is_fallback=False,
        quality_status=status,
        quality_reason="",
        provider_latency_ms=10.0,
        request_id="req-cache-test",
    )


class TestCachedEntry:
    def test_fields_present(self):
        now = datetime.now(timezone.utc)
        entry = CachedEntry(
            data={"symbol": "000001.SH", "price": "10.5"},
            cache_created_at=now,
            cache_age_seconds=0.0,
            source_provider="test",
            quality_status=QualityStatus.OK,
            is_stale=False,
        )
        assert entry.cache_hit is True
        assert entry.cache_age_seconds == 0.0
        assert entry.source_provider == "test"
        assert entry.quality_status == QualityStatus.OK
        assert entry.is_stale is False

    def test_age_calculated_on_access(self):
        now = datetime.now(timezone.utc)
        entry = CachedEntry(
            data={"symbol": "000001.SH"},
            cache_created_at=now - timedelta(seconds=30),
            cache_age_seconds=30.0,
            source_provider="test",
            quality_status=QualityStatus.OK,
            is_stale=False,
        )
        assert entry.cache_age_seconds == 30.0


class TestMarketDataCache:
    def test_set_and_get(self):
        cache = MarketDataCache()
        cache.set("key-1", {"symbol": "000001.SH"}, "test_provider", QualityStatus.OK)
        got = cache.get(
            "key-1",
            FreshnessPolicy(max_age_seconds=60.0, stale_age_seconds=300.0, acceptable_delay_ms=5000),
            CallerContext(name="research_readonly"),
        )
        assert got is not None
        assert got.cache_hit is True
        assert got.data == {"symbol": "000001.SH"}
        assert got.source_provider == "test_provider"
        assert got.quality_status == QualityStatus.OK
        assert got.is_stale is False

    def test_get_miss(self):
        cache = MarketDataCache()
        got = cache.get(
            "nonexistent",
            FreshnessPolicy(max_age_seconds=60.0, stale_age_seconds=300.0, acceptable_delay_ms=5000),
            CallerContext(name="research_readonly"),
        )
        assert got is None

    def test_stale_returns_stale_for_research(self):
        cache = MarketDataCache()
        cache.set("stale-key", {"symbol": "000001.SH"}, "test_provider", QualityStatus.OK)
        import time as _time
        _time.sleep(0.01)
        got = cache.get(
            "stale-key",
            FreshnessPolicy(max_age_seconds=0.0, stale_age_seconds=300.0, acceptable_delay_ms=5000),
            CallerContext(name="research_readonly"),
        )
        assert got is not None
        assert got.is_stale is True
        assert got.quality_status == QualityStatus.STALE

    def test_signal_generation_stale_fail_closed(self):
        cache = MarketDataCache()
        cache.set("sig-stale", {"symbol": "000001.SH"}, "test_provider", QualityStatus.OK)
        got = cache.get(
            "sig-stale",
            FreshnessPolicy(max_age_seconds=0.0, stale_age_seconds=300.0, acceptable_delay_ms=5000),
            CallerContext(name="signal_generation"),
        )
        assert got is None, "signal_generation must fail closed on stale cache"

    def test_real_trading_stale_fail_closed(self):
        cache = MarketDataCache()
        cache.set("trade-stale", {"symbol": "000001.SH"}, "test_provider", QualityStatus.OK)
        got = cache.get(
            "trade-stale",
            FreshnessPolicy(max_age_seconds=0.0, stale_age_seconds=300.0, acceptable_delay_ms=5000),
            CallerContext(name="real_trading"),
        )
        assert got is None, "real_trading must fail closed on stale cache"

    def test_fresh_returns_normal_for_all_contexts(self):
        cache = MarketDataCache()
        cache.set("fresh-k", {"symbol": "000001.SH"}, "test_provider", QualityStatus.OK)
        for ctx_name in ("research_readonly", "dashboard_observability", "signal_generation", "real_trading"):
            got = cache.get(
                "fresh-k",
                FreshnessPolicy(max_age_seconds=60.0, stale_age_seconds=300.0, acceptable_delay_ms=5000),
                CallerContext(name=ctx_name),
            )
            assert got is not None, f"fresh cache should be available for {ctx_name}"
            assert got.is_stale is False
            assert got.quality_status == QualityStatus.OK

    def test_position_sizing_stale_fail_closed(self):
        cache = MarketDataCache()
        cache.set("pos-stale", {"symbol": "000001.SH"}, "test_provider", QualityStatus.OK)
        got = cache.get(
            "pos-stale",
            FreshnessPolicy(max_age_seconds=0.0, stale_age_seconds=300.0, acceptable_delay_ms=5000),
            CallerContext(name="position_sizing"),
        )
        assert got is None, "position_sizing must fail closed on stale cache"

    def test_cache_does_not_pretend_live(self):
        cache = MarketDataCache()
        entry = cache.set("demo-key", {"symbol": "000001.SH"}, "demo_provider", QualityStatus.DEMO)
        assert entry.quality_status == QualityStatus.DEMO
        got = cache.get(
            "demo-key",
            FreshnessPolicy(max_age_seconds=60.0, stale_age_seconds=300.0, acceptable_delay_ms=5000),
            CallerContext(name="research_readonly"),
        )
        assert got is not None
        assert got.quality_status == QualityStatus.DEMO
