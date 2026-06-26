from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.product_app.market_data.contracts import (
    AuthRequirement,
    CachePolicy,
    DataQualityMetadata,
    FallbackEligibility,
    FreshnessPolicy,
    ItemError,
    MarketBar,
    MarketDataProviderContract,
    MarketQuote,
    MultiSymbolQuoteResult,
    ProviderAttempt,
    ProviderErrorCategory,
    QualityStatus,
    RateLimitPolicy,
    TimeoutPolicy,
)


class TestQualityStatus:
    def test_enum_values(self):
        assert QualityStatus.OK == "OK"
        assert QualityStatus.STALE == "STALE"
        assert QualityStatus.DEGRADED == "DEGRADED"
        assert QualityStatus.FALLBACK == "FALLBACK"
        assert QualityStatus.UNAVAILABLE == "UNAVAILABLE"
        assert QualityStatus.INVALID == "INVALID"
        assert QualityStatus.MOCK == "MOCK"
        assert QualityStatus.DEMO == "DEMO"

    def test_all_members_present(self):
        expected = {"OK", "STALE", "DEGRADED", "FALLBACK", "UNAVAILABLE", "INVALID", "MOCK", "DEMO"}
        assert set(QualityStatus.__members__) == expected


class TestProviderErrorCategory:
    def test_enum_values(self):
        assert ProviderErrorCategory.AUTH_FAILED == "AUTH_FAILED"
        assert ProviderErrorCategory.RATE_LIMITED == "RATE_LIMITED"
        assert ProviderErrorCategory.TIMEOUT == "TIMEOUT"
        assert ProviderErrorCategory.NETWORK_ERROR == "NETWORK_ERROR"
        assert ProviderErrorCategory.EMPTY_RESPONSE == "EMPTY_RESPONSE"
        assert ProviderErrorCategory.MALFORMED_RESPONSE == "MALFORMED_RESPONSE"
        assert ProviderErrorCategory.MISSING_FIELD == "MISSING_FIELD"
        assert ProviderErrorCategory.INVALID_VALUE == "INVALID_VALUE"
        assert ProviderErrorCategory.STALE_DATA == "STALE_DATA"
        assert ProviderErrorCategory.PROVIDER_UNAVAILABLE == "PROVIDER_UNAVAILABLE"
        assert ProviderErrorCategory.UNKNOWN_PROVIDER_ERROR == "UNKNOWN_PROVIDER_ERROR"

    def test_all_members_present(self):
        expected = {
            "AUTH_FAILED", "RATE_LIMITED", "TIMEOUT", "NETWORK_ERROR",
            "EMPTY_RESPONSE", "MALFORMED_RESPONSE", "MISSING_FIELD",
            "INVALID_VALUE", "STALE_DATA", "PROVIDER_UNAVAILABLE", "UNKNOWN_PROVIDER_ERROR",
        }
        assert set(ProviderErrorCategory.__members__) == expected


class TestAuthRequirement:
    def test_defaults(self):
        req = AuthRequirement()
        assert req.requires_auth is False
        assert req.auth_type == "none"

    def test_with_values(self):
        req = AuthRequirement(requires_auth=True, auth_type="api_key")
        assert req.requires_auth is True
        assert req.auth_type == "api_key"


class TestDataQualityMetadata:
    def test_minimal_fields(self):
        now = datetime.now(timezone.utc)
        meta = DataQualityMetadata(
            source_provider="akshare",
            source_priority=1,
            as_of=now,
            received_at=now,
            freshness_seconds=0.5,
            quality_status=QualityStatus.OK,
            quality_reason="fresh",
            request_id="req-001",
        )
        assert meta.source_provider == "akshare"
        assert meta.source_priority == 1
        assert meta.quality_status == QualityStatus.OK
        assert meta.is_stale is False
        assert meta.is_realtime is False
        assert meta.is_demo is False
        assert meta.is_mock is False
        assert meta.is_fallback is False
        assert meta.provider_latency_ms is None
        assert meta.freshness_seconds == 0.5
        assert meta.request_id == "req-001"

    def test_default_is_stale_false(self):
        now = datetime.now(timezone.utc)
        meta = DataQualityMetadata(
            source_provider="test",
            source_priority=1,
            as_of=now,
            received_at=now,
            freshness_seconds=1.0,
            quality_status=QualityStatus.OK,
            quality_reason="ok",
            request_id="r1",
        )
        assert meta.is_stale is False

    def test_missing_fields_raises(self):
        with pytest.raises(ValidationError):
            DataQualityMetadata()  # type: ignore[call-arg]


class TestMarketQuote:
    def test_minimal_quote(self):
        now = datetime.now(timezone.utc)
        quality = DataQualityMetadata(
            source_provider="akshare",
            source_priority=1,
            as_of=now,
            received_at=now,
            freshness_seconds=0.5,
            quality_status=QualityStatus.OK,
            quality_reason="fresh",
            request_id="req-001",
        )
        quote = MarketQuote(
            symbol="002463.SZ",
            market="A",
            asset_type="equity",
            price=Decimal("38.52"),
            quality=quality,
        )
        assert quote.symbol == "002463.SZ"
        assert quote.price == Decimal("38.52")
        assert quote.open is None
        assert quote.volume is None
        assert quote.currency is None
        assert quote.quality.quality_status == QualityStatus.OK

    def test_full_quote(self):
        now = datetime.now(timezone.utc)
        quality = DataQualityMetadata(
            source_provider="akshare",
            source_priority=1,
            as_of=now,
            received_at=now,
            freshness_seconds=0.5,
            quality_status=QualityStatus.OK,
            quality_reason="fresh",
            request_id="req-001",
        )
        quote = MarketQuote(
            symbol="002463.SZ",
            market="A",
            asset_type="equity",
            price=Decimal("38.52"),
            open=Decimal("37.20"),
            high=Decimal("38.80"),
            low=Decimal("37.00"),
            previous_close=Decimal("37.64"),
            volume=12580000,
            currency="CNY",
            quality=quality,
        )
        assert quote.open == Decimal("37.20")
        assert quote.high == Decimal("38.80")
        assert quote.volume == 12580000
        assert quote.currency == "CNY"


class TestMarketBar:
    def test_minimal_bar(self):
        now = datetime.now(timezone.utc)
        quality = DataQualityMetadata(
            source_provider="akshare",
            source_priority=1,
            as_of=now,
            received_at=now,
            freshness_seconds=0.5,
            quality_status=QualityStatus.OK,
            quality_reason="fresh",
            request_id="req-001",
        )
        bar = MarketBar(
            symbol="002463.SZ",
            market="A",
            granularity="1d",
            timestamp=now,
            open=Decimal("37.20"),
            high=Decimal("38.80"),
            low=Decimal("37.00"),
            close=Decimal("38.52"),
            quality=quality,
        )
        assert bar.symbol == "002463.SZ"
        assert bar.granularity == "1d"
        assert bar.close == Decimal("38.52")
        assert bar.volume is None

    def test_bar_with_volume(self):
        now = datetime.now(timezone.utc)
        quality = DataQualityMetadata(
            source_provider="akshare",
            source_priority=1,
            as_of=now,
            received_at=now,
            freshness_seconds=0.5,
            quality_status=QualityStatus.OK,
            quality_reason="fresh",
            request_id="req-001",
        )
        bar = MarketBar(
            symbol="002463.SZ",
            market="A",
            granularity="1d",
            timestamp=now,
            open=Decimal("37.20"),
            high=Decimal("38.80"),
            low=Decimal("37.00"),
            close=Decimal("38.52"),
            volume=12580000,
            quality=quality,
        )
        assert bar.volume == 12580000

    def test_bar_requires_open_high_low_close(self):
        now = datetime.now(timezone.utc)
        quality = DataQualityMetadata(
            source_provider="akshare",
            source_priority=1,
            as_of=now,
            received_at=now,
            freshness_seconds=0.5,
            quality_status=QualityStatus.OK,
            quality_reason="fresh",
            request_id="req-001",
        )
        with pytest.raises(ValidationError):
            MarketBar(
                symbol="002463.SZ",
                market="A",
                granularity="1d",
                timestamp=now,
                quality=quality,
            )


class TestProviderAttempt:
    def test_minimal(self):
        attempt = ProviderAttempt(provider_id="akshare", priority=1)
        assert attempt.provider_id == "akshare"
        assert attempt.priority == 1
        assert attempt.error_category is None
        assert attempt.quality_status is None
        assert attempt.latency_ms is None
        assert attempt.safe_reason == ""

    def test_full(self):
        attempt = ProviderAttempt(
            provider_id="eastmoney",
            priority=2,
            error_category=ProviderErrorCategory.TIMEOUT,
            quality_status=QualityStatus.FALLBACK,
            latency_ms=1500.0,
            safe_reason="Connection timed out after 1500ms",
        )
        assert attempt.error_category == ProviderErrorCategory.TIMEOUT
        assert attempt.quality_status == QualityStatus.FALLBACK
        assert attempt.latency_ms == 1500.0


class TestItemError:
    def test_fields(self):
        err = ItemError(
            symbol="002463.SZ",
            error_category=ProviderErrorCategory.EMPTY_RESPONSE,
            safe_reason="No data returned",
            quality_status=QualityStatus.UNAVAILABLE,
        )
        assert err.symbol == "002463.SZ"
        assert err.error_category == ProviderErrorCategory.EMPTY_RESPONSE
        assert err.quality_status == QualityStatus.UNAVAILABLE


class TestMultiSymbolQuoteResult:
    def test_minimal(self):
        now = datetime.now(timezone.utc)
        quality = DataQualityMetadata(
            source_provider="akshare",
            source_priority=1,
            as_of=now,
            received_at=now,
            freshness_seconds=0.5,
            quality_status=QualityStatus.OK,
            quality_reason="fresh",
            request_id="req-001",
        )
        quote = MarketQuote(
            symbol="002463.SZ",
            market="A",
            asset_type="equity",
            price=Decimal("38.52"),
            quality=quality,
        )
        result = MultiSymbolQuoteResult(
            results=[quote],
            item_errors=[],
            summary={"total": 1, "ok_count": 1, "failed_count": 0, "degraded_count": 0, "fallback_count": 0},
            request_quality=QualityStatus.OK,
            request_id="req-001",
        )
        assert len(result.results) == 1
        assert result.summary["total"] == 1
        assert result.request_quality == QualityStatus.OK

    def test_with_item_errors(self):
        now = datetime.now(timezone.utc)
        quality = DataQualityMetadata(
            source_provider="akshare",
            source_priority=1,
            as_of=now,
            received_at=now,
            freshness_seconds=0.5,
            quality_status=QualityStatus.OK,
            quality_reason="fresh",
            request_id="req-001",
        )
        quote = MarketQuote(
            symbol="002463.SZ",
            market="A",
            asset_type="equity",
            price=Decimal("38.52"),
            quality=quality,
        )
        err = ItemError(
            symbol="600000.SH",
            error_category=ProviderErrorCategory.EMPTY_RESPONSE,
            safe_reason="No data",
        )
        result = MultiSymbolQuoteResult(
            results=[quote],
            item_errors=[err],
            summary={"total": 2, "ok_count": 1, "failed_count": 1, "degraded_count": 0, "fallback_count": 0},
            request_quality=QualityStatus.DEGRADED,
            request_id="req-001",
        )
        assert len(result.item_errors) == 1
        assert result.request_quality == QualityStatus.DEGRADED
        assert result.results[0].symbol == "002463.SZ"


class TestMarketDataProviderContract:
    def test_minimal_contract(self):
        auth = AuthRequirement()
        rate_limit = RateLimitPolicy()
        timeout = TimeoutPolicy()
        freshness = FreshnessPolicy()
        cache = CachePolicy()
        fallback = FallbackEligibility()

        contract = MarketDataProviderContract(
            provider_id="akshare",
            provider_name="AkShare",
            market_scope=["A"],
            supported_asset_types=["equity"],
            supported_granularities=["1d"],
            supported_endpoints=["latest_quote", "bars"],
            auth_requirement=auth,
            rate_limit_policy=rate_limit,
            timeout_policy=timeout,
            freshness_policy=freshness,
            cache_policy=cache,
            fallback_eligibility=fallback,
            quality_status_mapping={"ok": QualityStatus.OK},
            error_mapping={"timeout": ProviderErrorCategory.TIMEOUT},
        )
        assert contract.provider_id == "akshare"
        assert contract.market_scope == ["A"]
        assert len(contract.supported_endpoints) == 2
        assert contract.quality_status_mapping["ok"] == QualityStatus.OK
        assert contract.error_mapping["timeout"] == ProviderErrorCategory.TIMEOUT

    def test_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            MarketDataProviderContract()  # type: ignore[call-arg]


class TestAuthRequirementModel:
    def test_defaults(self):
        req = AuthRequirement()
        assert req.requires_auth is False
        assert req.auth_type == "none"


class TestRateLimitPolicy:
    def test_defaults(self):
        policy = RateLimitPolicy()
        assert policy.max_requests_per_second == 10
        assert policy.max_requests_per_minute == 600
        assert policy.burst_size == 5


class TestTimeoutPolicy:
    def test_defaults(self):
        policy = TimeoutPolicy()
        assert policy.connect_timeout_seconds == 10.0
        assert policy.read_timeout_seconds == 30.0
        assert policy.total_timeout_seconds == 60.0


class TestFreshnessPolicy:
    def test_defaults(self):
        policy = FreshnessPolicy()
        assert policy.max_age_seconds == 60.0
        assert policy.stale_age_seconds == 300.0
        assert policy.acceptable_delay_ms == 5000


class TestCachePolicy:
    def test_defaults(self):
        policy = CachePolicy()
        assert policy.ttl_seconds == 30.0
        assert policy.max_size == 1000


class TestFallbackEligibility:
    def test_defaults(self):
        policy = FallbackEligibility()
        assert policy.can_fallback is True
        assert policy.fallback_priority_offset == 1
