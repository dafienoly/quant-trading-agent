"""Tests for Agent Pipeline Dashboard / Report Viewer.

Self-contained tests that do not require pandas, fastapi, akshare,
external services, GitHub API, or network access.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.agent_pipeline_report_viewer import (
    DashboardModel,
    build_model,
    build_stage_timeline,
    group_checks_by_category,
    load_gate_status,
    load_regression_report,
    render_dashboard_html,
    render_json_summary,
    scan_artifact_inventory,
    summarize_checks,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "agent_pipeline_report_viewer.py"
V13_REPORT = REPO_ROOT / ".agent" / "reports" / "v13_pipeline_regression.json"


# -- helpers ----------------------------------------------------------------

def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + list(args),
        capture_output=True, text=True, cwd=REPO_ROOT, timeout=30,
    )


def _fixture_report(tmp_path: Path, status: str = "pass") -> Path:
    """Create a minimal regression report fixture."""
    report = {
        "status": status,
        "summary": {"critical_count": 0, "warning_count": 0, "info_count": 0},
        "checks": [
            {"name": "workflow_has_codex_pm", "severity": "critical", "passed": True, "message": "ok"},
            {"name": "workflow_has_codex_architect", "severity": "critical", "passed": True, "message": "ok"},
            {"name": "runner_no_Register", "severity": "warning", "passed": False, "message": "warn"},
            {"name": "restricted_diff", "severity": "critical", "passed": True, "message": "clean"},
            {"name": "gitignore_agent_tmp", "severity": "critical", "passed": True, "message": "ok"},
            {"name": "agent_tmp_not_tracked", "severity": "critical", "passed": True, "message": "ok"},
        ],
        "artifacts": {},
    }
    p = tmp_path / "fixture_report.json"
    p.write_text(json.dumps(report, indent=2))
    return p


def _fixture_gate(tmp_path: Path, name: str, passed: bool = True) -> Path:
    """Create a minimal gate fixture."""
    gates_dir = tmp_path / ".agent" / "gates"
    gates_dir.mkdir(parents=True, exist_ok=True)
    gate = {
        "passed": passed,
        "feature_id": "test",
        "found": {"test": ["docs/test/test.md"]},
        "missing": {},
        "reasons": ["test"],
    }
    p = gates_dir / f"{name}.json"
    p.write_text(json.dumps(gate, indent=2))
    return p


# -- CLI tests --------------------------------------------------------------

def test_cli_rejects_missing_input():
    proc = _run("--input", "/nonexistent/file.json", "--json-summary")
    assert proc.returncode != 0


def test_cli_rejects_malformed_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("not json")
    proc = _run("--input", str(bad), "--json-summary")
    assert proc.returncode != 0


def test_cli_requires_output_unless_json_summary(tmp_path):
    report = _fixture_report(tmp_path)
    proc = _run("--input", str(report))
    assert proc.returncode != 0


def test_cli_json_summary_works(tmp_path):
    report = _fixture_report(tmp_path)
    proc = _run("--input", str(report), "--json-summary")
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["status"] == "pass"


def test_cli_generates_html(tmp_path):
    report = _fixture_report(tmp_path)
    out = tmp_path / "dashboard.html"
    proc = _run("--input", str(report), "--output", str(out))
    assert proc.returncode == 0
    assert out.exists()
    assert out.stat().st_size > 0


# -- Function tests ---------------------------------------------------------

def test_load_valid_report(tmp_path):
    p = _fixture_report(tmp_path)
    report = load_regression_report(p)
    assert report["status"] == "pass"
    assert len(report["checks"]) == 6


def test_load_missing_report():
    with pytest.raises(FileNotFoundError):
        load_regression_report("/nonexistent/report.json")


def test_load_malformed_report(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{invalid")
    with pytest.raises(ValueError):
        load_regression_report(p)


def test_load_incomplete_report(tmp_path):
    p = tmp_path / "incomplete.json"
    p.write_text('{"foo": "bar"}')
    with pytest.raises(ValueError):
        load_regression_report(p)


def test_summarize_counts(tmp_path):
    report = load_regression_report(_fixture_report(tmp_path))
    summary = summarize_checks(report)
    assert summary["critical_count"] == 0
    assert summary["warning_count"] == 1
    assert summary["total_checks"] == 6


def test_group_checks_by_category(tmp_path):
    report = load_regression_report(_fixture_report(tmp_path))
    cats = group_checks_by_category(report)
    assert "工作流" in cats
    assert "运行器" in cats
    assert "受限文件" in cats
    assert "运行期临时目录" in cats


def test_html_contains_status(tmp_path):
    report = load_regression_report(_fixture_report(tmp_path))
    model = DashboardModel()
    model.status = "pass"
    model.checks = report["checks"]
    model.summary = summarize_checks(report)
    model.categories = group_checks_by_category(report)
    model.gates = {}
    model.artifacts = {}
    model.stage_timeline = build_stage_timeline(report, {}, {})
    model.restricted = {}
    model.temp_hygiene = {}
    html = render_dashboard_html(model)
    assert "状态：通过" in html
    assert '<html lang="zh-CN">' in html


def test_html_contains_summary_counts(tmp_path):
    report = load_regression_report(_fixture_report(tmp_path))
    model = DashboardModel()
    model.status = "pass"
    model.checks = report["checks"]
    model.summary = summarize_checks(report)
    model.categories = group_checks_by_category(report)
    model.gates = {}
    model.artifacts = {}
    model.stage_timeline = build_stage_timeline(report, {}, {})
    model.restricted = {}
    model.temp_hygiene = {}
    html = render_dashboard_html(model)
    assert "检查总数" in html
    assert "6" in html


def test_html_contains_category_table(tmp_path):
    report = load_regression_report(_fixture_report(tmp_path))
    model = DashboardModel()
    model.status = "pass"
    model.checks = report["checks"]
    model.summary = summarize_checks(report)
    model.categories = group_checks_by_category(report)
    model.gates = {}
    model.artifacts = {}
    model.stage_timeline = build_stage_timeline(report, {}, {})
    model.restricted = {}
    model.temp_hygiene = {}
    html = render_dashboard_html(model)
    assert "分类统计" in html


def test_html_contains_stage_timeline(tmp_path):
    report = load_regression_report(_fixture_report(tmp_path))
    model = DashboardModel()
    model.status = "pass"
    model.checks = report["checks"]
    model.summary = summarize_checks(report)
    model.categories = group_checks_by_category(report)
    model.gates = {}
    model.artifacts = {}
    model.stage_timeline = build_stage_timeline(report, {}, {})
    model.restricted = {}
    model.temp_hygiene = {}
    html = render_dashboard_html(model)
    assert "Pipeline 阶段时间线" in html


def test_html_contains_gate_status(tmp_path):
    report = load_regression_report(_fixture_report(tmp_path))
    model = DashboardModel()
    model.status = "pass"
    model.checks = report["checks"]
    model.summary = summarize_checks(report)
    model.categories = group_checks_by_category(report)
    model.gates = {"pm": {"passed": True}}
    model.artifacts = {}
    model.stage_timeline = build_stage_timeline(report, model.gates, {})
    model.restricted = {}
    model.temp_hygiene = {}
    html = render_dashboard_html(model)
    assert "门禁状态" in html


def test_html_contains_artifact_inventory(tmp_path):
    report = load_regression_report(_fixture_report(tmp_path))
    model = DashboardModel()
    model.status = "pass"
    model.checks = report["checks"]
    model.summary = summarize_checks(report)
    model.categories = group_checks_by_category(report)
    model.gates = {}
    model.artifacts = {"docs/requirements": ["test.md"]}
    model.stage_timeline = build_stage_timeline(report, {}, model.artifacts)
    model.restricted = {}
    model.temp_hygiene = {}
    html = render_dashboard_html(model)
    assert "文档产物清单" in html


def test_html_contains_raw_json(tmp_path):
    report = load_regression_report(_fixture_report(tmp_path))
    model = DashboardModel()
    model.status = "pass"
    model.checks = report["checks"]
    model.summary = summarize_checks(report)
    model.categories = group_checks_by_category(report)
    model.gates = {}
    model.artifacts = {}
    model.stage_timeline = build_stage_timeline(report, {}, {})
    model.restricted = {}
    model.temp_hygiene = {}
    model.raw_report = report
    html = render_dashboard_html(model)
    assert "原始 JSON" in html


def test_html_contains_failed_checks_section(tmp_path):
    report = load_regression_report(_fixture_report(tmp_path))
    model = DashboardModel()
    model.status = "fail"
    model.checks = report["checks"]
    model.summary = summarize_checks(report)
    model.categories = group_checks_by_category(report)
    model.gates = {}
    model.artifacts = {}
    model.stage_timeline = build_stage_timeline(report, {}, {})
    model.restricted = {}
    model.temp_hygiene = {}
    html = render_dashboard_html(model)
    assert "失败与警告项" in html


def test_json_summary_valid(tmp_path):
    report = load_regression_report(_fixture_report(tmp_path))
    model = DashboardModel()
    model.status = "pass"
    model.input_path = str(tmp_path / "fixture_report.json")
    model.output_path = "/dev/null"
    model.checks = report["checks"]
    model.summary = summarize_checks(report)
    model.categories = group_checks_by_category(report)
    summary_str = render_json_summary(model)
    data = json.loads(summary_str)
    assert data["status"] == "pass"
    assert "summary" in data
    assert "categories" in data


def test_load_gate_status_detects_gates(tmp_path):
    _fixture_gate(tmp_path, "pm_gate", passed=True)
    gates = load_gate_status(tmp_path)
    assert "pm_gate" in gates
    assert gates["pm_gate"]["passed"] is True


def test_scan_artifact_inventory_discovers_files(tmp_path):
    d = tmp_path / "docs" / "features" / "agentops"
    d.mkdir(parents=True, exist_ok=True)
    (d / "acceptance.md").write_text("ok")
    (d / ".gitkeep").write_text("")
    arts = scan_artifact_inventory(tmp_path)
    assert "docs/features" in arts
    files = [f for f in arts["docs/features"] if ".gitkeep" not in f]
    assert len(files) == 1


def test_scan_artifact_inventory_excludes_gitkeep(tmp_path):
    d = tmp_path / "docs" / "review"
    d.mkdir(parents=True, exist_ok=True)
    (d / ".gitkeep").write_text("")
    arts = scan_artifact_inventory(tmp_path)
    if "docs/review" in arts:
        assert all(".gitkeep" not in f for f in arts["docs/review"])


def test_load_gate_status_returns_empty_for_missing_dir(tmp_path):
    gates = load_gate_status(tmp_path / "nonexistent")
    assert gates == {}


def test_healthy_fixture_renders_successfully(tmp_path):
    """A minimal healthy fixture produces a valid HTML dashboard."""
    report = _fixture_report(tmp_path)
    out = tmp_path / "dashboard.html"
    proc = _run("--input", str(report), "--output", str(out))
    assert proc.returncode == 0
    assert out.exists()
    html = out.read_text()
    assert "状态：通过" in html
    assert "summary-grid" in html
    assert "分类统计" in html
    assert "全部检查项" in html


def test_server_defaults_to_localhost():
    """Configuration logic defaults to 127.0.0.1, not 0.0.0.0."""
    from scripts.agent_pipeline_report_viewer import serve_dashboard
    import inspect
    sig = inspect.signature(serve_dashboard)
    assert sig.parameters["host"].default == "127.0.0.1"


def test_build_model_integration(tmp_path):
    """Full build_model pipeline with fixture report works."""
    report_p = _fixture_report(tmp_path)
    model = build_model(str(report_p), str(tmp_path / "out.html"), repo_root=tmp_path)
    assert model.status == "pass"
    assert len(model.checks) == 6
    assert model.summary["total_checks"] == 6
    assert model.categories is not None
    assert model.stage_timeline is not None
    assert model.gates is not None
