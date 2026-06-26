"""Product-facing realtime market data facade.

The product UI, API routes, and background jobs all fetch quotes through this
module so provider selection, demo fallback, and feedback reporting stay
consistent.
"""

from __future__ import annotations

import traceback
from datetime import datetime, time
from typing import Any

import pandas as pd

from src.config.settings import DEFAULT_DATA_PROVIDER
from src.data_gateway.aktools_provider import AkToolsProvider
from src.data_gateway.realtime_provider import AkShareRealtimeProvider, normalize_quote_symbol
from src.product_app.demo_data import DEMO_STOCKS, get_demo_quotes, is_demo_mode
from src.product_app.feedback import get_feedback_service

# Re-export new module symbols
from src.product_app.market_data.contracts import (
    AuthRequirement,
    CachePolicy,
    DataQualityMetadata,
    FallbackEligibility,
    FreshnessPolicy,
    ItemError,
    MarketBar,
    MarketDataProviderContract,
    MarketQuote,
    MultiSymbolQuoteResult,
    ProviderAttempt,
    ProviderErrorCategory,
    QualityStatus,
    RateLimitPolicy,
    TimeoutPolicy,
)
from src.product_app.market_data.errors import MarketDataUnavailableError, redact_secret, safe_error_summary
from src.product_app.market_data.quality import CallerContext, QualityGate
from src.product_app.market_data.audit import AuditRecorder, MarketDataAuditEvent
from src.product_app.market_data.cache import CachedEntry, MarketDataCache
from src.product_app.market_data.health import ProviderHealthAggregator
from src.product_app.market_data.relay import MarketDataRelay


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def is_trading_hours() -> bool:
    """Return True if the current time falls within A-share continuous auction hours.

    A-share trading sessions (Beijing time):
        Morning:  9:30 — 11:30
        Afternoon: 13:00 — 15:00
    """
    now = datetime.now()
    # Weekend check
    if now.weekday() >= 5:
        return False
    t = now.time()
    morning_start = time(9, 30)
    morning_end = time(11, 30)
    afternoon_start = time(13, 0)
    afternoon_end = time(15, 0)
    return (morning_start <= t <= morning_end) or (afternoon_start <= t <= afternoon_end)


def default_symbols() -> list[str]:
    return [normalize_quote_symbol(stock["symbol"]) for stock in DEMO_STOCKS]


def parse_symbols(symbols: str | list[str] | tuple[str, ...] | None) -> list[str]:
    if symbols is None:
        return default_symbols()
    if isinstance(symbols, str):
        raw_symbols = symbols.split(",")
    else:
        raw_symbols = list(symbols)

    parsed = [normalize_quote_symbol(str(item)) for item in raw_symbols if str(item).strip()]
    return parsed or default_symbols()


def build_realtime_provider(provider: str):
    provider_name = (provider or DEFAULT_DATA_PROVIDER or "akshare").lower()
    if provider_name == "aktools":
        return AkToolsProvider()
    if provider_name == "akshare":
        return AkShareRealtimeProvider()
    raise ValueError(f"Unsupported realtime provider: {provider}")


def records_from_frame(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    result = df.where(pd.notna(df), None).to_dict(orient="records")
    return [{str(key): value for key, value in row.items()} for row in result]


def demo_quote_records() -> list[dict[str, Any]]:
    return [quote.model_dump() for quote in get_demo_quotes()]


def write_data_feedback(
    *,
    title: str,
    summary: str,
    provider: str,
    symbols: list[str],
    exc: Exception | None = None,
) -> str | None:
    return get_feedback_service().write_bug_report(
        component="data_gateway",
        title=title,
        summary=summary,
        severity="medium",
        user_action="Refresh realtime quotes",
        endpoint_or_page="/product/quotes",
        exception_type=type(exc).__name__ if exc else "",
        exception_message=str(exc) if exc else "",
        sanitized_traceback=traceback.format_exc() if exc else "",
        runtime_context={"provider": provider, "symbols": symbols},
        reproduction_steps=[
            "Open product dashboard",
            "Select Realtime Market",
            "Refresh realtime quotes",
        ],
        related_log_files=["logs/quant_trading.log"],
    )


def fetch_product_quotes(
    symbols: str | list[str] | tuple[str, ...] | None = None,
    *,
    provider: str | None = None,
    allow_demo: bool = True,
    force_live: bool = False,
) -> dict[str, Any]:
    """Fetch product quotes with explicit provider and demo fallback status."""
    normalized_symbols = parse_symbols(symbols)
    provider_name = (provider or DEFAULT_DATA_PROVIDER or "akshare").lower()

    if allow_demo and is_demo_mode() and not force_live:
        return {
            "status": "demo",
            "provider": "demo",
            "requested_provider": provider_name,
            "is_demo": True,
            "timestamp": now_text(),
            "symbols": normalized_symbols,
            "quotes": demo_quote_records(),
            "messages": ["Market is closed or demo mode is enabled; using deterministic demo data."],
        }

    try:
        quote_provider = build_realtime_provider(provider_name)
        df = quote_provider.get_realtime_quotes(normalized_symbols)
        quotes = records_from_frame(df)
        if quotes:
            return {
                "status": "ok",
                "provider": provider_name,
                "requested_provider": provider_name,
                "is_demo": False,
                "timestamp": now_text(),
                "symbols": normalized_symbols,
                "quotes": quotes,
                "messages": [],
            }

        # Provider returned empty — decide whether to create a bug report.
        # Outside trading hours, empty results are expected (no live quotes).
        # During trading hours, this is a genuine data-source issue.
        bug_id = None
        if is_trading_hours():
            bug_id = write_data_feedback(
                title="Realtime provider returned no quotes",
                summary=f"{provider_name} returned no rows for {', '.join(normalized_symbols)}",
                provider=provider_name,
                symbols=normalized_symbols,
            )

        if allow_demo:
            return {
                "status": "fallback_demo",
                "provider": provider_name,
                "requested_provider": provider_name,
                "is_demo": True,
                "timestamp": now_text(),
                "symbols": normalized_symbols,
                "quotes": demo_quote_records(),
                "messages": [
                    "Realtime provider returned no quotes; fallback demo data is displayed."
                    + (" (non-trading hours, expected)" if not is_trading_hours() else "")
                ],
                "bug_id": bug_id,
            }
        return {
            "status": "empty",
            "provider": provider_name,
            "requested_provider": provider_name,
            "is_demo": False,
            "timestamp": now_text(),
            "symbols": normalized_symbols,
            "quotes": [],
            "messages": ["Realtime provider returned no quotes."],
            "bug_id": bug_id,
        }
    except Exception as exc:
        # Only file bug reports during trading hours — outside trading hours
        # provider failures are expected (API maintenance, no live data).
        bug_id = None
        if is_trading_hours():
            bug_id = write_data_feedback(
                title="Realtime quote refresh failed",
                summary=f"{provider_name} realtime quote refresh failed: {exc}",
                provider=provider_name,
                symbols=normalized_symbols,
                exc=exc,
            )
        if allow_demo:
            return {
                "status": "fallback_demo",
                "provider": provider_name,
                "requested_provider": provider_name,
                "is_demo": True,
                "timestamp": now_text(),
                "symbols": normalized_symbols,
                "quotes": demo_quote_records(),
                "messages": [f"Realtime provider failed; fallback demo data is displayed. bug_id={bug_id}"],
                "bug_id": bug_id,
            }
        return {
            "status": "error",
            "provider": provider_name,
            "requested_provider": provider_name,
            "is_demo": False,
            "timestamp": now_text(),
            "symbols": normalized_symbols,
            "quotes": [],
            "messages": [str(exc)],
            "bug_id": bug_id,
        }


__all__ = [
    "now_text",
    "is_trading_hours",
    "default_symbols",
    "parse_symbols",
    "build_realtime_provider",
    "records_from_frame",
    "demo_quote_records",
    "write_data_feedback",
    "fetch_product_quotes",
    # New contract symbols
    "AuthRequirement",
    "CachePolicy",
    "CallerContext",
    "DataQualityMetadata",
    "FallbackEligibility",
    "FreshnessPolicy",
    "ItemError",
    "MarketBar",
    "MarketDataProviderContract",
    "MarketDataUnavailableError",
    "MarketQuote",
    "MultiSymbolQuoteResult",
    "ProviderAttempt",
    "ProviderErrorCategory",
    "QualityGate",
    "QualityStatus",
    "RateLimitPolicy",
    "TimeoutPolicy",
    "redact_secret",
    "safe_error_summary",
    # Phase 3 symbols
    "AuditRecorder",
    "MarketDataAuditEvent",
    "CachedEntry",
    "MarketDataCache",
    "ProviderHealthAggregator",
    "MarketDataRelay",
]
