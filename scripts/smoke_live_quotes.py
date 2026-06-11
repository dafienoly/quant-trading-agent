#!/usr/bin/env python3
"""Market-hours smoke script for A-share live realtime quotes.

Usage:
    .venv/bin/python scripts/smoke_live_quotes.py \
        --symbols 600000.SH,000001.SZ,600584.SH,002463.SZ,603986.SH,601138.SH,000021.SZ,600703.SH,603228.SH,002371.SZ \
        --min-success 10 \
        --output docs/test_reports/2026-06-11-a-share-live-quote-smoke.json

Exit codes:
    0: realtime acceptance smoke passed.
    1: script error or invalid arguments.
    2: providers failed closed; safety preserved but product acceptance fails.
    3: providers returned data, but fewer than --min-success symbols were usable.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def _asia_shanghai_now() -> datetime:
    """Return current datetime in Asia/Shanghai timezone."""
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo("Asia/Shanghai")
        return datetime.now(tz)
    except Exception:
        # Fallback to UTC+8
        return datetime.now(timezone.utc).replace(tzinfo=timezone.utc)


def _trading_session(dt: datetime | None = None) -> str:
    """Determine current A-share trading session.

    Returns one of: "pre_open", "continuous_auction", "lunch_break",
    "afternoon_auction", "close", "closed".
    """
    if dt is None:
        dt = _asia_shanghai_now()

    # A-share trading sessions on trading days:
    # 09:15-09:25 集合竞价 (pre-open call auction)
    # 09:30-11:30 连续竞价 (morning continuous auction)
    # 11:30-13:00 午休 (lunch break)
    # 13:00-15:00 连续竞价 (afternoon continuous auction)
    # 15:00-15:30 盘后固定价格交易 (after-hours fixed price)
    hour = dt.hour
    minute = dt.minute

    # Not handling weekday check here; caller should decide.
    if hour < 9 or hour >= 15:
        return "closed"
    if hour == 9:
        if minute < 15:
            return "pre_open"
        if minute < 25:
            return "call_auction"
        if minute < 30:
            return "pre_open"
        return "continuous_auction"
    if hour == 11 and minute >= 30:
        return "lunch_break"
    if hour == 12:
        return "lunch_break"
    if 13 <= hour < 15:
        return "continuous_auction"
    if hour == 15 and minute < 30:
        return "after_hours"
    return "continuous_auction"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="A-share live realtime quote acceptance smoke test"
    )
    parser.add_argument(
        "--symbols",
        required=True,
        help="Comma-separated symbols, e.g. 600000.SH,000001.SZ",
    )
    parser.add_argument(
        "--min-success",
        type=int,
        default=10,
        help="Minimum number of symbols that must return usable data (default: 10)",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Path to write JSON report (e.g. docs/test_reports/smoke.json)",
    )
    parser.add_argument(
        "--allow-demo",
        action="store_true",
        default=False,
        help="Allow demo data fallback (for testing only, not for acceptance)",
    )

    args = parser.parse_args()
    symbol_list = [s.strip() for s in args.symbols.split(",") if s.strip()]

    if not symbol_list:
        print("ERROR: No symbols provided", file=sys.stderr)
        return 1

    if args.min_success < 1:
        print("ERROR: --min-success must be >= 1", file=sys.stderr)
        return 1

    run_at = _asia_shanghai_now()
    session = _trading_session(run_at)

    # Build report skeleton
    report: dict = {
        "status": "failed",
        "run_at": run_at.isoformat(),
        "trading_session": session,
        "symbols_requested": len(symbol_list),
        "symbols_succeeded": 0,
        "is_demo": False,
        "provider": "",
        "fallback_chain": [],
        "latency_ms": 0.0,
        "data_status": "FAILED",
        "updated_at_min": "",
        "updated_at_max": "",
        "feedback_bug_id": None,
        "quotes_sample": [],
    }

    # Call LiveDataService
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from src.product_app.live_data_service import get_live_data_service

        service = get_live_data_service()
        result = service.get_realtime_quotes(
            symbol_list,
            pool_type="watchlist",
            allow_demo=args.allow_demo,
        )
    except Exception as exc:
        print(f"ERROR: LiveDataService call failed: {exc}", file=sys.stderr)
        report["fallback_chain"] = [f"service_error: {exc}"]
        _write_report(report, args.output)
        return 1

    # Process result
    data_status = result.get("data_status", "FAILED")
    quotes = result.get("quotes", [])
    report["data_status"] = data_status
    report["provider"] = result.get("chosen_provider", "")
    report["fallback_chain"] = result.get("fallback_chain", [])
    report["latency_ms"] = result.get("data_delay_report", {}).get("elapsed_ms", 0.0)
    report["is_demo"] = result.get("is_demo", False)
    report["feedback_bug_id"] = result.get("feedback_bug_id", None)
    report["symbols_succeeded"] = len(quotes)

    # Collect updated_at range
    if quotes:
        timestamps = [q.get("updated_at", "") for q in quotes if q.get("updated_at")]
        if timestamps:
            timestamps.sort()
            report["updated_at_min"] = timestamps[0]
            report["updated_at_max"] = timestamps[-1]

    # Sample quotes (first few)
    report["quotes_sample"] = [
        {
            "symbol": q.get("symbol", ""),
            "price": q.get("last_price"),
            "volume": q.get("volume"),
            "updated_at": q.get("updated_at", ""),
            "provider": q.get("data_source", report["provider"]),
        }
        for q in quotes[:5]
    ]

    # ── Acceptance gate logic ──────────────────────────────────────

    # Refuse to pass if is_demo=True and --allow-demo was not set
    if report["is_demo"] and not args.allow_demo:
        print("FAILED: Data is demo but --allow-demo was not set")
        report["status"] = "failed"
        _write_report(report, args.output)
        return 2

    # Fail closed
    if data_status == "FAILED":
        print(
            f"FAILED: All providers failed. Chain: {report['fallback_chain']}"
        )
        if report["feedback_bug_id"]:
            print(f"  Feedback bug: {report['feedback_bug_id']}")
        report["status"] = "failed"
        _write_report(report, args.output)
        return 2

    # Partial success
    succeeded = len(quotes)
    if succeeded < args.min_success:
        print(
            f"PARTIAL: Got {succeeded}/{args.symbols_requested} quotes, "
            f"need at least {args.min_success}"
        )
        report["status"] = "partial"
        _write_report(report, args.output)
        return 3

    # Full pass
    print(
        f"PASSED: {succeeded}/{args.symbols_requested} quotes from "
        f"{report['provider']} ({report['latency_ms']:.0f}ms)"
    )
    report["status"] = "passed"
    _write_report(report, args.output)
    print(f"Report written to: {args.output}")
    return 0


def _write_report(report: dict, output_path: str) -> None:
    """Write JSON report to output_path."""
    if not output_path:
        return
    try:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
    except OSError as exc:
        print(f"WARNING: Could not write report to {output_path}: {exc}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
