from __future__ import annotations

from datetime import datetime, time
from unittest.mock import patch

import pandas as pd

from src.data_gateway.aktools_provider import AkToolsProvider
from src.data_gateway.realtime_provider import AkShareRealtimeProvider
from src.product_app.market_data import fetch_product_quotes, is_trading_hours


def test_akshare_realtime_provider_maps_a_share_columns(monkeypatch):
    raw = pd.DataFrame(
        [
            {
                "代码": "002463",
                "名称": "沪电股份",
                "最新价": 38.52,
                "涨跌幅": 2.35,
                "涨跌额": 0.88,
                "成交量": 125800,
                "成交额": 485000000,
                "今开": 37.2,
                "最高": 38.8,
                "最低": 37.0,
                "昨收": 37.64,
            }
        ]
    )

    import src.data_gateway.realtime_provider as realtime_provider

    monkeypatch.setattr(realtime_provider.ak, "stock_zh_a_spot_em", lambda: raw)

    provider = AkShareRealtimeProvider(request_interval=0)
    result = provider.get_realtime_quotes(["002463.SZ"])

    assert len(result) == 1
    row = result.iloc[0]
    assert row["symbol"] == "002463.SZ"
    assert row["market"] == "SZ"
    assert row["name"] == "沪电股份"
    assert row["last_price"] == 38.52
    assert row["pct_change"] == 2.35
    assert row["volume"] == 12580000
    assert row["source_volume_unit"] == "lot"
    assert row["data_source"] == "akshare"
    assert row["status"] == "NORMAL"


def test_akshare_realtime_provider_marks_mainboard_limit_up(monkeypatch):
    raw = pd.DataFrame(
        [
            {
                "代码": "600584",
                "名称": "长电科技",
                "最新价": 31.78,
                "涨跌幅": 10.01,
                "成交量": 100,
                "成交额": 317800,
            }
        ]
    )

    import src.data_gateway.realtime_provider as realtime_provider

    monkeypatch.setattr(realtime_provider.ak, "stock_zh_a_spot_em", lambda: raw)

    provider = AkShareRealtimeProvider(request_interval=0)
    result = provider.get_realtime_quotes(["600584.SH"])

    assert result.iloc[0]["status"] == "LIMIT_UP"
    assert result.iloc[0]["market"] == "SH"


def test_aktools_provider_fetches_realtime_quotes_from_http_mapping(monkeypatch):
    raw = pd.DataFrame(
        [
            {
                "代码": "002463",
                "名称": "沪电股份",
                "最新价": 38.52,
                "涨跌幅": 2.35,
                "成交量": 125800,
                "成交额": 485000000,
            }
        ]
    )

    provider = AkToolsProvider(base_url="http://aktools.local")
    monkeypatch.setattr(provider, "_get", lambda endpoint, params=None: raw)

    result = provider.get_realtime_quotes(["002463.SZ"])

    assert len(result) == 1
    assert result.iloc[0]["symbol"] == "002463.SZ"
    assert result.iloc[0]["last_price"] == 38.52
    assert result.iloc[0]["data_source"] == "aktools"


# ---------------------------------------------------------------------------
# Retry + backoff tests
# ---------------------------------------------------------------------------

def test_akshare_retries_on_empty_result_and_eventually_succeeds(monkeypatch):
    """First call returns empty, second call returns data — should succeed."""
    call_count = [0]

    def _spot_em():
        call_count[0] += 1
        if call_count[0] < 2:
            return pd.DataFrame()  # empty on first attempt
        return pd.DataFrame([
            {"代码": "002463", "名称": "沪电股份", "最新价": 38.52,
             "涨跌幅": 2.35, "涨跌额": 0.88, "成交量": 125800, "成交额": 485000000,
             "今开": 37.2, "最高": 38.8, "最低": 37.0, "昨收": 37.64}
        ])

    import src.data_gateway.realtime_provider as rt
    monkeypatch.setattr(rt.ak, "stock_zh_a_spot_em", _spot_em)

    provider = AkShareRealtimeProvider(request_interval=0)
    # Override retry timing for fast tests
    provider._RETRY_BASE_DELAY = 0.01
    result = provider.get_realtime_quotes(["002463.SZ"])

    assert len(result) == 1, f"Expected 1 row after retry, got {len(result)}"
    assert result.iloc[0]["symbol"] == "002463.SZ"
    assert call_count[0] == 2, f"Expected 2 calls (1 empty + 1 success), got {call_count[0]}"


def test_akshare_retry_exhausted_returns_empty(monkeypatch):
    """All retries return empty — should return empty DataFrame."""
    import src.data_gateway.realtime_provider as rt
    monkeypatch.setattr(rt.ak, "stock_zh_a_spot_em", lambda: pd.DataFrame())

    provider = AkShareRealtimeProvider(request_interval=0)
    provider._RETRY_BASE_DELAY = 0.01
    provider._MAX_RETRIES = 2  # fewer retries for test speed
    result = provider.get_realtime_quotes(["002463.SZ"])

    assert result.empty


def test_akshare_per_symbol_fallback_kicks_in(monkeypatch):
    """Bulk fetch always empty → per-symbol fallback should be tried."""
    bulk_calls: list[str] = []

    def _spot_em():
        bulk_calls.append("called")
        return pd.DataFrame()  # always empty

    import src.data_gateway.realtime_provider as rt
    monkeypatch.setattr(rt.ak, "stock_zh_a_spot_em", _spot_em)

    provider = AkShareRealtimeProvider(request_interval=0)
    provider._RETRY_BASE_DELAY = 0.01
    provider._MAX_RETRIES = 1  # exhaust quickly
    provider._SYMBOL_INTERVAL = 0.0

    result = provider.get_realtime_quotes(["002463.SZ", "600584.SH"])

    # Should be empty (our mock returns empty for all paths)
    assert result.empty
    # bulk_calls includes: 1 bulk attempt + per-symbol calls (one per symbol)
    # So total = _MAX_RETRIES (bulk) + len(symbols) (per-symbol fallback)
    assert len(bulk_calls) >= provider._MAX_RETRIES, (
        f"Expected at least {provider._MAX_RETRIES} bulk calls, "
        f"got {len(bulk_calls)}"
    )


# ---------------------------------------------------------------------------
# Trading hours detection tests
# ---------------------------------------------------------------------------

class TestIsTradingHours:
    """Test is_trading_hours() against known-true/false time windows."""

    def test_weekday_morning_session_returns_true(self, monkeypatch):
        mock_dt = datetime(2026, 6, 10, 10, 30, 0)  # Wednesday 10:30
        with patch("src.product_app.market_data.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_dt
            assert is_trading_hours() is True

    def test_weekday_afternoon_session_returns_true(self, monkeypatch):
        mock_dt = datetime(2026, 6, 10, 14, 0, 0)  # Wednesday 14:00
        with patch("src.product_app.market_data.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_dt
            assert is_trading_hours() is True

    def test_weekday_lunch_break_returns_false(self, monkeypatch):
        mock_dt = datetime(2026, 6, 10, 12, 0, 0)  # lunch break
        with patch("src.product_app.market_data.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_dt
            assert is_trading_hours() is False

    def test_weekday_before_open_returns_false(self, monkeypatch):
        mock_dt = datetime(2026, 6, 10, 9, 0, 0)  # before market open
        with patch("src.product_app.market_data.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_dt
            assert is_trading_hours() is False

    def test_weekday_after_close_returns_false(self, monkeypatch):
        mock_dt = datetime(2026, 6, 10, 15, 30, 0)  # after close
        with patch("src.product_app.market_data.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_dt
            assert is_trading_hours() is False

    def test_saturday_returns_false(self, monkeypatch):
        mock_dt = datetime(2026, 6, 13, 10, 30, 0)  # Saturday
        with patch("src.product_app.market_data.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_dt
            assert is_trading_hours() is False

    def test_sunday_returns_false(self, monkeypatch):
        mock_dt = datetime(2026, 6, 14, 14, 0, 0)  # Sunday
        with patch("src.product_app.market_data.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_dt
            assert is_trading_hours() is False


# ---------------------------------------------------------------------------
# Non-trading-hours: no Bug generation tests
# ---------------------------------------------------------------------------

def test_empty_quotes_during_trading_hours_writes_bug(monkeypatch, tmp_path):
    """Empty quotes during trading hours should generate a bug report."""
    mock_dt = datetime(2026, 6, 10, 10, 30, 0)  # Wednesday trading hours

    import src.data_gateway.realtime_provider as rt
    monkeypatch.setattr(rt.ak, "stock_zh_a_spot_em", lambda: pd.DataFrame())

    with patch("src.product_app.market_data.datetime") as mock_datetime:
        mock_datetime.now.return_value = mock_dt
        result = fetch_product_quotes(
            ["002463.SZ"], provider="akshare", allow_demo=True, force_live=True,
        )

    assert result["status"] == "fallback_demo"
    assert result["is_demo"] is True
    # Bug should be generated during trading hours
    assert result.get("bug_id") is not None, "Expected bug_id during trading hours"


def test_empty_quotes_outside_trading_hours_skips_bug(monkeypatch):
    """Empty quotes outside trading hours should NOT generate a bug report."""
    mock_dt = datetime(2026, 6, 13, 10, 30, 0)  # Saturday

    import src.data_gateway.realtime_provider as rt
    monkeypatch.setattr(rt.ak, "stock_zh_a_spot_em", lambda: pd.DataFrame())

    with patch("src.product_app.market_data.datetime") as mock_datetime:
        mock_datetime.now.return_value = mock_dt
        result = fetch_product_quotes(
            ["002463.SZ"], provider="akshare", allow_demo=True, force_live=True,
        )

    assert result["status"] == "fallback_demo"
    assert result["is_demo"] is True
    # Bug should NOT be generated outside trading hours
    assert result.get("bug_id") is None, "Expected no bug_id outside trading hours"
