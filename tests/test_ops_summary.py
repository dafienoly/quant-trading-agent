from __future__ import annotations

import json
import subprocess
import sys

from src.product_app.ops_summary import build_ops_summary


def test_ops_summary_empty_repo_has_stable_shape(tmp_path):
    summary = build_ops_summary(tmp_path)

    assert summary.contract_version == "ops_summary.v1"
    assert summary.readonly is True
    assert summary.repo_root == tmp_path.resolve().as_posix()
    assert [section.name for section in summary.sections] == [
        "runtime_profiles",
        "quality_summary",
        "roadmap_docs",
    ]
    assert len(summary.runtime_profiles) == 9
    assert summary.quality_summary["contract_version"] == "quality_index.summary.v1"
    assert summary.overall_status in {"pass", "warn", "unknown"}


def test_ops_summary_uses_quality_counts(tmp_path):
    item_dir = tmp_path / "feedback" / "bugs" / "open"
    item_dir.mkdir(parents=True)
    (item_dir / "Q_001.json").write_text(
        json.dumps({"id": "Q_001", "state": "open", "priority": "p1"}),
        encoding="utf-8",
    )

    summary = build_ops_summary(tmp_path)

    assert summary.quality_summary["total_count"] == 1
    assert summary.quality_summary["open_count"] == 1
    quality_section = next(section for section in summary.sections if section.name == "quality_summary")
    assert quality_section.status == "warn"
    assert "open=1" in quality_section.note


def test_ops_summary_runtime_profiles_are_secret_safe(tmp_path):
    summary = build_ops_summary(tmp_path, stages=("codex_pm", "runtime_preflight"))
    text = summary.model_dump_json()

    assert len(summary.runtime_profiles) == 2
    assert "CODEX_A_PM_AGENT_COMMAND" in text
    assert "Invoke-Expression" not in text
    assert "SECRET" not in text


def test_ops_summary_roadmap_docs_pass_when_present(tmp_path):
    roadmap = tmp_path / "docs" / "roadmap"
    roadmap.mkdir(parents=True)
    (roadmap / "MASTER_ROADMAP.md").write_text("# roadmap\n", encoding="utf-8")
    (roadmap / "README.md").write_text("# readme\n", encoding="utf-8")

    summary = build_ops_summary(tmp_path)

    roadmap_section = next(section for section in summary.sections if section.name == "roadmap_docs")
    assert roadmap_section.available is True
    assert roadmap_section.status == "pass"


def test_ops_summary_cli_outputs_json():
    result = subprocess.run(
        [sys.executable, "scripts/ops_summary.py", "--repo-root", "."],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    payload = json.loads(result.stdout)

    assert payload["contract_version"] == "ops_summary.v1"
    assert payload["readonly"] is True
    assert {section["name"] for section in payload["sections"]} == {
        "runtime_profiles",
        "quality_summary",
        "roadmap_docs",
    }
