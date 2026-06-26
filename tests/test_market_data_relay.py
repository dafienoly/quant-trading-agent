from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.product_app.market_data.contracts import (
    DataQualityMetadata,
    MarketDataProviderContract,
    MarketQuote,
    ProviderAttempt,
    ProviderErrorCategory,
    QualityStatus,
)
from src.product_app.market_data.errors import MarketDataUnavailableError
from src.product_app.market_data.quality import CallerContext, QualityGate
from src.product_app.market_data.relay import MarketDataRelay
from src.product_app.market_data.provider_registry import ProviderRegistry
from tests.test_market_data_cache import _make_quality


def _make_contract(provider_id: str) -> MarketDataProviderContract:
    from src.product_app.market_data.contracts import (
        AuthRequirement, CachePolicy, FallbackEligibility, FreshnessPolicy,
        RateLimitPolicy, TimeoutPolicy,
    )
    return MarketDataProviderContract(
        provider_id=provider_id,
        provider_name=provider_id,
        market_scope=["SH", "SZ"],
        supported_asset_types=["equity"],
        supported_granularities=["1d"],
        supported_endpoints=["latest_quote", "bars"],
        auth_requirement=AuthRequirement(),
        rate_limit_policy=RateLimitPolicy(),
        timeout_policy=TimeoutPolicy(),
        freshness_policy=FreshnessPolicy(),
        cache_policy=CachePolicy(),
        fallback_eligibility=FallbackEligibility(can_fallback=True),
        quality_status_mapping={},
        error_mapping={},
    )


def _make_quote(symbol: str, provider_id: str, status: QualityStatus = QualityStatus.OK) -> MarketQuote:
    import uuid
    now = datetime.now(timezone.utc)
    return MarketQuote(
        symbol=symbol,
        market="SH",
        asset_type="equity",
        price=Decimal("10.5"),
        quality=DataQualityMetadata(
            source_provider=provider_id,
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
            request_id=uuid.uuid4().hex[:12],
        ),
    )


class _FakeAdapter:
    def __init__(self, provider_id: str):
        self._provider_id = provider_id
        self.contract = _make_contract(provider_id)

    def fetch_latest_quote(self, symbol: str, timeout: float | None = None, priority: int = 1) -> MarketQuote:
        return _make_quote(symbol, self._provider_id)

    def fetch_latest_quotes(
        self, symbols: list[str], timeout: float | None = None, priority: int = 1
    ) -> Any:
        from src.product_app.market_data.contracts import MultiSymbolQuoteResult
        import uuid
        quotes = [_make_quote(s, self._provider_id) for s in symbols]
        return MultiSymbolQuoteResult(
            results=quotes,
            item_errors=[],
            summary={"total": len(quotes), "ok_count": len(quotes), "failed_count": 0, "degraded_count": 0, "fallback_count": 0},
            request_quality=QualityStatus.OK,
            request_id=uuid.uuid4().hex[:12],
        )

    def fetch_bars(self, symbol: str, granularity: str, start: datetime, end: datetime, timeout: float | None = None) -> list[Any]:
        from src.product_app.market_data.contracts import MarketBar
        now = datetime.now(timezone.utc)
        return [
            MarketBar(
                symbol=symbol,
                market="SH",
                granularity=granularity,
                timestamp=now,
                open=Decimal("10.0"),
                high=Decimal("11.0"),
                low=Decimal("9.5"),
                close=Decimal("10.5"),
                volume=100000,
                quality=_make_quality(),
            )
        ]


class _FakeFailingAdapter:
    def __init__(self, provider_id: str):
        self._provider_id = provider_id
        self.contract = _make_contract(provider_id)

    def fetch_latest_quote(self, symbol: str, timeout: float | None = None, priority: int = 1) -> MarketQuote:
        raise MarketDataUnavailableError(
            request_id="req-fail",
            safe_reason=f"{self._provider_id}: unavailable",
            provider_attempts=[ProviderAttempt(
                provider_id=self._provider_id, priority=priority,
                error_category=ProviderErrorCategory.PROVIDER_UNAVAILABLE,
                latency_ms=1000.0, safe_reason="unavailable",
            )],
            quality_status=QualityStatus.UNAVAILABLE,
        )

    def fetch_latest_quotes(self, symbols: list[str], timeout: float | None = None, priority: int = 1) -> Any:
        raise MarketDataUnavailableError(
            request_id="req-fail",
            safe_reason=f"{self._provider_id}: unavailable",
            provider_attempts=[ProviderAttempt(
                provider_id=self._provider_id, priority=priority,
                error_category=ProviderErrorCategory.PROVIDER_UNAVAILABLE,
                latency_ms=1000.0, safe_reason="unavailable",
            )],
            quality_status=QualityStatus.UNAVAILABLE,
        )

    def fetch_bars(self, symbol: str, granularity: str, start: datetime, end: datetime, timeout: float | None = None) -> list[Any]:
        raise MarketDataUnavailableError(
            request_id="req-fail",
            safe_reason=f"{self._provider_id}: unavailable",
            provider_attempts=[ProviderAttempt(
                provider_id=self._provider_id, priority=999,
                error_category=ProviderErrorCategory.PROVIDER_UNAVAILABLE,
                latency_ms=1000.0, safe_reason="unavailable",
            )],
            quality_status=QualityStatus.UNAVAILABLE,
        )


class TestMarketDataRelay:
    def _make_relay(self) -> MarketDataRelay:
        registry = ProviderRegistry()
        audit = MagicMock()
        health = MagicMock()
        cache = MagicMock()
        quality_gate = QualityGate()
        return MarketDataRelay(
            registry=registry,
            audit=audit,
            health=health,
            cache=cache,
            quality_gate=quality_gate,
        )

    def _register(self, relay, provider_id: str, adapter, priority: int = 1):
        relay._registry.register(
            contract=_make_contract(provider_id),
            priority=priority,
            fallback_allowed=True,
            risk_sensitive_allowed=True,
            adapter=adapter,
        )

    def test_get_latest_quote_success(self):
        relay = self._make_relay()
        self._register(relay, "eastmoney", _FakeAdapter("eastmoney"))

        quote = relay.get_latest_quote(
            symbol="000001.SH",
            market="SH",
            caller_context=CallerContext(name="research_readonly"),
        )
        assert quote.symbol == "000001.SH"
        assert quote.quality.quality_status == QualityStatus.OK
        relay._audit.record_success.assert_called_once()
        relay._health.record_success.assert_called_once()

    def test_get_latest_quote_fail_closed(self):
        relay = self._make_relay()
        self._register(relay, "eastmoney", _FakeFailingAdapter("eastmoney"))

        with pytest.raises(MarketDataUnavailableError) as exc_info:
            relay.get_latest_quote(
                symbol="000001.SH",
                market="SH",
                caller_context=CallerContext(name="research_readonly"),
            )
        assert exc_info.value.quality_status == QualityStatus.UNAVAILABLE
        assert exc_info.value.fallback_used is False
        relay._audit.record_fail_closed.assert_called_once()
        relay._health.record_failure.assert_called_once()

    def test_get_latest_quote_fallback_success(self):
        relay = self._make_relay()
        self._register(relay, "eastmoney", _FakeFailingAdapter("eastmoney"), priority=1)
        self._register(relay, "akshare", _FakeAdapter("akshare"), priority=2)

        quote = relay.get_latest_quote(
            symbol="000001.SH",
            market="SH",
            caller_context=CallerContext(name="research_readonly"),
        )
        assert quote.symbol == "000001.SH"
        assert quote.quality.is_fallback is True
        assert quote.quality.source_priority == 2

    def test_get_latest_quote_all_fail(self):
        relay = self._make_relay()
        self._register(relay, "p1", _FakeFailingAdapter("p1"), priority=1)
        self._register(relay, "p2", _FakeFailingAdapter("p2"), priority=2)

        with pytest.raises(MarketDataUnavailableError) as exc_info:
            relay.get_latest_quote(
                symbol="000001.SH",
                market="SH",
                caller_context=CallerContext(name="research_readonly"),
            )
        assert exc_info.value.fallback_used is True
        assert len(exc_info.value.provider_attempts) == 2

    def test_get_latest_quotes_success(self):
        relay = self._make_relay()
        self._register(relay, "eastmoney", _FakeAdapter("eastmoney"))

        result = relay.get_latest_quotes(
            symbols=["000001.SH", "600000.SH"],
            market="SH",
            caller_context=CallerContext(name="research_readonly"),
        )
        assert len(result.results) == 2
        assert result.request_quality == QualityStatus.OK
        relay._audit.record_success.assert_called_once()

    def test_get_bars_success(self):
        relay = self._make_relay()
        self._register(relay, "eastmoney", _FakeAdapter("eastmoney"))

        now = datetime.now(timezone.utc)
        bars = relay.get_bars(
            symbol="000001.SH",
            market="SH",
            granularity="1d",
            start=now,
            end=now,
            caller_context=CallerContext(name="research_readonly"),
        )
        assert len(bars) == 1
        assert bars[0].granularity == "1d"

    def test_request_id_unique(self):
        relay = self._make_relay()
        self._register(relay, "eastmoney", _FakeAdapter("eastmoney"))

        q1 = relay.get_latest_quote("000001.SH", "SH", CallerContext(name="research_readonly"))
        q2 = relay.get_latest_quote("600000.SH", "SH", CallerContext(name="research_readonly"))
        assert q1.quality.request_id != q2.quality.request_id

    def test_signal_generation_blocks_non_ok(self):
        relay = self._make_relay()
        class _StaleProvider:
            def __init__(self):
                self.contract = _make_contract("stale_provider")
            def fetch_latest_quote(self, symbol, timeout=None, priority=1):
                now = datetime.now(timezone.utc)
                return MarketQuote(
                    symbol=symbol, market="SH", asset_type="equity",
                    price=Decimal("10.0"),
                    quality=DataQualityMetadata(
                        source_provider="stale_provider", source_priority=1,
                        as_of=now, received_at=now, freshness_seconds=300.0,
                        is_stale=True, is_realtime=False, is_demo=False, is_mock=False,
                        is_fallback=False, quality_status=QualityStatus.STALE,
                        quality_reason="data too old", provider_latency_ms=100.0,
                        request_id="req-stale",
                    ),
                )
            def fetch_bars(self, *a, **kw): raise NotImplementedError
            def fetch_latest_quotes(self, *a, **kw): raise NotImplementedError

        self._register(relay, "stale_provider", _StaleProvider())

        with pytest.raises(MarketDataUnavailableError):
            relay.get_latest_quote(
                symbol="000001.SH", market="SH",
                caller_context=CallerContext(name="signal_generation"),
            )

    def test_allow_demo_false_blocks_demo(self):
        relay = self._make_relay()
        class _DemoProvider:
            def __init__(self):
                self.contract = _make_contract("demo_provider")
            def fetch_latest_quote(self, symbol, timeout=None, priority=1):
                q = _make_quote(symbol, "demo_provider", QualityStatus.DEMO)
                q.quality.is_demo = True
                return q
            def fetch_bars(self, *a, **kw): raise NotImplementedError
            def fetch_latest_quotes(self, *a, **kw): raise NotImplementedError

        self._register(relay, "demo_provider", _DemoProvider())

        with pytest.raises(MarketDataUnavailableError):
            relay.get_latest_quote(
                symbol="000001.SH", market="SH",
                caller_context=CallerContext(name="research_readonly", allow_demo=False),
            )

    def test_selected_providers_none_raises(self):
        relay = self._make_relay()
        with pytest.raises(MarketDataUnavailableError):
            relay.get_latest_quote(
                symbol="000001.SH", market="SH",
                caller_context=CallerContext(name="research_readonly"),
            )

    def test_audit_error_code_on_failure(self):
        relay = self._make_relay()
        self._register(relay, "eastmoney", _FakeFailingAdapter("eastmoney"))

        with pytest.raises(MarketDataUnavailableError):
            relay.get_latest_quote(
                symbol="000001.SH", market="SH",
                caller_context=CallerContext(name="research_readonly"),
            )
        call_kwargs = relay._audit.record_fail_closed.call_args[1]
        assert "error_code" in call_kwargs

    def test_cache_hit_returns_stale_for_research(self):
        relay = self._make_relay()
        mock_cache = MagicMock()
        cached_quote = _make_quote("000001.SH", "cache", QualityStatus.STALE)
        cached_entry = MagicMock()
        cached_entry.cache_hit = True
        cached_entry.is_stale = True
        cached_entry.quality_status = QualityStatus.STALE
        cached_entry.data = cached_quote
        mock_cache.get.return_value = cached_entry
        relay._cache = mock_cache

        result = relay.get_latest_quote(
            symbol="000001.SH", market="SH",
            caller_context=CallerContext(name="research_readonly"),
        )
        assert result is not None
        assert result.quality.quality_status == QualityStatus.STALE

    def test_cache_stale_fail_closed_for_signal(self):
        relay = self._make_relay()
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        relay._cache = mock_cache

        with pytest.raises(MarketDataUnavailableError):
            relay.get_latest_quote(
                symbol="000001.SH", market="SH",
                caller_context=CallerContext(name="signal_generation"),
            )
