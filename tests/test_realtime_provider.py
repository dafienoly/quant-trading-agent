from __future__ import annotations

import pandas as pd

from src.data_gateway.aktools_provider import AkToolsProvider
from src.data_gateway.realtime_provider import AkShareRealtimeProvider


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
