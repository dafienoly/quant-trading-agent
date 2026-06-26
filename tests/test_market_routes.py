from __future__ import annotations

from pathlib import Path

import pytest

from src.api.app import app
from src.data_gateway.provider_contracts import (
    DataQualityStatus,
    DataUsage,
    MarketDataEnvelope,
    MarketDataType,
)


class FakeRelay:
    def _result(self, data_type):
        return MarketDataEnvelope(
            request_id="req",
            source="fixture",
            provider_name="manual_fixture",
            data_type=data_type,
            fetched_at="2026-06-25T10:00:00+08:00",
            latency_ms=1,
            cached=False,
            stale=False,
            mock=True,
            quality_status=DataQualityStatus.MOCK,
            blocking_for_signal=True,
            payload=[],
        )

    def get_health(self):
        return self._result(MarketDataType.SOURCE_HEALTH)

    def get_sources(self):
        return self._result(MarketDataType.SOURCE_LIST)

    def get_stock_quotes(self, symbols, usage):
        assert symbols == ["600000.SH"]
        return self._result(MarketDataType.STOCK_QUOTE)

    def get_index_quotes(self, symbols, usage):
        return self._result(MarketDataType.INDEX_QUOTE)

    def get_etf_quotes(self, symbols, usage):
        return self._result(MarketDataType.ETF_QUOTE)

    def get_sector_quotes(self, symbols, usage):
        return self._result(MarketDataType.SECTOR_QUOTE)

    def get_bars(self, *args, **kwargs):
        return self._result(MarketDataType.STOCK_BARS)

    def get_calendar(self, *args, **kwargs):
        return self._result(MarketDataType.TRADE_CALENDAR)


def test_market_routes_return_unified_envelope(monkeypatch):
    import src.api.market_routes as routes

    monkeypatch.setattr(routes, "_get_relay", lambda: FakeRelay())
    results = [
        routes.market_health(),
        routes.market_sources(),
        routes.market_quotes("600000.SH", DataUsage.DISPLAY),
        routes.market_indexes("000001.SH", DataUsage.DISPLAY),
        routes.market_etfs("510300.SH", DataUsage.DISPLAY),
        routes.market_sectors("半导体", DataUsage.DISPLAY),
        routes.market_bars(
            "600000.SH",
            "20260601",
            "20260625",
            "daily",
            "qfq",
            "stock",
            DataUsage.ANALYSIS,
        ),
        routes.market_calendar(
            "20260601",
            "20260625",
            DataUsage.ANALYSIS,
        ),
    ]
    for body in results:
        assert body["request_id"] == "req"
        assert body["blocking_for_signal"] is True


def test_market_routes_are_registered_and_usage_enum_fails_closed():
    paths = set()
    for route in app.router.routes:
        if (
            type(route).__name__ == "_IncludedRouter"
            and route.include_context.prefix == "/product/market"
        ):
            paths.update(
                f"/product/market{item.path}"
                for item in route.include_context.included_router.routes
            )
    assert {
        "/product/market/health",
        "/product/market/sources",
        "/product/market/quotes",
        "/product/market/indexes",
        "/product/market/etfs",
        "/product/market/sectors",
        "/product/market/bars",
        "/product/market/calendar",
    }.issubset(paths)
    with pytest.raises(ValueError):
        DataUsage("unknown")


def test_dashboard_contains_market_relay_health_entry():
    text = Path("src/ui_report/product_dashboard.py").read_text(encoding="utf-8")

    assert "/product/market/health" in text
    assert "market_relay_health" in text
