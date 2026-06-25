from __future__ import annotations

from src.data_gateway.provider_contracts import (
    DataQualityStatus,
    MarketDataEnvelope,
    MarketDataType,
    QuoteSnapshot,
)


def test_market_data_envelope_serializes_enums_and_payload():
    quote = QuoteSnapshot(
        symbol="600000.SH",
        name="浦发银行",
        price=10.5,
        prev_close=10.0,
        open=10.1,
        high=10.6,
        low=10.0,
        volume=1000,
        amount=10500.0,
        change=0.5,
        pct_change=5.0,
        timestamp="2026-06-25T10:00:00+08:00",
        trading_day="20260625",
    )
    envelope = MarketDataEnvelope(
        request_id="req-1",
        source="live",
        provider_name="eastmoney",
        data_type=MarketDataType.STOCK_QUOTE,
        fetched_at="2026-06-25T10:00:01+08:00",
        latency_ms=12.5,
        cached=False,
        stale=False,
        mock=False,
        quality_status=DataQualityStatus.COMPLETE,
        blocking_for_signal=False,
        payload=[quote.to_dict()],
    )

    result = envelope.to_dict()

    assert result["data_type"] == "stock_quote"
    assert result["quality_status"] == "complete"
    assert result["payload"][0]["symbol"] == "600000.SH"
    assert result["blocking_for_signal"] is False
