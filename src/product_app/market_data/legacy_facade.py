"""Legacy facade — migrated from flat src/product_app/market_data.py.

All implementation lives in __init__.py for backward-compatible patching
by existing tests. This module re-exports all public symbols from __init__
for documentation and import clarity.
"""
from __future__ import annotations

from src.product_app.market_data import (
    build_realtime_provider,
    default_symbols,
    demo_quote_records,
    fetch_product_quotes,
    is_trading_hours,
    now_text,
    parse_symbols,
    records_from_frame,
    write_data_feedback,
)

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
]
