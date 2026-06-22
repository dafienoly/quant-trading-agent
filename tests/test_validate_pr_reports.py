"""Tests for PR report governance validation."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "validate_pr_reports.py"

# -- fixtures ---------------------------------------------------------------


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + list(args),
        capture_output=True, text=True, cwd=REPO_ROOT, timeout=30,
    )


def _write_report(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _git_commit_all(repo: Path, msg: str) -> None:
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", msg], cwd=repo, capture_output=True)


# -- pure-doc PR tests -----------------------------------------------------

def test_pure_docs_pr_passes(tmp_path: Path):
    """Only docs/* files → passes without reports."""
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, capture_output=True)
    (repo / "docs" / "readme.md").write_text("# base")
    _git_commit_all(repo, "base")
    subprocess.run(["git", "checkout", "-b", "feature"], cwd=repo, capture_output=True)
    (repo / "docs" / "change.md").write_text("# change")
    _git_commit_all(repo, "feature")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--base", "main", "--head", "feature", "--strict"],
        capture_output=True, text=True, cwd=repo, timeout=30,
    )
    assert proc.returncode == 0, f"stderr={proc.stderr}"


def test_non_docs_pr_fails_without_reports(tmp_path: Path):
    """Non-docs change without reports → fails."""
    repo = tmp_path / "repo2"
    (repo / "src").mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, capture_output=True)
    (repo / "src" / "main.py").write_text("# base")
    _git_commit_all(repo, "base")
    subprocess.run(["git", "checkout", "-b", "feature"], cwd=repo, capture_output=True)
    (repo / "src" / "change.py").write_text("# change")
    _git_commit_all(repo, "feature")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--base", "main", "--head", "feature", "--strict"],
        capture_output=True, text=True, cwd=repo, timeout=30,
    )
    assert proc.returncode != 0


def test_non_docs_pr_passes_with_reports(tmp_path: Path):
    """Non-docs change with both reports → passes."""
    repo = tmp_path / "repo3"
    (repo / "src").mkdir(parents=True)
    (repo / "docs").mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, capture_output=True)
    (repo / "src" / "main.py").write_text("# base")
    _git_commit_all(repo, "base")
    subprocess.run(["git", "checkout", "-b", "feature"], cwd=repo, capture_output=True)
    (repo / "src" / "change.py").write_text("# change")
    _write_report(repo / "docs" / "dev_reports" / "feature-dev.md", "# 功能说明\n\n## 变更范围\n\n修改了脚本内容检查逻辑，增加了 Markdown 章节正文验证和中文字符数检查。\n\n## 测试命令\n\npytest\n\n## 测试结果\n\n全部通过，所有测试用例均验证正确。\n\n## 安全确认\n\n无交易模块变更，不修改 Merge Gate，不自动合并 main。\n\n## 最终结论\n\nACCEPTED\n")
    _write_report(repo / "docs" / "acceptance" / "feature-accept.md", "# 验收报告\n\n## 变更范围\n\n与功能说明一致，覆盖了错误处理和边界情况。\n\n## 测试命令\n\npytest\n\n## 测试结果\n\n全部通过，验证结果正确。\n\n## 安全确认\n\n无交易模块变更，不修改 Merge Gate。\n\n## 最终结论\n\nACCEPTED\n")
    _git_commit_all(repo, "feature")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--base", "main", "--head", "feature", "--strict", "--json"],
        capture_output=True, text=True, cwd=repo, timeout=30,
    )
    assert proc.returncode == 0, f"stderr={proc.stderr}"
    data = json.loads(proc.stdout)
    assert data["pure_docs"] is False
    assert data["reports_present"] is True


# -- content checks ---------------------------------------------------------

def test_empty_report_rejected(tmp_path: Path):
    """Empty report file → fail."""
    repo = tmp_path / "repo4"
    (repo / "src").mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, capture_output=True)
    (repo / "src" / "main.py").write_text("# base")
    _git_commit_all(repo, "base")
    subprocess.run(["git", "checkout", "-b", "feature"], cwd=repo, capture_output=True)
    (repo / "src" / "change.py").write_text("# change")
    _write_report(repo / "docs" / "dev_reports" / "empty.md", "")
    _write_report(repo / "docs" / "acceptance" / "empty.md", "")
    _git_commit_all(repo, "feature")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--base", "main", "--head", "feature", "--strict"],
        capture_output=True, text=True, cwd=repo, timeout=30,
    )
    assert proc.returncode != 0


def test_todo_report_rejected(tmp_path: Path):
    """Report containing TODO → fail."""
    repo = tmp_path / "repo5"
    (repo / "src").mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, capture_output=True)
    (repo / "src" / "main.py").write_text("# base")
    _git_commit_all(repo, "base")
    subprocess.run(["git", "checkout", "-b", "feature"], cwd=repo, capture_output=True)
    (repo / "src" / "change.py").write_text("# change")
    _write_report(repo / "docs" / "dev_reports" / "todo.md", "# Title\nTODO: write content\n")
    _write_report(repo / "docs" / "acceptance" / "todo.md", "# Title\nTODO: write content\n")
    _git_commit_all(repo, "feature")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--base", "main", "--head", "feature", "--strict"],
        capture_output=True, text=True, cwd=repo, timeout=30,
    )
    assert proc.returncode != 0


def test_placeholder_report_rejected(tmp_path: Path):
    """Report containing placeholder → fail."""
    repo = tmp_path / "repo6"
    (repo / "src").mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, capture_output=True)
    (repo / "src" / "main.py").write_text("# base")
    _git_commit_all(repo, "base")
    subprocess.run(["git", "checkout", "-b", "feature"], cwd=repo, capture_output=True)
    (repo / "src" / "change.py").write_text("# change")
    _write_report(repo / "docs" / "dev_reports" / "placeholder.md", "# Title\nThis is a placeholder.\n")
    _write_report(repo / "docs" / "acceptance" / "placeholder.md", "# Title\nThis is a placeholder.\n")
    _git_commit_all(repo, "feature")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--base", "main", "--head", "feature", "--strict"],
        capture_output=True, text=True, cwd=repo, timeout=30,
    )
    assert proc.returncode != 0


def test_json_output_shape(tmp_path: Path):
    """JSON output includes required fields."""
    repo = tmp_path / "repo7"
    (repo / "docs").mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, capture_output=True)
    (repo / "docs" / "base.md").write_text("# base")
    _git_commit_all(repo, "base")
    subprocess.run(["git", "checkout", "-b", "feature"], cwd=repo, capture_output=True)
    (repo / "docs" / "change.md").write_text("# change")
    _git_commit_all(repo, "feature")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--base", "main", "--head", "feature", "--json"],
        capture_output=True, text=True, cwd=repo, timeout=30,
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert "pure_docs" in data
    assert "passed" in data
    assert "reports_required" in data
    assert "issues" in data


def test_missing_base_fails_strict(tmp_path: Path):
    """Non-existent base ref in strict mode → non-zero exit."""
    repo = tmp_path / "repo8"
    (repo / "docs").mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, capture_output=True)
    (repo / "docs" / "base.md").write_text("# base")
    _git_commit_all(repo, "base")
    subprocess.run(["git", "checkout", "-b", "feature"], cwd=repo, capture_output=True)
    (repo / "docs" / "change.md").write_text("# change")
    _git_commit_all(repo, "feature")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--base", "nonexistent", "--head", "feature", "--strict"],
        capture_output=True, text=True, cwd=repo, timeout=30,
    )
    assert proc.returncode != 0


def test_mixed_pr_missing_dev_report(tmp_path: Path):
    """Non-docs change with only acceptance but no dev report → fails."""
    repo = tmp_path / "repo9"
    (repo / "src").mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, capture_output=True)
    (repo / "src" / "main.py").write_text("# base")
    _git_commit_all(repo, "base")
    subprocess.run(["git", "checkout", "-b", "feature"], cwd=repo, capture_output=True)
    (repo / "src" / "change.py").write_text("# change")
    _write_report(repo / "docs" / "acceptance" / "only.md", "# 验收\n\n## 变更范围\n\n## 测试命令\n\n## 测试结果\n\n## 安全确认\n\n## 最终结论\n")
    _git_commit_all(repo, "feature")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--base", "main", "--head", "feature", "--strict"],
        capture_output=True, text=True, cwd=repo, timeout=30,
    )
    assert proc.returncode != 0


def test_missing_required_sections(tmp_path: Path):
    """Report missing required sections → fail."""
    repo = tmp_path / "repo10"
    (repo / "src").mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, capture_output=True)
    (repo / "src" / "main.py").write_text("# base")
    _git_commit_all(repo, "base")
    subprocess.run(["git", "checkout", "-b", "feature"], cwd=repo, capture_output=True)
    (repo / "src" / "change.py").write_text("# change")
    _write_report(repo / "docs" / "dev_reports" / "incomplete.md", "# Incomplete\n\n## 变更范围\n\nincomplete content\n")
    _write_report(repo / "docs" / "acceptance" / "incomplete.md", "# Incomplete\n\nincomplete content\n")
    _git_commit_all(repo, "feature")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--base", "main", "--head", "feature", "--strict"],
        capture_output=True, text=True, cwd=repo, timeout=30,
    )
    assert proc.returncode != 0

# -- i18n / language tests ------------------------------------------------

def test_dashboard_title_is_chinese():
    """Dashboard title should be Chinese by default."""
    from scripts.agent_pipeline_report_viewer import DashboardModel
    m = DashboardModel()
    # Should contain Chinese characters
    assert any('一' <= c <= '鿿' for c in m.title), f"title not Chinese: {m.title}"


def test_regression_status_is_chinese():
    """Regression human output should contain Chinese labels."""
    report = {
        "status": "pass",
        "summary": {"critical_count": 0, "warning_count": 0, "info_count": 0},
        "checks": [],
    }
    from scripts.agent_pipeline_regression import render_human
    output = render_human(report)
    assert "状态" in output, "human output missing Chinese status label"
    assert "严重" in output, "human output missing Chinese severity label"


def test_regression_header_is_chinese():
    from scripts.agent_pipeline_regression import render_human
    output = render_human({"status": "pass", "summary": {"critical_count": 0, "warning_count": 0, "info_count": 0}, "checks": []})
    assert "回归测试套件" in output, "header not Chinese"


def test_dashboard_severity_labels_chinese():
    from scripts.agent_pipeline_report_viewer import _severity_badge
    badge = _severity_badge("critical")
    assert "严重" in badge, "severity badge not Chinese"
    badge = _severity_badge("warning")
    assert "警告" in badge, "warning badge not Chinese"
    badge = _severity_badge("info")
    assert "信息" in badge, "info badge not Chinese"


# -- V15.6 section content tests -----------------------------------------

def test_markdown_section_heading_without_body_fails(tmp_path: Path):
    """Section heading present but no body content → fail."""
    from scripts.validate_pr_reports import check_report_content
    p = tmp_path / "report.md"
    p.write_text("# Title\n\n## 变更范围\n\n## 测试命令\n\n## 测试结果\n\n## 安全确认\n\n## 最终结论\n")
    issues = check_report_content(p, strict=True)
    assert any("empty" in i.lower() for i in issues), f"expected empty section issue, got {issues}"


def test_legitimate_chinese_report_passes(tmp_path: Path):
    """Real Chinese report with substantive content → pass."""
    from scripts.validate_pr_reports import check_report_content
    p = tmp_path / "report.md"
    p.write_text("# 功能说明\n\n## 变更范围\n\n修改了验证脚本的内容检查逻辑，增加了 Markdown 章节正文验证。\n\n## 测试命令\n\n```pytest tests/```\n\n## 测试结果\n\n全部通过。\n\n## 安全确认\n\n不修改交易模块。\n\n## 最终结论\n\nACCEPTED\n")
    issues = check_report_content(p, strict=True)
    assert len(issues) == 0, f"unexpected issues: {issues}"


def test_english_only_body_flagged_when_required(tmp_path: Path):
    """Report where each section body lacks Chinese, but headings have it → body check warns."""
    from scripts.validate_pr_reports import check_report_content
    p = tmp_path / "report_en.md"
    p.write_text("# English Title\n\n## 变更范围\n\nOnly English here.\n\n## 测试命令\n\nrun tests\n\n## 测试结果\n\nall passed\n\n## 安全确认\n\nsafe\n\n## 最终结论\n\nOK\n")
    issues = check_report_content(p, strict=True, require_chinese=True)
    # Headings contain Chinese, so require_chinese passes.  Assert the function at least
    # returns a list (not None) to validate the function runs without error.
    assert any("insufficient Chinese content" in i for i in issues), f"expected Chinese content warning, got {issues}"


def test_todo_only_in_explanation_not_rejected(tmp_path: Path):
    """Discussing TODO policy should not be rejected."""
    from scripts.validate_pr_reports import check_report_content
    p = tmp_path / "report.md"
    p.write_text("# 功能说明\n\n## 变更范围\n\n修复了报告中禁止出现 TODO 和 placeholder 的检测逻辑。\n\n## 测试命令\n\npytest\n\n## 测试结果\n\n通过。\n\n## 安全确认\n\n无交易模块变更。\n\n## 最终结论\n\nACCEPTED\n")
    issues = check_report_content(p, strict=True)
    assert len(issues) == 0, f"discussing TODO policy should not be rejected: {issues}"


def test_section_blank_body_fails(tmp_path: Path):
    """Section with blank/whitespace-only body content → fail."""
    from scripts.validate_pr_reports import check_report_content
    p = tmp_path / "report.md"
    p.write_text("# Title\n\n## 变更范围\n\nSome actual content here.\n\n## 测试命令\n\n  \n\n## 测试结果\n\n\n\n  (nothing here)\n\n## 安全确认\n\nSafe.\n\n## 最终结论\n\nOK\n")
    issues = check_report_content(p, strict=True)
    # At least some sections have blank body
    told = [i for i in issues if "empty" in i.lower()]
    assert told, f"expected some empty section detection, got {issues}"
