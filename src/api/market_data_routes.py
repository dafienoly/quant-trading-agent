"""Product Market Data API routes — /product/market/**

Consumes MarketDataRelay for all data access. No raw provider imports.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Path, Query
from fastapi.responses import JSONResponse

from src.product_app.market_data.errors import MarketDataUnavailableError
from src.product_app.market_data.quality import CallerContext

router = APIRouter()


def _get_market_data_relay():
    """获取共享的 MarketDataRelay 单例"""
    from src.product_app.market_data.relay import MarketDataRelay
    return MarketDataRelay()


def _error_response(status_code: int, request_id: str, error_code: str, quality_status: str | None, safe_reason: str, provider_attempt_count: int, fallback_used: bool) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "request_id": request_id,
                "error_code": error_code,
                "quality_status": quality_status,
                "safe_reason": safe_reason,
                "provider_attempt_count": provider_attempt_count,
                "fallback_used": fallback_used,
            }
        },
    )


@router.get("/latest/{symbol}", response_model=None)
def get_latest_quote(
    symbol: str = Path(..., description="Stock symbol, e.g. 000001.SZ"),
    market: str = Query("cn_stock_a", description="Market identifier"),
) -> Any:
    """Get the latest quote for a single symbol with quality metadata."""
    relay = _get_market_data_relay()
    caller_context = CallerContext(name="dashboard_observability")
    try:
        quote = relay.get_latest_quote(symbol=symbol, market=market, caller_context=caller_context)
        return quote.model_dump()
    except MarketDataUnavailableError as exc:
        return _error_response(
            status_code=503,
            request_id=exc.request_id,
            error_code="MARKET_DATA_UNAVAILABLE",
            quality_status=exc.quality_status.value if exc.quality_status else None,
            safe_reason=exc.safe_reason,
            provider_attempt_count=len(exc.provider_attempts),
            fallback_used=exc.fallback_used,
        )
    except Exception as exc:
        return _error_response(
            status_code=500,
            request_id="internal",
            error_code="INTERNAL_ERROR",
            quality_status=None,
            safe_reason=str(type(exc).__name__),
            provider_attempt_count=0,
            fallback_used=False,
        )


class _LatestQuotesBody:
    """POST /product/market/latest 请求体模型"""

    @staticmethod
    def parse(body: dict[str, Any]) -> tuple[list[str], str, str, bool]:
        symbols = body.get("symbols", [])
        if not symbols or not isinstance(symbols, list):
            raise ValueError("symbols must be a non-empty list")
        market = body.get("market", "cn_stock_a")
        caller_context = body.get("caller_context", "dashboard_observability")
        allow_demo = body.get("allow_demo", False)
        return symbols, market, caller_context, allow_demo


@router.post("/latest", response_model=None)
def post_latest_quotes(
    body: dict[str, Any] = Body(default_factory=dict),
) -> Any:
    """Get latest quotes for multiple symbols."""
    try:
        symbols, market, caller_ctx, allow_demo = _LatestQuotesBody.parse(body)
    except (ValueError, TypeError) as exc:
        return JSONResponse(
            status_code=422,
            content={"error": {"safe_reason": str(exc), "error_code": "INVALID_PARAMETERS"}},
        )

    relay = _get_market_data_relay()
    caller_context = CallerContext(name=caller_ctx, allow_demo=allow_demo)
    try:
        result = relay.get_latest_quotes(symbols=symbols, market=market, caller_context=caller_context)
        return result.model_dump()
    except MarketDataUnavailableError as exc:
        return _error_response(
            status_code=503,
            request_id=exc.request_id,
            error_code="MARKET_DATA_UNAVAILABLE",
            quality_status=exc.quality_status.value if exc.quality_status else None,
            safe_reason=exc.safe_reason,
            provider_attempt_count=len(exc.provider_attempts),
            fallback_used=exc.fallback_used,
        )
    except Exception as exc:
        return _error_response(
            status_code=500,
            request_id="internal",
            error_code="INTERNAL_ERROR",
            quality_status=None,
            safe_reason=str(type(exc).__name__),
            provider_attempt_count=0,
            fallback_used=False,
        )


@router.get("/bars/{symbol}", response_model=None)
def get_bars(
    symbol: str = Path(..., description="Stock symbol"),
    granularity: str = Query(..., description="Bar granularity, e.g. 1d, 1h, 5m"),
    start: str = Query(..., description="Start date YYYY-MM-DD"),
    end: str = Query(..., description="End date YYYY-MM-DD"),
    market: str = Query("cn_stock_a", description="Market identifier"),
) -> Any:
    """Get historical bars for a symbol."""
    relay = _get_market_data_relay()
    caller_context = CallerContext(name="research_readonly")
    try:
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
    except (ValueError, TypeError):
        return JSONResponse(
            status_code=422,
            content={"error": {"safe_reason": "Invalid date format, use YYYY-MM-DD", "error_code": "INVALID_PARAMETERS"}},
        )

    try:
        bars = relay.get_bars(
            symbol=symbol,
            market=market,
            granularity=granularity,
            start=start_dt,
            end=end_dt,
            caller_context=caller_context,
        )
        return [bar.model_dump() for bar in bars]
    except MarketDataUnavailableError as exc:
        return _error_response(
            status_code=503,
            request_id=exc.request_id,
            error_code="MARKET_DATA_UNAVAILABLE",
            quality_status=exc.quality_status.value if exc.quality_status else None,
            safe_reason=exc.safe_reason,
            provider_attempt_count=len(exc.provider_attempts),
            fallback_used=exc.fallback_used,
        )
    except Exception as exc:
        return _error_response(
            status_code=500,
            request_id="internal",
            error_code="INTERNAL_ERROR",
            quality_status=None,
            safe_reason=str(type(exc).__name__),
            provider_attempt_count=0,
            fallback_used=False,
        )


@router.get("/providers/health")
def get_providers_health() -> dict[str, Any]:
    """Get provider health snapshot (availability, latency, circuit breaker)."""
    relay = _get_market_data_relay()
    return relay._health.snapshot()


@router.get("/providers/quality")
def get_providers_quality() -> dict[str, Any]:
    """Get provider quality status summary."""
    relay = _get_market_data_relay()
    events = relay._audit.get_events()
    if not events:
        return {"status": "no_data", "events": []}
    return {
        "status": "ok",
        "last_event": {
            "request_id": events[-1].request_id,
            "quality_status": events[-1].quality_status.value if events[-1].quality_status else None,
            "provider_selected": events[-1].provider_selected,
            "created_at": events[-1].created_at.isoformat(),
        },
        "total_events": len(events),
    }


@router.get("/providers/fallback")
def get_providers_fallback() -> dict[str, Any]:
    """Get provider fallback activation summary."""
    relay = _get_market_data_relay()
    health = relay._health.snapshot()
    result: dict[str, Any] = {}
    for provider_id, info in health.items():
        result[provider_id] = {
            "fallback_activation_count": info.get("fallback_activation_count", 0),
            "circuit_breaker_status": info.get("circuit_breaker_status", "unknown"),
            "consecutive_failures": info.get("consecutive_failures", 0),
        }
    return result
