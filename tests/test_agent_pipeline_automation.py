"""Tests for issue-driven Agent pipeline automation helpers."""
from __future__ import annotations

from pathlib import Path

from src.product_app.agent_pipeline_automation import (
    STAGES_WITH_GATES,
    build_feature_state,
    check_required_reports,
    check_state_gate_consistency,
    classify_changed_files,
    normalize_gate_decision,
    read_state,
    set_pr_metadata,
    slugify_feature,
    sync_state_from_gates,
    write_feature_state,
    write_handoff,
    write_json,
)


RUNNER_REFERENCE = Path("docs/ops/agent-runners/run-codex-stage.ps1.reference")
PR_VALIDATION_WORKFLOW = Path(".github/workflows/agent-pr-validation.yml")
TEAM_STAGE_RUNNER = Path("scripts/run-pipeline-team-agent.sh")
WINDOWS_TEAM_STAGE_RUNNER = Path("scripts/run-team-stage.ps1")
RUNTIME_PREFLIGHT_WORKFLOW = Path(".github/workflows/agent-runtime-preflight.yml")
AGENT_ISSUE_TEMPLATE = Path(".github/ISSUE_TEMPLATE/agent_feature_request.yml")


def _valid_requirements(feature_id: str = "agent-pipeline") -> str:
    return f"""# {feature_id} Requirements

## User Goal

Generate traceable PM requirements.

## Functional Requirements

- Produce a requirements artifact.

## Non-functional Requirements

- Keep output deterministic.

## Acceptance Criteria

- Gate validation passes.

## Safety Constraints

- Do not bypass manual approval.
"""


def _valid_architecture(feature_id: str = "agent-pipeline") -> str:
    return f"""# {feature_id} Architecture

## Architecture Summary

Use the existing agent pipeline gates.

## Module Plan

- Keep changes in pipeline automation.

## Technical Decisions

- Validate generated artifacts before gate pass.

## Safety Impact

- No trading-sensitive behavior changes.

## Development Guidance

- Add regression tests.
"""


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
    assert "Claude Code Developer" in text
    assert "ultracode-xhigh" in text


def test_feature_state_contains_team_pipeline_defaults():
    state = build_feature_state(
        title="[Feature] Agent Pipeline",
        feature_id="agent-pipeline",
        risk_level="docs-only",
        issue_number=12,
    )

    assert state["team_pipeline"]["mode"] == "opencode_lead_claude_dev_opencode_test"
    assert state["team_pipeline"]["all_phases_tested"] is False
    assert state["team_pipeline"]["max_codex_review_attempts"] == 3
    assert state["agent_roles"]["codex_a"] == ["pm", "acceptance"]
    assert state["agent_roles"]["opencode_lead"] == [
        "team_plan",
        "team_lead_review",
        "team_performance",
    ]
    assert state["agent_roles"]["claude_developer"] == ["phase_dev", "bugfix"]
    assert state["agent_roles"]["opencode_tester"] == ["phase_test"]


def test_team_stage_runner_forces_requested_models_effort_and_skills():
    text = TEAM_STAGE_RUNNER.read_text(encoding="utf-8")

    assert 'OPENCODE_LEAD_MODEL="opencode-go/glm-5.2"' in text
    assert 'OPENCODE_TESTER_MODEL="opencode-go/deepseek-v4-pro"' in text
    assert 'OPENCODE_TESTER_VARIANT="max"' in text
    assert 'CLAUDE_DEVELOPER_MODEL="ultracode-xhigh"' in text
    assert 'CLAUDE_DEVELOPER_EFFORT="xhigh"' in text
    assert "--variant" in text
    assert "--model" in text
    assert "--effort" in text
    assert "using-superpowers" in text
    assert "verification-before-completion" in text
    assert "systematic-debugging" in text
    assert "/feature-dev" in text
    assert "superpowers:using-superpowers" in text
    assert "--permission-mode dontAsk" in text
    assert "--allowedTools" in text
    assert "--permission-mode allow" not in text
    assert "--dangerously-skip-permissions" not in text
    assert "PIPELINE_RUNTIME_OK" in text
    assert "--preflight-only" in text
    assert "PREFLIGHT_TIMEOUT_SECONDS" in text
    assert "timeout --signal=TERM --kill-after=10s" in text
    assert text.count("--format json") == 3


def test_windows_team_runner_dispatches_to_repository_owned_wsl_runner():
    text = WINDOWS_TEAM_STAGE_RUNNER.read_text(encoding="utf-8")

    assert "scripts/run-pipeline-team-agent.sh" in text
    assert "wsl.exe" in text
    assert '"--cd", $wslRoot' in text
    assert '"bash", "-l", "scripts/run-pipeline-team-agent.sh"' in text
    assert '"-lc"' not in text
    assert "$bashCommand" not in text
    assert "PreflightOnly" in text
    assert "Remove-Item -Force -ErrorAction SilentlyContinue $metadataPath" in text
    assert "runtime-preflight-$preflightRole.execution.json" in text
    assert "CLAUDE_LEAD_AGENT_COMMAND" not in text
    assert "CLAUDE_TESTER_AGENT_COMMAND" not in text


def test_runtime_preflight_workflow_probes_all_fixed_team_roles():
    text = RUNTIME_PREFLIGHT_WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in text
    assert "runs-on: [self-hosted, Windows, X64, local-windows-codex]" in text
    assert "-Stage claude_lead_plan -PreflightOnly" in text
    assert "-Stage claude_tester -PreflightOnly" in text
    assert "-Stage claude_developer -PreflightOnly" in text
    assert "actions/upload-artifact@v4" in text
    assert ".agent/tmp/runtime-preflight-*" in text
    assert "if-no-files-found: error" in text
    assert "include-hidden-files: true" in text
    assert "git push" not in text
    assert "gh pr merge" not in text


def test_existing_stage_runner_can_preflight_a_pr_branch_without_advancing_pipeline():
    text = Path(".github/workflows/agent-stage-runner.yml").read_text(encoding="utf-8")

    assert "- runtime_preflight" in text
    assert "runtime_role:" in text
    assert "inputs.stage != 'runtime_preflight'" in text
    assert "inputs.stage == 'runtime_preflight'" in text
    assert "-Stage claude_lead_plan -PreflightOnly" in text
    assert "-Stage claude_tester -PreflightOnly" in text
    assert "-Stage claude_developer -PreflightOnly" in text
    assert ".agent/tmp/runtime-preflight-*" in text
    assert "if-no-files-found: error" in text
    assert "include-hidden-files: true" in text


def test_agent_issue_template_uses_current_roles_and_manual_merge():
    text = AGENT_ISSUE_TEMPLATE.read_text(encoding="utf-8")

    assert "agent:pipeline" in text
    assert "stage:pm-pending" in text
    assert "OpenCode Lead" in text
    assert "Claude Code Developer" in text
    assert "OpenCode Test Engineer" in text
    assert "manual main merge" in text
    assert "Claude Code A" not in text
    assert "Claude Code B" not in text
    assert "Claude Code C" not in text
    assert "automatic main merge" not in text


def test_github_workflows_use_repository_owned_team_runner():
    stage_runner = Path(".github/workflows/agent-stage-runner.yml").read_text(encoding="utf-8")
    bootstrap = Path(".github/workflows/agent-issue-bootstrap.yml").read_text(encoding="utf-8")

    assert "run-team-stage.ps1" in stage_runner
    assert "run-team-stage.ps1" in bootstrap
    assert '"claude_lead_plan" { & .\\scripts\\run-team-stage.ps1' in stage_runner
    assert '"claude_developer" { & .\\scripts\\run-team-stage.ps1' in stage_runner
    assert '"claude_tester" { & .\\scripts\\run-team-stage.ps1' in stage_runner
    assert '"claude_lead_review" { & .\\scripts\\run-team-stage.ps1' in stage_runner
    assert '"bugfix" { & .\\scripts\\run-team-stage.ps1' in stage_runner
    assert "CLAUDE_TESTER_AGENT_COMMAND" not in stage_runner
    assert "CLAUDE_LEAD_AGENT_COMMAND" not in stage_runner
    assert '".github",' in stage_runner
    assert '"scripts",' in stage_runner


def test_feature_state_branch_includes_issue_number_for_restart_isolation():
    state = build_feature_state(
        title="[Feature] Agent Pipeline",
        feature_id="agent-pipeline",
        risk_level="docs-only",
        issue_number=62,
    )

    epic_branch = state["epic_branch"]

    assert epic_branch.startswith("epic/")
    assert epic_branch.endswith("-agent-pipeline-issue-62")

    date_part = epic_branch.split("/")[1].split("-")[0]
    assert len(date_part) == 8
    assert date_part.isdigit()


def test_same_feature_restarts_use_distinct_issue_scoped_branches():
    first = build_feature_state(
        title="[Feature] Agent Pipeline",
        feature_id="agent-pipeline",
        risk_level="docs-only",
        issue_number=62,
    )
    second = build_feature_state(
        title="[Feature] Agent Pipeline",
        feature_id="agent-pipeline",
        risk_level="docs-only",
        issue_number=63,
    )

    assert first["epic_branch"] != second["epic_branch"]
    assert first["epic_branch"].endswith("-issue-62")
    assert second["epic_branch"].endswith("-issue-63")


def test_pr_metadata_is_written_to_state_and_current_task(tmp_path: Path):
    state = build_feature_state(
        title="[Feature] Agent Pipeline",
        feature_id="agent-pipeline",
        risk_level="docs-only",
        issue_number=62,
    )
    write_feature_state(tmp_path, state)

    set_pr_metadata(tmp_path, pr_number=64, pr_url="https://github.com/dafienoly/quant-trading-agent/pull/64")

    updated = read_state(tmp_path)
    assert updated["pr_number"] == 64
    assert updated["pr_url"] == "https://github.com/dafienoly/quant-trading-agent/pull/64"
    assert updated["pull_request"]["number"] == 64
    task_text = (tmp_path / ".agent" / "current_task.yaml").read_text(encoding="utf-8")
    assert "pr_number: 64" in task_text


def test_issue_bootstrap_queries_pr_state_before_reuse():
    text = Path(".github/workflows/agent-issue-bootstrap.yml").read_text(encoding="utf-8")

    assert "gh pr view $branch --json number,state,merged,headRefName,url" in text
    assert "$existingPr.state -eq \"OPEN\"" in text
    assert "$existingPr.state -eq \"CLOSED\"" in text
    assert "set-pr-metadata" in text


def test_issue_bootstrap_reuses_open_pr_from_remote_branch():
    text = Path(".github/workflows/agent-issue-bootstrap.yml").read_text(encoding="utf-8")

    assert "git fetch origin $branch" in text
    assert "git switch -C $branch --track origin/$branch" in text


def test_stage_runner_validates_dispatched_pr_is_open_and_matches_ref():
    text = Path(".github/workflows/agent-stage-runner.yml").read_text(encoding="utf-8")

    assert "Validate dispatched PR is open and matches ref" in text
    assert "gh pr view $pr --json number,state,headRefName,url" in text
    assert "$prState.state -ne \"OPEN\"" in text
    assert "$prState.headRefName -ne $expectedBranch" in text


def test_main_merge_gate_never_auto_merges():
    text = Path(".github/workflows/agent-main-merge-gate.yml").read_text(encoding="utf-8")

    assert "gh pr merge" not in text
    assert "需要人工审阅和手动合并" in text


def test_pr_validation_runs_required_lightweight_checks():
    text = PR_VALIDATION_WORKFLOW.read_text(encoding="utf-8")

    assert "pull_request:" in text
    assert "python scripts/agent_pipeline_regression.py --strict" in text
    assert (
        "python -m pytest tests/test_agent_pipeline_automation.py "
        "tests/test_agent_pipeline_regression.py -q" in text
    )
    assert "mkdir -p runtime" in text
    assert "git diff --check" in text
    assert "git diff --name-only origin/main...HEAD" in text
    assert "git ls-files .agent/tmp .agent/reports" in text


def test_pr_validation_uploads_dashboard_even_when_validation_fails():
    text = PR_VALIDATION_WORKFLOW.read_text(encoding="utf-8")

    assert "if: always()" in text
    assert "actions/upload-artifact@v4" in text
    assert ".agent/reports/pipeline_report.json" in text
    assert ".agent/reports/pipeline_dashboard.html" in text
    assert "<!-- agent-pipeline-dashboard -->" in text
    assert "查看 Pipeline Dashboard" in text


def test_pr_validation_report_aggregates_all_step_outcomes():
    text = PR_VALIDATION_WORKFLOW.read_text(encoding="utf-8")

    assert "REGRESSION_OUTCOME: ${{ steps.regression.outcome }}" in text
    assert "TEST_OUTCOME: ${{ steps.tests.outcome }}" in text
    assert "DIFF_OUTCOME: ${{ steps.diff_check.outcome }}" in text
    assert "RESTRICTED_OUTCOME: ${{ steps.restricted.outcome }}" in text
    assert "TRACKED_OUTCOME: ${{ steps.tracked_files.outcome }}" in text
    assert '"workflow_step_outcomes"' in text
    assert 'report["status"] = "fail"' in text


def test_pipeline_workflows_keep_diagnostic_artifacts_on_failure():
    for workflow in (
        Path(".github/workflows/agent-stage-runner.yml"),
        Path(".github/workflows/agent-main-merge-gate.yml"),
    ):
        text = workflow.read_text(encoding="utf-8")
        assert "Generate Pipeline Diagnostic Report" in text
        assert "上传 Pipeline Dashboard artifact" in text
        assert "if: always()" in text
        assert "actions/upload-artifact@v4" in text
        assert ".agent/reports/pipeline_report.json" in text
        assert ".agent/reports/pipeline_dashboard.html" in text


def test_agent_report_runtime_directory_is_ignored_and_untracked():
    gitignore = Path(".gitignore").read_text(encoding="utf-8")

    assert ".agent/reports/" in gitignore


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

    assert "OpenCode Test Engineer" in handoff
    assert "opencode-go/deepseek-v4-pro" in handoff
    assert "variant=max" in handoff
    assert "superpowers" in handoff
    assert "route back to Claude Code Developer for the next phase unless all phases are complete" in handoff


def test_team_lead_and_developer_handoffs_pin_runtime_contract(tmp_path: Path):
    state = build_feature_state(
        title="[Feature] Agent Pipeline",
        feature_id="agent-pipeline",
        risk_level="docs-only",
        issue_number=12,
    )
    write_feature_state(tmp_path, state)

    lead = write_handoff(tmp_path, "claude_lead_plan").read_text(encoding="utf-8")
    developer = write_handoff(tmp_path, "claude_developer").read_text(encoding="utf-8")
    review = write_handoff(tmp_path, "claude_lead_review").read_text(encoding="utf-8")

    assert "OpenCode Team Leader" in lead
    assert "opencode-go/glm-5.2" in lead
    assert "Claude Code Developer" in developer
    assert "ultracode-xhigh" in developer
    assert "effort=xhigh" in developer
    assert "feature-dev workflow" in developer
    assert "superpowers" in developer
    assert "OpenCode Team Leader" in review


def test_required_report_gate_finds_feature_reports(tmp_path: Path):
    feature_id = "agent-pipeline"
    files = {
        "docs/requirements/2026-06-12-agent-pipeline-requirements.md": _valid_requirements(feature_id),
        "docs/design/2026-06-12-agent-pipeline-architecture.md": _valid_architecture(feature_id),
        "docs/dev_plans/2026-06-12-agent-pipeline-team-plan.md": "ok",
        "docs/dev_reports/2026-06-12-agent-pipeline-phase-1-dev-report.md": "ok",
    }
    for path, content in files.items():
        full_path = tmp_path / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")

    result = check_required_reports(tmp_path, feature_id=feature_id, through_stage="phase_dev")

    assert result.passed is True
    assert result.missing == {}
    assert result.invalid == {}
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


def test_corrupted_pm_artifact_fails_gate(tmp_path: Path):
    feature_id = "agent-pipeline"
    path = tmp_path / "docs/requirements/2026-06-12-agent-pipeline-requirements.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("$($EventArgs.Data)\n", encoding="utf-8")

    result = check_required_reports(tmp_path, feature_id=feature_id, through_stage="pm")

    assert result.passed is False
    assert "pm" in result.invalid
    assert any("artifact_contains_literal_eventargs_data" in item for item in result.invalid["pm"])


def test_corrupted_architecture_artifact_fails_gate(tmp_path: Path):
    feature_id = "agent-pipeline"
    path = tmp_path / "docs/design/2026-06-12-agent-pipeline-architecture.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("$($EventArgs.Data)\n", encoding="utf-8")
    req_path = tmp_path / "docs/requirements/2026-06-12-agent-pipeline-requirements.md"
    req_path.parent.mkdir(parents=True, exist_ok=True)
    req_path.write_text(_valid_requirements(feature_id), encoding="utf-8")

    result = check_required_reports(tmp_path, feature_id=feature_id, through_stage="architecture")

    assert result.passed is False
    assert "architecture" in result.invalid
    assert any("artifact_contains_literal_eventargs_data" in item for item in result.invalid["architecture"])


def test_pm_missing_headings_fails_gate(tmp_path: Path):
    feature_id = "agent-pipeline"
    path = tmp_path / "docs/requirements/2026-06-12-agent-pipeline-requirements.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {feature_id} Requirements\n\n## User Goal\n\nOnly one section.\n", encoding="utf-8")

    result = check_required_reports(tmp_path, feature_id=feature_id, through_stage="pm")

    assert result.passed is False
    assert "pm" in result.invalid
    assert any("Functional Requirements" in item for item in result.invalid["pm"])


def test_architecture_missing_headings_fails_gate(tmp_path: Path):
    feature_id = "agent-pipeline"
    req_path = tmp_path / "docs/requirements/2026-06-12-agent-pipeline-requirements.md"
    req_path.parent.mkdir(parents=True, exist_ok=True)
    req_path.write_text(_valid_requirements(feature_id), encoding="utf-8")
    arch_path = tmp_path / "docs/design/2026-06-12-agent-pipeline-architecture.md"
    arch_path.parent.mkdir(parents=True, exist_ok=True)
    arch_path.write_text(f"# {feature_id} Architecture\n\n## Architecture Summary\n\nToo thin.\n", encoding="utf-8")

    result = check_required_reports(tmp_path, feature_id=feature_id, through_stage="architecture")

    assert result.passed is False
    assert "architecture" in result.invalid
    assert any("Module Plan" in item for item in result.invalid["architecture"])


def test_runner_reference_contains_no_register_object_event():
    text = RUNNER_REFERENCE.read_text(encoding="utf-8-sig")

    assert "Register-ObjectEvent" not in text
    assert "$($EventArgs.Data)" not in text


def test_runner_reference_does_not_use_sequential_read_to_end_deadlock_pattern():
    text = RUNNER_REFERENCE.read_text(encoding="utf-8-sig")

    assert "ReadToEnd()" not in text
    assert "StandardOutput.ReadToEnd" not in text
    assert "StandardError.ReadToEnd" not in text


def test_runner_reference_uses_agent_tmp_files_for_pm_and_architect():
    text = RUNNER_REFERENCE.read_text(encoding="utf-8-sig")

    for suffix in ["prompt.md", "runner.sh", "stdout.log", "stderr.log", "output.md", "exitcode"]:
        assert f"$StageName.{suffix}" in text
    assert '-StageName "codex_pm"' in text
    assert '-StageName "codex_architect"' in text


def test_runner_reference_avoids_powershell_pipe_capture_for_codex_output():
    text = RUNNER_REFERENCE.read_text(encoding="utf-8-sig")

    assert "RedirectStandardOutput = $true" not in text
    assert "RedirectStandardError = $true" not in text


# ---------------------------------------------------------------------------
# State / gate consistency
# ---------------------------------------------------------------------------

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
