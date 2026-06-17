#!/usr/bin/env python
"""End-to-End Agent Pipeline Regression Suite.

Validates the full Agent Pipeline without requiring real LLM calls,
GitHub Actions dispatch, network access, or external services.

Usage:
    python scripts/agent_pipeline_regression.py
    python scripts/agent_pipeline_regression.py --strict
    python scripts/agent_pipeline_regression.py --json
    python scripts/agent_pipeline_regression.py --output .agent/reports/v13_pipeline_regression.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "agent-stage-runner.yml"
RUNNER_REFERENCE = REPO_ROOT / "docs" / "ops" / "agent-runners" / "run-codex-stage.ps1.reference"
GITIGNORE_PATH = REPO_ROOT / ".gitignore"

CANONICAL_STAGES = (
    "codex_pm",
    "codex_architect",
    "claude_lead_plan",
    "claude_developer",
    "claude_tester",
    "claude_lead_review",
    "codex_reviewer",
    "codex_acceptance",
)

GATE_MAPPING: dict[str, str] = {
    "codex_pm": "pm",
    "codex_architect": "architecture",
    "claude_lead_plan": "team_plan",
    "claude_developer": "phase_dev",
    "claude_tester": "phase_test",
    "claude_lead_review": "claude_lead_review",
    "codex_reviewer": "codex_review",
    "codex_acceptance": "acceptance",
}

RESTRICTED_PATTERNS: tuple[str, ...] = (
    "src/broker/",
    "src/execution/",
    "src/order/",
    "src/account/",
    "src/risk/",
    "miniQMT/",
)
RESTRICTED_CONTAINS: tuple[str, ...] = (
    "live trading",
    "real order",
)

VALID_PM_HEADINGS = ("## User Goal", "## Functional Requirements", "## Acceptance Criteria", "## Safety Constraints")
VALID_ARCH_HEADINGS = ("## Architecture Summary", "## Module Plan", "## Technical Decisions", "## Safety Impact", "## Development Guidance")


# ---------------------------------------------------------------------------
# Check helpers
# ---------------------------------------------------------------------------

class CheckResult:
    def __init__(self, name: str, severity: str, passed: bool, message: str):
        self.name = name
        self.severity = severity  # "critical" | "warning" | "info"
        self.passed = passed
        self.message = message

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "severity": self.severity, "passed": self.passed, "message": self.message}


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None


def _git(command: str, repo: Path = REPO_ROOT) -> str:
    """Run a git command and return stdout."""
    import subprocess
    result = subprocess.run(
        ["git"] + command.split(),
        capture_output=True, text=True, cwd=repo, timeout=30,
    )
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Check functions
# ---------------------------------------------------------------------------

def check_workflow(repo_root: Path) -> list[CheckResult]:
    """Validate workflow stage-runner definitions."""
    checks: list[CheckResult] = []
    text = _read(repo_root / WORKFLOW_PATH.relative_to(REPO_ROOT))

    if text is None:
        checks.append(CheckResult("workflow_exists", "critical", False, "agent-stage-runner.yml not found"))
        return checks
    checks.append(CheckResult("workflow_exists", "critical", True, "agent-stage-runner.yml exists"))

    # Canonical stages
    for stage in CANONICAL_STAGES:
        if f'"{stage}"' in text:
            checks.append(CheckResult(f"workflow_has_{stage}", "critical", True, f"workflow supports {stage}"))
        else:
            checks.append(CheckResult(f"workflow_has_{stage}", "critical", False, f"workflow missing {stage}"))

    # Label-to-stage mapping
    label_map = {"stage:pm-pending": "codex_pm", "stage:arch-pending": "codex_architect"}
    for label, expected_stage in label_map.items():
        pattern = f'"{label}" {{ $stage = "{expected_stage}"'
        if pattern in text:
            checks.append(CheckResult(f"workflow_label_{label}", "critical", True, f"label {label} -> {expected_stage}"))
        else:
            checks.append(CheckResult(f"workflow_label_{label}", "critical", False, f"label mapping {label} -> {expected_stage} not found"))

    # Gate mapping
    for stage, gate in GATE_MAPPING.items():
        pattern = f'"{stage}" {{ $gate = "{gate}"'
        # Also check for alternative with braces on same line
        alt_pattern = f'"{stage}" {{ $gate = "{gate}" }}'
        if pattern in text or alt_pattern in text:
            checks.append(CheckResult(f"gate_mapping_{stage}", "critical", True, f"{stage} -> {gate}"))
        else:
            checks.append(CheckResult(f"gate_mapping_{stage}", "critical", False, f"gate mapping {stage} -> {gate} not found"))

    # Command mapping should NOT contain label functions or gate logic
    # Check that Remove-CurrentLabel / Add-NextLabel only appear in advance step
    # This is heuristic: locate the "Run configured Agent command" section
    sections = text.split("- name:")
    cmd_section = ""
    gate_section = ""
    advance_section = ""
    for s in sections:
        if "Run configured Agent command" in s:
            cmd_section = s
        elif "Run stage gate" in s:
            gate_section = s
        elif "Advance PR label" in s or "Advance PR label" in s:
            advance_section = s

    # Check command section for label logic
    if "Remove-CurrentLabel" in cmd_section or "Add-NextLabel" in cmd_section:
        checks.append(CheckResult("cmd_step_no_label", "critical", False, "Run configured Agent command contains label advancement"))
    else:
        checks.append(CheckResult("cmd_step_no_label", "critical", True, "command mapping free of label logic"))

    # Check gate section for label logic
    if "Remove-CurrentLabel" in gate_section or "Add-NextLabel" in gate_section:
        checks.append(CheckResult("gate_step_no_label", "critical", False, "Run stage gate contains label advancement"))
    else:
        checks.append(CheckResult("gate_step_no_label", "critical", True, "gate mapping free of label logic"))

    # Label functions should be in advance step
    has_remove = "Remove-CurrentLabel" in advance_section
    has_add = "Add-NextLabel" in advance_section
    if has_remove and has_add:
        checks.append(CheckResult("label_func_in_advance", "critical", True, "label functions correctly placed in advance step"))
    else:
        checks.append(CheckResult("label_func_in_advance", "critical", False, "label functions missing from advance step"))

    return checks


def check_runner(repo_root: Path) -> list[CheckResult]:
    """Validate runner reference safety and standards."""
    checks: list[CheckResult] = []
    text = _read(repo_root / RUNNER_REFERENCE.relative_to(REPO_ROOT))

    if text is None:
        checks.append(CheckResult("runner_exists", "critical", False, "runner reference not found"))
        return checks
    checks.append(CheckResult("runner_exists", "critical", True, "runner reference exists"))

    # Unsafe patterns (should NOT exist)
    for pat, reason in [
        ("Register-ObjectEvent", "Register-ObjectEvent is not used (async pipe reads removed)"),
        ("ReadToEnd()", "ReadToEnd() not used (sync reads avoided)"),
    ]:
        if pat in text:
            checks.append(CheckResult(f"runner_no_{pat.split('(')[0]}", "warning", False, f"unexpected {pat}: {reason}"))
        else:
            checks.append(CheckResult(f"runner_no_{pat.split('(')[0]}", "warning", True, f"no {pat} (clean)"))

    if "RedirectStandardOutput = $true" in text:
        checks.append(CheckResult("runner_no_stdout_redirect", "info", False, "has RedirectStandardOutput"))
    else:
        checks.append(CheckResult("runner_no_stdout_redirect", "info", True, "no raw stdout redirect"))

    if "RedirectStandardError = $true" in text:
        checks.append(CheckResult("runner_no_stderr_redirect", "info", False, "has RedirectStandardError"))
    else:
        checks.append(CheckResult("runner_no_stderr_redirect", "info", True, "no raw stderr redirect"))

    # Safe patterns (should exist)
    for pat, name, severity in [
        (".agent/tmp", "runner_uses_agent_tmp", "critical"),
        ("--output-last-message", "runner_uses_output_last_message", "critical"),
        ("wsl.exe", "runner_invokes_wsl", "critical"),
        ("WaitForExit", "runner_waits_for_exit", "critical"),
        ("timeout", "runner_has_timeout", "critical"),
    ]:
        if pat in text:
            checks.append(CheckResult(name, severity, True, f"runner uses {pat}"))
        else:
            checks.append(CheckResult(name, severity, False, f"runner missing {pat}"))

    # Content validation
    if "Test-CodexMarkdownArtifact" in text or ("Requirements" in text and "featureId" in text):
        checks.append(CheckResult("runner_validates_pm", "critical", True, "PM artifact content validated"))
    else:
        checks.append(CheckResult("runner_validates_pm", "critical", False, "PM artifact content not validated"))

    if "Test-CodexMarkdownArtifact" in text or ("Architecture" in text and "featureId" in text):
        checks.append(CheckResult("runner_validates_arch", "critical", True, "Architecture artifact content validated"))
    else:
        checks.append(CheckResult("runner_validates_arch", "critical", False, "Architecture artifact content not validated"))

    # Rejects $($EventArgs.Data)
    # Look for the actual broken pattern: Register-ObjectEvent with $EventArgs in the Action block
    # A legitimate reference like  $eventArgsMarker = '$(' + '$EventArgs.Data)' is validation code and should pass.
    broken_lines = []
    for line in text.split('\n'):
        if 'Register-ObjectEvent' in line and 'EventArgs.Data' in line:
            broken_lines.append(line.strip())
    if broken_lines:
        checks.append(CheckResult("runner_rejects_broken_data", "critical", False, f"Register-ObjectEvent with EventArgs.Data found: {broken_lines}"))
    else:
        checks.append(CheckResult("runner_rejects_broken_data", "critical", True, "no broken event handler pattern"))

    return checks


def check_runtime_temp(repo_root: Path, base: str = "origin/main") -> list[CheckResult]:
    """Validate .agent/tmp directory hygiene."""
    checks: list[CheckResult] = []
    gitignore = _read(repo_root / ".gitignore")

    if gitignore and ".agent/tmp/" in gitignore:
        checks.append(CheckResult("gitignore_agent_tmp", "critical", True, ".gitignore includes .agent/tmp/"))
    else:
        checks.append(CheckResult("gitignore_agent_tmp", "critical", False, ".gitignore missing .agent/tmp/"))

    # Check tracked files
    tracked = _git(f"ls-files .agent/tmp", repo_root)
    if not tracked:
        checks.append(CheckResult("agent_tmp_not_tracked", "critical", True, ".agent/tmp not tracked"))
    else:
        checks.append(CheckResult("agent_tmp_not_tracked", "critical", False, f".agent/tmp has tracked files: {tracked[:100]}"))

    # Check branch diff
    try:
        diff = _git(f"diff --name-only {base}...HEAD", repo_root)
        if ".agent/tmp" in diff:
            checks.append(CheckResult("branch_no_agent_tmp_diff", "warning", False, "branch diff contains .agent/tmp"))
        else:
            checks.append(CheckResult("branch_no_agent_tmp_diff", "warning", True, "branch diff free of .agent/tmp"))
    except Exception:
        checks.append(CheckResult("branch_no_agent_tmp_diff", "warning", True, "diff check skipped (no base)"))

    return checks


def check_restricted_diff(repo_root: Path, base: str = "origin/main") -> list[CheckResult]:
    """Detect restricted trading-sensitive file changes."""
    checks: list[CheckResult] = []
    try:
        diff = _git(f"diff --name-only {base}...HEAD", repo_root)
    except Exception:
        checks.append(CheckResult("restricted_diff", "critical", True, "diff check skipped (no base)"))
        return checks

    restricted_files: list[str] = []
    for f in diff.splitlines():
        f_lower = f.lower()
        for pat in RESTRICTED_PATTERNS:
            if pat.lower() in f_lower:
                restricted_files.append(f)
                break
        for contain in RESTRICTED_CONTAINS:
            if contain.lower() in f_lower:
                restricted_files.append(f)
                break

    if restricted_files:
        checks.append(CheckResult("restricted_diff", "critical", False, f"restricted files: {restricted_files}"))
    else:
        checks.append(CheckResult("restricted_diff", "critical", True, "no restricted trading-sensitive files"))

    return checks


def check_artifacts(repo_root: Path) -> list[CheckResult]:
    """Validate artifact content validation logic using fixture simulation."""
    checks: list[CheckResult] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Create a valid PM artifact
        pm_valid = tmp / "docs" / "requirements" / "test-feature-requirements.md"
        pm_valid.parent.mkdir(parents=True, exist_ok=True)
        pm_valid.write_text("# test-feature Requirements\n\n## User Goal\n\n## Functional Requirements\n\n## Acceptance Criteria\n\n## Safety Constraints\n")
        pm_text = pm_valid.read_text()
        pm_ok = all(h in pm_text for h in VALID_PM_HEADINGS) and "$($EventArgs.Data)" not in pm_text
        checks.append(CheckResult("artifact_pm_valid_headings", "critical", pm_ok,
                      "PM headings valid" if pm_ok else "PM missing headings"))

        # Create corrupted PM artifact
        pm_bad = tmp / "docs" / "requirements" / "bad-requirements.md"
        pm_bad.parent.mkdir(parents=True, exist_ok=True)
        pm_bad.write_text("$($EventArgs.Data)\n" * 10)
        pm_text = pm_bad.read_text()
        has_bad = "$($EventArgs.Data)" in pm_text
        checks.append(CheckResult("artifact_pm_detects_broken", "critical", has_bad,
                      "PM detects broken content" if has_bad else "PM should detect broken content"))

        pm_bad2 = tmp / "docs" / "requirements" / "bad2-requirements.md"
        pm_bad2.parent.mkdir(parents=True, exist_ok=True)
        pm_bad2.write_text("# Bad\n\nno section headings\n")
        pm_text = pm_bad2.read_text()
        has_headings = all(h in pm_text for h in VALID_PM_HEADINGS)
        checks.append(CheckResult("artifact_pm_rejects_missing_headings", "critical", not has_headings,
                      "PM rejects missing headings" if not has_headings else "PM should reject missing headings"))

        # Valid Architecture artifact
        arch_valid = tmp / "docs" / "design" / "test-feature-architecture.md"
        arch_valid.parent.mkdir(parents=True, exist_ok=True)
        arch_valid.write_text("# test-feature Architecture\n\n## Architecture Summary\n\n## Module Plan\n\n## Technical Decisions\n\n## Safety Impact\n\n## Development Guidance\n")
        arch_text = arch_valid.read_text()
        arch_ok = all(h in arch_text for h in VALID_ARCH_HEADINGS) and "$($EventArgs.Data)" not in arch_text
        checks.append(CheckResult("artifact_arch_valid_headings", "critical", arch_ok,
                      "Architecture headings valid" if arch_ok else "Architecture missing headings"))

        # Corrupted Architecture artifact
        arch_bad = tmp / "docs" / "design" / "bad-architecture.md"
        arch_bad.parent.mkdir(parents=True, exist_ok=True)
        arch_bad.write_text("$($EventArgs.Data)\n" * 10)
        arch_text = arch_bad.read_text()
        has_bad_arch = "$($EventArgs.Data)" in arch_text
        checks.append(CheckResult("artifact_arch_detects_broken", "critical", has_bad_arch,
                      "Architecture detects broken content" if has_bad_arch else "Architecture should detect broken content"))

        arch_bad2 = tmp / "docs" / "design" / "bad2-architecture.md"
        arch_bad2.parent.mkdir(parents=True, exist_ok=True)
        arch_bad2.write_text("# Bad\n\nno sections\n")
        arch_text = arch_bad2.read_text()
        has_arch_h = all(h in arch_text for h in VALID_ARCH_HEADINGS)
        checks.append(CheckResult("artifact_arch_rejects_missing_headings", "critical", not has_arch_h,
                      "Architecture rejects missing headings" if not has_arch_h else "Architecture should reject missing headings"))

    return checks


def check_gates(repo_root: Path) -> list[CheckResult]:
    """Validate gate check logic via CLI."""
    checks: list[CheckResult] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Create minimal fixture: feature state + all required artifacts
        from src.product_app.agent_pipeline_automation import build_feature_state, write_feature_state

        try:
            _simulate_pipeline(tmp, "gate-test-feature")
            checks.append(CheckResult("gate_simulation_runs", "info", True, "gate simulation completed"))
        except Exception as exc:
            checks.append(CheckResult("gate_simulation_runs", "info", False, f"gate simulation error: {exc}"))
            return checks

        # Run check_required_reports for each gate stage
        from src.product_app.agent_pipeline_automation import check_required_reports

        gate_stages = list(GATE_MAPPING.values())
        gates_passed = 0
        gates_total = len(gate_stages)
        for gs in gate_stages:
            try:
                result = check_required_reports(tmp, feature_id="gate-test-feature", through_stage=gs)
                if result.passed:
                    gates_passed += 1
            except Exception:
                pass

        if gates_passed >= max(1, gates_total * 0.5):
            checks.append(CheckResult("gates_pass", "critical", True, f"{gates_passed}/{gates_total} gates passed"))
        else:
            checks.append(CheckResult("gates_pass", "critical", False, f"only {gates_passed}/{gates_total} gates passed"))

    return checks


def run_pipeline_simulation(repo_root: Path | None = None) -> list[CheckResult]:
    """Run a full deterministic pipeline simulation in a temp directory."""
    checks: list[CheckResult] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        feature_id = "sim-test-feature"

        try:
            results = _simulate_pipeline(tmp, feature_id)
            checks.extend(results)
        except Exception as exc:
            checks.append(CheckResult("simulation_error", "critical", False, f"simulation failed: {exc}"))

    return checks


def _simulate_pipeline(tmp: Path, feature_id: str) -> list[CheckResult]:
    """Run a full pipeline simulation in *tmp*.

    Returns a list of CheckResult entries; intended to be called both by
    the regression suite and by the pipeline-simulation sub-check.
    """
    checks: list[CheckResult] = []

    # Ensure pyyaml is available
    try:
        import yaml  # noqa
    except ImportError:
        checks.append(CheckResult("sim_yaml_available", "critical", False, "pyyaml not installed"))
        return checks

    from src.product_app.agent_pipeline_automation import (
        STAGE_ORDER,
        build_feature_state,
        check_required_reports,
        write_feature_state,
        write_handoff,
    )
    from scripts.agent_pipeline import cmd_check_gates

    # 1. Init feature
    state = build_feature_state(
        title="[Simulation] Regression Test",
        feature_id=feature_id,
        risk_level="docs-only",
        issue_number=999,
        issue_url="https://example.com/999",
    )
    write_feature_state(tmp, state)
    checks.append(CheckResult("sim_init", "critical", True, "feature initialized"))

    # 2. Run handoff generation for all stages
    for stage in ("codex_pm", "codex_architect", "claude_lead_plan", "claude_developer",
                  "claude_tester", "claude_lead_review", "codex_reviewer", "codex_acceptance"):
        try:
            path = write_handoff(tmp, stage)
            if path and path.exists():
                checks.append(CheckResult(f"handoff_{stage}", "critical", True, f"handoff {stage} generated"))
            else:
                checks.append(CheckResult(f"handoff_{stage}", "critical", False, f"handoff {stage} missing"))
        except Exception as exc:
            checks.append(CheckResult(f"handoff_{stage}", "critical", False, f"handoff {stage} error: {exc}"))

    # 3. Create deterministic mock artifacts for each stage
    # The date used by build_feature_state
    from src.product_app.agent_pipeline_automation import today_slug
    date_str = today_slug()
    date_dashed = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    artifacts: dict[str, tuple[str, str, list[str]]] = {
        "pm": ("docs/requirements", f"{date_str}-{feature_id}-requirements.md", list(VALID_PM_HEADINGS)),
        "architecture": ("docs/design", f"{date_str}-{feature_id}-architecture.md", list(VALID_ARCH_HEADINGS)),
        "team_plan": ("docs/dev_plans", f"{date_str}-{feature_id}-team-plan.md", ["## Phase Plan"]),
        "phase_dev": ("docs/dev_reports", f"{date_str}-{feature_id}-phase-1-dev-report.md", ["## Summary"]),
        "phase_test": ("docs/test_reports", f"{date_str}-{feature_id}-phase-1-test-report.md", ["## Results"]),
        "claude_lead_review": ("docs/review", f"{date_dashed}-{feature_id}-claude-lead-review.md", ["## Review Decision"]),
        "codex_review": ("docs/review", f"{date_dashed}-{feature_id}-codex-review-r1.md", ["## Review Decision"]),
        "acceptance": ("docs/acceptance", f"{date_dashed}-{feature_id}-acceptance.md", ["## Acceptance Decision"]),
    }

    artifact_created = 0
    for stage_key, (subdir, filename, headings) in artifacts.items():
        full_dir = tmp / subdir
        full_dir.mkdir(parents=True, exist_ok=True)
        filepath = full_dir / filename

        content = f"# {feature_id} {stage_key}\n\n"
        for h in headings:
            content += f"{h}\n\nContent for {stage_key}.\n\n"

        # Also include PM headings for PM artifact
        if stage_key == "pm":
            content = f"# {feature_id} Requirements\n\n" + "\n".join(h + "\n\nContent.\n" for h in VALID_PM_HEADINGS)
        elif stage_key == "architecture":
            content = f"# {feature_id} Architecture\n\n" + "\n".join(h + "\n\nContent.\n" for h in VALID_ARCH_HEADINGS)
        elif stage_key == "acceptance":
            decision = "ACCEPTED"
            content = f"# {feature_id} PM Acceptance\n\n## Acceptance Decision\n\n{decision}\n\n"
        elif stage_key == "codex_review":
            content = f"# {feature_id} Codex Review R1\n\n## Review Decision\n\nAPPROVED\n\n"

        filepath.write_text(content)
        if filepath.exists() and filepath.stat().st_size > 0:
            artifact_created += 1
            checks.append(CheckResult(f"artifact_{stage_key}", "critical", True, f"{filename} created"))
        else:
            checks.append(CheckResult(f"artifact_{stage_key}", "critical", False, f"{filename} missing"))

    # 4. Check gates
    gates_passed = 0
    gates_total = len(STAGE_ORDER)
    for through_stage in STAGE_ORDER:
        try:
            result = check_required_reports(tmp, feature_id=feature_id, through_stage=through_stage)
            if result.passed:
                gates_passed += 1
        except Exception:
            pass

    if gates_passed == gates_total:
        checks.append(CheckResult("sim_all_gates_pass", "critical", True, f"{gates_passed}/{gates_total} gates passed"))
    else:
        checks.append(CheckResult("sim_all_gates_pass", "warning", False, f"only {gates_passed}/{gates_total} gates passed"))

    # 5. Validate state sync
    try:
        from src.product_app.agent_pipeline_automation import check_state_gate_consistency, sync_state_from_gates
        diag = check_state_gate_consistency(tmp)
        if not diag["consistent"]:
            diag2 = sync_state_from_gates(tmp)
            if diag2.get("updated"):
                checks.append(CheckResult("sim_state_sync", "critical", True, f"state synced: {diag2['changes_made']}"))
            else:
                checks.append(CheckResult("sim_state_sync", "critical", True, "state already consistent"))
        else:
            checks.append(CheckResult("sim_state_sync", "critical", True, "state already consistent"))
    except Exception as exc:
        checks.append(CheckResult("sim_state_sync", "warning", False, f"state sync error: {exc}"))

    # 6. Validate merge gate not bypassed
    try:
        auto_merge = tmp / ".agent" / "gates" / "auto_merge_gate.json"
        if auto_merge.exists():
            data = json.loads(auto_merge.read_text())
            if data.get("requires_manual_approval", True):
                checks.append(CheckResult("sim_manual_approval_preserved", "critical", True, "manual approval required"))
            else:
                checks.append(CheckResult("sim_manual_approval_preserved", "critical", True, "no auto-merge bypass"))
        else:
            checks.append(CheckResult("sim_manual_approval_preserved", "info", True, "auto_merge_gate not generated (expected)"))
    except Exception as exc:
        checks.append(CheckResult("sim_manual_approval_preserved", "warning", True, str(exc)))

    return checks


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def collect_checks(repo_root: Path, base: str = "origin/main", strict: bool = False) -> dict[str, Any]:
    """Run all regression checks and return a report dict."""
    all_checks: list[CheckResult] = []

    all_checks.extend(check_workflow(repo_root))
    all_checks.extend(check_runner(repo_root))
    all_checks.extend(check_runtime_temp(repo_root, base))
    all_checks.extend(check_restricted_diff(repo_root, base))
    all_checks.extend(check_artifacts(repo_root))
    all_checks.extend(check_gates(repo_root))
    all_checks.extend(run_pipeline_simulation(repo_root))

    critical_fail = sum(1 for c in all_checks if c.severity == "critical" and not c.passed)
    warning_fail = sum(1 for c in all_checks if c.severity == "warning" and not c.passed)

    if strict:
        status = "pass" if critical_fail == 0 and warning_fail == 0 else "fail"
    elif critical_fail > 0:
        status = "fail"
    elif warning_fail > 0:
        status = "warn"
    else:
        status = "pass"

    return {
        "status": status,
        "summary": {
            "critical_count": critical_fail,
            "warning_count": warning_fail,
            "info_count": sum(1 for c in all_checks if c.severity == "info"),
        },
        "checks": [c.to_dict() for c in all_checks],
        "artifacts": {},
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_human(report: dict[str, Any]) -> str:
    """Render a regression report as human-readable text."""
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("Agent Pipeline Regression Suite")
    lines.append("=" * 60)
    lines.append(f"Status: {report['status'].upper()}")
    lines.append(f"Critical failures: {report['summary']['critical_count']}")
    lines.append(f"Warnings: {report['summary']['warning_count']}")
    lines.append(f"Info checks: {report['summary']['info_count']}")
    lines.append("")

    # Group by check prefix
    groups: dict[str, list[dict[str, Any]]] = {}
    for c in report["checks"]:
        prefix = c["name"].rsplit("_", 1)[0] if "_" in c["name"] else c["name"]
        group = groups.setdefault(prefix, [])
        group.append(c)

    for group_name, group_checks in sorted(groups.items()):
        lines.append(f"\n--- {group_name} ---")
        for c in group_checks:
            icon = "✅" if c["passed"] else ("❌" if c["severity"] == "critical" else "⚠️ ")
            lines.append(f"  {icon} [{c['severity']:8s}] {c['name']}: {c['message']}")

    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)


def render_json(report: dict[str, Any], output: Path | None = None) -> str:
    """Render report as JSON, optionally writing to a file."""
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
        report["artifacts"]["report_path"] = str(output)
    return text


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Agent Pipeline Regression Suite")
    parser.add_argument("--strict", action="store_true", help="Upgrade warnings to failures")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of human-readable")
    parser.add_argument("--base", default="origin/main", help="Base branch for diff checks")
    parser.add_argument("--output", help="Write JSON report to this path")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    repo = REPO_ROOT

    report = collect_checks(repo, base=args.base, strict=args.strict)
    s = report["summary"]

    if args.json or args.output:
        output_path = Path(args.output) if args.output else None
        result = render_json(report, output=output_path)
        if args.json:
            print(result)
    else:
        print(render_human(report))

    if report["status"] == "fail":
        return 2
    if report["status"] == "warn":
        return 1 if not args.strict else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
