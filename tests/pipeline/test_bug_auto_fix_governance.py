from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from scripts.pipeline.bug_auto_fix_governance import (
    BugAutoFixCandidate,
    BugAutoFixGovernanceEvaluator,
    TestEvidence,
)

POLICY_PATH = Path(
    "docs/pipeline/bug_auto_fix_governance_policy.yaml"
)


def _load_policy() -> dict:
    with open(POLICY_PATH) as f:
        return yaml.safe_load(f)


def _make_candidate(
    touched_files: list[str] | None = None,
    candidate_files: list[str] | None = None,
    test_evidence: list[TestEvidence] | None = None,
    change_kind: str | None = None,
    artifact_branch: str | None = None,
    artifact_run_id: str | None = None,
    change_summary: str = "test fix",
    feature_id: str = "bug-auto-fix-system-governance",
    issue_number: int = 122,
    run_id: str = "run-001",
    branch: str = "feat/bug-auto-fix-system-governance/core",
    base_branch: str = "epic/20260629-bug-auto-fix-system-governance-issue-122",
    stage: str = "bugfix",
    review_evidence: dict | None = None,
) -> BugAutoFixCandidate:
    return BugAutoFixCandidate(
        feature_id=feature_id,
        issue_number=issue_number,
        run_id=run_id,
        branch=branch,
        base_branch=base_branch,
        stage=stage,
        candidate_files=candidate_files or touched_files or [],
        touched_files=touched_files or candidate_files or [],
        change_summary=change_summary,
        change_kind=change_kind,
        diff_stats={"files_changed": len(touched_files or [])},
        test_evidence=test_evidence or [],
        review_evidence=review_evidence,
        artifact_branch=artifact_branch or branch,
        artifact_run_id=artifact_run_id or run_id,
    )


def _make_test_evidence(
    command: str = "pytest tests/pipeline/",
    exit_code: int = 0,
    summary: str = "All tests passed",
) -> TestEvidence:
    return TestEvidence(
        command=command,
        exit_code=exit_code,
        summary=summary,
    )


class TestNormalPaths:
    """Scenarios that should result in ALLOW_AUTO_FIX."""

    def test_1_documentation_typo_fix(self):
        policy = _load_policy()
        candidate = _make_candidate(
            touched_files=["docs/README.md"],
            change_kind="typo",
            test_evidence=[_make_test_evidence()],
        )
        evaluator = BugAutoFixGovernanceEvaluator(policy)
        decision = evaluator.evaluate(candidate)
        assert decision.auto_fix_decision == "ALLOW_AUTO_FIX", (
            f"Expected ALLOW_AUTO_FIX, got {decision.auto_fix_decision}: "
            f"{decision.decision_reason}"
        )

    def test_2_test_fixture_update(self):
        policy = _load_policy()
        candidate = _make_candidate(
            touched_files=["tests/fixtures/input.csv"],
            change_kind="fixture_update",
            test_evidence=[_make_test_evidence()],
        )
        evaluator = BugAutoFixGovernanceEvaluator(policy)
        decision = evaluator.evaluate(candidate)
        assert decision.auto_fix_decision == "ALLOW_AUTO_FIX", (
            f"Expected ALLOW_AUTO_FIX, got {decision.auto_fix_decision}"
        )

    def test_3_test_assertion_correction(self):
        policy = _load_policy()
        candidate = _make_candidate(
            touched_files=["tests/test_foo.py"],
            change_kind="assertion_correction",
            test_evidence=[_make_test_evidence()],
        )
        evaluator = BugAutoFixGovernanceEvaluator(policy)
        decision = evaluator.evaluate(candidate)
        assert decision.auto_fix_decision == "ALLOW_AUTO_FIX", (
            f"Expected ALLOW_AUTO_FIX, got {decision.auto_fix_decision}"
        )


class TestNegativePaths:
    """Scenarios that should result in blocking decisions."""

    def test_4_non_whitelisted_business_logic(self):
        policy = _load_policy()
        candidate = _make_candidate(
            touched_files=[
                "src/product_app/feedback_service.py"
            ],
            change_kind="bugfix",
            test_evidence=[_make_test_evidence()],
        )
        evaluator = BugAutoFixGovernanceEvaluator(policy)
        decision = evaluator.evaluate(candidate)
        assert decision.auto_fix_decision == "BLOCK_NOT_WHITELISTED", (
            f"Expected BLOCK_NOT_WHITELISTED, got "
            f"{decision.auto_fix_decision}"
        )

    def test_5_restricted_risk_engine(self):
        policy = _load_policy()
        candidate = _make_candidate(
            touched_files=["src/risk_engine/risk_evaluator.py"],
            change_kind="bugfix",
        )
        evaluator = BugAutoFixGovernanceEvaluator(policy)
        decision = evaluator.evaluate(candidate)
        assert decision.auto_fix_decision == "BLOCK_RESTRICTED_MODULE"

    def test_6_restricted_execution_engine(self):
        policy = _load_policy()
        candidate = _make_candidate(
            touched_files=["src/execution_engine/broker.py"],
            change_kind="bugfix",
        )
        evaluator = BugAutoFixGovernanceEvaluator(policy)
        decision = evaluator.evaluate(candidate)
        assert decision.auto_fix_decision == "BLOCK_RESTRICTED_MODULE"

    def test_7_restricted_data_gateway(self):
        policy = _load_policy()
        candidate = _make_candidate(
            touched_files=["src/data_gateway/provider.py"],
            change_kind="bugfix",
        )
        evaluator = BugAutoFixGovernanceEvaluator(policy)
        decision = evaluator.evaluate(candidate)
        assert decision.auto_fix_decision == "BLOCK_RESTRICTED_MODULE"

    def test_8_restricted_product_app_tools(self):
        policy = _load_policy()
        candidate = _make_candidate(
            touched_files=["src/product_app/tools/tool.py"],
            change_kind="bugfix",
        )
        evaluator = BugAutoFixGovernanceEvaluator(policy)
        decision = evaluator.evaluate(candidate)
        assert decision.auto_fix_decision == "BLOCK_RESTRICTED_MODULE"

    def test_9_multi_file_with_restricted(self):
        policy = _load_policy()
        candidate = _make_candidate(
            touched_files=[
                "docs/README.md",
                "src/risk_engine/eval.py",
            ],
            change_kind="typo",
        )
        evaluator = BugAutoFixGovernanceEvaluator(policy)
        decision = evaluator.evaluate(candidate)
        assert decision.auto_fix_decision == "BLOCK_RESTRICTED_MODULE"

    def test_10_missing_candidate_files(self):
        policy = _load_policy()
        candidate = _make_candidate(
            touched_files=["docs/README.md"],
            candidate_files=[],
            change_kind="typo",
        )
        evaluator = BugAutoFixGovernanceEvaluator(policy)
        decision = evaluator.evaluate(candidate)
        assert decision.auto_fix_decision == "BLOCK_INSUFFICIENT_EVIDENCE"

    def test_11_missing_evidence_fields(self):
        policy = _load_policy()
        candidate = _make_candidate(
            touched_files=["docs/README.md"],
            change_kind="typo",
            feature_id="",
            issue_number=0,
        )
        evaluator = BugAutoFixGovernanceEvaluator(policy)
        decision = evaluator.evaluate(candidate)
        assert decision.auto_fix_decision == "BLOCK_INSUFFICIENT_EVIDENCE"

    def test_12_missing_test_evidence(self):
        policy = _load_policy()
        candidate = _make_candidate(
            touched_files=["docs/README.md"],
            change_kind="typo",
            test_evidence=[],
        )
        evaluator = BugAutoFixGovernanceEvaluator(policy)
        decision = evaluator.evaluate(candidate)
        assert decision.auto_fix_decision == "BLOCK_INSUFFICIENT_EVIDENCE"

    def test_13_test_failure(self):
        policy = _load_policy()
        candidate = _make_candidate(
            touched_files=["docs/README.md"],
            change_kind="typo",
            test_evidence=[
                _make_test_evidence(exit_code=1, summary="1 failed")
            ],
        )
        evaluator = BugAutoFixGovernanceEvaluator(policy)
        decision = evaluator.evaluate(candidate)
        assert decision.auto_fix_decision == "BLOCK_INSUFFICIENT_EVIDENCE"

    def test_14_secret_like_content(self):
        policy = _load_policy()
        candidate = _make_candidate(
            touched_files=["docs/README.md"],
            change_kind="typo",
            change_summary="fix config with password=123456",
            test_evidence=[_make_test_evidence()],
        )
        evaluator = BugAutoFixGovernanceEvaluator(policy)
        decision = evaluator.evaluate(candidate)
        assert decision.auto_fix_decision == "REQUIRE_MANUAL_APPROVAL"

    def test_15_manual_approval_policy_live_trading(self):
        policy = _load_policy()
        candidate = _make_candidate(
            touched_files=["docs/README.md"],
            change_kind="typo",
            change_summary="enable live-trading endpoint",
            test_evidence=[_make_test_evidence()],
        )
        evaluator = BugAutoFixGovernanceEvaluator(policy)
        decision = evaluator.evaluate(candidate)
        assert decision.auto_fix_decision == "REQUIRE_MANUAL_APPROVAL"

    def test_16_stale_cross_branch_artifact(self):
        policy = _load_policy()
        candidate = _make_candidate(
            touched_files=["docs/README.md"],
            change_kind="typo",
            test_evidence=[_make_test_evidence()],
            artifact_branch="main",
            artifact_run_id="old-run-001",
        )
        evaluator = BugAutoFixGovernanceEvaluator(policy)
        decision = evaluator.evaluate(candidate)
        assert decision.auto_fix_decision == "BLOCK_INSUFFICIENT_EVIDENCE"


class TestOptionalNegativePaths:
    """Additional boundary tests (recommended but not mandatory)."""

    def test_17_policy_unreadable(self):
        evaluator = BugAutoFixGovernanceEvaluator(None)
        candidate = _make_candidate(
            touched_files=["docs/README.md"],
            change_kind="typo",
            test_evidence=[_make_test_evidence()],
        )
        decision = evaluator.evaluate(candidate)
        assert decision.auto_fix_decision == "BLOCK_INSUFFICIENT_EVIDENCE"

    def test_18_invalid_candidate_missing_branch(self):
        policy = _load_policy()
        candidate = _make_candidate(
            touched_files=["docs/README.md"],
            branch="",
            change_kind="typo",
        )
        evaluator = BugAutoFixGovernanceEvaluator(policy)
        decision = evaluator.evaluate(candidate)
        assert decision.auto_fix_decision == "BLOCK_INSUFFICIENT_EVIDENCE"

    def test_19_codex_review_three_failures(self):
        policy = _load_policy()
        candidate = _make_candidate(
            touched_files=["tests/test_foo.py"],
            change_kind="assertion_correction",
            test_evidence=[_make_test_evidence()],
            review_evidence={
                "status": "failed",
                "attempts": 3,
                "codex_review_attempts": 3,
            },
        )
        evaluator = BugAutoFixGovernanceEvaluator(policy)
        decision = evaluator.evaluate(candidate)
        assert decision.auto_fix_decision == "REQUIRE_MANUAL_APPROVAL"

    def test_20_workflow_file_touched(self):
        policy = _load_policy()
        candidate = _make_candidate(
            touched_files=[".github/workflows/ci.yml"],
            change_kind="bugfix",
        )
        evaluator = BugAutoFixGovernanceEvaluator(policy)
        decision = evaluator.evaluate(candidate)
        assert decision.auto_fix_decision in (
            "BLOCK_RESTRICTED_MODULE",
            "REQUIRE_MANUAL_APPROVAL",
        )


class TestCLI:
    """Test the CLI entry point."""

    def test_cli_help(self):
        from scripts.pipeline.bug_auto_fix_governance import main

        with patch("sys.argv", ["bug_auto_fix_governance.py", "--help"]):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 0


class TestDecisionOutput:
    """Verify governance decision JSON output contains all required fields."""

    def test_decision_json_fields(self):
        policy = _load_policy()
        candidate = _make_candidate(
            touched_files=["docs/README.md"],
            change_kind="typo",
            test_evidence=[_make_test_evidence()],
        )
        evaluator = BugAutoFixGovernanceEvaluator(policy)
        decision = evaluator.evaluate(candidate)

        required_fields = [
            "feature_id",
            "issue_number",
            "run_id",
            "candidate_files",
            "change_summary",
            "risk_level",
            "allowed_by_whitelist",
            "restricted_module_touched",
            "manual_approval_required",
            "auto_fix_decision",
            "decision_reason",
            "audit_artifact_path",
        ]
        d = decision.to_dict()
        for field in required_fields:
            assert field in d, (
                f"Missing required field: {field}"
            )

    def test_decision_json_serializable(self):
        policy = _load_policy()
        candidate = _make_candidate(
            touched_files=["docs/README.md"],
            change_kind="typo",
            test_evidence=[_make_test_evidence()],
        )
        evaluator = BugAutoFixGovernanceEvaluator(policy)
        decision = evaluator.evaluate(candidate)
        json_str = json.dumps(decision.to_dict(), ensure_ascii=False)
        parsed = json.loads(json_str)
        assert parsed["auto_fix_decision"] == "ALLOW_AUTO_FIX"


class TestPathNormalization:
    """Verify path normalization rules."""

    def test_windows_backslash_normalized(self):
        policy = _load_policy()
        candidate = _make_candidate(
            touched_files=[
                "src\\risk_engine\\risk_evaluator.py"
            ],
            change_kind="bugfix",
        )
        evaluator = BugAutoFixGovernanceEvaluator(policy)
        decision = evaluator.evaluate(candidate)
        assert decision.auto_fix_decision == "BLOCK_RESTRICTED_MODULE"

    def test_leading_dot_slash_removed(self):
        policy = _load_policy()
        candidate = _make_candidate(
            touched_files=["./docs/README.md"],
            change_kind="typo",
            test_evidence=[_make_test_evidence()],
        )
        evaluator = BugAutoFixGovernanceEvaluator(policy)
        decision = evaluator.evaluate(candidate)
        assert decision.auto_fix_decision == "ALLOW_AUTO_FIX"

    def test_allowed_by_whitelist_flag_true_on_allow(self):
        policy = _load_policy()
        candidate = _make_candidate(
            touched_files=["docs/README.md"],
            change_kind="typo",
            test_evidence=[_make_test_evidence()],
        )
        evaluator = BugAutoFixGovernanceEvaluator(policy)
        decision = evaluator.evaluate(candidate)
        assert decision.allowed_by_whitelist is True

    def test_allowed_by_whitelist_flag_false_on_block(self):
        policy = _load_policy()
        candidate = _make_candidate(
            touched_files=["src/product_app/feedback_service.py"],
            change_kind="bugfix",
        )
        evaluator = BugAutoFixGovernanceEvaluator(policy)
        decision = evaluator.evaluate(candidate)
        assert decision.allowed_by_whitelist is False
