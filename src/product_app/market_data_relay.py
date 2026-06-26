"""统一市场数据 Relay。

所有新产品能力应优先通过本服务读取市场数据。旧的 LiveDataService 继续作为
个股实时和个股日线真实数据入口，Relay 负责统一 envelope、质量门禁和缓存策略。
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from time import monotonic
from typing import Any, Callable
from uuid import uuid4

import pandas as pd

from src.data_gateway.market_relay_provider import (
    AkShareMarketRelayProvider,
    LocalCacheProvider,
)
from src.data_gateway.provider_contracts import (
    Bar,
    BarSeries,
    DataCapability,
    DataQualityStatus,
    DataSourceHealth,
    DataUsage,
    MarketDataEnvelope,
    MarketDataType,
    ProviderHealth,
    ProviderStatus,
    QuoteSnapshot,
)
from src.data_gateway.provider_hub import DataProviderHub
from src.data_gateway.realtime_provider import normalize_quote_symbol
from src.product_app.live_data_service import LiveDataService, get_live_data_service


SPOT_REQUIRED_FIELDS = [
    "symbol",
    "last_price",
    "datetime",
    "data_source",
]
BAR_REQUIRED_FIELDS = [
    "symbol",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "volume",
]
CALENDAR_REQUIRED_FIELDS = ["trade_date"]


def _as_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_number(value: Any) -> float | int | None:
    number = _as_float(value)
    if number is None:
        return None
    return int(number) if number.is_integer() else number


def _parse_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class MarketDataRelayService:
    """市场数据统一契约、用途治理和缓存 fallback。"""

    REALTIME_FRESHNESS_SECONDS = 120.0
    CACHE_FRESHNESS_SECONDS = 900.0

    def __init__(
        self,
        *,
        live_data_service: LiveDataService | None = None,
        relay_providers: list[Any] | None = None,
        cache_provider: LocalCacheProvider | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._live_data_service = live_data_service or get_live_data_service()
        providers = relay_providers or [AkShareMarketRelayProvider()]
        self._relay_hub = DataProviderHub(providers)
        self._cache = cache_provider or LocalCacheProvider()
        self._now = now or (lambda: datetime.now(timezone.utc))

    def get_sources(self) -> MarketDataEnvelope:
        registry: dict[str, dict[str, Any]] = {}
        for provider in self._relay_hub._providers:
            entry = registry.setdefault(
                provider.name,
                {
                    "provider_name": provider.name,
                    "test_only": provider.name == "manual_fixture",
                    "capabilities": [],
                },
            )
            entry["capabilities"].extend(
                capability.value
                for capability, method in (
                    (DataCapability.INDEX_QUOTES, "get_index_realtime_quotes"),
                    (DataCapability.INDEX_BARS, "get_index_daily_bars"),
                    (DataCapability.ETF_QUOTES, "get_etf_realtime_quotes"),
                    (DataCapability.ETF_BARS, "get_etf_daily_bars"),
                    (DataCapability.SECTOR_QUOTES, "get_sector_quotes"),
                    (DataCapability.TRADE_CALENDAR, "get_trade_dates"),
                )
                if hasattr(provider, method)
            )
        for name in self._live_data_service._provider_order:
            entry = registry.setdefault(
                name,
                {
                    "provider_name": name,
                    "test_only": False,
                    "capabilities": [],
                },
            )
            entry["capabilities"].extend(
                [
                    DataCapability.REALTIME_QUOTES.value,
                    DataCapability.DAILY_BARS.value,
                ]
            )
        providers = []
        for entry in registry.values():
            entry["capabilities"] = sorted(set(entry["capabilities"]))
            providers.append(entry)
        return self._static_envelope(MarketDataType.SOURCE_LIST, providers)

    def get_health(self) -> MarketDataEnvelope:
        items: list[dict[str, Any]] = []
        capability_methods = (
            DataCapability.INDEX_QUOTES,
            DataCapability.INDEX_BARS,
            DataCapability.ETF_QUOTES,
            DataCapability.ETF_BARS,
            DataCapability.SECTOR_QUOTES,
            DataCapability.TRADE_CALENDAR,
        )
        for capability in capability_methods:
            for health in self._relay_hub.get_health(capability):
                items.append(self._health_to_contract(health).to_dict())
        for capability, hub in (
            (DataCapability.REALTIME_QUOTES, self._live_data_service._realtime_hub),
            (DataCapability.DAILY_BARS, self._live_data_service._daily_bars_hub),
        ):
            for health in hub.get_health(capability):
                items.append(self._health_to_contract(health).to_dict())
        return self._static_envelope(MarketDataType.SOURCE_HEALTH, items)

    def get_stock_quotes(
        self,
        symbols: list[str],
        *,
        usage: DataUsage = DataUsage.DISPLAY,
    ) -> MarketDataEnvelope:
        normalized = self._normalize_symbols(symbols)
        started = monotonic()
        try:
            result = self._live_data_service.get_realtime_quotes(
                normalized,
                allow_demo=False,
            )
        except Exception as exc:
            return self._complete_or_fallback(
                data_type=MarketDataType.STOCK_QUOTE,
                identity=",".join(normalized),
                usage=usage,
                provider_name="",
                payload=[],
                latency_ms=(monotonic() - started) * 1000.0,
                live_ok=False,
                warnings=[],
                errors=[f"live_data_service_error:{type(exc).__name__}"],
            )
        latency_ms = (monotonic() - started) * 1000.0
        payload = self._quote_payload(result.get("quotes", []))
        return self._complete_or_fallback(
            data_type=MarketDataType.STOCK_QUOTE,
            identity=",".join(normalized),
            usage=usage,
            provider_name=str(result.get("chosen_provider") or ""),
            payload=payload,
            latency_ms=latency_ms,
            live_ok=result.get("data_status") != "FAILED" and bool(payload),
            warnings=list(result.get("fallback_chain") or []),
            errors=self._live_errors(result),
        )

    def get_index_quotes(
        self,
        symbols: list[str],
        *,
        usage: DataUsage = DataUsage.DISPLAY,
    ) -> MarketDataEnvelope:
        return self._fetch_special_quotes(
            symbols,
            usage=usage,
            capability=DataCapability.INDEX_QUOTES,
            method="get_index_realtime_quotes",
            data_type=MarketDataType.INDEX_QUOTE,
        )

    def get_etf_quotes(
        self,
        symbols: list[str],
        *,
        usage: DataUsage = DataUsage.DISPLAY,
    ) -> MarketDataEnvelope:
        return self._fetch_special_quotes(
            symbols,
            usage=usage,
            capability=DataCapability.ETF_QUOTES,
            method="get_etf_realtime_quotes",
            data_type=MarketDataType.ETF_QUOTE,
        )

    def get_sector_quotes(
        self,
        symbols: list[str],
        *,
        usage: DataUsage = DataUsage.DISPLAY,
    ) -> MarketDataEnvelope:
        return self._fetch_special_quotes(
            symbols,
            usage=usage,
            capability=DataCapability.SECTOR_QUOTES,
            method="get_sector_quotes",
            data_type=MarketDataType.SECTOR_QUOTE,
            normalize=False,
        )

    def get_bars(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        *,
        frequency: str = "daily",
        adjust: str = "qfq",
        asset_type: str = "stock",
        usage: DataUsage = DataUsage.ANALYSIS,
    ) -> MarketDataEnvelope:
        if frequency != "daily":
            return self._unavailable(
                MarketDataType.STOCK_BARS,
                ["V16.2 仅支持 daily frequency"],
            )
        normalized = normalize_quote_symbol(symbol)
        if asset_type == "stock":
            started = monotonic()
            try:
                live = self._live_data_service.get_daily_bars(
                    [normalized],
                    start_date,
                    end_date,
                    adjust=adjust,
                )
            except Exception as exc:
                return self._complete_or_fallback(
                    data_type=MarketDataType.STOCK_BARS,
                    identity=f"{normalized}:{start_date}:{end_date}:{adjust}",
                    usage=usage,
                    provider_name="",
                    payload=[],
                    latency_ms=(monotonic() - started) * 1000.0,
                    live_ok=False,
                    warnings=[],
                    errors=[f"live_data_service_error:{type(exc).__name__}"],
                    realtime=False,
                )
            latency_ms = (monotonic() - started) * 1000.0
            rows = list(live.get("daily_bars") or [])
            payload = self._bar_payload(normalized, frequency, adjust, rows)
            return self._complete_or_fallback(
                data_type=MarketDataType.STOCK_BARS,
                identity=f"{normalized}:{start_date}:{end_date}:{adjust}",
                usage=usage,
                provider_name=str(live.get("chosen_provider") or ""),
                payload=payload,
                latency_ms=latency_ms,
                live_ok=live.get("data_status") != "FAILED" and bool(rows),
                warnings=list(live.get("fallback_chain") or []),
                errors=self._live_errors(live),
                realtime=False,
            )

        mapping = {
            "index": (
                DataCapability.INDEX_BARS,
                "get_index_daily_bars",
                MarketDataType.INDEX_BARS,
            ),
            "etf": (
                DataCapability.ETF_BARS,
                "get_etf_daily_bars",
                MarketDataType.ETF_BARS,
            ),
        }
        if asset_type not in mapping:
            return self._unavailable(
                MarketDataType.STOCK_BARS,
                [f"不支持的 asset_type: {asset_type}"],
            )
        capability, method, data_type = mapping[asset_type]
        result = self._relay_hub.fetch_with_fallback(
            capability,
            method,
            normalized,
            start_date,
            end_date,
            adjust,
            required_fields=BAR_REQUIRED_FIELDS,
        )
        rows = self._records(result.data)
        return self._complete_or_fallback(
            data_type=data_type,
            identity=f"{normalized}:{start_date}:{end_date}:{adjust}",
            usage=usage,
            provider_name=result.provider,
            payload=self._bar_payload(normalized, frequency, adjust, rows),
            latency_ms=result.elapsed_ms,
            live_ok=result.status == "ok" and bool(rows),
            warnings=result.fallback_chain,
            errors=[result.error] if result.error else [],
            realtime=False,
        )

    def get_calendar(
        self,
        start_date: str,
        end_date: str,
        *,
        usage: DataUsage = DataUsage.ANALYSIS,
    ) -> MarketDataEnvelope:
        result = self._relay_hub.fetch_with_fallback(
            DataCapability.TRADE_CALENDAR,
            "get_trade_dates",
            start_date,
            end_date,
            required_fields=CALENDAR_REQUIRED_FIELDS,
        )
        rows = self._records(result.data)
        payload = [str(row["trade_date"]) for row in rows if row.get("trade_date")]
        return self._complete_or_fallback(
            data_type=MarketDataType.TRADE_CALENDAR,
            identity=f"{start_date}:{end_date}",
            usage=usage,
            provider_name=result.provider,
            payload=payload,
            latency_ms=result.elapsed_ms,
            live_ok=result.status == "ok" and bool(payload),
            warnings=result.fallback_chain,
            errors=[result.error] if result.error else [],
            realtime=False,
        )

    def _fetch_special_quotes(
        self,
        symbols: list[str],
        *,
        usage: DataUsage,
        capability: DataCapability,
        method: str,
        data_type: MarketDataType,
        normalize: bool = True,
    ) -> MarketDataEnvelope:
        normalized = (
            self._normalize_symbols(symbols)
            if normalize
            else [str(symbol).strip() for symbol in symbols if str(symbol).strip()]
        )
        result = self._relay_hub.fetch_with_fallback(
            capability,
            method,
            normalized,
            required_fields=SPOT_REQUIRED_FIELDS,
        )
        payload = self._quote_payload(self._records(result.data))
        return self._complete_or_fallback(
            data_type=data_type,
            identity=",".join(normalized),
            usage=usage,
            provider_name=result.provider,
            payload=payload,
            latency_ms=result.elapsed_ms,
            live_ok=result.status == "ok" and bool(payload),
            warnings=result.fallback_chain,
            errors=[result.error] if result.error else [],
        )

    def _complete_or_fallback(
        self,
        *,
        data_type: MarketDataType,
        identity: str,
        usage: DataUsage,
        provider_name: str,
        payload: Any,
        latency_ms: float,
        live_ok: bool,
        warnings: list[str],
        errors: list[str],
        realtime: bool = True,
    ) -> MarketDataEnvelope:
        cache_key = self._cache.make_key(data_type.value, identity)
        quality = self._quality_for_payload(payload, realtime=realtime)
        is_mock = provider_name == "manual_fixture"
        if is_mock and live_ok:
            quality = DataQualityStatus.MOCK
        stale = quality == DataQualityStatus.STALE
        if live_ok and quality in {
            DataQualityStatus.COMPLETE,
            DataQualityStatus.STALE,
            DataQualityStatus.INCOMPLETE,
            DataQualityStatus.MOCK,
        }:
            envelope = MarketDataEnvelope(
                request_id=str(uuid4()),
                source="fixture" if is_mock else "live",
                provider_name=provider_name,
                data_type=data_type,
                fetched_at=self._now().isoformat(),
                latency_ms=latency_ms,
                cached=False,
                stale=stale,
                mock=is_mock,
                quality_status=quality,
                blocking_for_signal=quality != DataQualityStatus.COMPLETE,
                payload=payload,
                warnings=warnings,
                errors=errors,
            )
            if quality == DataQualityStatus.COMPLETE and not is_mock:
                try:
                    self._cache.write(cache_key, envelope.to_dict())
                except OSError:
                    return replace(
                        envelope,
                        warnings=[
                            *envelope.warnings,
                            "本地缓存写入失败，实时数据仍可使用",
                        ],
                    )
            return envelope

        if usage != DataUsage.EXECUTION:
            try:
                cached = self._cache.read(cache_key)
            except OSError:
                cached = None
                errors = [*errors, "local_cache_read_failed"]
            if cached:
                return self._cached_envelope(
                    cached,
                    data_type=data_type,
                    warnings=[*warnings, "实时数据不可用，已使用本地缓存"],
                    errors=errors,
                )
        return self._unavailable(
            data_type,
            errors or ["所有实时数据源均不可用"],
            warnings=warnings,
            provider_name=provider_name,
            latency_ms=latency_ms,
        )

    def _quality_for_payload(
        self,
        payload: Any,
        *,
        realtime: bool,
    ) -> DataQualityStatus:
        if not payload:
            return DataQualityStatus.UNAVAILABLE
        if isinstance(payload, dict) and "bars" in payload:
            bars = payload.get("bars") or []
            if not bars:
                return DataQualityStatus.UNAVAILABLE
            required = ("trade_date", "open", "high", "low", "close", "volume")
            return (
                DataQualityStatus.COMPLETE
                if all(all(bar.get(key) is not None for key in required) for bar in bars)
                else DataQualityStatus.INCOMPLETE
            )
        if not isinstance(payload, list):
            return DataQualityStatus.INCOMPLETE
        if payload and isinstance(payload[0], str):
            return DataQualityStatus.COMPLETE
        required = ("symbol", "price", "timestamp")
        if not all(all(row.get(key) is not None for key in required) for row in payload):
            return DataQualityStatus.INCOMPLETE
        if realtime:
            timestamps = [
                parsed
                for parsed in (_parse_timestamp(str(row.get("timestamp") or "")) for row in payload)
                if parsed is not None
            ]
            if not timestamps:
                return DataQualityStatus.INCOMPLETE
            age = (self._now().astimezone(timezone.utc) - max(timestamps)).total_seconds()
            if age > self.REALTIME_FRESHNESS_SECONDS:
                return DataQualityStatus.STALE
        return DataQualityStatus.COMPLETE

    def _cached_envelope(
        self,
        cached: dict[str, Any],
        *,
        data_type: MarketDataType,
        warnings: list[str],
        errors: list[str],
    ) -> MarketDataEnvelope:
        fetched_at = str(cached.get("fetched_at") or "")
        parsed = _parse_timestamp(fetched_at)
        stale = (
            parsed is None
            or (self._now().astimezone(timezone.utc) - parsed).total_seconds()
            > self.CACHE_FRESHNESS_SECONDS
        )
        return MarketDataEnvelope(
            request_id=str(uuid4()),
            source="cache",
            provider_name="local_cache",
            data_type=data_type,
            fetched_at=fetched_at or self._now().isoformat(),
            latency_ms=0.0,
            cached=True,
            stale=stale,
            mock=bool(cached.get("mock")),
            quality_status=(
                DataQualityStatus.MOCK
                if cached.get("mock")
                else DataQualityStatus.STALE
                if stale
                else DataQualityStatus.COMPLETE
            ),
            blocking_for_signal=True,
            payload=cached.get("payload"),
            warnings=warnings,
            errors=errors,
        )

    def _unavailable(
        self,
        data_type: MarketDataType,
        errors: list[str],
        *,
        warnings: list[str] | None = None,
        provider_name: str = "",
        latency_ms: float = 0.0,
    ) -> MarketDataEnvelope:
        return MarketDataEnvelope(
            request_id=str(uuid4()),
            source="unavailable",
            provider_name=provider_name,
            data_type=data_type,
            fetched_at=self._now().isoformat(),
            latency_ms=latency_ms,
            cached=False,
            stale=False,
            mock=False,
            quality_status=DataQualityStatus.UNAVAILABLE,
            blocking_for_signal=True,
            payload=[],
            warnings=warnings or [],
            errors=errors,
        )

    def _static_envelope(
        self,
        data_type: MarketDataType,
        payload: Any,
    ) -> MarketDataEnvelope:
        return MarketDataEnvelope(
            request_id=str(uuid4()),
            source="registry",
            provider_name="market_data_relay",
            data_type=data_type,
            fetched_at=self._now().isoformat(),
            latency_ms=0.0,
            cached=False,
            stale=False,
            mock=False,
            quality_status=DataQualityStatus.COMPLETE,
            blocking_for_signal=False,
            payload=payload,
        )

    @staticmethod
    def _normalize_symbols(symbols: list[str]) -> list[str]:
        return [
            normalize_quote_symbol(symbol)
            for symbol in symbols
            if str(symbol).strip()
        ]

    @staticmethod
    def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
        if frame is None or frame.empty:
            return []
        return frame.where(pd.notna(frame), None).to_dict(orient="records")

    @staticmethod
    def _quote_payload(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        payload = []
        for row in rows:
            timestamp = str(
                row.get("datetime")
                or row.get("updated_at")
                or row.get("timestamp")
                or ""
            )
            trading_day = str(
                row.get("trading_day")
                or timestamp[:10].replace("-", "")
                or ""
            )
            payload.append(
                QuoteSnapshot(
                    symbol=str(row.get("symbol") or ""),
                    name=str(row.get("name") or ""),
                    price=_as_float(row.get("last_price", row.get("price"))),
                    prev_close=_as_float(row.get("pre_close", row.get("prev_close"))),
                    open=_as_float(row.get("open")),
                    high=_as_float(row.get("high")),
                    low=_as_float(row.get("low")),
                    volume=_as_number(row.get("volume")),
                    amount=_as_float(row.get("amount")),
                    change=_as_float(row.get("change")),
                    pct_change=_as_float(row.get("pct_change")),
                    timestamp=timestamp,
                    trading_day=trading_day,
                    currency=str(row.get("currency") or "CNY"),
                    timezone=str(row.get("timezone") or "Asia/Shanghai"),
                    source_volume_unit=str(
                        row.get("source_volume_unit") or "share"
                    ),
                    status=str(row.get("status") or "NORMAL"),
                ).to_dict()
            )
        return payload

    @staticmethod
    def _bar_payload(
        symbol: str,
        frequency: str,
        adjust: str,
        rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        bars = [
            Bar(
                trade_date=str(row.get("trade_date") or ""),
                open=_as_float(row.get("open")),
                high=_as_float(row.get("high")),
                low=_as_float(row.get("low")),
                close=_as_float(row.get("close")),
                volume=_as_number(row.get("volume")),
                amount=_as_float(row.get("amount")),
                raw_close=_as_float(row.get("raw_close", row.get("close"))),
                adjusted_close=_as_float(
                    row.get("adjusted_close", row.get("close"))
                ),
                is_suspended=bool(row.get("is_suspended", False)),
            )
            for row in rows
        ]
        return BarSeries(
            symbol=symbol,
            frequency=frequency,
            adjust=adjust,
            bars=bars,
        ).to_dict()

    @staticmethod
    def _live_errors(result: dict[str, Any]) -> list[str]:
        if result.get("data_status") != "FAILED":
            return []
        chain = list(result.get("fallback_chain") or [])
        return chain or ["live_data_failed"]

    @staticmethod
    def _health_to_contract(health: ProviderHealth) -> DataSourceHealth:
        status_map = {
            "OK": ProviderStatus.OK,
            "ERROR": ProviderStatus.ERROR,
            "CIRCUIT_OPEN": ProviderStatus.CIRCUIT_OPEN,
            "UNKNOWN": ProviderStatus.UNKNOWN,
        }
        return DataSourceHealth(
            provider_name=health.provider,
            status=status_map.get(health.status, ProviderStatus.UNKNOWN),
            capabilities=[health.capability.value],
            last_success_at=health.last_success_at,
            last_error_at=health.last_error_at,
            latency_ms=health.latency_ms,
            rate_limit_status=health.rate_limit_status,
            error_summary=health.error,
        )


_RELAY_SERVICE: MarketDataRelayService | None = None


def get_market_data_relay_service() -> MarketDataRelayService:
    global _RELAY_SERVICE
    if _RELAY_SERVICE is None:
        _RELAY_SERVICE = MarketDataRelayService()
    return _RELAY_SERVICE
