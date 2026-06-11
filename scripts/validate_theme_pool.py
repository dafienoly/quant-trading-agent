#!/usr/bin/env python3
"""Validate theme pool JSON data file against architecture contract rules.

Usage:
    .venv/bin/python scripts/validate_theme_pool.py [--path data/reference/theme_pools/ai_semiconductor.json]

Exits with code 0 if valid, 1 if any errors found.
"""
from __future__ import annotations

import json
import re
import sys

SYMBOL_PATTERN = re.compile(r"^\d{6}\.(SH|SZ)$")
MAINBOARD_PREFIXES = ("600", "601", "603", "605", "000", "001", "002", "003")
REQUIRED_TOP_LEVEL = {"pool_id", "name", "version", "updated_at", "data_source", "universe", "tags", "stocks"}
REQUIRED_STOCK_FIELDS = {"symbol", "name", "exchange", "board_type", "tags", "is_st", "is_delisting", "evidence"}
REQUIRED_TAG_IDS = {"ai_chip", "optical_module"}


def validate_theme_pool(payload: dict) -> list[str]:
    errors: list[str] = []

    # --- Top-level fields ---
    for field in REQUIRED_TOP_LEVEL:
        if field not in payload:
            errors.append(f"Missing top-level field: {field}")

    stocks = payload.get("stocks", [])
    tags_list = payload.get("tags", [])

    # --- Tag validation ---
    if not isinstance(tags_list, list):
        errors.append("'tags' must be a list")
    else:
        tag_ids = {tag.get("id") for tag in tags_list if isinstance(tag, dict)}
        missing_tags = REQUIRED_TAG_IDS - tag_ids
        if missing_tags:
            errors.append(f"Required tags missing: {missing_tags}")

    # --- Stock count ---
    if not isinstance(stocks, list):
        errors.append("'stocks' must be a list")
    else:
        if not 100 <= len(stocks) <= 300:
            errors.append(f"Stock count {len(stocks)} must be between 100 and 300")

    # --- Per-stock validation ---
    seen_symbols: set[str] = set()
    for i, item in enumerate(stocks):
        if not isinstance(item, dict):
            errors.append(f"Stock at index {i} is not a dict")
            continue

        symbol = item.get("symbol", f"<index {i}>")

        # Required fields
        for field in REQUIRED_STOCK_FIELDS:
            if field not in item:
                errors.append(f"{symbol}: missing field '{field}'")

        # Duplicate check
        if symbol in seen_symbols:
            errors.append(f"{symbol}: duplicate symbol")
        seen_symbols.add(symbol)

        # Symbol pattern
        if not SYMBOL_PATTERN.match(symbol):
            errors.append(f"{symbol}: does not match pattern ^\\d{{6}}\\.(SH|SZ)$")

        # Mainboard check
        code = symbol.split(".")[0]
        if not code.startswith(MAINBOARD_PREFIXES):
            errors.append(f"{symbol}: non-mainboard symbol (prefix {code[:3]})")

        # Risk fields
        if item.get("is_st"):
            errors.append(f"{symbol}: is_st=True not allowed in main pool")
        if item.get("is_delisting"):
            errors.append(f"{symbol}: is_delisting=True not allowed in main pool")

        # Tag validation
        stock_tags = set(item.get("tags", []))
        if tag_ids:
            unknown = stock_tags - tag_ids
            if unknown:
                errors.append(f"{symbol}: unknown tags {unknown}")
        if not stock_tags:
            errors.append(f"{symbol}: must have at least one tag")

    return errors


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "data/reference/theme_pools/ai_semiconductor.json"

    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    errors = validate_theme_pool(payload)

    if errors:
        print(f"VALIDATION FAILED ({len(errors)} errors):")
        for err in errors:
            print(f"  - {err}")
        return 1

    stocks = payload.get("stocks", [])
    print(f"VALIDATION PASSED: {len(stocks)} stocks, {len(payload.get('tags', []))} tags")
    return 0


if __name__ == "__main__":
    sys.exit(main())
