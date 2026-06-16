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
    FULL_STAGE_ORDER,
    STAGES_WITH_GATES,
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


def _write_auto_merge_gate(tmp_path: Path, *, requires_manual: bool):
    gate = {
        "eligible_for_auto_main_merge": not requires_manual,
        "requires_manual_approval": requires_manual,
        "risk_level": "manual-main-approval" if requires_manual else "safe-auto-main",
        "changed_files": [],
        "restricted_files": [],
        "unsafe_files": [],
        "safe_files": [],
        "reasons": ["changed_files_outside_auto_merge_allowlist"] if requires_manual else [],
    }
    write_json(tmp_path / ".agent" / "gates" / "auto_merge_gate.json", gate)


def _gates_up_to(limit: str) -> list[tuple[str, list[str]]]:
    """Return (gate_name, found_keys) pairs for all stages up to *limit*."""
    stages_keys = {
        "phase_dev": ["pm", "architecture", "team_plan", "phase_dev"],
        "phase_test": ["pm", "architecture", "team_plan", "phase_dev", "phase_test"],
        "claude_lead_review": ["pm", "architecture", "team_plan", "phase_dev", "phase_test", "claude_lead_review"],
        "codex_review": ["pm", "architecture", "team_plan", "phase_dev", "phase_test", "claude_lead_review", "codex_review"],
        "acceptance": ["pm", "architecture", "team_plan", "phase_dev", "phase_test", "claude_lead_review", "codex_review", "acceptance"],
    }
    result = []
    for s in STAGES_WITH_GATES:
        if s in stages_keys:
            result.append((f"{s}_gate.json", stages_keys[s]))
        if s == limit:
            break
    return result


# -- current_stage progression tests ------------------------------------

def test_phase_dev_passed_sets_next_merge_gate_pending(tmp_path: Path):
    """When acceptance gate passes, expected current_stage = merge_gate_pending."""
    state = build_feature_state(title="[Test]", feature_id="test-feature-x")
    write_feature_state(tmp_path, state)
    for gname, fk in _gates_up_to("acceptance"):
        _write_gate(tmp_path, gname, passed=True, found_keys=fk)

    result = check_state_gate_consistency(tmp_path)
    assert result["consistent"] is False
    # The checker should flag pm_pending as stale when acceptance passed
    cs_issue = [i for i in result["issues"] if "current_stage" in i]
    assert len(cs_issue) > 0
    assert "merge_gate_pending" in cs_issue[0] or "manual_approval" in cs_issue[0]


def test_sync_sets_merge_gate_pending_when_acceptance_passed(tmp_path: Path):
    """sync-state-from-gates repairs current_stage=pm_pending → merge_gate_pending."""
    state = build_feature_state(title="[Test]", feature_id="test-feature-y")
    write_feature_state(tmp_path, state)
    for gname, fk in _gates_up_to("acceptance"):
        _write_gate(tmp_path, gname, passed=True, found_keys=fk)

    # Sanity: it's stale
    before = check_state_gate_consistency(tmp_path)
    assert before["consistent"] is False

    result = sync_state_from_gates(tmp_path)
    assert result["updated"] is True

    # Verify no pm_pending regression: the target must be merge_gate_pending
    cs_changes = [c for c in result["changes_made"] if "current_stage" in c]
    assert len(cs_changes) > 0
    assert any("→" in c and "merge_gate_pending" in c for c in cs_changes), \
        f"expected merge_gate_pending target, got: {cs_changes}"

    after = check_state_gate_consistency(tmp_path)
    assert after["consistent"] is True


def test_sync_no_regression_pm_pending_when_all_passed(tmp_path: Path):
    """After acceptance passed, sync MUST NOT set current_stage=pm_pending."""
    state = build_feature_state(title="[Test]", feature_id="test-no-regress")
    write_feature_state(tmp_path, state)
    for gname, fk in _gates_up_to("acceptance"):
        _write_gate(tmp_path, gname, passed=True, found_keys=fk)

    result = sync_state_from_gates(tmp_path)
    cs_changes = [c for c in result["changes_made"] if "current_stage" in c]
    for c in cs_changes:
        # The change message says old→new. Check that the TARGET (after →) is NOT pm_pending.
        after_arrow = c.split("→")[-1].strip().strip("'").strip('"')
        assert after_arrow != "pm_pending", \
            f"REGRESSION: current_stage should NOT become pm_pending: {c}"
    # Final check
    after = check_state_gate_consistency(tmp_path)
    assert after["consistent"] is True


def test_manual_approval_required_when_auto_merge_gate_present(tmp_path: Path):
    """When auto_merge_gate requires manual, current_stage→manual_approval_required."""
    state = build_feature_state(title="[Test]", feature_id="test-manual")
    write_feature_state(tmp_path, state)
    for gname, fk in _gates_up_to("acceptance"):
        _write_gate(tmp_path, gname, passed=True, found_keys=fk)
    _write_auto_merge_gate(tmp_path, requires_manual=True)

    result = sync_state_from_gates(tmp_path)
    assert result["updated"] is True
    cs_changes = [c for c in result["changes_made"] if "current_stage" in c]
    cs_text = " ".join(cs_changes)
    assert "manual_approval_required" in cs_text, f"expected manual_approval_required, got: {cs_text}"


# -- stage_status tests --------------------------------------------------

def test_consistency_clean_when_no_gates(tmp_path: Path):
    """No gates means no conflicts."""
    state = build_feature_state(title="[Test] Consistency", feature_id="test-feature")
    write_feature_state(tmp_path, state)
    result = check_state_gate_consistency(tmp_path)
    assert result["consistent"] is True
    assert result["issues"] == []


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


# -- sync repair tests ---------------------------------------------------

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


# -- implicit pre-gate stage inference -----------------------------------

def test_pre_gate_stages_passed_when_downstream_gate_evidence(tmp_path: Path):
    """pm, architecture, team_plan inferred passed when phase_dev gate passed."""
    state = build_feature_state(title="[Test]", feature_id="test-pregate")
    write_feature_state(tmp_path, state)
    _write_gate(tmp_path, "phase_dev_gate.json", passed=True, found_keys=["pm", "architecture", "team_plan", "phase_dev"])

    passed = check_state_gate_consistency(tmp_path)["passed_stages"]
    assert passed.get("pm") is True
    assert passed.get("architecture") is True
    assert passed.get("team_plan") is True


# ---------------------------------------------------------------------------
# Gate decision normalization
# ---------------------------------------------------------------------------

from src.product_app.agent_pipeline_automation import normalize_gate_decision


def test_normalize_accepted():
    assert normalize_gate_decision("accepted") == "ACCEPTED"
    assert normalize_gate_decision("ACCEPTED") == "ACCEPTED"
    assert normalize_gate_decision("Accepted") == "ACCEPTED"


def test_normalize_accepted_with_notes():
    assert normalize_gate_decision("accepted_with_notes") == "ACCEPTED_WITH_NOTES"
    assert normalize_gate_decision("accepted-with-notes") == "ACCEPTED_WITH_NOTES"
    assert normalize_gate_decision("ACCEPTED_WITH_NOTES") == "ACCEPTED_WITH_NOTES"


def test_normalize_changes_requested():
    assert normalize_gate_decision("changes_requested") == "CHANGES_REQUESTED"
    assert normalize_gate_decision("changes-requested") == "CHANGES_REQUESTED"
    assert normalize_gate_decision("CHANGES_REQUESTED") == "CHANGES_REQUESTED"


def test_normalize_blocked():
    assert normalize_gate_decision("blocked") == "BLOCKED"
    assert normalize_gate_decision("BLOCKED") == "BLOCKED"


def test_normalize_approved():
    assert normalize_gate_decision("approved") == "APPROVED"
    assert normalize_gate_decision("APPROVED") == "APPROVED"


def test_normalize_approved_with_notes():
    assert normalize_gate_decision("approved_with_notes") == "APPROVED_WITH_NOTES"
    assert normalize_gate_decision("approved-with-notes") == "APPROVED_WITH_NOTES"
    assert normalize_gate_decision("APPROVED_WITH_NOTES") == "APPROVED_WITH_NOTES"


def test_normalize_unknown_returns_none():
    assert normalize_gate_decision(None) is None
    assert normalize_gate_decision("") is None
    assert normalize_gate_decision("foobar") is None
    assert normalize_gate_decision("rejected") is None
