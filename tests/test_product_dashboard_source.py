from __future__ import annotations

from pathlib import Path


def test_product_dashboard_has_readable_product_sections():
    dashboard_source = Path("src/ui_report/product_dashboard.py").read_text(encoding="utf-8")
    i18n_source = Path("src/ui_report/i18n.py").read_text(encoding="utf-8")
    source = dashboard_source + "\n" + i18n_source

    for label in (
        "System",
        "Realtime Market",
        "Watchlist",
        "Factor Lab",
        "Backtest",
        "Signals",
        "Human Confirmation",
        "Configuration",
        "Feedback",
        "Data provider",
        "Force realtime fetch",
        "BugFix Agent",
        "Start BugFix Agent",
    ):
        assert label in source

    for mojibake in ("绯荤", "琛屾儏", "閰嶇疆", "鍙嶉"):
        assert mojibake not in source
