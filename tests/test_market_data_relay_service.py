from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pandas as pd

from src.data_gateway.market_relay_provider import (
    LocalCacheProvider,
    ManualFixtureProvider,
)
from src.data_gateway.provider_contracts import DataUsage
from src.product_app.market_data_relay import MarketDataRelayService


class FakeLiveDataService:
    def __init__(self, now: datetime):
        self.now = now
        self.failed = False
        self._provider_order = ["eastmoney"]
        self._realtime_hub = MagicMock()
        self._daily_bars_hub = MagicMock()
        self._realtime_hub.get_health.return_value = []
        self._daily_bars_hub.get_health.return_value = []

    def get_realtime_quotes(self, symbols, allow_demo=False):
        assert allow_demo is False
        if self.failed:
            return {
                "data_status": "FAILED",
                "chosen_provider": "",
                "fallback_chain": ["eastmoney: timeout"],
                "quotes": [],
            }
        return {
            "data_status": "OK",
            "chosen_provider": "eastmoney",
            "fallback_chain": ["eastmoney: ok"],
            "quotes": [
                {
                    "symbol": symbols[0],
                    "name": "浦发银行",
                    "last_price": 10.5,
                    "pre_close": 10.0,
                    "open": 10.1,
                    "high": 10.6,
                    "low": 10.0,
                    "volume": 1000,
                    "amount": 10500,
                    "change": 0.5,
                    "pct_change": 5.0,
                    "datetime": self.now.isoformat(),
                    "trading_day": "20260625",
                    "data_source": "eastmoney",
                }
            ],
        }

    def get_daily_bars(self, symbols, start_date, end_date, adjust="qfq"):
        if self.failed:
            return {
                "data_status": "FAILED",
                "chosen_provider": "",
                "fallback_chain": ["eastmoney: timeout"],
                "daily_bars": [],
            }
        return {
            "data_status": "OK",
            "chosen_provider": "eastmoney",
            "fallback_chain": ["eastmoney: ok"],
            "daily_bars": [
                {
                    "symbol": symbols[0],
                    "trade_date": "20260625",
                    "open": 10,
                    "high": 11,
                    "low": 9,
                    "close": 10.5,
                    "volume": 100,
                    "amount": 1000,
                }
            ],
        }


def _service(tmp_path, now):
    live = FakeLiveDataService(now)
    fixture = ManualFixtureProvider(
        {
            "index_quotes": pd.DataFrame(
                [
                    {
                        "symbol": "000001.SH",
                        "name": "上证指数",
                        "last_price": 3000,
                        "datetime": now.isoformat(),
                        "data_source": "manual_fixture",
                    }
                ]
            ),
            "etf_quotes": pd.DataFrame(
                [
                    {
                        "symbol": "510300.SH",
                        "name": "沪深300ETF",
                        "last_price": 4.2,
                        "datetime": now.isoformat(),
                        "data_source": "manual_fixture",
                    }
                ]
            ),
            "sector_quotes": pd.DataFrame(
                [
                    {
                        "symbol": "BK1036",
                        "name": "半导体",
                        "last_price": 1234,
                        "datetime": now.isoformat(),
                        "data_source": "manual_fixture",
                    }
                ]
            ),
            "index_bars": pd.DataFrame(
                [
                    {
                        "symbol": "000001.SH",
                        "trade_date": "20260625",
                        "open": 10,
                        "high": 11,
                        "low": 9,
                        "close": 10.5,
                        "volume": 100,
                        "amount": 1000,
                    }
                ]
            ),
            "etf_bars": pd.DataFrame(
                [
                    {
                        "symbol": "510300.SH",
                        "trade_date": "20260625",
                        "open": 4,
                        "high": 4.3,
                        "low": 3.9,
                        "close": 4.2,
                        "volume": 100,
                        "amount": 420,
                    }
                ]
            ),
            "trade_calendar": pd.DataFrame([{"trade_date": "20260625"}]),
        },
        test_mode=True,
    )
    clock = {"now": now}
    service = MarketDataRelayService(
        live_data_service=live,
        relay_providers=[fixture],
        cache_provider=LocalCacheProvider(tmp_path),
        now=lambda: clock["now"],
    )
    return service, live, clock


def test_live_stock_quote_is_complete_and_cache_fallback_blocks_signal(tmp_path):
    now = datetime(2026, 6, 25, 2, 0, tzinfo=timezone.utc)
    service, live, _ = _service(tmp_path, now)

    live_result = service.get_stock_quotes(["600000.SH"], usage=DataUsage.SIGNAL)
    live.failed = True
    cached = service.get_stock_quotes(["600000.SH"], usage=DataUsage.DISPLAY)
    execution = service.get_stock_quotes(
        ["600000.SH"],
        usage=DataUsage.EXECUTION,
    )

    assert live_result.quality_status.value == "complete"
    assert live_result.blocking_for_signal is False
    assert cached.cached is True
    assert cached.blocking_for_signal is True
    assert execution.quality_status.value == "unavailable"


def test_cached_quote_becomes_stale(tmp_path):
    now = datetime(2026, 6, 25, 2, 0, tzinfo=timezone.utc)
    service, live, clock = _service(tmp_path, now)
    service.get_stock_quotes(["600000.SH"])
    live.failed = True
    clock["now"] = now + timedelta(seconds=901)

    cached = service.get_stock_quotes(["600000.SH"])

    assert cached.cached is True
    assert cached.stale is True
    assert cached.quality_status.value == "stale"


def test_manual_fixture_is_mock_and_signal_blocked(tmp_path):
    now = datetime(2026, 6, 25, 2, 0, tzinfo=timezone.utc)
    service, _, _ = _service(tmp_path, now)

    result = service.get_index_quotes(["000001.SH"], usage=DataUsage.SIGNAL)

    assert result.mock is True
    assert result.quality_status.value == "mock"
    assert result.blocking_for_signal is True


def test_bars_calendar_health_and_sources_have_unified_envelope(tmp_path):
    now = datetime(2026, 6, 25, 2, 0, tzinfo=timezone.utc)
    service, _, _ = _service(tmp_path, now)

    stock = service.get_bars(
        "600000.SH", "20260601", "20260625", asset_type="stock"
    )
    index = service.get_bars(
        "000001.SH", "20260601", "20260625", asset_type="index"
    )
    calendar = service.get_calendar("20260601", "20260625")
    health = service.get_health()
    sources = service.get_sources()

    assert stock.payload["frequency"] == "daily"
    assert stock.quality_status.value == "complete"
    assert index.mock is True
    assert calendar.payload == ["20260625"]
    assert health.data_type.value == "source_health"
    assert sources.payload[0]["test_only"] is True


def test_incomplete_quote_is_signal_blocked(tmp_path):
    now = datetime(2026, 6, 25, 2, 0, tzinfo=timezone.utc)
    service, live, _ = _service(tmp_path, now)
    original = live.get_realtime_quotes

    def incomplete(*args, **kwargs):
        result = original(*args, **kwargs)
        result["quotes"][0]["last_price"] = None
        return result

    live.get_realtime_quotes = incomplete

    result = service.get_stock_quotes(["600000.SH"])

    assert result.quality_status.value == "incomplete"
    assert result.blocking_for_signal is True


def test_live_service_exception_returns_unavailable_instead_of_raising(tmp_path):
    now = datetime(2026, 6, 25, 2, 0, tzinfo=timezone.utc)
    service, live, _ = _service(tmp_path, now)

    def broken(*args, **kwargs):
        raise RuntimeError("provider exploded")

    live.get_realtime_quotes = broken

    result = service.get_stock_quotes(["600000.SH"])

    assert result.quality_status.value == "unavailable"
    assert result.blocking_for_signal is True
    assert result.errors == ["live_data_service_error:RuntimeError"]


def test_cache_write_failure_does_not_hide_valid_live_data(tmp_path, monkeypatch):
    now = datetime(2026, 6, 25, 2, 0, tzinfo=timezone.utc)
    service, _, _ = _service(tmp_path, now)

    def broken_write(*args, **kwargs):
        raise OSError("disk unavailable")

    monkeypatch.setattr(service._cache, "write", broken_write)

    result = service.get_stock_quotes(["600000.SH"])

    assert result.quality_status.value == "complete"
    assert result.source == "live"
    assert "本地缓存写入失败" in result.warnings[-1]
