"""V16.2 统一市场数据 Relay API。"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query

from src.data_gateway.provider_contracts import DataUsage
from src.product_app.market_data_relay import (
    MarketDataRelayService,
    get_market_data_relay_service,
)

router = APIRouter()


def _get_relay() -> MarketDataRelayService:
    return get_market_data_relay_service()


def _symbols(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@router.get("/health")
def market_health() -> dict:
    return _get_relay().get_health().to_dict()


@router.get("/sources")
def market_sources() -> dict:
    return _get_relay().get_sources().to_dict()


@router.get("/quotes")
def market_quotes(
    symbols: str = Query(..., min_length=1, description="逗号分隔的 A 股代码"),
    usage: DataUsage = Query(DataUsage.DISPLAY),
) -> dict:
    return _get_relay().get_stock_quotes(_symbols(symbols), usage=usage).to_dict()


@router.get("/indexes")
def market_indexes(
    symbols: str = Query(..., min_length=1, description="逗号分隔的指数代码"),
    usage: DataUsage = Query(DataUsage.DISPLAY),
) -> dict:
    return _get_relay().get_index_quotes(_symbols(symbols), usage=usage).to_dict()


@router.get("/etfs")
def market_etfs(
    symbols: str = Query(..., min_length=1, description="逗号分隔的 ETF 代码"),
    usage: DataUsage = Query(DataUsage.DISPLAY),
) -> dict:
    return _get_relay().get_etf_quotes(_symbols(symbols), usage=usage).to_dict()


@router.get("/sectors")
def market_sectors(
    symbols: str = Query("", description="可选的行业板块名称或代码"),
    usage: DataUsage = Query(DataUsage.DISPLAY),
) -> dict:
    return _get_relay().get_sector_quotes(_symbols(symbols), usage=usage).to_dict()


@router.get("/bars")
def market_bars(
    symbol: str = Query(..., min_length=1),
    start: str = Query(..., min_length=8),
    end: str = Query(..., min_length=8),
    frequency: Literal["daily"] = Query("daily"),
    adjust: Literal["qfq", "hfq", ""] = Query("qfq"),
    asset_type: Literal["stock", "index", "etf"] = Query("stock"),
    usage: DataUsage = Query(DataUsage.ANALYSIS),
) -> dict:
    return _get_relay().get_bars(
        symbol,
        start,
        end,
        frequency=frequency,
        adjust=adjust,
        asset_type=asset_type,
        usage=usage,
    ).to_dict()


@router.get("/calendar")
def market_calendar(
    start: str = Query(..., min_length=8),
    end: str = Query(..., min_length=8),
    usage: DataUsage = Query(DataUsage.ANALYSIS),
) -> dict:
    return _get_relay().get_calendar(start, end, usage=usage).to_dict()
