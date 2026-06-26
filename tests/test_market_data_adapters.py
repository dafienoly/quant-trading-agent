from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.data_gateway.provider_contracts import DataCapability, ProviderResult
from src.product_app.market_data.contracts import (
    AuthRequirement,
    CachePolicy,
    FallbackEligibility,
    FreshnessPolicy,
    MarketDataProviderContract,
    MarketQuote,
    MultiSymbolQuoteResult,
    QualityStatus,
    RateLimitPolicy,
    TimeoutPolicy,
)
from src.product_app.market_data.errors import MarketDataUnavailableError
from src.product_app.market_data.adapters import (
    AkShareRealtimeAdapter,
    EastmoneyRealtimeAdapter,
    MarketDataAdapter,
)


def _make_contract(
    provider_id: str = "test_adapter",
    provider_name: str = "Test Adapter",
) -> MarketDataProviderContract:
    return MarketDataProviderContract(
        provider_id=provider_id,
        provider_name=provider_name,
        market_scope=["A_SHARE"],
        supported_asset_types=["equity"],
        supported_granularities=["1d"],
        supported_endpoints=["latest_quote"],
        auth_requirement=AuthRequirement(),
        rate_limit_policy=RateLimitPolicy(),
        timeout_policy=TimeoutPolicy(),
        freshness_policy=FreshnessPolicy(),
        cache_policy=CachePolicy(),
        fallback_eligibility=FallbackEligibility(),
        quality_status_mapping={},
        error_mapping={},
    )


def _make_quote_row(symbol: str = "600000.SH") -> dict:
    return {
        "symbol": symbol,
        "name": "Test Stock",
        "market": "SH",
        "datetime": datetime.now(timezone.utc).isoformat(),
        "last_price": 10.50,
        "open": 10.40,
        "high": 10.60,
        "low": 10.30,
        "pre_close": 10.45,
        "pct_change": 0.48,
        "change": 0.05,
        "volume": 1000000,
        "amount": 10500000.0,
        "status": "NORMAL",
        "delay_seconds": 0.0,
        "currency": "CNY",
        "timezone": "Asia/Shanghai",
        "data_source": "eastmoney",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "data_version": "realtime-v1",
        "source_volume_unit": "lot",
    }


def _make_success_result(
    rows: list[dict] | None = None,
    provider: str = "eastmoney",
    elapsed_ms: float = 150.0,
) -> ProviderResult:
    if rows is None:
        rows = [_make_quote_row()]
    return ProviderResult(
        status="ok",
        provider=provider,
        capability=DataCapability.REALTIME_QUOTES,
        data=pd.DataFrame(rows),
        messages=[],
        error="",
        elapsed_ms=elapsed_ms,
        fallback_chain=[f"{provider}: ok"],
    )


def _make_failed_result(provider: str = "eastmoney") -> ProviderResult:
    return ProviderResult(
        status="failed",
        provider=provider,
        capability=DataCapability.REALTIME_QUOTES,
        data=pd.DataFrame(),
        messages=[],
        error="all_providers_failed",
        elapsed_ms=0.0,
        fallback_chain=[f"{provider}: empty_data"],
    )


class TestMarketDataAdapter:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            MarketDataAdapter()


class TestEastmoneyRealtimeAdapter:
    def _make_adapter(self, contract=None, mock_hub=None):
        if contract is None:
            contract = _make_contract(provider_id="eastmoney")
        if mock_hub is None:
            mock_hub = MagicMock()
        return EastmoneyRealtimeAdapter(contract=contract, hub=mock_hub), mock_hub

    def test_fetch_latest_quote_returns_market_quote(self):
        adapter, mock_hub = self._make_adapter()
        mock_hub.fetch_with_fallback.return_value = _make_success_result(provider="eastmoney")

        quote = adapter.fetch_latest_quote("600000.SH")
        assert isinstance(quote, MarketQuote)
        assert quote.symbol == "600000.SH"
        assert quote.price == Decimal("10.50")
        assert quote.open == Decimal("10.40")
        assert quote.high == Decimal("10.60")
        assert quote.low == Decimal("10.30")
        assert quote.previous_close == Decimal("10.45")
        assert quote.volume == 1000000
        assert quote.currency == "CNY"

    def test_fetch_latest_quote_quality_metadata(self):
        adapter, mock_hub = self._make_adapter()
        mock_hub.fetch_with_fallback.return_value = _make_success_result(provider="eastmoney", elapsed_ms=200.0)

        quote = adapter.fetch_latest_quote("600000.SH")
        q = quote.quality
        assert q.source_provider == "eastmoney"
        assert q.source_priority == 1
        assert q.is_fallback is False
        assert q.is_demo is False
        assert q.is_mock is False
        assert q.quality_status == QualityStatus.OK
        assert q.request_id != ""
        assert q.provider_latency_ms == 200.0

    def test_fetch_latest_quote_raises_on_empty_data(self):
        adapter, mock_hub = self._make_adapter()
        mock_hub.fetch_with_fallback.return_value = _make_failed_result()

        with pytest.raises(MarketDataUnavailableError) as exc_info:
            adapter.fetch_latest_quote("600000.SH")
        err = exc_info.value
        assert err.fallback_used is False
        assert len(err.provider_attempts) > 0

    def test_fetch_latest_quote_raises_on_failed_status(self):
        adapter, mock_hub = self._make_adapter()
        mock_hub.fetch_with_fallback.return_value = ProviderResult(
            status="failed",
            provider="eastmoney",
            capability=DataCapability.REALTIME_QUOTES,
            data=pd.DataFrame(),
            messages=[],
            error="all_providers_failed",
            elapsed_ms=0.0,
            fallback_chain=["eastmoney: error"],
        )

        with pytest.raises(MarketDataUnavailableError):
            adapter.fetch_latest_quote("600000.SH")

    def test_fetch_latest_quotes_all_succeed(self):
        adapter, mock_hub = self._make_adapter()

        rows = [_make_quote_row("600000.SH"), _make_quote_row("000001.SZ")]
        rows[1]["last_price"] = 8.20
        rows[1]["symbol"] = "000001.SZ"

        mock_hub.fetch_with_fallback.return_value = _make_success_result(rows=rows, provider="eastmoney")

        result = adapter.fetch_latest_quotes(["600000.SH", "000001.SZ"])
        assert isinstance(result, MultiSymbolQuoteResult)
        assert len(result.results) == 2
        assert result.summary["ok_count"] == 2
        assert result.summary["failed_count"] == 0
        assert result.item_errors == []

    def test_fetch_latest_quotes_empty_data_raises(self):
        adapter, mock_hub = self._make_adapter()
        mock_hub.fetch_with_fallback.return_value = _make_failed_result()

        with pytest.raises(MarketDataUnavailableError):
            adapter.fetch_latest_quotes(["600000.SH"])

    def test_contract_property(self):
        adapter, _ = self._make_adapter()
        assert adapter.contract.provider_id == "eastmoney"

    def test_request_id_unique_per_call(self):
        adapter, mock_hub = self._make_adapter()
        mock_hub.fetch_with_fallback.return_value = _make_success_result()

        q1 = adapter.fetch_latest_quote("600000.SH")
        q2 = adapter.fetch_latest_quote("000001.SZ")
        assert q1.quality.request_id != q2.quality.request_id


class TestAkShareRealtimeAdapter:
    def _make_adapter(self, contract=None, mock_hub=None):
        if contract is None:
            contract = _make_contract(provider_id="akshare_realtime")
        if mock_hub is None:
            mock_hub = MagicMock()
        return AkShareRealtimeAdapter(contract=contract, hub=mock_hub), mock_hub

    def test_fetch_latest_quote_returns_market_quote(self):
        adapter, mock_hub = self._make_adapter()
        mock_hub.fetch_with_fallback.return_value = _make_success_result(provider="akshare_realtime")

        quote = adapter.fetch_latest_quote("600000.SH")
        assert isinstance(quote, MarketQuote)
        assert quote.symbol == "600000.SH"
        assert quote.price == Decimal("10.50")

    def test_fetch_latest_quote_quality_fallback_flag(self):
        adapter, mock_hub = self._make_adapter()
        mock_hub.fetch_with_fallback.return_value = _make_success_result(provider="akshare_realtime")

        quote = adapter.fetch_latest_quote("600000.SH")
        assert quote.quality.is_fallback is False
        assert quote.quality.quality_status == QualityStatus.OK
        assert quote.quality.source_provider == "akshare_realtime"

    def test_fetch_latest_quote_raises_on_empty(self):
        adapter, mock_hub = self._make_adapter()
        mock_hub.fetch_with_fallback.return_value = _make_failed_result(provider="akshare_realtime")

        with pytest.raises(MarketDataUnavailableError):
            adapter.fetch_latest_quote("600000.SH")

    def test_fetch_latest_quotes_all_succeed(self):
        adapter, mock_hub = self._make_adapter()

        rows = [_make_quote_row("600000.SH"), _make_quote_row("000001.SZ")]
        rows[1]["symbol"] = "000001.SZ"

        mock_hub.fetch_with_fallback.return_value = _make_success_result(rows=rows, provider="akshare_realtime")

        result = adapter.fetch_latest_quotes(["600000.SH", "000001.SZ"])
        assert len(result.results) == 2
        assert result.summary["ok_count"] == 2

    def test_fetch_bars_not_implemented(self):
        adapter, _ = self._make_adapter()
        with pytest.raises(NotImplementedError):
            adapter.fetch_bars("600000.SH", "1d", datetime.now(timezone.utc), datetime.now(timezone.utc))


class TestDataQualityMetadataPopulation:
    def _make_adapter(self, contract=None, mock_hub=None):
        if contract is None:
            contract = _make_contract(provider_id="eastmoney")
        if mock_hub is None:
            mock_hub = MagicMock()
        return EastmoneyRealtimeAdapter(contract=contract, hub=mock_hub), mock_hub

    def test_fallback_priority_sets_is_fallback(self):
        adapter, mock_hub = self._make_adapter()
        mock_hub.fetch_with_fallback.return_value = _make_success_result()

        quote = adapter.fetch_latest_quote("600000.SH", priority=2)
        assert quote.quality.is_fallback is True
        assert quote.quality.source_priority == 2

    def test_quality_reason_on_success(self):
        adapter, mock_hub = self._make_adapter()
        mock_hub.fetch_with_fallback.return_value = _make_success_result()

        quote = adapter.fetch_latest_quote("600000.SH")
        assert isinstance(quote.quality.quality_reason, str)
