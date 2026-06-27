from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.product_app.quality_index import build_quality_summary


def test_quality_summary_empty_repo(tmp_path):
    summary = build_quality_summary(tmp_path)

    assert summary.contract_version == "quality_index.summary.v1"
    assert summary.readonly is True
    assert summary.total_count == 0
    assert summary.open_count == 0
    assert summary.resolved_count == 0
    assert summary.invalid_count == 0
    assert summary.scanned_roots == ["feedback/bugs/open", "feedback/bugs/resolved"]


def test_quality_summary_indexes_open_and_resolved_items(tmp_path):
    open_dir = tmp_path / "feedback" / "bugs" / "open"
    resolved_dir = tmp_path / "feedback" / "bugs" / "resolved"
    open_dir.mkdir(parents=True)
    resolved_dir.mkdir(parents=True)
    (open_dir / "Q_001.json").write_text(
        json.dumps(
            {
                "id": "Q_001",
                "state": "open",
                "priority": "p1",
                "source_stage": "claude_tester",
                "route_back_to": "claude_developer",
                "title": "Route stage feedback",
                "summary": "A safe short summary.",
                "evidence_paths": ["docs/test_reports/r.md"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (resolved_dir / "Q_002.yaml").write_text(
        "id: Q_002\nstate: resolved\npriority: p3\ntitle: Done\n",
        encoding="utf-8",
    )

    summary = build_quality_summary(tmp_path)

    assert summary.total_count == 2
    assert summary.open_count == 1
    assert summary.resolved_count == 1
    assert summary.priority_counts == {"p1": 1, "p3": 1}
    assert summary.state_counts == {"open": 1, "resolved": 1}
    first = summary.items[0]
    assert first.item_path.startswith("feedback/bugs/")
    assert first.related_paths == ["docs/test_reports/r.md"]


def test_quality_summary_parses_markdown_feedback(tmp_path):
    open_dir = tmp_path / "feedback" / "bugs" / "open"
    open_dir.mkdir(parents=True)
    (open_dir / "Q_003.md").write_text(
        "# Markdown Feedback\n\nid: Q_003\npriority: high\nsource_stage: claude_tester\nsummary: concise note\n",
        encoding="utf-8",
    )

    summary = build_quality_summary(tmp_path)

    assert summary.total_count == 1
    item = summary.items[0]
    assert item.item_id == "Q_003"
    assert item.priority.value == "p1"
    assert item.state.value == "open"
    assert item.title == "Markdown Feedback"
    assert item.safe_summary == "concise note"


def test_quality_summary_marks_invalid_json(tmp_path):
    open_dir = tmp_path / "feedback" / "bugs" / "open"
    open_dir.mkdir(parents=True)
    (open_dir / "broken.json").write_text("{", encoding="utf-8")

    summary = build_quality_summary(tmp_path)

    assert summary.total_count == 1
    assert summary.invalid_count == 0
    assert summary.items[0].state.value == "open"
    assert summary.items[0].parse_notes == ["invalid json"]


def test_quality_summary_skips_unsupported_files(tmp_path):
    open_dir = tmp_path / "feedback" / "bugs" / "open"
    open_dir.mkdir(parents=True)
    (open_dir / "skip.exe").write_text("no", encoding="utf-8")

    summary = build_quality_summary(tmp_path)

    assert summary.total_count == 0
    assert summary.warnings == ["skipped unsupported file: feedback/bugs/open/skip.exe"]


def test_quality_index_cli_outputs_json():
    result = subprocess.run(
        [sys.executable, "scripts/quality_index_summary.py", "--repo-root", "."],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    payload = json.loads(result.stdout)

    assert payload["contract_version"] == "quality_index.summary.v1"
    assert payload["readonly"] is True
    assert payload["scanned_roots"] == ["feedback/bugs/open", "feedback/bugs/resolved"]
