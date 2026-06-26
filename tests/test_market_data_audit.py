from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.product_app.market_data.audit import AuditRecorder, MarketDataAuditEvent
from src.product_app.market_data.contracts import ProviderAttempt, ProviderErrorCategory, QualityStatus
from src.product_app.market_data.errors import redact_secret


class TestMarketDataAuditEvent:
    def test_event_fields_present(self):
        event = MarketDataAuditEvent(
            request_id="req-123",
            caller_context="research_readonly",
            endpoint="get_latest_quote",
            symbols=["000001.SH"],
            market="SH",
            provider_selected="eastmoney",
            provider_attempts=[],
            fallback_used=False,
            quality_status=QualityStatus.OK,
            error_code=None,
            created_at=datetime.now(timezone.utc),
            latency_ms=42.5,
        )
        assert event.request_id == "req-123"
        assert event.caller_context == "research_readonly"
        assert event.endpoint == "get_latest_quote"
        assert event.symbols == ["000001.SH"]
        assert event.market == "SH"
        assert event.provider_selected == "eastmoney"
        assert event.fallback_used is False
        assert event.quality_status == QualityStatus.OK
        assert event.error_code is None
        assert event.latency_ms == 42.5

    def test_event_with_fallback(self):
        event = MarketDataAuditEvent(
            request_id="req-456",
            caller_context="dashboard_observability",
            endpoint="get_latest_quotes",
            symbols=["000001.SH"],
            market="SH",
            provider_selected="akshare",
            provider_attempts=[
                ProviderAttempt(
                    provider_id="eastmoney",
                    priority=1,
                    error_category=ProviderErrorCategory.TIMEOUT,
                    quality_status=None,
                    latency_ms=5000.0,
                    safe_reason="timeout",
                ),
                ProviderAttempt(
                    provider_id="akshare",
                    priority=2,
                    error_category=None,
                    quality_status=QualityStatus.OK,
                    latency_ms=100.0,
                    safe_reason="",
                ),
            ],
            fallback_used=True,
            quality_status=QualityStatus.FALLBACK,
            error_code="PROVIDER_TIMEOUT",
            created_at=datetime.now(timezone.utc),
            latency_ms=5100.0,
        )
        assert event.fallback_used is True
        assert event.quality_status == QualityStatus.FALLBACK
        assert event.error_code == "PROVIDER_TIMEOUT"
        assert len(event.provider_attempts) == 2

    def test_audit_recorder_redacts_secret(self):
        recorder = AuditRecorder()
        event = recorder.record_fail_closed(
            request_id="req-sec",
            caller_context="research_readonly",
            endpoint="get_latest_quote",
            symbols=["600000.SH"],
            market="SH",
            attempts=[
                ProviderAttempt(
                    provider_id="test",
                    priority=1,
                    error_category=ProviderErrorCategory.AUTH_FAILED,
                    quality_status=None,
                    latency_ms=10.0,
                    safe_reason="invalid api_key",
                ),
            ],
            error_code="AUTH_FAILED",
            latency_ms=10.0,
        )
        model_str = str(event.model_dump())
        assert "<redacted>" in model_str


class TestAuditRecorder:
    def test_record_success(self):
        recorder = AuditRecorder()
        event = recorder.record_success(
            request_id="req-1",
            caller_context="research_readonly",
            endpoint="get_latest_quote",
            symbols=["000001.SH"],
            market="SH",
            provider_selected="eastmoney",
            attempts=[],
            quality_status=QualityStatus.OK,
            latency_ms=100.0,
        )
        assert isinstance(event, MarketDataAuditEvent)
        assert event.request_id == "req-1"
        assert event.quality_status == QualityStatus.OK
        assert event.error_code is None
        assert event.fallback_used is False

    def test_record_fail_closed(self):
        recorder = AuditRecorder()
        event = recorder.record_fail_closed(
            request_id="req-2",
            caller_context="signal_generation",
            endpoint="get_latest_quote",
            symbols=["999999.XSHE"],
            market="SZ",
            attempts=[
                ProviderAttempt(
                    provider_id="eastmoney",
                    priority=1,
                    error_category=ProviderErrorCategory.PROVIDER_UNAVAILABLE,
                    latency_ms=5000.0,
                    safe_reason="provider unavailable",
                ),
            ],
            error_code="ALL_PROVIDERS_FAILED",
            latency_ms=5000.0,
        )
        assert isinstance(event, MarketDataAuditEvent)
        assert event.request_id == "req-2"
        assert event.quality_status is None
        assert event.error_code == "ALL_PROVIDERS_FAILED"
        assert event.fallback_used is False
        assert len(event.provider_attempts) == 1

    def test_get_events_and_clear(self):
        recorder = AuditRecorder()
        assert recorder.get_events() == []
        recorder.record_success(
            request_id="r1",
            caller_context="research_readonly",
            endpoint="test",
            symbols=["A"],
            market="SH",
            provider_selected="p1",
            attempts=[],
            quality_status=QualityStatus.OK,
            latency_ms=1.0,
        )
        recorder.record_fail_closed(
            request_id="r2",
            caller_context="research_readonly",
            endpoint="test",
            symbols=["B"],
            market="SZ",
            attempts=[],
            error_code="ERROR",
            latency_ms=2.0,
        )
        assert len(recorder.get_events()) == 2
        recorder.clear()
        assert recorder.get_events() == []

    def test_redact_in_recorder(self):
        recorder = AuditRecorder()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.product_app.market_data.audit.redact_secret", lambda v: "<redacted>")
            recorder.record_success(
                request_id="r3",
                caller_context="research_readonly",
                endpoint="test",
                symbols=["C"],
                market="SH",
                provider_selected="test_provider",
                attempts=[
                    ProviderAttempt(
                        provider_id="test",
                        priority=1,
                        error_category=ProviderErrorCategory.AUTH_FAILED,
                        latency_ms=5.0,
                        safe_reason="api_key=secret123",
                    ),
                ],
                quality_status=QualityStatus.OK,
                latency_ms=5.0,
            )
            events = recorder.get_events()
            for ev in events:
                for attempt in ev.provider_attempts:
                    assert redact_secret(attempt.safe_reason) == attempt.safe_reason
