"""Tests for issue-driven Agent pipeline automation helpers."""
from __future__ import annotations

from pathlib import Path

from src.product_app.agent_pipeline_automation import (
    build_feature_state,
    check_required_reports,
    classify_changed_files,
    slugify_feature,
    write_feature_state,
    write_handoff,
)


def test_safe_docs_and_tests_are_auto_merge_eligible():
    decision = classify_changed_files([
        "docs/pipeline/AUTO_MERGE_POLICY.md",
        "tests/test_agent_pipeline_automation.py",
        ".github/ISSUE_TEMPLATE/agent_feature_request.yml",
    ])

    assert decision.eligible_for_auto_main_merge is True
    assert decision.requires_manual_approval is False
    assert decision.restricted_files == []
    assert decision.unsafe_files == []


def test_workflow_changes_require_manual_approval():
    decision = classify_changed_files([
        ".github/workflows/agent-main-merge-gate.yml",
    ])

    assert decision.eligible_for_auto_main_merge is False
    assert decision.requires_manual_approval is True
    assert ".github/workflows/agent-main-merge-gate.yml" in decision.unsafe_files


def test_trading_sensitive_paths_require_manual_approval():
    decision = classify_changed_files([
        "src/execution_engine/execution_service.py",
        "tests/test_phase5_execution.py",
    ])

    assert decision.eligible_for_auto_main_merge is False
    assert decision.requires_manual_approval is True
    assert "src/execution_engine/execution_service.py" in decision.restricted_files
    assert "restricted_trading_or_secret_paths_touched" in decision.reasons


def test_unknown_business_code_requires_manual_approval():
    decision = classify_changed_files(["src/strategy_engine/signal_generator.py"])

    assert decision.eligible_for_auto_main_merge is False
    assert decision.requires_manual_approval is True
    assert "src/strategy_engine/signal_generator.py" in decision.unsafe_files


def test_slugify_feature_handles_issue_prefix_and_spaces():
    slug = slugify_feature("[Feature] 接入 Tencent Quote Provider!!!")

    assert slug.startswith("接入-tencent-quote-provider")
    assert " " not in slug
    assert "!" not in slug


def test_feature_state_writes_current_task_and_handoff(tmp_path: Path):
    state = build_feature_state(
        title="[Feature] Agent Pipeline",
        feature_id="agent-pipeline",
        risk_level="docs-only",
        issue_number=12,
    )

    write_feature_state(tmp_path, state)
    handoff = write_handoff(tmp_path, "developer")

    assert (tmp_path / ".agent" / "state.json").exists()
    assert (tmp_path / ".agent" / "current_task.yaml").exists()
    text = handoff.read_text(encoding="utf-8")
    assert "Feature: agent-pipeline" in text
    assert "Claude Code B" in text
    assert "feat/agent-pipeline/phase-<n>-<module>" in text


def test_feature_state_contains_team_pipeline_defaults():
    state = build_feature_state(
        title="[Feature] Agent Pipeline",
        feature_id="agent-pipeline",
        risk_level="docs-only",
        issue_number=12,
    )

    assert state["team_pipeline"]["mode"] == "claude_first_review"
    assert state["team_pipeline"]["all_phases_tested"] is False
    assert state["team_pipeline"]["max_codex_review_attempts"] == 3
    assert state["agent_roles"]["codex_a"] == ["pm", "acceptance"]
    assert state["agent_roles"]["claude_b"] == ["phase_dev"]


def test_codex_pm_handoff_only_requests_requirements(tmp_path: Path):
    state = build_feature_state(
        title="[Feature] Agent Pipeline",
        feature_id="agent-pipeline",
        risk_level="docs-only",
        issue_number=12,
    )
    write_feature_state(tmp_path, state)

    handoff = write_handoff(tmp_path, "codex_pm").read_text(encoding="utf-8")

    assert "Codex A" in handoff
    assert "Produce the PM requirements document" in handoff
    assert "Do not write architecture" in handoff


def test_claude_tester_handoff_routes_back_to_developer_until_all_phases_pass(tmp_path: Path):
    state = build_feature_state(
        title="[Feature] Agent Pipeline",
        feature_id="agent-pipeline",
        risk_level="docs-only",
        issue_number=12,
    )
    write_feature_state(tmp_path, state)

    handoff = write_handoff(tmp_path, "claude_tester").read_text(encoding="utf-8")

    assert "Claude Code C" in handoff
    assert "route back to Claude Code B for the next phase unless all phases are complete" in handoff


def test_required_report_gate_finds_feature_reports(tmp_path: Path):
    feature_id = "agent-pipeline"
    paths = [
        "docs/requirements/2026-06-12-agent-pipeline-requirements.md",
        "docs/design/2026-06-12-agent-pipeline-architecture.md",
        "docs/dev_plans/2026-06-12-agent-pipeline-team-plan.md",
        "docs/dev_reports/2026-06-12-agent-pipeline-phase-1-dev-report.md",
    ]
    for path in paths:
        full_path = tmp_path / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text("ok", encoding="utf-8")

    result = check_required_reports(tmp_path, feature_id=feature_id, through_stage="phase_dev")

    assert result.passed is True
    assert result.missing == {}
    assert set(result.found) == {"pm", "architecture", "team_plan", "phase_dev"}


def test_required_report_gate_fails_closed_when_missing(tmp_path: Path):
    result = check_required_reports(tmp_path, feature_id="missing", through_stage="codex_review")

    assert result.passed is False
    assert set(result.missing) == {
        "pm",
        "architecture",
        "team_plan",
        "phase_dev",
        "phase_test",
        "claude_lead_review",
        "codex_review",
    }


# ---------------------------------------------------------------------------
# State / gate consistency
# ---------------------------------------------------------------------------

from src.product_app.agent_pipeline_automation import (
    check_state_gate_consistency,
    sync_state_from_gates,
    write_json,
)


def _write_gate(tmp_path: Path, gate_name: str, *, passed: bool, found_keys: list[str] | None = None):
    """Helper to write a minimal gate JSON."""
    found = {}
    if found_keys:
        found = {k: [f"docs/{k}/dummy.md"] for k in found_keys}
    gate = {"passed": passed, "feature_id": "test-feature", "found": found, "missing": {}}
    write_json(tmp_path / ".agent" / "gates" / gate_name, gate)


def test_consistency_clean_when_no_gates(tmp_path: Path):
    """No gates means no conflicts."""
    state = build_feature_state(title="[Test] Consistency", feature_id="test-feature")
    write_feature_state(tmp_path, state)
    result = check_state_gate_consistency(tmp_path)
    assert result["consistent"] is True
    assert result["issues"] == []


def test_consistency_detects_stale_current_stage(tmp_path: Path):
    """current_stage=pm_pending but gate shows phase_dev passed -> issue."""
    state = build_feature_state(title="[Test] Stale Stage", feature_id="test-feature")
    write_feature_state(tmp_path, state)
    _write_gate(tmp_path, "phase_dev_gate.json", passed=True, found_keys=["pm", "architecture", "team_plan", "phase_dev"])

    result = check_state_gate_consistency(tmp_path)

    assert result["consistent"] is False
    issue_texts = " ".join(result["issues"])
    assert "current_stage" in issue_texts or "stage_status" in issue_texts


def test_consistency_detects_stale_stage_status(tmp_path: Path):
    """gate passed but stage_status still pending."""
    state = build_feature_state(title="[Test] Stale Status", feature_id="test-feature")
    write_feature_state(tmp_path, state)
    _write_gate(tmp_path, "phase_test_gate.json", passed=True, found_keys=["pm", "architecture", "team_plan", "phase_dev", "phase_test"])

    result = check_state_gate_consistency(tmp_path)

    stage_issues = [i for i in result["issues"] if "stage_status" in i]
    assert len(stage_issues) > 0
    assert any("phase_dev" in i or "phase_test" in i for i in stage_issues)


def test_consistency_detects_all_phases_not_tested(tmp_path: Path):
    """phase_test gate passed but all_phases_tested is false."""
    state = build_feature_state(title="[Test] Phases", feature_id="test-feature")
    write_feature_state(tmp_path, state)
    _write_gate(tmp_path, "phase_test_gate.json", passed=True, found_keys=["pm", "architecture", "team_plan", "phase_dev", "phase_test"])

    result = check_state_gate_consistency(tmp_path)

    tp_issues = [i for i in result["issues"] if "all_phases_tested" in i]
    assert len(tp_issues) > 0


def test_sync_repairs_stale_state(tmp_path: Path):
    """sync-state-from-gates repairs current_stage and stage_status."""
    state = build_feature_state(title="[Test] Repair", feature_id="test-feature")
    write_feature_state(tmp_path, state)

    for gate_name, fk in [
        ("phase_dev_gate.json", ["pm", "architecture", "team_plan", "phase_dev"]),
        ("phase_test_gate.json", ["pm", "architecture", "team_plan", "phase_dev", "phase_test"]),
        ("claude_lead_review_gate.json", ["pm", "architecture", "team_plan", "phase_dev", "phase_test", "claude_lead_review"]),
        ("codex_review_gate.json", ["pm", "architecture", "team_plan", "phase_dev", "phase_test", "claude_lead_review", "codex_review"]),
    ]:
        _write_gate(tmp_path, gate_name, passed=True, found_keys=fk)

    before = check_state_gate_consistency(tmp_path)
    assert before["consistent"] is False

    result = sync_state_from_gates(tmp_path)
    assert result["updated"] is True
    assert len(result["changes_made"]) > 0

    after = check_state_gate_consistency(tmp_path)
    assert after["consistent"] is True


def test_sync_respects_no_gates_no_changes(tmp_path: Path):
    """sync with no gates makes no changes."""
    state = build_feature_state(title="[Test] No Gates", feature_id="test-feature")
    write_feature_state(tmp_path, state)

    result = sync_state_from_gates(tmp_path)

    assert result["updated"] is False
    assert result["changes_made"] == []


def test_sync_does_not_mark_unpassed_stages(tmp_path: Path):
    """Only gates that actually passed cause stage_status changes."""
    state = build_feature_state(title="[Test] Partial", feature_id="test-feature")
    write_feature_state(tmp_path, state)

    _write_gate(tmp_path, "phase_dev_gate.json", passed=True, found_keys=["pm", "architecture", "team_plan", "phase_dev"])

    result = sync_state_from_gates(tmp_path)
    assert result["updated"] is True

    synced = check_state_gate_consistency(tmp_path)
    passed = synced["passed_stages"]
    assert passed.get("phase_dev") is True
    assert passed.get("phase_test") is False
    assert passed.get("claude_lead_review") is False
