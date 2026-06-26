from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any


from src.data_gateway.eastmoney_provider import EastmoneyProvider
from src.data_gateway.live_data_mapper import REALTIME_REQUIRED_FIELDS
from src.data_gateway.provider_contracts import DataCapability
from src.data_gateway.provider_hub import DataProviderHub
from src.data_gateway.realtime_provider import AkShareRealtimeProvider
from src.product_app.market_data.contracts import (
    DataQualityMetadata,
    MarketBar,
    MarketDataProviderContract,
    MarketQuote,
    MultiSymbolQuoteResult,
    ProviderAttempt,
    ProviderErrorCategory,
    QualityStatus,
)
from src.product_app.market_data.errors import MarketDataUnavailableError


def _new_request_id() -> str:
    return uuid.uuid4().hex[:12]


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (ValueError, ArithmeticError):
        return None


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _build_quality(
    provider_id: str,
    priority: int,
    is_fallback: bool,
    request_id: str,
    latency_ms: float | None = None,
    quality_status: QualityStatus = QualityStatus.OK,
    quality_reason: str = "",
) -> DataQualityMetadata:
    now = datetime.now(timezone.utc)
    return DataQualityMetadata(
        source_provider=provider_id,
        source_priority=priority,
        as_of=now,
        received_at=now,
        freshness_seconds=0.0,
        is_stale=False,
        is_realtime=True,
        is_demo=False,
        is_mock=False,
        is_fallback=is_fallback,
        quality_status=quality_status,
        quality_reason=quality_reason,
        provider_latency_ms=latency_ms,
        request_id=request_id,
    )


def _df_row_to_quote(row: dict[str, Any], provider_id: str, priority: int, request_id: str, elapsed_ms: float) -> MarketQuote:
    symbol = str(row.get("symbol", ""))
    market = str(row.get("market", ""))
    if not market:
        if symbol.endswith(".HK"):
            market = "HK"
        elif symbol.endswith((".SH", ".SSE")):
            market = "SH"
        elif symbol.endswith((".SZ", ".SZSE")):
            market = "SZ"
        else:
            market = "A_SHARE"

    return MarketQuote(
        symbol=symbol,
        market=market,
        asset_type="equity",
        price=_to_decimal(row.get("last_price")),
        open=_to_decimal(row.get("open")),
        high=_to_decimal(row.get("high")),
        low=_to_decimal(row.get("low")),
        previous_close=_to_decimal(row.get("pre_close")),
        volume=_to_int(row.get("volume")),
        currency=str(row.get("currency", "CNY")),
        quality=_build_quality(
            provider_id=provider_id,
            priority=priority,
            is_fallback=(priority != 1),
            request_id=request_id,
            latency_ms=elapsed_ms,
        ),
    )


class MarketDataAdapter(ABC):
    @property
    @abstractmethod
    def contract(self) -> MarketDataProviderContract:
        ...

    @abstractmethod
    def fetch_latest_quote(
        self,
        symbol: str,
        timeout: float | None = None,
        priority: int = 1,
    ) -> MarketQuote:
        ...

    @abstractmethod
    def fetch_latest_quotes(
        self,
        symbols: list[str],
        timeout: float | None = None,
        priority: int = 1,
    ) -> MultiSymbolQuoteResult:
        ...

    @abstractmethod
    def fetch_bars(
        self,
        symbol: str,
        granularity: str,
        start: datetime,
        end: datetime,
        timeout: float | None = None,
    ) -> list[MarketBar]:
        ...


class _BaseRealtimeAdapter(MarketDataAdapter):
    def __init__(
        self,
        contract: MarketDataProviderContract,
        hub: DataProviderHub,
    ) -> None:
        self._contract = contract
        self._hub = hub

    @property
    def contract(self) -> MarketDataProviderContract:
        return self._contract

    def fetch_latest_quote(
        self,
        symbol: str,
        timeout: float | None = None,
        priority: int = 1,
    ) -> MarketQuote:
        request_id = _new_request_id()
        result = self._hub.fetch_with_fallback(
            DataCapability.REALTIME_QUOTES,
            "get_realtime_quotes",
            [symbol],
            required_fields=REALTIME_REQUIRED_FIELDS,
        )
        if result.status == "failed" or result.data is None or result.data.empty:
            attempt = ProviderAttempt(
                provider_id=self._contract.provider_id,
                priority=priority,
                error_category=ProviderErrorCategory.EMPTY_RESPONSE,
                quality_status=QualityStatus.UNAVAILABLE,
                safe_reason=result.error or "empty data",
                latency_ms=result.elapsed_ms,
            )
            raise MarketDataUnavailableError(
                request_id=request_id,
                safe_reason=f"{self._contract.provider_id}: no data available",
                provider_attempts=[attempt],
                fallback_used=False,
                quality_status=QualityStatus.UNAVAILABLE,
            )
        row = result.data.iloc[0].to_dict()
        return _df_row_to_quote(
            row=row,
            provider_id=result.provider or self._contract.provider_id,
            priority=priority,
            request_id=request_id,
            elapsed_ms=result.elapsed_ms,
        )

    def fetch_latest_quotes(
        self,
        symbols: list[str],
        timeout: float | None = None,
        priority: int = 1,
    ) -> MultiSymbolQuoteResult:
        request_id = _new_request_id()
        result = self._hub.fetch_with_fallback(
            DataCapability.REALTIME_QUOTES,
            "get_realtime_quotes",
            symbols,
            required_fields=REALTIME_REQUIRED_FIELDS,
        )
        if result.status == "failed" or result.data is None or result.data.empty:
            attempt = ProviderAttempt(
                provider_id=self._contract.provider_id,
                priority=priority,
                error_category=ProviderErrorCategory.EMPTY_RESPONSE,
                quality_status=QualityStatus.UNAVAILABLE,
                safe_reason=result.error or "empty data",
                latency_ms=result.elapsed_ms,
            )
            raise MarketDataUnavailableError(
                request_id=request_id,
                safe_reason=f"{self._contract.provider_id}: no quotes available",
                provider_attempts=[attempt],
                fallback_used=False,
                quality_status=QualityStatus.UNAVAILABLE,
            )
        quotes: list[MarketQuote] = []
        for _, row in result.data.iterrows():
            row_dict = row.to_dict()
            quotes.append(
                _df_row_to_quote(
                    row=row_dict,
                    provider_id=result.provider or self._contract.provider_id,
                    priority=priority,
                    request_id=request_id,
                    elapsed_ms=result.elapsed_ms,
                )
            )
        return MultiSymbolQuoteResult(
            results=quotes,
            item_errors=[],
            summary={
                "total": len(quotes),
                "ok_count": len(quotes),
                "failed_count": 0,
                "degraded_count": 0,
                "fallback_count": 0,
            },
            request_quality=QualityStatus.OK,
            request_id=request_id,
        )

    def fetch_bars(
        self,
        symbol: str,
        granularity: str,
        start: datetime,
        end: datetime,
        timeout: float | None = None,
    ) -> list[MarketBar]:
        raise NotImplementedError("fetch_bars not implemented in this adapter")


class EastmoneyRealtimeAdapter(_BaseRealtimeAdapter):
    def __init__(
        self,
        contract: MarketDataProviderContract,
        provider: EastmoneyProvider | None = None,
        hub: DataProviderHub | None = None,
    ) -> None:
        if hub is not None:
            _hub = hub
        else:
            _provider = provider or EastmoneyProvider()
            _hub = DataProviderHub(providers=[_provider])
        super().__init__(contract=contract, hub=_hub)


class AkShareRealtimeAdapter(_BaseRealtimeAdapter):
    def __init__(
        self,
        contract: MarketDataProviderContract,
        provider: AkShareRealtimeProvider | None = None,
        hub: DataProviderHub | None = None,
    ) -> None:
        if hub is not None:
            _hub = hub
        else:
            _provider = provider or AkShareRealtimeProvider()
            _hub = DataProviderHub(providers=[_provider])
        super().__init__(contract=contract, hub=_hub)
