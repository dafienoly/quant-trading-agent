from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.product_app.market_data.contracts import MarketDataProviderContract


class SelectedProvider(BaseModel):
    contract: MarketDataProviderContract
    priority: int
    fallback_allowed: bool
    risk_sensitive_allowed: bool
    adapter: Any = None


class _RegistryEntry:
    __slots__ = ("contract", "priority", "fallback_allowed", "risk_sensitive_allowed", "adapter")

    def __init__(
        self,
        contract: MarketDataProviderContract,
        priority: int,
        fallback_allowed: bool,
        risk_sensitive_allowed: bool,
        adapter: Any = None,
    ) -> None:
        self.contract = contract
        self.priority = priority
        self.fallback_allowed = fallback_allowed
        self.risk_sensitive_allowed = risk_sensitive_allowed
        self.adapter = adapter


class ProviderRegistry:
    def __init__(self) -> None:
        self._entries: list[_RegistryEntry] = []

    def register(
        self,
        contract: MarketDataProviderContract,
        priority: int,
        fallback_allowed: bool,
        risk_sensitive_allowed: bool,
        adapter: Any = None,
    ) -> None:
        self._entries.append(
            _RegistryEntry(
                contract=contract,
                priority=priority,
                fallback_allowed=fallback_allowed,
                risk_sensitive_allowed=risk_sensitive_allowed,
                adapter=adapter,
            )
        )

    def select(
        self,
        market: str,
        asset_type: str,
        endpoint: str,
        granularity: str | None = None,
    ) -> list[SelectedProvider]:
        matching: list[_RegistryEntry] = []
        for entry in self._entries:
            if market not in entry.contract.market_scope:
                continue
            if asset_type not in entry.contract.supported_asset_types:
                continue
            if endpoint not in entry.contract.supported_endpoints:
                continue
            if granularity is not None and granularity not in entry.contract.supported_granularities:
                continue
            matching.append(entry)

        matching.sort(key=lambda e: e.priority)

        return [
            SelectedProvider(
                contract=entry.contract,
                priority=entry.priority,
                fallback_allowed=entry.fallback_allowed,
                risk_sensitive_allowed=entry.risk_sensitive_allowed,
                adapter=entry.adapter,
            )
            for entry in matching
        ]
