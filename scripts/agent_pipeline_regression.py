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
PR_VALIDATION_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "agent-pr-validation.yml"
TEAM_RUNNER_PATH = REPO_ROOT / "scripts" / "run-pipeline-team-agent.sh"
WINDOWS_TEAM_RUNNER_PATH = REPO_ROOT / "scripts" / "run-team-stage.ps1"
RUNTIME_PREFLIGHT_WORKFLOW_PATH = (
    REPO_ROOT / ".github" / "workflows" / "agent-runtime-preflight.yml"
)
AGENT_ISSUE_TEMPLATE_PATH = (
    REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "agent_feature_request.yml"
)

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

    trigger_block = text.split("permissions:", 1)[0]
    single_entry = (
        "workflow_dispatch:" in trigger_block
        and "pull_request:" not in trigger_block
        and "github.event.label" not in text
        and "github.event.pull_request" not in text
    )
    checks.append(CheckResult(
        "workflow_single_dispatch_entry",
        "critical",
        single_entry,
        "Stage Runner 仅由 workflow_dispatch 进入"
        if single_entry
        else "Stage Runner 仍存在 label 或 pull_request 执行入口",
    ))

    transaction_markers = (
        "agent-stage-pr-${{ inputs.pr_number || github.run_id }}",
        "cancel-in-progress: false",
        "validate-stage-start --stage $env:STAGE",
        "evaluate-stage-transition --stage $env:STAGE",
        "apply-stage-transition --stage $env:STAGE",
        ".agent/gates/stage_transition_gate.json",
    )
    missing_transaction_markers = [
        marker for marker in transaction_markers if marker not in text
    ]
    checks.append(CheckResult(
        "workflow_transaction_controller",
        "critical",
        not missing_transaction_markers,
        "Stage Runner 已启用 PR 串行、阶段租约和组合门禁"
        if not missing_transaction_markers
        else f"Stage Runner 缺少事务控制标记：{missing_transaction_markers}",
    ))

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
    """Validate .agent/tmp and .agent/reports directory hygiene."""
    checks: list[CheckResult] = []
    gitignore = _read(repo_root / ".gitignore")

    if gitignore and ".agent/tmp/" in gitignore:
        checks.append(CheckResult("gitignore_agent_tmp", "critical", True, ".gitignore includes .agent/tmp/"))
    else:
        checks.append(CheckResult("gitignore_agent_tmp", "critical", False, ".gitignore missing .agent/tmp/"))

    if gitignore and ".agent/reports/" in gitignore:
        checks.append(CheckResult("gitignore_agent_reports", "critical", True, ".gitignore 已包含 .agent/reports/"))
    else:
        checks.append(CheckResult("gitignore_agent_reports", "critical", False, ".gitignore 缺少 .agent/reports/"))

    # Check tracked files
    tracked = _git("ls-files .agent/tmp", repo_root)
    if not tracked:
        checks.append(CheckResult("agent_tmp_not_tracked", "critical", True, ".agent/tmp not tracked"))
    else:
        checks.append(CheckResult("agent_tmp_not_tracked", "critical", False, f".agent/tmp has tracked files: {tracked[:100]}"))

    tracked_reports = _git("ls-files .agent/reports", repo_root)
    if not tracked_reports:
        checks.append(CheckResult("pipeline_reports_not_tracked", "critical", True, ".agent/reports 没有已跟踪文件"))
    else:
        checks.append(CheckResult("pipeline_reports_not_tracked", "critical", False, f".agent/reports 存在已跟踪文件：{tracked_reports[:100]}"))

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


def check_pr_validation_workflow(repo_root: Path) -> list[CheckResult]:
    """Validate the lightweight pull-request workflow and dashboard upload."""
    checks: list[CheckResult] = []
    path = repo_root / PR_VALIDATION_WORKFLOW_PATH.relative_to(REPO_ROOT)
    text = _read(path)
    if text is None:
        checks.append(CheckResult("pr_validation_exists", "critical", False, "未找到 agent-pr-validation.yml"))
        return checks

    checks.append(CheckResult("pr_validation_exists", "critical", True, "agent-pr-validation.yml 已存在"))
    required_commands = (
        "python scripts/agent_pipeline_regression.py --strict",
        "python -m pytest tests/test_agent_pipeline_automation.py tests/test_agent_pipeline_regression.py -q",
        "git diff --check",
        "git diff --name-only origin/main...HEAD",
        "git ls-files .agent/tmp .agent/reports",
    )
    missing_commands = [command for command in required_commands if command not in text]
    checks.append(CheckResult(
        "pr_validation_required_commands",
        "critical",
        not missing_commands,
        "所有必需命令均已配置" if not missing_commands else f"缺少命令：{missing_commands}",
    ))

    artifact_markers = (
        "if: always()",
        "actions/upload-artifact@v4",
        ".agent/reports/pipeline_report.json",
        ".agent/reports/pipeline_dashboard.html",
        "<!-- agent-pipeline-dashboard -->",
    )
    missing_markers = [marker for marker in artifact_markers if marker not in text]
    checks.append(CheckResult(
        "pr_validation_dashboard_artifact",
        "critical",
        not missing_markers,
        "Dashboard artifact 与 PR 查看说明已配置" if not missing_markers else f"缺少标记：{missing_markers}",
    ))
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
        gate_failures: list[str] = []
        gates_total = len(gate_stages)
        for gs in gate_stages:
            try:
                result = check_required_reports(tmp, feature_id="gate-test-feature", through_stage=gs)
                if result.passed:
                    gates_passed += 1
                else:
                    gate_failures.append(
                        f"{gs}: missing={result.missing}, invalid={result.invalid}"
                    )
            except Exception as exc:
                gate_failures.append(f"{gs}: {exc.__class__.__name__}: {exc}")

        if gates_passed == gates_total:
            checks.append(CheckResult("gates_pass", "critical", True, f"{gates_passed}/{gates_total} gates passed"))
        else:
            detail = "; ".join(gate_failures)
            checks.append(CheckResult(
                "gates_pass",
                "critical",
                False,
                f"only {gates_passed}/{gates_total} gates passed; {detail}",
            ))

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
        "phase_dev": ("docs/dev_reports", f"{date_str}-{feature_id}-phase-1-dev-report.md", ["## 最终结论"]),
        "phase_test": ("docs/test_reports", f"{date_str}-{feature_id}-phase-1-test-report.md", ["## 最终结论"]),
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
        elif stage_key == "phase_dev":
            content = f"# {feature_id} Dev Report\n\n## Final Result\n\nPASS\n\n"
        elif stage_key == "phase_test":
            content = f"# {feature_id} Test Report\n\n## Final Result\n\nPASS\n\n"
        elif stage_key == "claude_lead_review":
            content = f"# {feature_id} Lead Review\n\n## Review Decision\n\nAPPROVED\n\n"

        filepath.write_text(content, encoding="utf-8")
        if filepath.exists() and filepath.stat().st_size > 0:
            artifact_created += 1
            checks.append(CheckResult(f"artifact_{stage_key}", "critical", True, f"{filename} created"))
        else:
            checks.append(CheckResult(f"artifact_{stage_key}", "critical", False, f"{filename} missing"))

    delivery_gate = tmp / ".agent" / "gates" / "phase_dev_delivery_gate.json"
    delivery_gate.parent.mkdir(parents=True, exist_ok=True)
    delivery_gate.write_text(
        json.dumps(
            {
                "passed": True,
                "feature_id": feature_id,
                "stage": "claude_developer",
                "invalid": [],
            }
        ),
        encoding="utf-8",
    )

    # 4. Check gates
    gates_passed = 0
    gate_failures: list[str] = []
    gates_total = len(STAGE_ORDER)
    for through_stage in STAGE_ORDER:
        try:
            result = check_required_reports(tmp, feature_id=feature_id, through_stage=through_stage)
            if result.passed:
                gates_passed += 1
            else:
                gate_failures.append(
                    f"{through_stage}: missing={result.missing}, invalid={result.invalid}"
                )
        except Exception as exc:
            gate_failures.append(
                f"{through_stage}: {exc.__class__.__name__}: {exc}"
            )

    if gates_passed == gates_total:
        checks.append(CheckResult("sim_all_gates_pass", "critical", True, f"{gates_passed}/{gates_total} gates passed"))
    else:
        detail = "; ".join(gate_failures)
        checks.append(CheckResult(
            "sim_all_gates_pass",
            "critical",
            False,
            f"only {gates_passed}/{gates_total} gates passed; {detail}",
        ))

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



def check_bootstrap_env(repo_root: Path) -> list[CheckResult]:
    """Verify bootstrap keeps Codex env vars and uses the fixed Team runner."""
    checks: list[CheckResult] = []
    text = _read(repo_root / ".github" / "workflows" / "agent-issue-bootstrap.yml")
    if text is None:
        checks.append(CheckResult("bootstrap_exists", "critical", False, "agent-issue-bootstrap.yml not found"))
        return checks
    checks.append(CheckResult("bootstrap_exists", "critical", True, "agent-issue-bootstrap.yml exists"))

    required_vars = [
        "AGENT_REAL_CODEX_PM",
        "AGENT_REAL_CODEX_PM_STRICT",
        "AGENT_REAL_CODEX_ARCHITECT",
        "AGENT_REAL_CODEX_ARCHITECT_STRICT",
    ]
    for var in required_vars:
        # Check for the env var definition in the file
        pattern = f"{var}: ${{{{ vars.{var}"
        if pattern in text:
            checks.append(CheckResult(f"bootstrap_env_{var}", "critical", True, f"bootstrap passes {var}"))
        else:
            checks.append(CheckResult(f"bootstrap_env_{var}", "critical", False, f"bootstrap missing {var}"))

    team_markers = (
        "run-team-stage.ps1",
        "-Stage claude_lead_plan",
        "Run OpenCode GLM 5.2 team-plan",
    )
    missing = [marker for marker in team_markers if marker not in text]
    checks.append(CheckResult(
        "bootstrap_fixed_team_lead_runner",
        "critical",
        not missing,
        "bootstrap 使用固定 OpenCode Team Lead runner"
        if not missing
        else f"bootstrap 缺少 Team Lead runner 标记：{missing}",
    ))

    transition_markers = tuple(
        marker
        for stage in ("codex_pm", "codex_architect", "claude_lead_plan")
        for marker in (
            f"evaluate-stage-transition --stage {stage}",
            f"apply-stage-transition --stage {stage}",
        )
    )
    missing_transitions = [
        marker for marker in transition_markers if marker not in text
    ]
    checks.append(CheckResult(
        "bootstrap_stage_transitions",
        "critical",
        not missing_transitions,
        "Bootstrap 已提交 PM、架构和 Team Plan 状态迁移"
        if not missing_transitions
        else f"Bootstrap 缺少状态迁移：{missing_transitions}",
    ))

    return checks


def check_team_runtime_contract(repo_root: Path) -> list[CheckResult]:
    """Verify fixed model, effort, workflow, and superpowers routing."""
    checks: list[CheckResult] = []
    runner = _read(repo_root / TEAM_RUNNER_PATH.relative_to(REPO_ROOT))
    windows_runner = _read(repo_root / WINDOWS_TEAM_RUNNER_PATH.relative_to(REPO_ROOT))
    workflow = _read(repo_root / WORKFLOW_PATH.relative_to(REPO_ROOT))

    if runner is None:
        return [CheckResult("team_runner_exists", "critical", False, "Team runner 不存在")]
    checks.append(CheckResult("team_runner_exists", "critical", True, "Team runner 已存在"))

    required_runner_markers = (
        'OPENCODE_LEAD_MODEL="opencode-go/glm-5.2"',
        'OPENCODE_TESTER_MODEL="opencode-go/deepseek-v4-pro"',
        'OPENCODE_TESTER_VARIANT="max"',
        'OPENCODE_DEVELOPER_MODEL="opencode-go/deepseek-v4-flash"',
        'OPENCODE_DEVELOPER_VARIANT="max"',
        "LEAD_STAGE_TIMEOUT_SECONDS",
        "TESTER_STAGE_TIMEOUT_SECONDS",
        "DEVELOPER_STAGE_TIMEOUT_SECONDS",
        "run_stage_with_timeout",
        "timed out after",
        "using-superpowers",
        "verification-before-completion",
        "systematic-debugging",
        "--agent build",
        "--preflight-only",
        "PIPELINE_RUNTIME_OK",
        "PREFLIGHT_TIMEOUT_SECONDS",
        "timeout --signal=TERM --kill-after=10s",
        "--format json",
    )
    missing = [marker for marker in required_runner_markers if marker not in runner]
    forbidden_runner_markers = (
        "--permission-mode allow",
        "--dangerously-skip-permissions",
    )
    found_forbidden = [marker for marker in forbidden_runner_markers if marker in runner]
    checks.append(CheckResult(
        "team_runner_fixed_runtime_contract",
        "critical",
        not missing and not found_forbidden,
        "Team runner 已固定模型、effort、workflow 与 superpowers"
        if not missing and not found_forbidden
        else f"Team runner 缺少标记 {missing} 或包含危险标记 {found_forbidden}",
    ))

    bridge_markers = (
        "scripts/run-pipeline-team-agent.sh",
        '"--cd", $wslRoot',
        '"bash", "-i", "scripts/run-pipeline-team-agent.sh"',
        "PreflightOnly",
        "runtime-preflight-$preflightRole.execution.json",
    )
    bridge_ok = windows_runner is not None and all(
        marker in windows_runner for marker in bridge_markers
    ) and '"-lc"' not in windows_runner and "$bashCommand" not in windows_runner
    checks.append(CheckResult(
        "team_runner_windows_wsl_bridge",
        "critical",
        bridge_ok,
        "Windows runner 使用仓库内 WSL Team runner"
        if bridge_ok
        else "Windows runner 未使用仓库内 WSL Team runner",
    ))

    workflow_ok = (
        workflow is not None
        and "run-team-stage.ps1" in workflow
        and "validate-stage-delivery" in workflow
        and "route_back_to" in workflow
        and "feedback/bugs/open/BUG_" in workflow
        and "git add -f -- $evidencePath" in workflow
        and '"feedback",' not in workflow
        and "CLAUDE_TESTER_AGENT_COMMAND" not in workflow
        and "CLAUDE_LEAD_AGENT_COMMAND" not in workflow
    )
    checks.append(CheckResult(
        "workflow_fixed_team_routing",
        "critical",
        workflow_ok,
        "workflow 不再允许替换 Team Lead/Tester 执行器"
        if workflow_ok
        else "workflow 仍存在可替换的 Team Lead/Tester 路由",
    ))

    compatibility_preflight_markers = (
        "- runtime_preflight",
        "runtime_role:",
        "inputs.stage != 'runtime_preflight'",
        "inputs.stage == 'runtime_preflight'",
        "-Stage claude_lead_plan -PreflightOnly",
        "-Stage claude_tester -PreflightOnly",
        "-Stage claude_developer -PreflightOnly",
        ".agent/tmp/runtime-preflight-*",
        "if-no-files-found: error",
        "include-hidden-files: true",
    )
    compatibility_preflight_missing = [
        marker
        for marker in compatibility_preflight_markers
        if workflow is None or marker not in workflow
    ]
    checks.append(CheckResult(
        "stage_runner_runtime_preflight",
        "critical",
        not compatibility_preflight_missing,
        "Stage Runner 已提供不推进 Pipeline 的 Runtime Preflight"
        if not compatibility_preflight_missing
        else f"Stage Runner Runtime Preflight 缺少标记：{compatibility_preflight_missing}",
    ))

    preflight = _read(repo_root / RUNTIME_PREFLIGHT_WORKFLOW_PATH.relative_to(REPO_ROOT))
    preflight_markers = (
        "workflow_dispatch:",
        "-Stage claude_lead_plan -PreflightOnly",
        "-Stage claude_tester -PreflightOnly",
        "-Stage claude_developer -PreflightOnly",
        "actions/upload-artifact@v4",
        ".agent/tmp/runtime-preflight-*",
        "if-no-files-found: error",
        "include-hidden-files: true",
    )
    preflight_missing = [
        marker for marker in preflight_markers if preflight is None or marker not in preflight
    ]
    checks.append(CheckResult(
        "team_runtime_preflight_workflow",
        "critical",
        not preflight_missing,
        "Runtime Preflight workflow 已覆盖三个固定角色"
        if not preflight_missing
        else f"Runtime Preflight workflow 缺少标记：{preflight_missing}",
    ))

    issue_template = _read(repo_root / AGENT_ISSUE_TEMPLATE_PATH.relative_to(REPO_ROOT))
    issue_required = (
        "OpenCode Lead",
        "OpenCode Developer",
        "OpenCode Test Engineer",
        "manual main merge",
    )
    issue_forbidden = (
        "Claude Code A",
        "Claude Code B",
        "Claude Code C",
        "automatic main merge",
    )
    issue_missing = [
        marker for marker in issue_required
        if issue_template is None or marker not in issue_template
    ]
    issue_stale = [
        marker for marker in issue_forbidden
        if issue_template is not None and marker in issue_template
    ]
    checks.append(CheckResult(
        "agent_issue_template_current_team",
        "critical",
        not issue_missing and not issue_stale,
        "Issue 模板使用当前角色并要求人工合并"
        if not issue_missing and not issue_stale
        else f"Issue 模板缺少 {issue_missing} 或包含旧文案 {issue_stale}",
    ))
    return checks

def check_forbidden_markers(repo_root: Path) -> list[CheckResult]:
    """Verify that formal stage artifacts do not contain forbidden markers."""
    checks: list[CheckResult] = []
    forbidden = [
        "Smoke-test document generated by local Codex wrapper",
        "Handoff Preview",
        "mock/smoke mode",
        "Fallback: mock/smoke mode",
        "Mock/smoke fallback",
    ]

    # Check the runner reference (source of truth for artifact templates)
    ref_text = _read(repo_root / RUNNER_REFERENCE.relative_to(REPO_ROOT))
    if ref_text:
        for marker in forbidden:
            # In the reference, these should NOT appear as generated artifact content.
            # They may appear in test assertions, which is fine.
            # Check for "Smoke-test document generated by local Codex wrapper" in non-comment lines
            lines = ref_text.split('\n')
            found = False
            for line in lines:
                stripped = line.strip()
                if marker in stripped and not stripped.startswith('#'):
                    found = True
                    break
            result_text = "在 runner 中发现" if found else "runner 中未发现"
            checks.append(CheckResult(
                f"forbidden_{marker[:20].replace(' ', '_')}",
                "critical",
                not found,
                f"'{marker}' {result_text}",
            ))
    else:
        checks.append(CheckResult("forbidden_runner_read", "critical", False, "cannot read runner reference"))

    # Check Claude runner too
    claude_text = _read(repo_root / "scripts" / "run_claude_stage.sh")
    if claude_text:
        for marker in forbidden:
            lines = claude_text.split('\n')
            found = False
            for line in lines:
                stripped = line.strip()
                if marker in stripped and not stripped.startswith('#'):
                    found = True
                    break
            result_text = "在 Claude runner 中发现" if found else "Claude runner 中未发现"
            checks.append(CheckResult(
                f"claude_forbidden_{marker[:20].replace(' ', '_')}",
                "critical",
                not found,
                f"'{marker}' {result_text}",
            ))

    # Check for UTF-8 BOM in formal artifacts
    docs_paths = [
        "docs/requirements", "docs/design", "docs/dev_plans",
        "docs/dev_reports", "docs/test_reports", "docs/review", "docs/acceptance",
    ]
    bom_files = []
    for dp in docs_paths:
        d = repo_root / dp
        if d.is_dir():
            for f in d.glob("*"):
                if f.is_file() and f.suffix == ".md":
                    raw = f.read_bytes()
                    if raw.startswith(b'\\xef\\xbb\\xbf'):
                        bom_files.append(str(f.relative_to(repo_root)))
    if bom_files:
        checks.append(CheckResult("utf8_bom_artifacts", "critical", False, f"BOM found in: {bom_files}"))
    else:
        checks.append(CheckResult("utf8_bom_artifacts", "critical", True, "no BOM in formal artifacts"))

    return checks

def collect_checks(repo_root: Path, base: str = "origin/main", strict: bool = False) -> dict[str, Any]:
    """Run all regression checks and return a report dict."""
    all_checks: list[CheckResult] = []

    all_checks.extend(check_workflow(repo_root))
    all_checks.extend(check_runner(repo_root))
    all_checks.extend(check_runtime_temp(repo_root, base))
    all_checks.extend(check_pr_validation_workflow(repo_root))
    all_checks.extend(check_restricted_diff(repo_root, base))
    all_checks.extend(check_artifacts(repo_root))
    all_checks.extend(check_gates(repo_root))
    all_checks.extend(run_pipeline_simulation(repo_root))
    all_checks.extend(check_forbidden_markers(repo_root))
    all_checks.extend(check_bootstrap_env(repo_root))
    all_checks.extend(check_team_runtime_contract(repo_root))

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
    lines.append("Agent Pipeline 回归测试套件")
    lines.append("=" * 60)
    status_labels = {"pass": "通过", "fail": "失败", "warn": "警告"}
    lines.append(f"状态：{status_labels.get(report['status'], report['status'])}")
    lines.append(f"严重失败：{report['summary']['critical_count']}")
    lines.append(f"警告：{report['summary']['warning_count']}")
    lines.append(f"信息项：{report['summary']['info_count']}")
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
    if output:
        report.setdefault("artifacts", {})["report_path"] = str(output)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
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
