from __future__ import annotations

import json

from src.product_app.service_manager import ServiceManager


def test_quote_refresh_job_writes_latest_quotes_snapshot(tmp_path, monkeypatch):
    import src.product_app.service_manager as service_manager

    calls = []

    def fake_fetch(symbols, *, provider, allow_demo, force_live):
        calls.append(
            {
                "symbols": symbols,
                "provider": provider,
                "allow_demo": allow_demo,
                "force_live": force_live,
            }
        )
        return {
            "status": "ok",
            "provider": provider,
            "is_demo": False,
            "quotes": [{"symbol": "002463.SZ", "last_price": 38.52}],
            "messages": [],
        }

    monkeypatch.setattr(service_manager, "fetch_product_quotes", fake_fetch)

    manager = ServiceManager(state_dir=str(tmp_path))
    manager._execute_job(
        "quote_refresh",
        {
            "symbols": "002463.SZ",
            "provider": "akshare",
            "allow_demo": "false",
            "force_live": "true",
        },
    )

    payload = json.loads((tmp_path / "latest_quotes.json").read_text(encoding="utf-8"))

    assert calls == [
        {
            "symbols": "002463.SZ",
            "provider": "akshare",
            "allow_demo": False,
            "force_live": True,
        }
    ]
    assert payload["status"] == "ok"
    assert payload["provider"] == "akshare"
    assert payload["quotes"][0]["symbol"] == "002463.SZ"
    assert payload["updated_at"]
