"""Tests for issue-driven Agent pipeline automation helpers."""
from __future__ import annotations

from pathlib import Path

from src.product_app.agent_pipeline_automation import (
    STAGES_WITH_GATES,
    apply_stage_transition,
    advance_after_phase_test,
    build_feature_state,
    check_required_reports,
    check_state_gate_consistency,
    classify_changed_files,
    evaluate_stage_transition,
    extract_report_decision,
    normalize_gate_decision,
    read_state,
    register_stage_failure,
    set_pr_metadata,
    slugify_feature,
    sync_state_from_gates,
    sync_team_plan_metadata,
    validate_stage_delivery,
    validate_stage_start,
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

    assert slug.startswith("tencent-quote-provider")
    assert " " not in slug
    assert "!" not in slug
    # Non-ASCII (Chinese) must be stripped to avoid Windows encoding issues
    assert all(ord(c) < 128 for c in slug)


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
    assert "OpenCode Developer" in text
    assert "opencode-go/deepseek-v4-flash" in text


def test_feature_state_contains_team_pipeline_defaults():
    state = build_feature_state(
        title="[Feature] Agent Pipeline",
        feature_id="agent-pipeline",
        risk_level="docs-only",
        issue_number=12,
    )

    assert state["team_pipeline"]["mode"] == "opencode_lead_deepseek_dev_test"
    assert state["team_pipeline"]["total_phases"] == 1
    assert state["team_pipeline"]["completed_phases"] == []
    assert state["team_pipeline"]["all_phases_tested"] is False
    assert state["team_pipeline"]["max_codex_review_attempts"] == 3
    assert state["agent_roles"]["codex_a"] == ["pm", "acceptance"]
    assert state["agent_roles"]["opencode_lead"] == [
        "team_plan",
        "team_lead_review",
        "team_performance",
    ]
    assert state["agent_roles"]["opencode_developer"] == ["phase_dev", "bugfix"]
    assert state["agent_roles"]["opencode_tester"] == ["phase_test"]


def test_team_stage_runner_forces_requested_models_effort_and_skills():
    text = TEAM_STAGE_RUNNER.read_text(encoding="utf-8")

    assert 'OPENCODE_LEAD_MODEL="opencode-go/glm-5.2"' in text
    assert 'OPENCODE_TESTER_MODEL="opencode-go/deepseek-v4-pro"' in text
    assert 'OPENCODE_TESTER_VARIANT="max"' in text
    assert 'OPENCODE_DEVELOPER_MODEL="opencode-go/deepseek-v4-flash"' in text
    assert 'OPENCODE_DEVELOPER_VARIANT="max"' in text
    assert "--variant" in text
    assert "--model" in text
    assert "using-superpowers" in text
    assert "verification-before-completion" in text
    assert "systematic-debugging" in text
    assert "--agent build" in text
    assert "--permission-mode allow" not in text
    assert "--dangerously-skip-permissions" not in text
    assert "PIPELINE_RUNTIME_OK" in text
    assert "--preflight-only" in text
    assert "PREFLIGHT_TIMEOUT_SECONDS" in text
    assert "timeout --signal=TERM --kill-after=10s" in text
    assert text.count("--format json") == 4


def test_windows_team_runner_dispatches_to_repository_owned_wsl_runner():
    text = WINDOWS_TEAM_STAGE_RUNNER.read_text(encoding="utf-8")

    assert "scripts/run-pipeline-team-agent.sh" in text
    assert "wsl.exe" in text
    assert '"--cd", $wslRoot' in text
    assert '"bash", "-i", "scripts/run-pipeline-team-agent.sh"' in text
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
    assert "OpenCode Developer" in text
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
    assert '"feedback",' not in stage_runner
    assert "feedback/bugs/open/BUG_" in stage_runner
    assert "git add -f -- $evidencePath" in stage_runner
    assert "validate-stage-delivery" in stage_runner
    assert "steps.stage-gate.outputs.gate_passed" in stage_runner
    assert "route_back_to" in stage_runner
    assert "register-stage-failure" in stage_runner
    assert "retry_allowed" in stage_runner
    assert "agent-pr-validation.yml" in stage_runner
    assert "-f pr_number=$pr" in stage_runner
    assert "advance-phase" in stage_runner
    assert "Stage gate failed" in stage_runner


def test_stage_runner_has_one_dispatch_entry_and_serializes_by_pr():
    text = Path(".github/workflows/agent-stage-runner.yml").read_text(encoding="utf-8")

    trigger_block = text.split("permissions:", 1)[0]
    concurrency_block = text.split("concurrency:", 1)[1].split("defaults:", 1)[0]

    assert "workflow_dispatch:" in trigger_block
    assert "pull_request:" not in trigger_block
    assert "github.event.label" not in text
    assert "github.event.pull_request" not in text
    assert "agent-stage-pr-${{ inputs.pr_number || github.run_id }}" in concurrency_block
    assert "cancel-in-progress: false" in concurrency_block
    assert "validate-stage-start --stage $env:STAGE" in text
    assert "evaluate-stage-transition --stage $env:STAGE" in text
    assert "apply-stage-transition --stage $env:STAGE" in text


def test_stage_start_rejects_stale_queued_run(tmp_path: Path):
    state = build_feature_state(title="[Feature] Lease", feature_id="lease")
    state["current_stage"] = "phase_test_pending"
    write_feature_state(tmp_path, state)

    result = validate_stage_start(tmp_path, stage="claude_developer")

    assert result.passed is False
    assert result.expected_current_stage == "phase_dev_pending"
    assert result.actual_current_stage == "phase_test_pending"
    assert "stale_or_out_of_order_stage" in result.reasons


def test_stage_start_accepts_current_state_lease(tmp_path: Path):
    state = build_feature_state(title="[Feature] Lease", feature_id="lease")
    state["current_stage"] = "phase_test_pending"
    write_feature_state(tmp_path, state)

    result = validate_stage_start(tmp_path, stage="claude_tester")

    assert result.passed is True


def test_developer_transition_requires_report_and_delivery_gates(tmp_path: Path):
    state = build_feature_state(title="[Feature] Atomic", feature_id="atomic")
    state["current_stage"] = "phase_dev_pending"
    write_feature_state(tmp_path, state)
    write_json(
        tmp_path / ".agent/gates/phase_dev_gate.json",
        {"passed": True, "feature_id": "atomic", "decision": "PASS"},
    )
    write_json(
        tmp_path / ".agent/gates/phase_dev_delivery_gate.json",
        {
            "passed": False,
            "feature_id": "atomic",
            "current_phase": 1,
            "invalid": ["report_only_delivery"],
        },
    )

    result = evaluate_stage_transition(tmp_path, stage="claude_developer")

    assert result.passed is False
    assert result.report_gate_passed is True
    assert result.delivery_gate_passed is False
    assert result.failure_kind == "delivery_gate"
    assert result.route_back_to == ""


def test_tester_transition_routes_rejection_to_developer(tmp_path: Path):
    state = build_feature_state(title="[Feature] Atomic", feature_id="atomic")
    state["current_stage"] = "phase_test_pending"
    write_feature_state(tmp_path, state)
    write_json(
        tmp_path / ".agent/gates/phase_test_gate.json",
        {"passed": False, "feature_id": "atomic", "decision": "REJECTED"},
    )

    result = evaluate_stage_transition(tmp_path, stage="claude_tester")

    assert result.passed is False
    assert result.failure_kind == "report_gate"
    assert result.route_back_to == "claude_developer"


def test_passing_transition_commits_next_stage_state(tmp_path: Path):
    state = build_feature_state(title="[Feature] Atomic", feature_id="atomic")
    write_feature_state(tmp_path, state)
    write_json(
        tmp_path / ".agent/gates/stage_transition_gate.json",
        {
            "passed": True,
            "feature_id": "atomic",
            "stage": "codex_pm",
        },
    )

    result = apply_stage_transition(tmp_path, stage="codex_pm")

    assert result["updated"] is True
    assert read_state(tmp_path)["current_stage"] == "architecture_pending"
    assert read_state(tmp_path)["stage_status"]["pm"] == "passed"


def test_failed_developer_transition_enters_manual_state(tmp_path: Path):
    state = build_feature_state(title="[Feature] Atomic", feature_id="atomic")
    state["current_stage"] = "phase_dev_pending"
    write_feature_state(tmp_path, state)
    write_json(
        tmp_path / ".agent/gates/stage_transition_gate.json",
        {
            "passed": False,
            "feature_id": "atomic",
            "stage": "claude_developer",
            "route_back_to": "",
        },
    )

    result = apply_stage_transition(tmp_path, stage="claude_developer")

    assert result["passed"] is False
    assert read_state(tmp_path)["current_stage"] == "manual_approval_required"


def test_pr_validation_supports_explicit_bot_dispatch():
    text = PR_VALIDATION_WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in text
    assert "pr_number:" in text
    assert "github.event.inputs.pr_number" in text
    assert "github.event.pull_request.number || github.event.inputs.pr_number" in text


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

    assert "gh pr view $branch --json number,state,headRefName,url" in text
    assert "$existingPr.state -eq \"OPEN\"" in text
    assert "$existingPr.state -eq \"MERGED\"" in text
    assert "$existingPr.state -eq \"CLOSED\"" in text
    assert "set-pr-metadata" in text


def test_issue_bootstrap_reuses_open_pr_from_remote_branch():
    text = Path(".github/workflows/agent-issue-bootstrap.yml").read_text(encoding="utf-8")

    assert "git fetch origin $branch" in text
    assert "git switch -C $branch --track origin/$branch" in text


def test_issue_bootstrap_commits_pre_pr_stage_transitions():
    text = Path(".github/workflows/agent-issue-bootstrap.yml").read_text(encoding="utf-8")

    for stage in ("codex_pm", "codex_architect", "claude_lead_plan"):
        assert f"evaluate-stage-transition --stage {stage}" in text
        assert f"apply-stage-transition --stage {stage}" in text
    assert (
        "gh workflow run agent-stage-runner.yml --ref $branch "
        "-f stage=claude_lead_plan"
    ) not in text
    assert (
        "gh workflow run agent-stage-runner.yml --ref $branch "
        "-f stage=claude_developer -f pr_number=$pr"
    ) in text


def test_stage_runner_validates_dispatched_pr_is_open_and_matches_ref():
    text = Path(".github/workflows/agent-stage-runner.yml").read_text(encoding="utf-8")

    assert "Validate dispatched PR is open and matches ref" in text
    assert "gh pr view $pr --json number,state,headRefName,url" in text
    assert "$prState.state -ne \"OPEN\"" in text
    assert "$prState.headRefName -ne $expectedBranch" in text


def test_main_merge_gate_never_auto_merges():
    text = Path(".github/workflows/agent-main-merge-gate.yml").read_text(encoding="utf-8")

    assert "gh pr merge" not in text
    assert "requires manual review and merge" in text
    assert "Publish user acceptance entry to PR body" in text
    assert "agent_pipeline_acceptance_entry.py" in text
    assert "agent-user-acceptance:start" in text
    assert ".agent/reports/pr_acceptance_entry.md" in text
    assert "Enforce Pipeline diagnostic result" in text
    assert "steps.diagnostics.outputs.regression_status" in text
    assert "Require manual approval for non-auto-merge changes" in text
    assert "[System.IO.File]::WriteAllText($changedFilesPath" in text
    assert "Publish final acceptance status on PR head" in text
    assert 'context="Pipeline 最终验收"' in text
    assert "statuses: write" in text


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
    assert "!feedback/index.json" not in gitignore
    assert not Path("feedback/index.json").exists()


def test_tester_runner_cleans_runtime_feedback_index_before_path_guard():
    text = TEAM_STAGE_RUNNER.read_text(encoding="utf-8")

    cleanup_pos = text.index("cleanup_tester_runtime_artifacts")
    call_pos = text.rindex("    cleanup_tester_runtime_artifacts")
    guard_pos = text.rindex("    verify_tester_did_not_modify_business_code")

    assert cleanup_pos < call_pos < guard_pos
    assert "rm -f feedback/index.json" in text


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
    assert "route back to OpenCode Developer for the next phase unless all phases are complete" in handoff


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
    assert "OpenCode Developer" in developer
    assert "opencode-go/deepseek-v4-flash" in developer
    assert "variant=max" in developer
    assert "build Agent permissions" in developer
    assert "superpowers" in developer
    assert "OpenCode Team Leader" in review


def test_required_report_gate_finds_feature_reports(tmp_path: Path):
    feature_id = "agent-pipeline"
    files = {
        "docs/requirements/2026-06-12-agent-pipeline-requirements.md": _valid_requirements(feature_id),
        "docs/design/2026-06-12-agent-pipeline-architecture.md": _valid_architecture(feature_id),
        "docs/dev_plans/2026-06-12-agent-pipeline-team-plan.md": "ok",
        "docs/dev_reports/2026-06-12-agent-pipeline-phase-1-dev-report.md": (
            "## 变更范围\n\n`src/example.py`\n\n## 最终结论\n\nPASS\n"
        ),
    }
    for path, content in files.items():
        full_path = tmp_path / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
    write_json(
        tmp_path / ".agent/gates/phase_dev_delivery_gate.json",
        {
            "passed": True,
            "feature_id": feature_id,
            "invalid": [],
        },
    )

    result = check_required_reports(tmp_path, feature_id=feature_id, through_stage="phase_dev")

    assert result.passed is True
    assert result.missing == {}
    assert result.invalid == {}
    assert set(result.found) == {"pm", "architecture", "team_plan", "phase_dev"}


def test_developer_delivery_rejects_report_only_claims(tmp_path: Path):
    state = build_feature_state(
        title="[Feature] AgentOps",
        feature_id="agentops",
        risk_level="product",
    )
    write_feature_state(tmp_path, state)
    report = tmp_path / "docs/dev_reports/2026-06-24-agentops-phase-1-dev-report.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        """# 开发报告

## 变更范围

| 文件 | 说明 |
|---|---|
| src/product_app/agentops/observation.py | 新增模型 |
| tests/test_agentops_observation.py | 新增测试 |

## 最终结论

PASS
""",
        encoding="utf-8",
    )

    result = validate_stage_delivery(
        tmp_path,
        stage="claude_developer",
        changed_files=[str(report.relative_to(tmp_path))],
    )

    assert result.passed is False
    assert "report_only_delivery" in result.invalid
    assert "claimed_path_missing:src/product_app/agentops/observation.py" in result.invalid
    assert "claimed_path_missing:tests/test_agentops_observation.py" in result.invalid


def test_developer_delivery_accepts_real_implementation_and_test_diff(tmp_path: Path):
    state = build_feature_state(
        title="[Feature] AgentOps",
        feature_id="agentops",
        risk_level="product",
    )
    write_feature_state(tmp_path, state)
    paths = {
        "src/product_app/agentops/observation.py": "VALUE = 1\n",
        "tests/test_agentops_observation.py": "def test_value():\n    assert True\n",
    }
    for rel_path, content in paths.items():
        path = tmp_path / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    report = tmp_path / "docs/dev_reports/2026-06-24-agentops-phase-1-dev-report.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        """## 变更范围

- `src/product_app/agentops/observation.py`
- `tests/test_agentops_observation.py`

## 最终结论

PASS
""",
        encoding="utf-8",
    )
    changed = [*paths, str(report.relative_to(tmp_path))]

    result = validate_stage_delivery(
        tmp_path,
        stage="claude_developer",
        changed_files=changed,
    )

    assert result.passed is True
    assert result.claimed_files == sorted(paths)


def test_developer_delivery_accepts_explicit_docs_only_phase(tmp_path: Path):
    state = build_feature_state(
        title="[Feature] AgentOps",
        feature_id="agentops",
        risk_level="product",
    )
    state["team_pipeline"]["current_phase"] = 5
    state["team_pipeline"]["total_phases"] = 5
    write_feature_state(tmp_path, state)
    plan = tmp_path / "docs/dev_plans/2026-06-24-agentops-team-plan.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(
        "### Phase 4 — UI\n\n实现页面。\n\n"
        "### Phase 5 — 文档、报告与回归\n\n"
        "| Restricted modules | 无代码变更；仅文档与回归。 |\n",
        encoding="utf-8",
    )
    log_path = tmp_path / "docs/log/DEVELOPMENT_LOG.md"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("阶段五回归完成。\n", encoding="utf-8")
    report = tmp_path / "docs/dev_reports/2026-06-24-agentops-phase-5-dev-report.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        "# 第五阶段开发报告\n\n"
        "## 变更范围\n\n- `docs/log/DEVELOPMENT_LOG.md`\n\n"
        "## 最终结论\n\nPASS\n",
        encoding="utf-8",
    )

    result = validate_stage_delivery(
        tmp_path,
        stage="claude_developer",
        changed_files=[
            "docs/log/DEVELOPMENT_LOG.md",
            "docs/dev_reports/2026-06-24-agentops-phase-5-dev-report.md",
        ],
    )

    assert result.passed is True
    assert result.substantive_files == ["docs/log/DEVELOPMENT_LOG.md"]
    assert result.test_files == []


def test_legacy_delivery_gate_is_not_reused_for_later_phase(tmp_path: Path):
    state = build_feature_state(
        title="[Feature] AgentOps",
        feature_id="agentops",
        risk_level="product",
    )
    state["team_pipeline"]["current_phase"] = 2
    state["team_pipeline"]["total_phases"] = 3
    write_feature_state(tmp_path, state)
    write_json(
        tmp_path / ".agent/gates/phase_dev_delivery_gate.json",
        {
            "passed": True,
            "feature_id": "agentops",
            "substantive_files": ["src/product_app/agentops/phase_one.py"],
            "test_files": ["tests/test_agentops_phase_one.py"],
        },
    )
    report = tmp_path / "docs/dev_reports/2026-06-24-agentops-phase-2-dev-report.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("## 变更范围\n\n仅报告。\n\n## 最终结论\n\nPASS\n", encoding="utf-8")

    result = validate_stage_delivery(
        tmp_path,
        stage="claude_developer",
        changed_files=[str(report.relative_to(tmp_path))],
    )

    assert result.passed is False
    assert "report_only_delivery" in result.invalid


def test_developer_delivery_uses_latest_report_revision(tmp_path: Path):
    state = build_feature_state(
        title="[Feature] AgentOps",
        feature_id="agentops",
        risk_level="product",
    )
    write_feature_state(tmp_path, state)
    implementation = tmp_path / "src/product_app/agentops/observation.py"
    test_file = tmp_path / "tests/test_agentops_observation.py"
    implementation.parent.mkdir(parents=True, exist_ok=True)
    test_file.parent.mkdir(parents=True, exist_ok=True)
    implementation.write_text("VALUE = 1\n", encoding="utf-8")
    test_file.write_text("def test_value():\n    assert True\n", encoding="utf-8")
    report_dir = tmp_path / "docs/dev_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "2026-06-24-agentops-phase-1-dev-report.md").write_text(
        "## 变更范围\n\n- `src/product_app/agentops/missing.py`\n",
        encoding="utf-8",
    )
    revised_report = report_dir / "2026-06-24-agentops-phase-1-dev-report-r2.md"
    revised_report.write_text(
        "## 变更范围\n\n"
        "- `src/product_app/agentops/observation.py`\n"
        "- `tests/test_agentops_observation.py`\n",
        encoding="utf-8",
    )

    result = validate_stage_delivery(
        tmp_path,
        stage="claude_developer",
        changed_files=[
            "src/product_app/agentops/observation.py",
            "tests/test_agentops_observation.py",
            str(revised_report.relative_to(tmp_path)),
        ],
    )

    assert result.passed is True
    assert result.claimed_files == [
        "src/product_app/agentops/observation.py",
        "tests/test_agentops_observation.py",
    ]


def test_phase_test_rejected_decision_fails_gate(tmp_path: Path):
    feature_id = "agentops"
    files = {
        "docs/requirements/2026-06-24-agentops-requirements.md": _valid_requirements(feature_id),
        "docs/design/2026-06-24-agentops-architecture.md": _valid_architecture(feature_id),
        "docs/dev_plans/2026-06-24-agentops-team-plan.md": "### Phase 1\n",
        "docs/dev_reports/2026-06-24-agentops-phase-1-dev-report.md": "## 最终结论\n\nPASS\n",
        "docs/test_reports/2026-06-24-agentops-phase-1-test-report.md": (
            "## 最终结论\n\n**REJECTED**\n"
        ),
    }
    for rel_path, content in files.items():
        path = tmp_path / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    write_json(
        tmp_path / ".agent/gates/phase_dev_delivery_gate.json",
        {"passed": True, "feature_id": feature_id, "invalid": []},
    )

    result = check_required_reports(
        tmp_path,
        feature_id=feature_id,
        through_stage="phase_test",
    )

    assert result.passed is False
    assert result.decisions["phase_test"] == "REJECTED"
    assert any("blocking_decision:REJECTED" in item for item in result.invalid["phase_test"])


def test_latest_phase_test_report_can_close_older_rejection(tmp_path: Path):
    feature_id = "agentops"
    files = {
        "docs/requirements/2026-06-24-agentops-requirements.md": _valid_requirements(feature_id),
        "docs/design/2026-06-24-agentops-architecture.md": _valid_architecture(feature_id),
        "docs/dev_plans/2026-06-24-agentops-team-plan.md": "### Phase 1\n",
        "docs/dev_reports/2026-06-24-agentops-phase-1-dev-report.md": "## 最终结论\n\nPASS\n",
        "docs/test_reports/2026-06-24-agentops-phase-1-test-report.md": (
            "## Feedback Bug 文件\n\n"
            "`feedback/bugs/open/BUG_OLD.md`\n\n"
            "## 最终结论\n\nREJECTED\n"
        ),
        "docs/test_reports/2026-06-24-agentops-phase-1-test-report-r2.md": (
            "## 最终结论\n\nREJECTED\n"
        ),
        "docs/test_reports/2026-06-24-agentops-phase-1-test-report-r3.md": (
            "## 最终结论\n\nPASS\n"
        ),
    }
    for rel_path, content in files.items():
        path = tmp_path / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    write_json(
        tmp_path / ".agent/gates/phase_dev_delivery_gate.json",
        {"passed": True, "feature_id": feature_id, "invalid": []},
    )

    result = check_required_reports(
        tmp_path,
        feature_id=feature_id,
        through_stage="phase_test",
    )

    assert result.passed is True
    assert result.decisions["phase_test"] == "PASS"


def test_lead_changes_requested_decision_fails_gate(tmp_path: Path):
    assert extract_report_decision("## 最终结论\n\n**CHANGES_REQUESTED**") == "CHANGES_REQUESTED"


def test_team_plan_phase_count_and_intermediate_phase_advance(tmp_path: Path):
    state = build_feature_state(title="[Feature] Multi", feature_id="multi")
    write_feature_state(tmp_path, state)
    plan = tmp_path / "docs/dev_plans/2026-06-24-multi-team-plan.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text("### Phase 1\n\n### Phase 2\n\n### Phase 3\n", encoding="utf-8")

    metadata = sync_team_plan_metadata(tmp_path, feature_id="multi")
    assert metadata["total_phases"] == 3

    write_json(
        tmp_path / ".agent/gates/phase_test_gate.json",
        {
            "passed": True,
            "feature_id": "multi",
            "found": {"phase_test": ["docs/test_reports/phase-1.md"]},
        },
    )
    result = advance_after_phase_test(tmp_path)

    assert result["next_stage"] == "claude_developer"
    assert result["current_phase"] == 2
    assert result["all_phases_tested"] is False
    updated = read_state(tmp_path)
    assert updated["team_pipeline"]["completed_phases"] == [1]
    assert updated["current_stage"] == "phase_dev_pending"
    reset_gate = (
        tmp_path / ".agent/gates/phase_test_gate.json"
    ).read_text(encoding="utf-8")
    assert '"passed": false' in reset_gate
    synced = sync_state_from_gates(tmp_path)
    assert synced["updated"] is False
    assert read_state(tmp_path)["current_stage"] == "phase_dev_pending"


def test_phase_advance_migrates_missing_team_plan_metadata(tmp_path: Path):
    state = build_feature_state(title="[Feature] Multi", feature_id="multi")
    state["team_pipeline"].pop("total_phases")
    state["team_pipeline"].pop("completed_phases")
    write_feature_state(tmp_path, state)
    plan = tmp_path / "docs/dev_plans/2026-06-24-multi-team-plan.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(
        "\n".join(f"### Phase {number}" for number in range(1, 6)),
        encoding="utf-8",
    )
    write_json(
        tmp_path / ".agent/gates/phase_test_gate.json",
        {
            "passed": True,
            "feature_id": "multi",
            "found": {"phase_test": ["docs/test_reports/phase-1.md"]},
        },
    )

    result = advance_after_phase_test(tmp_path)

    assert result["advanced"] is True
    assert result["next_stage"] == "claude_developer"
    assert result["current_phase"] == 2
    assert result["total_phases"] == 5
    assert read_state(tmp_path)["team_pipeline"]["completed_phases"] == [1]


def test_phase_advance_fails_closed_when_team_plan_has_no_phase_headings(tmp_path: Path):
    state = build_feature_state(title="[Feature] Multi", feature_id="multi")
    write_feature_state(tmp_path, state)
    plan = tmp_path / "docs/dev_plans/2026-06-24-multi-team-plan.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text("# Team Plan\n\nNo deterministic phases.\n", encoding="utf-8")
    write_json(
        tmp_path / ".agent/gates/phase_test_gate.json",
        {"passed": True, "feature_id": "multi"},
    )

    result = advance_after_phase_test(tmp_path)

    assert result["advanced"] is False
    assert result["next_stage"] == ""
    assert result["reason"] == "team_plan_phase_metadata_unavailable"


def test_phase_test_failure_stops_after_retry_budget(tmp_path: Path):
    state = build_feature_state(title="[Feature] Retry", feature_id="retry")
    write_feature_state(tmp_path, state)
    gate = {
        "passed": False,
        "feature_id": "retry",
        "decision": "REJECTED",
        "invalid": {"phase_test": ["blocking_decision:REJECTED"]},
    }
    write_json(tmp_path / ".agent/gates/phase_test_gate.json", gate)

    first = register_stage_failure(tmp_path, stage="phase_test")
    second = register_stage_failure(tmp_path, stage="phase_test")
    third = register_stage_failure(tmp_path, stage="phase_test")

    assert first["retry_allowed"] is True
    assert second["retry_allowed"] is True
    assert third["retry_allowed"] is False
    assert third["route_back_to"] == ""
    assert third["reason"] == "phase_test_retry_budget_exhausted"
    assert read_state(tmp_path)["team_pipeline"]["phase_test_attempts"]["1"] == 3


def test_stale_feature_gate_does_not_pollute_current_state(tmp_path: Path):
    state = build_feature_state(title="[Feature] Current", feature_id="current-feature")
    write_feature_state(tmp_path, state)
    write_json(
        tmp_path / ".agent/gates/phase_test_gate.json",
        {
            "passed": True,
            "feature_id": "old-feature",
            "found": {"phase_test": ["docs/test_reports/old.md"]},
        },
    )

    result = check_state_gate_consistency(tmp_path)

    assert result["passed_stages"]["phase_test"] is False
    assert read_state(tmp_path)["current_stage"] == "pm_pending"


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
    state = read_state(tmp_path)
    gate = {
        "passed": passed,
        "feature_id": state.get("feature_id", "test-feature"),
        "found": found,
        "missing": {},
    }
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
    assert normalize_gate_decision("rejected") == "REJECTED"
