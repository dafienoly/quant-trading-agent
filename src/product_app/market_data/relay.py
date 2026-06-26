from __future__ import annotations

import uuid
from datetime import datetime
from time import monotonic
from typing import Any

from src.product_app.market_data.audit import AuditRecorder
from src.product_app.market_data.cache import MarketDataCache
from src.product_app.market_data.contracts import (
    FreshnessPolicy,
    MarketBar,
    MarketDataProviderContract,
    MarketQuote,
    MultiSymbolQuoteResult,
    ProviderAttempt,
    ProviderErrorCategory,
    QualityStatus,
)
from src.product_app.market_data.errors import MarketDataUnavailableError
from src.product_app.market_data.health import ProviderHealthAggregator
from src.product_app.market_data.quality import CallerContext, QualityGate


def _new_request_id() -> str:
    return uuid.uuid4().hex[:12]


class _ProviderHolder:
    def __init__(self, contract: MarketDataProviderContract, adapter: Any, priority: int) -> None:
        self.contract = contract
        self.adapter = adapter
        self.priority = priority


_DEFAULT_FRESHNESS = FreshnessPolicy(
    max_age_seconds=30.0, stale_age_seconds=300.0, acceptable_delay_ms=5000,
)


class MarketDataRelay:
    def __init__(
        self,
        registry: Any = None,
        health: ProviderHealthAggregator | None = None,
        audit: AuditRecorder | None = None,
        cache: MarketDataCache | None = None,
        quality_gate: QualityGate | None = None,
    ) -> None:
        self._registry = registry
        self._health = health or ProviderHealthAggregator()
        self._audit = audit or AuditRecorder()
        self._cache = cache or MarketDataCache()
        self._quality_gate = quality_gate or QualityGate()

    def _cache_key_quote(self, market: str, asset_type: str, symbol: str) -> str:
        return f"quote:{market}:{asset_type}:{symbol}"

    def _cache_key_quotes(self, market: str, asset_type: str, symbols: tuple[str, ...]) -> str:
        return f"quotes:{market}:{asset_type}:{','.join(sorted(symbols))}"

    def _cache_key_bars(self, market: str, asset_type: str, symbol: str, granularity: str) -> str:
        return f"bars:{market}:{asset_type}:{symbol}:{granularity}"

    def get_latest_quote(
        self,
        symbol: str,
        market: str,
        caller_context: CallerContext,
        allow_demo: bool = False,
        asset_type: str = "equity",
    ) -> MarketQuote:
        request_id = _new_request_id()
        started = monotonic()

        cache_key = self._cache_key_quote(market, asset_type, symbol)
        cached = self._cache.get(cache_key, _DEFAULT_FRESHNESS, caller_context)
        if cached is not None:
            if isinstance(cached.data, MarketQuote):
                return cached.data

        providers: list[_ProviderHolder] = self._select_providers(market, asset_type, "latest_quote")
        if not providers:
            raise MarketDataUnavailableError(
                request_id=request_id,
                safe_reason=f"No providers registered for market={market} asset_type={asset_type}",
                provider_attempts=[],
                fallback_used=False,
                quality_status=QualityStatus.UNAVAILABLE,
            )

        attempts: list[ProviderAttempt] = []
        for holder in providers:
            started_provider = monotonic()
            try:
                quote = holder.adapter.fetch_latest_quote(
                    symbol=symbol,
                    timeout=holder.contract.timeout_policy.total_timeout_seconds,
                    priority=holder.priority,
                )

                is_fallback = holder.priority > 1
                quote.quality.is_fallback = is_fallback
                quote.quality.source_priority = holder.priority

                if self._quality_gate.blocks(quote.quality, caller_context):
                    attempt = ProviderAttempt(
                        provider_id=holder.contract.provider_id,
                        priority=holder.priority,
                        quality_status=quote.quality.quality_status,
                        latency_ms=(monotonic() - started_provider) * 1000,
                        safe_reason=f"quality gate blocked: {quote.quality.quality_reason}",
                    )
                    attempts.append(attempt)
                    continue

                elapsed = (monotonic() - started) * 1000
                self._audit.record_success(
                    request_id=request_id,
                    caller_context=caller_context.name,
                    endpoint="get_latest_quote",
                    symbols=[symbol],
                    market=market,
                    provider_selected=holder.contract.provider_id,
                    attempts=attempts,
                    quality_status=quote.quality.quality_status,
                    latency_ms=elapsed,
                )
                self._health.record_success(
                    provider_id=holder.contract.provider_id,
                    latency_ms=(monotonic() - started_provider) * 1000,
                    is_fallback=is_fallback,
                )
                self._cache.set(cache_key, quote, holder.contract.provider_id, quote.quality.quality_status)
                return quote

            except MarketDataUnavailableError as exc:
                elapsed_provider = (monotonic() - started_provider) * 1000
                category = ProviderErrorCategory.PROVIDER_UNAVAILABLE
                attempt = ProviderAttempt(
                    provider_id=holder.contract.provider_id,
                    priority=holder.priority,
                    error_category=category,
                    quality_status=exc.quality_status,
                    latency_ms=elapsed_provider,
                    safe_reason=exc.safe_reason,
                )
                attempts.append(attempt)
                self._health.record_failure(
                    provider_id=holder.contract.provider_id,
                    error_category=category,
                    latency_ms=elapsed_provider,
                )
                if not holder.contract.fallback_eligibility.can_fallback:
                    break

            except Exception as exc:
                elapsed_provider = (monotonic() - started_provider) * 1000
                category = ProviderErrorCategory.UNKNOWN_PROVIDER_ERROR
                attempt = ProviderAttempt(
                    provider_id=holder.contract.provider_id,
                    priority=holder.priority,
                    error_category=category,
                    latency_ms=elapsed_provider,
                    safe_reason=str(exc),
                )
                attempts.append(attempt)
                self._health.record_failure(
                    provider_id=holder.contract.provider_id,
                    error_category=category,
                    latency_ms=elapsed_provider,
                )
                if not holder.contract.fallback_eligibility.can_fallback:
                    break

        elapsed_total = (monotonic() - started) * 1000
        fallback_used = any(a.priority > 1 for a in attempts)
        last_status = attempts[-1].quality_status if attempts else QualityStatus.UNAVAILABLE
        self._audit.record_fail_closed(
            request_id=request_id,
            caller_context=caller_context.name,
            endpoint="get_latest_quote",
            symbols=[symbol],
            market=market,
            attempts=attempts,
            error_code="ALL_PROVIDERS_FAILED",
            latency_ms=elapsed_total,
        )
        raise MarketDataUnavailableError(
            request_id=request_id,
            safe_reason="All providers failed to return acceptable quote",
            provider_attempts=attempts,
            fallback_used=fallback_used,
            quality_status=last_status,
        )

    def get_latest_quotes(
        self,
        symbols: list[str],
        market: str,
        caller_context: CallerContext,
        allow_demo: bool = False,
        asset_type: str = "equity",
    ) -> MultiSymbolQuoteResult:
        request_id = _new_request_id()
        started = monotonic()

        cache_key = self._cache_key_quotes(market, asset_type, tuple(symbols))
        cached = self._cache.get(cache_key, _DEFAULT_FRESHNESS, caller_context)
        if cached is not None:
            if isinstance(cached.data, MultiSymbolQuoteResult):
                return cached.data

        providers = self._select_providers(market, asset_type, "latest_quote")
        if not providers:
            raise MarketDataUnavailableError(
                request_id=request_id,
                safe_reason=f"No providers registered for market={market} asset_type={asset_type}",
                provider_attempts=[],
                fallback_used=False,
                quality_status=QualityStatus.UNAVAILABLE,
            )

        attempts: list[ProviderAttempt] = []
        for holder in providers:
            started_provider = monotonic()
            try:
                result = holder.adapter.fetch_latest_quotes(
                    symbols=symbols,
                    timeout=holder.contract.timeout_policy.total_timeout_seconds,
                    priority=holder.priority,
                )

                is_fallback = holder.priority > 1
                for quote in result.results:
                    quote.quality.is_fallback = is_fallback
                    quote.quality.source_priority = holder.priority

                if result.results:
                    sample_quality = result.results[0].quality
                    if self._quality_gate.blocks(sample_quality, caller_context):
                        attempt = ProviderAttempt(
                            provider_id=holder.contract.provider_id,
                            priority=holder.priority,
                            quality_status=sample_quality.quality_status,
                            latency_ms=(monotonic() - started_provider) * 1000,
                            safe_reason=f"quality gate blocked: {sample_quality.quality_reason}",
                        )
                        attempts.append(attempt)
                        continue

                elapsed = (monotonic() - started) * 1000
                self._audit.record_success(
                    request_id=request_id,
                    caller_context=caller_context.name,
                    endpoint="get_latest_quotes",
                    symbols=symbols,
                    market=market,
                    provider_selected=holder.contract.provider_id,
                    attempts=attempts,
                    quality_status=result.request_quality,
                    latency_ms=elapsed,
                )
                self._health.record_success(
                    provider_id=holder.contract.provider_id,
                    latency_ms=(monotonic() - started_provider) * 1000,
                    is_fallback=is_fallback,
                )
                self._cache.set(cache_key, result, holder.contract.provider_id, result.request_quality)
                return result

            except MarketDataUnavailableError as exc:
                elapsed_provider = (monotonic() - started_provider) * 1000
                category = ProviderErrorCategory.PROVIDER_UNAVAILABLE
                attempt = ProviderAttempt(
                    provider_id=holder.contract.provider_id,
                    priority=holder.priority,
                    error_category=category,
                    quality_status=exc.quality_status,
                    latency_ms=elapsed_provider,
                    safe_reason=exc.safe_reason,
                )
                attempts.append(attempt)
                self._health.record_failure(
                    provider_id=holder.contract.provider_id,
                    error_category=category,
                    latency_ms=elapsed_provider,
                )
                if not holder.contract.fallback_eligibility.can_fallback:
                    break

            except Exception as exc:
                elapsed_provider = (monotonic() - started_provider) * 1000
                category = ProviderErrorCategory.UNKNOWN_PROVIDER_ERROR
                attempt = ProviderAttempt(
                    provider_id=holder.contract.provider_id,
                    priority=holder.priority,
                    error_category=category,
                    latency_ms=elapsed_provider,
                    safe_reason=str(exc),
                )
                attempts.append(attempt)
                self._health.record_failure(
                    provider_id=holder.contract.provider_id,
                    error_category=category,
                    latency_ms=elapsed_provider,
                )
                if not holder.contract.fallback_eligibility.can_fallback:
                    break

        elapsed_total = (monotonic() - started) * 1000
        fallback_used = any(a.priority > 1 for a in attempts)
        last_status = attempts[-1].quality_status if attempts else QualityStatus.UNAVAILABLE
        self._audit.record_fail_closed(
            request_id=request_id,
            caller_context=caller_context.name,
            endpoint="get_latest_quotes",
            symbols=symbols,
            market=market,
            attempts=attempts,
            error_code="ALL_PROVIDERS_FAILED",
            latency_ms=elapsed_total,
        )
        raise MarketDataUnavailableError(
            request_id=request_id,
            safe_reason="All providers failed to return acceptable quotes",
            provider_attempts=attempts,
            fallback_used=fallback_used,
            quality_status=last_status,
        )

    def get_bars(
        self,
        symbol: str,
        market: str,
        granularity: str,
        start: datetime,
        end: datetime,
        caller_context: CallerContext,
        asset_type: str = "equity",
    ) -> list[MarketBar]:
        request_id = _new_request_id()
        started = monotonic()

        cache_key = self._cache_key_bars(market, asset_type, symbol, granularity)
        cached = self._cache.get(cache_key, _DEFAULT_FRESHNESS, caller_context)
        if cached is not None:
            if isinstance(cached.data, list):
                return cached.data

        providers = self._select_providers(market, asset_type, "bars")
        if not providers:
            raise MarketDataUnavailableError(
                request_id=request_id,
                safe_reason=f"No providers registered for market={market} bars",
                provider_attempts=[],
                fallback_used=False,
                quality_status=QualityStatus.UNAVAILABLE,
            )

        attempts: list[ProviderAttempt] = []
        for holder in providers:
            started_provider = monotonic()
            try:
                bars = holder.adapter.fetch_bars(
                    symbol=symbol,
                    granularity=granularity,
                    start=start,
                    end=end,
                    timeout=holder.contract.timeout_policy.total_timeout_seconds,
                )

                is_fallback = holder.priority > 1
                for bar in bars:
                    bar.quality.is_fallback = is_fallback
                    bar.quality.source_priority = holder.priority

                if bars:
                    if self._quality_gate.blocks(bars[0].quality, caller_context):
                        attempt = ProviderAttempt(
                            provider_id=holder.contract.provider_id,
                            priority=holder.priority,
                            quality_status=bars[0].quality.quality_status,
                            latency_ms=(monotonic() - started_provider) * 1000,
                            safe_reason=f"quality gate blocked: {bars[0].quality.quality_reason}",
                        )
                        attempts.append(attempt)
                        continue

                elapsed = (monotonic() - started) * 1000
                self._audit.record_success(
                    request_id=request_id,
                    caller_context=caller_context.name,
                    endpoint="get_bars",
                    symbols=[symbol],
                    market=market,
                    provider_selected=holder.contract.provider_id,
                    attempts=attempts,
                    quality_status=bars[0].quality.quality_status if bars else QualityStatus.OK,
                    latency_ms=elapsed,
                )
                self._health.record_success(
                    provider_id=holder.contract.provider_id,
                    latency_ms=(monotonic() - started_provider) * 1000,
                    is_fallback=is_fallback,
                )
                self._cache.set(cache_key, bars, holder.contract.provider_id, bars[0].quality.quality_status if bars else QualityStatus.OK)
                return bars

            except MarketDataUnavailableError as exc:
                elapsed_provider = (monotonic() - started_provider) * 1000
                category = ProviderErrorCategory.PROVIDER_UNAVAILABLE
                attempt = ProviderAttempt(
                    provider_id=holder.contract.provider_id,
                    priority=holder.priority,
                    error_category=category,
                    quality_status=exc.quality_status,
                    latency_ms=elapsed_provider,
                    safe_reason=exc.safe_reason,
                )
                attempts.append(attempt)
                self._health.record_failure(
                    provider_id=holder.contract.provider_id,
                    error_category=category,
                    latency_ms=elapsed_provider,
                )
                if not holder.contract.fallback_eligibility.can_fallback:
                    break

            except Exception as exc:
                elapsed_provider = (monotonic() - started_provider) * 1000
                category = ProviderErrorCategory.UNKNOWN_PROVIDER_ERROR
                attempt = ProviderAttempt(
                    provider_id=holder.contract.provider_id,
                    priority=holder.priority,
                    error_category=category,
                    latency_ms=elapsed_provider,
                    safe_reason=str(exc),
                )
                attempts.append(attempt)
                self._health.record_failure(
                    provider_id=holder.contract.provider_id,
                    error_category=category,
                    latency_ms=elapsed_provider,
                )
                if not holder.contract.fallback_eligibility.can_fallback:
                    break

        elapsed_total = (monotonic() - started) * 1000
        fallback_used = any(a.priority > 1 for a in attempts)
        last_status = attempts[-1].quality_status if attempts else QualityStatus.UNAVAILABLE
        self._audit.record_fail_closed(
            request_id=request_id,
            caller_context=caller_context.name,
            endpoint="get_bars",
            symbols=[symbol],
            market=market,
            attempts=attempts,
            error_code="ALL_PROVIDERS_FAILED",
            latency_ms=elapsed_total,
        )
        raise MarketDataUnavailableError(
            request_id=request_id,
            safe_reason="All providers failed to return acceptable bars",
            provider_attempts=attempts,
            fallback_used=fallback_used,
            quality_status=last_status,
        )

    def _select_providers(
        self,
        market: str,
        asset_type: str,
        endpoint: str,
    ) -> list[_ProviderHolder]:
        if self._registry is None:
            return []
        providers: list[_ProviderHolder] = []
        try:
            selected = self._registry.select(
                market=market,
                asset_type=asset_type,
                endpoint=endpoint,
            )
            for sp in selected:
                if sp.adapter is not None:
                    providers.append(
                        _ProviderHolder(
                            contract=sp.contract,
                            adapter=sp.adapter,
                            priority=sp.priority,
                        )
                    )
        except Exception:
            pass
        return providers
