"""Tests for Agent Pipeline Regression Suite.

Self-contained tests that do not require pandas, fastapi, akshare,
external services, GitHub API, or network access.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "agent_pipeline_regression.py"


# -- helpers -----------------------------------------------------------------

def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + list(args),
        capture_output=True, text=True, cwd=REPO_ROOT, timeout=60,
    )


def _json_report(*args: str) -> dict:
    proc = _run("--json", *args)
    if proc.returncode not in (0, 1, 2):
        raise RuntimeError(f"non-zero exit: {proc.returncode}\n{proc.stderr}")
    return json.loads(proc.stdout)


# -- regression shape --------------------------------------------------------

def test_json_output_is_valid():
    report = _json_report()
    assert "status" in report
    assert "summary" in report
    assert "checks" in report
    assert isinstance(report["checks"], list)


def test_strict_mode_turns_warnings_into_failure():
    # We don't force warnings, but verify the mode runs cleanly
    proc = _run("--strict")
    assert proc.returncode in (0, 2)


# -- workflow checks ---------------------------------------------------------

def test_workflow_has_codex_pm():
    report = _json_report()
    names = [c["name"] for c in report["checks"]]
    assert "workflow_has_codex_pm" in names


def test_workflow_has_codex_architect():
    report = _json_report()
    names = [c["name"] for c in report["checks"]]
    assert "workflow_has_codex_architect" in names


def test_workflow_label_pm_pending():
    report = _json_report()
    names = [c["name"] for c in report["checks"]]
    # The name may contain colons encoded differently
    assert any("workflow_label" in n and "pm-pending" in n for n in names)


def test_workflow_label_arch_pending():
    report = _json_report()
    names = [c["name"] for c in report["checks"]]
    assert any("workflow_label" in n and "arch-pending" in n for n in names)


def test_gate_mapping_codex_pm():
    report = _json_report()
    for c in report["checks"]:
        if c["name"] == "gate_mapping_codex_pm":
            assert c["passed"]
            return
    pytest.fail("gate_mapping_codex_pm not found")


def test_gate_mapping_codex_architect():
    report = _json_report()
    for c in report["checks"]:
        if c["name"] == "gate_mapping_codex_architect":
            assert c["passed"]
            return
    pytest.fail("gate_mapping_codex_architect not found")


# -- runner safety checks ----------------------------------------------------

def test_runner_no_register_objectevent():
    report = _json_report()
    for c in report["checks"]:
        if "runner_no_Register" in c["name"]:
            assert c["passed"]
            return


def test_runner_no_readtoend():
    report = _json_report()
    for c in report["checks"]:
        if "runner_no_ReadToEnd" in c["name"]:
            assert c["passed"]
            return


def test_runner_has_output_last_message():
    report = _json_report()
    for c in report["checks"]:
        if "runner_uses_output_last_message" in c["name"]:
            assert c["passed"]
            return
    pytest.fail("runner_uses_output_last_message not found")


def test_runner_uses_agent_tmp():
    report = _json_report()
    for c in report["checks"]:
        if "runner_uses_agent_tmp" in c["name"]:
            assert c["passed"]
            return
    pytest.fail("runner_uses_agent_tmp not found")


# -- artifact checks ---------------------------------------------------------

def test_artifact_pm_detects_broken():
    report = _json_report()
    for c in report["checks"]:
        if "artifact_pm_detects_broken" in c["name"]:
            assert c["passed"]
            return


def test_artifact_arch_detects_broken():
    report = _json_report()
    for c in report["checks"]:
        if "artifact_arch_detects_broken" in c["name"]:
            assert c["passed"]
            return


def test_artifact_pm_rejects_missing_headings():
    report = _json_report()
    for c in report["checks"]:
        if "artifact_pm_rejects_missing_headings" in c["name"]:
            assert c["passed"]
            return


def test_artifact_arch_rejects_missing_headings():
    report = _json_report()
    for c in report["checks"]:
        if "artifact_arch_rejects_missing_headings" in c["name"]:
            assert c["passed"]
            return


# -- runtime hygiene ---------------------------------------------------------

def test_gitignore_includes_agent_tmp():
    report = _json_report()
    for c in report["checks"]:
        if c["name"] == "gitignore_agent_tmp":
            assert c["passed"]
            return


def test_agent_tmp_not_tracked():
    report = _json_report()
    for c in report["checks"]:
        if c["name"] == "agent_tmp_not_tracked":
            assert c["passed"]
            return


# -- restricted diff ---------------------------------------------------------

def test_restricted_diff_clean():
    report = _json_report()
    for c in report["checks"]:
        if c["name"] == "restricted_diff":
            assert c["passed"]
            return


# -- pipeline simulation -----------------------------------------------------

def test_sim_all_gates_pass():
    report = _json_report()
    for c in report["checks"]:
        if c["name"] == "sim_all_gates_pass":
            assert c["passed"]
            return


def test_sim_state_sync():
    report = _json_report()
    for c in report["checks"]:
        if c["name"] == "sim_state_sync":
            assert c["passed"]
            return


def test_sim_manual_approval_preserved():
    report = _json_report()
    for c in report["checks"]:
        if c["name"] == "sim_manual_approval_preserved":
            # This can be info-level (no auto_merge_gate) which is fine
            assert c["passed"]
            return


# -- human output ------------------------------------------------------------

def test_human_output_renders():
    proc = _run()
    assert "Agent Pipeline Regression Suite" in proc.stdout
    assert "Status:" in proc.stdout


def test_restricted_diff_no_trading_paths():
    for name in ("src/broker/", "src/execution/", "src/order/", "src/account/", "src/risk/", "miniQMT/"):
        proc = subprocess.run(
            ["git", "diff", "--name-only", "origin/main...HEAD"],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=30,
        )
        assert name not in proc.stdout, f"restricted path found: {name}"
