from __future__ import annotations

import json

from scripts.summarize_feedback_bugs import classify_bug, summarize_bug_dir


def test_classify_dashboard_timeout():
    bug = {"summary": "GET /product/live-data/quotes failed: read timeout=8", "component": "dashboard"}

    assert classify_bug(bug) == "dashboard_timeout"


def test_classify_provider_capability_gap():
    bug = {"summary": "AkToolsProvider object has no attribute get_fundamentals"}

    assert classify_bug(bug) == "provider_capability_gap"


def test_summarize_bug_dir(tmp_path):
    open_dir = tmp_path / "feedback" / "bugs" / "open"
    open_dir.mkdir(parents=True)
    (open_dir / "BUG_TEST.json").write_text(
        json.dumps({"bug_id": "BUG_TEST", "summary": "read timeout=8", "component": "dashboard"}),
        encoding="utf-8",
    )

    result = summarize_bug_dir(open_dir)

    assert result["total"] == 1
    assert result["by_category"]["dashboard_timeout"] == 1
