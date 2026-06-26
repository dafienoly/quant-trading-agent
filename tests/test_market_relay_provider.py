from __future__ import annotations

import pandas as pd
import pytest

from src.data_gateway.market_relay_provider import (
    AkShareMarketRelayProvider,
    LocalCacheProvider,
    ManualFixtureProvider,
)
from src.data_gateway.provider_contracts import DataCapability
from src.data_gateway.provider_hub import DataProviderHub


def test_manual_fixture_provider_requires_explicit_test_mode():
    with pytest.raises(RuntimeError, match="test_mode"):
        ManualFixtureProvider({})


def test_manual_fixture_provider_returns_copy():
    source = pd.DataFrame([{"trade_date": "20260625"}])
    provider = ManualFixtureProvider(
        {"trade_calendar": source},
        test_mode=True,
    )

    result = provider.get_trade_dates("20260601", "20260630")
    result.loc[0, "trade_date"] = "changed"

    assert source.loc[0, "trade_date"] == "20260625"


def test_akshare_relay_provider_maps_index_etf_sector_and_calendar(monkeypatch):
    import src.data_gateway.market_relay_provider as module

    monkeypatch.setattr(
        module.ak,
        "stock_zh_index_spot_em",
        lambda: pd.DataFrame(
            [{"代码": "000001", "名称": "上证指数", "最新价": 3000, "成交量": 10}]
        ),
    )
    monkeypatch.setattr(
        module.ak,
        "fund_etf_spot_em",
        lambda: pd.DataFrame(
            [{"代码": "510300", "名称": "沪深300ETF", "最新价": 4.2, "成交量": 20}]
        ),
    )
    monkeypatch.setattr(
        module.ak,
        "stock_board_industry_spot_em",
        lambda: pd.DataFrame(
            [{"板块代码": "BK1036", "板块名称": "半导体", "最新价": 1234}]
        ),
    )
    monkeypatch.setattr(
        module.ak,
        "tool_trade_date_hist_sina",
        lambda: pd.DataFrame(
            {"trade_date": pd.to_datetime(["2026-06-24", "2026-06-25"])}
        ),
    )
    provider = AkShareMarketRelayProvider()

    index = provider.get_index_realtime_quotes(["000001.SH"])
    etf = provider.get_etf_realtime_quotes(["510300.SH"])
    sector = provider.get_sector_quotes(["半导体"])
    calendar = provider.get_trade_dates("2026-06-25", "2026-06-25")

    assert index.iloc[0]["symbol"] == "000001.SH"
    assert index.iloc[0]["name"] == "上证指数"
    assert index.iloc[0]["volume"] == 1000
    assert index.iloc[0]["source_volume_unit"] == "lot"
    assert etf.iloc[0]["symbol"] == "510300.SH"
    assert sector.iloc[0]["symbol"] == "BK1036"
    assert calendar["trade_date"].tolist() == ["20260625"]


def test_akshare_relay_provider_maps_index_and_etf_bars(monkeypatch):
    import src.data_gateway.market_relay_provider as module

    raw = pd.DataFrame(
        [
            {
                "日期": "2026-06-25",
                "开盘": 10,
                "最高": 11,
                "最低": 9,
                "收盘": 10.5,
                "成交量": 100,
                "成交额": 1000,
            }
        ]
    )
    monkeypatch.setattr(module.ak, "index_zh_a_hist", lambda **kwargs: raw)
    monkeypatch.setattr(module.ak, "fund_etf_hist_em", lambda **kwargs: raw)
    provider = AkShareMarketRelayProvider()

    index = provider.get_index_daily_bars(
        "000001.SH", "20260601", "20260625"
    )
    etf = provider.get_etf_daily_bars(
        "510300.SH", "20260601", "20260625"
    )

    assert index.iloc[0]["trade_date"] == "20260625"
    assert etf.iloc[0]["adjusted_close"] == 10.5


def test_local_cache_provider_round_trip_and_corrupt_file(tmp_path):
    cache = LocalCacheProvider(tmp_path)
    cache.write("quote-key", {"payload": [{"symbol": "600000.SH"}]})

    assert cache.read("quote-key")["payload"][0]["symbol"] == "600000.SH"

    (tmp_path / "broken.json").write_text("{", encoding="utf-8")
    assert cache.read("broken") is None


def test_provider_hub_health_tracks_success_and_error():
    success = ManualFixtureProvider(
        {
            "trade_calendar": pd.DataFrame(
                [{"trade_date": "20260625"}]
            )
        },
        test_mode=True,
    )
    hub = DataProviderHub([success])

    before = hub.get_health(DataCapability.TRADE_CALENDAR)[0]
    result = hub.fetch_with_fallback(
        DataCapability.TRADE_CALENDAR,
        "get_trade_dates",
        "20260601",
        "20260630",
        required_fields=["trade_date"],
    )
    after = hub.get_health(DataCapability.TRADE_CALENDAR)[0]

    assert before.status == "UNKNOWN"
    assert result.request_id
    assert result.started_at and result.completed_at
    assert after.status == "OK"
    assert after.last_success_at
    assert after.row_count == 1
