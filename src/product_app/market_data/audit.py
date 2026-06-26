from __future__ import annotations

from datetime import datetime, timezone
from pydantic import BaseModel

from src.product_app.market_data.contracts import ProviderAttempt, QualityStatus
from src.product_app.market_data.errors import redact_secret


class MarketDataAuditEvent(BaseModel):
    request_id: str
    caller_context: str
    endpoint: str
    symbols: list[str]
    market: str | None = None
    provider_selected: str | None = None
    provider_attempts: list[ProviderAttempt] = []
    fallback_used: bool = False
    quality_status: QualityStatus | None = None
    error_code: str | None = None
    created_at: datetime
    latency_ms: float = 0.0


class AuditRecorder:
    def __init__(self) -> None:
        self._events: list[MarketDataAuditEvent] = []

    def record_success(
        self,
        request_id: str,
        caller_context: str,
        endpoint: str,
        symbols: list[str],
        market: str | None,
        provider_selected: str | None,
        attempts: list[ProviderAttempt],
        quality_status: QualityStatus,
        latency_ms: float,
    ) -> MarketDataAuditEvent:
        event = MarketDataAuditEvent(
            request_id=request_id,
            caller_context=caller_context,
            endpoint=endpoint,
            symbols=symbols,
            market=market,
            provider_selected=provider_selected,
            provider_attempts=[self._redact_attempt(a) for a in attempts],
            fallback_used=False,
            quality_status=quality_status,
            error_code=None,
            created_at=datetime.now(timezone.utc),
            latency_ms=latency_ms,
        )
        self._events.append(event)
        return event

    def record_fail_closed(
        self,
        request_id: str,
        caller_context: str,
        endpoint: str,
        symbols: list[str],
        market: str | None,
        attempts: list[ProviderAttempt],
        error_code: str,
        latency_ms: float,
    ) -> MarketDataAuditEvent:
        event = MarketDataAuditEvent(
            request_id=request_id,
            caller_context=caller_context,
            endpoint=endpoint,
            symbols=symbols,
            market=market,
            provider_selected=None,
            provider_attempts=[self._redact_attempt(a) for a in attempts],
            fallback_used=False,
            quality_status=None,
            error_code=error_code,
            created_at=datetime.now(timezone.utc),
            latency_ms=latency_ms,
        )
        self._events.append(event)
        return event

    def get_events(self) -> list[MarketDataAuditEvent]:
        return list(self._events)

    def clear(self) -> None:
        self._events.clear()

    @staticmethod
    def _redact_attempt(attempt: ProviderAttempt) -> ProviderAttempt:
        attempt.safe_reason = redact_secret(attempt.safe_reason)
        return attempt
