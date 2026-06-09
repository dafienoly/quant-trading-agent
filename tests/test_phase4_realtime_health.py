"""Phase 4 实时数据健康门禁测试"""
from datetime import datetime

from src.data_gateway.realtime_health import build_realtime_health_report


def test_realtime_health_report_marks_stale_quote():
    now = datetime(2026, 6, 8, 10, 0, 20)
    quotes = [
        {"symbol": "002463.SZ", "datetime": "2026-06-08 10:00:00", "last_price": 10.0},
    ]

    report = build_realtime_health_report(
        provider="mock",
        quotes=quotes,
        now=now,
        max_delay_seconds=10,
    )

    assert report.is_acceptable is False
    assert report.delayed_symbols[0]["symbol"] == "002463.SZ"


def test_realtime_health_report_accepts_fresh_quote():
    now = datetime(2026, 6, 8, 10, 0, 5)
    quotes = [
        {"symbol": "002463.SZ", "datetime": "2026-06-08 10:00:00", "last_price": 10.0},
    ]

    report = build_realtime_health_report(
        provider="mock",
        quotes=quotes,
        now=now,
        max_delay_seconds=10,
    )

    assert report.is_acceptable is True
    assert report.delayed_symbols == []
