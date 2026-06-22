from __future__ import annotations

import pandas as pd
from fastapi.testclient import TestClient

from src.api.app import create_app


def test_product_quotes_endpoint_returns_requested_provider_quotes(monkeypatch):
    import src.product_app.market_data as market_data

    class FakeProvider:
        def get_realtime_quotes(self, symbols):
            assert symbols == ["002463.SZ"]
            return pd.DataFrame(
                [
                    {
                        "symbol": "002463.SZ",
                        "market": "SZ",
                        "name": "Test Stock",
                        "datetime": "2026-06-10T10:00:00+08:00",
                        "last_price": 38.52,
                        "pct_change": 2.35,
                        "volume": 12580000,
                        "amount": 485000000.0,
                        "status": "NORMAL",
                        "data_source": "akshare",
                    }
                ]
            )

    monkeypatch.setattr(market_data, "build_realtime_provider", lambda provider: FakeProvider())
    client = TestClient(create_app())

    response = client.get(
        "/product/quotes",
        params={"symbols": "002463.SZ", "provider": "akshare", "allow_demo": "false"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["provider"] == "akshare"
    assert body["is_demo"] is False
    assert body["quotes"][0]["symbol"] == "002463.SZ"
    assert body["quotes"][0]["name"] == "Test Stock"


def test_product_quotes_endpoint_falls_back_to_demo_and_records_feedback(monkeypatch):
    import src.product_app.market_data as market_data
    monkeypatch.setattr(market_data, "is_trading_hours", lambda: True)

    class BrokenProvider:
        def get_realtime_quotes(self, symbols):
            raise RuntimeError("akshare boom")

    bug_calls = []

    class FakeFeedback:
        def write_bug_report(self, **kwargs):
            bug_calls.append(kwargs)
            return "BUG_TEST"

    monkeypatch.setattr(market_data, "build_realtime_provider", lambda provider: BrokenProvider())
    monkeypatch.setattr(market_data, "get_feedback_service", lambda: FakeFeedback())
    client = TestClient(create_app())

    response = client.get(
        "/product/quotes",
        params={
            "symbols": "002463.SZ",
            "provider": "akshare",
            "allow_demo": "true",
            "force_live": "true",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "fallback_demo"
    assert body["is_demo"] is True
    assert body["quotes"]
    assert bug_calls
    assert bug_calls[0]["component"] == "data_gateway"
    assert bug_calls[0]["endpoint_or_page"] == "/product/quotes"
