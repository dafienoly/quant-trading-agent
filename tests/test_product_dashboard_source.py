from __future__ import annotations

from pathlib import Path


def test_product_dashboard_has_readable_product_sections():
    dashboard_source = Path("src/ui_report/product_dashboard.py").read_text(encoding="utf-8")
    i18n_source = Path("src/ui_report/i18n.py").read_text(encoding="utf-8")
    routes_source = Path("src/api/product_routes.py").read_text(encoding="utf-8")
    source = dashboard_source + "\n" + i18n_source + "\n" + routes_source

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
        "AI Factor Discovery",
        "AI Research Ranking",
        "AI Signal Explanation",
        "AI output is research/explanation only",
    ):
        assert label in source

    for mojibake in ("绯荤", "琛屾儨", "閰嶇疆", "鍙嶉"):
        assert mojibake not in source


def test_bugfix_merge_endpoint_strings_exist():
    """Required bugfix API endpoint strings exist in product_routes.py."""
    source = Path("src/api/product_routes.py").read_text(encoding="utf-8")
    assert "/merge" in source or "merge" in source
    assert "cleanup-worktree" in source


def test_bugfix_button_labels_in_dashboard():
    """Required bugfix action strings exist in API routes or dashboard i18n."""
    routes = Path("src/api/product_routes.py").read_text(encoding="utf-8")
    i18n = Path("src/ui_report/i18n.py").read_text(encoding="utf-8")
    combined = routes + i18n
    for term in ("merge", "cleanup-worktree", "merge_bug_fix", "cleanup_worktree"):
        assert term in combined, f"Required term '{term}' not found in routes or i18n"
