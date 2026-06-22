from __future__ import annotations

import pandas as pd

from src.product_app.market_data import fetch_product_quotes, parse_symbols


def test_parse_symbols_normalizes_and_defaults():
    assert parse_symbols("002463,600584.SH") == ["002463.SZ", "600584.SH"]
    assert parse_symbols("")[:1]


def test_fetch_product_quotes_uses_selected_provider(monkeypatch):
    import src.product_app.market_data as market_data

    class FakeProvider:
        def get_realtime_quotes(self, symbols):
            assert symbols == ["002463.SZ"]
            return pd.DataFrame(
                [
                    {
                        "symbol": "002463.SZ",
                        "market": "SZ",
                        "last_price": 38.52,
                        "data_source": "akshare",
                    }
                ]
            )

    monkeypatch.setattr(market_data, "build_realtime_provider", lambda provider: FakeProvider())

    result = fetch_product_quotes(
        "002463.SZ",
        provider="akshare",
        allow_demo=False,
        force_live=True,
    )

    assert result["status"] == "ok"
    assert result["provider"] == "akshare"
    assert result["is_demo"] is False
    assert result["quotes"][0]["symbol"] == "002463.SZ"


def test_fetch_product_quotes_records_feedback_on_provider_failure(monkeypatch):
    import src.product_app.market_data as market_data
    monkeypatch.setattr(market_data, "is_trading_hours", lambda: True)

    class BrokenProvider:
        def get_realtime_quotes(self, symbols):
            raise RuntimeError("provider unavailable")

    bug_calls = []

    class FakeFeedback:
        def write_bug_report(self, **kwargs):
            bug_calls.append(kwargs)
            return "BUG_QUOTES"

    monkeypatch.setattr(market_data, "build_realtime_provider", lambda provider: BrokenProvider())
    monkeypatch.setattr(market_data, "get_feedback_service", lambda: FakeFeedback())

    result = fetch_product_quotes(
        ["002463.SZ"],
        provider="akshare",
        allow_demo=True,
        force_live=True,
    )

    assert result["status"] == "fallback_demo"
    assert result["is_demo"] is True
    assert result["bug_id"] == "BUG_QUOTES"
    assert bug_calls[0]["component"] == "data_gateway"
    assert bug_calls[0]["runtime_context"]["symbols"] == ["002463.SZ"]
