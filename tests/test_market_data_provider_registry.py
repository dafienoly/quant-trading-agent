from __future__ import annotations


from src.product_app.market_data.contracts import (
    AuthRequirement,
    CachePolicy,
    FallbackEligibility,
    FreshnessPolicy,
    MarketDataProviderContract,
    RateLimitPolicy,
    TimeoutPolicy,
)
from src.product_app.market_data.provider_registry import ProviderRegistry, SelectedProvider


def _make_contract(
    provider_id: str = "test_provider",
    provider_name: str = "Test Provider",
    market_scope: list[str] | None = None,
    supported_endpoints: list[str] | None = None,
) -> MarketDataProviderContract:
    return MarketDataProviderContract(
        provider_id=provider_id,
        provider_name=provider_name,
        market_scope=market_scope or ["A_SHARE"],
        supported_asset_types=["equity"],
        supported_granularities=["1d"],
        supported_endpoints=supported_endpoints or ["latest_quote"],
        auth_requirement=AuthRequirement(),
        rate_limit_policy=RateLimitPolicy(),
        timeout_policy=TimeoutPolicy(),
        freshness_policy=FreshnessPolicy(),
        cache_policy=CachePolicy(),
        fallback_eligibility=FallbackEligibility(),
        quality_status_mapping={},
        error_mapping={},
    )


class TestProviderRegistry:
    def test_register_and_select_single(self):
        registry = ProviderRegistry()
        contract = _make_contract(provider_id="eastmoney")
        registry.register(contract, priority=1, fallback_allowed=True, risk_sensitive_allowed=False)

        results = registry.select(market="A_SHARE", asset_type="equity", endpoint="latest_quote")
        assert len(results) == 1
        assert results[0].contract.provider_id == "eastmoney"
        assert results[0].priority == 1
        assert results[0].fallback_allowed is True
        assert results[0].risk_sensitive_allowed is False

    def test_select_returns_sorted_by_priority(self):
        registry = ProviderRegistry()
        registry.register(_make_contract(provider_id="primary"), priority=1, fallback_allowed=True, risk_sensitive_allowed=True)
        registry.register(_make_contract(provider_id="fallback"), priority=2, fallback_allowed=True, risk_sensitive_allowed=False)
        registry.register(_make_contract(provider_id="last_resort"), priority=3, fallback_allowed=True, risk_sensitive_allowed=False)

        results = registry.select(market="A_SHARE", asset_type="equity", endpoint="latest_quote")
        assert len(results) == 3
        assert [r.contract.provider_id for r in results] == ["primary", "fallback", "last_resort"]
        assert [r.priority for r in results] == [1, 2, 3]

    def test_select_filters_by_market(self):
        registry = ProviderRegistry()
        registry.register(_make_contract(provider_id="eastmoney", market_scope=["A_SHARE"]), priority=1, fallback_allowed=True, risk_sensitive_allowed=False)
        registry.register(_make_contract(provider_id="hk_provider", market_scope=["HK"]), priority=1, fallback_allowed=True, risk_sensitive_allowed=False)

        results = registry.select(market="HK", asset_type="equity", endpoint="latest_quote")
        assert len(results) == 1
        assert results[0].contract.provider_id == "hk_provider"

    def test_select_filters_by_asset_type(self):
        registry = ProviderRegistry()
        c1 = _make_contract(provider_id="equity_provider")
        c2 = _make_contract(provider_id="fund_provider")
        c2.supported_asset_types = ["fund"]
        registry.register(c1, priority=1, fallback_allowed=True, risk_sensitive_allowed=False)
        registry.register(c2, priority=1, fallback_allowed=True, risk_sensitive_allowed=False)

        results = registry.select(market="A_SHARE", asset_type="fund", endpoint="latest_quote")
        assert len(results) == 1
        assert results[0].contract.provider_id == "fund_provider"

    def test_select_filters_by_endpoint(self):
        registry = ProviderRegistry()
        c1 = _make_contract(provider_id="quotes_only", supported_endpoints=["latest_quote"])
        c2 = _make_contract(provider_id="bars_only", supported_endpoints=["bars"])
        registry.register(c1, priority=1, fallback_allowed=True, risk_sensitive_allowed=False)
        registry.register(c2, priority=1, fallback_allowed=True, risk_sensitive_allowed=False)

        results = registry.select(market="A_SHARE", asset_type="equity", endpoint="bars")
        assert len(results) == 1
        assert results[0].contract.provider_id == "bars_only"

    def test_select_filters_by_granularity(self):
        registry = ProviderRegistry()
        c1 = _make_contract(provider_id="daily_only")
        c1.supported_granularities = ["1d"]
        c2 = _make_contract(provider_id="intraday_only")
        c2.supported_granularities = ["1m"]
        registry.register(c1, priority=1, fallback_allowed=True, risk_sensitive_allowed=False)
        registry.register(c2, priority=1, fallback_allowed=True, risk_sensitive_allowed=False)

        results = registry.select(market="A_SHARE", asset_type="equity", endpoint="latest_quote", granularity="1m")
        assert len(results) == 1
        assert results[0].contract.provider_id == "intraday_only"

    def test_select_no_match_returns_empty(self):
        registry = ProviderRegistry()
        registry.register(_make_contract(market_scope=["HK"]), priority=1, fallback_allowed=True, risk_sensitive_allowed=False)

        results = registry.select(market="A_SHARE", asset_type="equity", endpoint="latest_quote")
        assert results == []

    def test_select_empty_registry_returns_empty(self):
        registry = ProviderRegistry()
        results = registry.select(market="A_SHARE", asset_type="equity", endpoint="latest_quote")
        assert results == []

    def test_selected_provider_adapter_field_default_none(self):
        registry = ProviderRegistry()
        contract = _make_contract()
        registry.register(contract, priority=1, fallback_allowed=True, risk_sensitive_allowed=False)

        results = registry.select(market="A_SHARE", asset_type="equity", endpoint="latest_quote")
        assert len(results) == 1
        assert results[0].adapter is None

    def test_register_multiple_same_priority(self):
        registry = ProviderRegistry()
        registry.register(_make_contract(provider_id="a"), priority=1, fallback_allowed=True, risk_sensitive_allowed=False)
        registry.register(_make_contract(provider_id="b"), priority=1, fallback_allowed=True, risk_sensitive_allowed=False)

        results = registry.select(market="A_SHARE", asset_type="equity", endpoint="latest_quote")
        assert len(results) == 2

    def test_select_all_fields(self):
        registry = ProviderRegistry()
        registry.register(_make_contract(provider_id="eastmoney"), priority=1, fallback_allowed=True, risk_sensitive_allowed=False)

        results = registry.select(market="A_SHARE", asset_type="equity", endpoint="latest_quote", granularity="1d")
        assert len(results) == 1
        sp = results[0]
        assert sp.contract.provider_id == "eastmoney"
        assert sp.priority == 1
        assert sp.fallback_allowed is True
        assert sp.risk_sensitive_allowed is False
        assert sp.adapter is None

    def test_selected_provider_fields(self):
        sp = SelectedProvider(
            contract=_make_contract(),
            priority=1,
            fallback_allowed=True,
            risk_sensitive_allowed=False,
        )
        assert sp.contract.provider_id == "test_provider"
        assert sp.priority == 1
        assert sp.fallback_allowed is True
        assert sp.risk_sensitive_allowed is False
        assert sp.adapter is None
