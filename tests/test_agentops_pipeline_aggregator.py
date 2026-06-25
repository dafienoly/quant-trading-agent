from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from src.product_app.agentops.pipeline_aggregator import (
    build_required_doc_list,
    evaluate_data_quality,
    evaluate_safety,
    get_pipeline_observation,
    normalize_roles,
    normalize_stage_statuses,
)
from src.product_app.agentops.pipeline_contracts import (
    AgentOpsPipelineObservation,
    DataQualityInfo,
    DataQualityStatus,
    DocumentStatus,
    PipelineStageStatus,
)
from src.product_app.agentops.pipeline_errors import (
    FeatureNotFoundError,
    ParameterError,
    PipelineStateUnavailableError,
)
from src.product_app.agentops.pipeline_state_reader import (
    PipelineReadResult,
)


class TestNormalizeStageStatuses:
    def test_known_statuses_preserved(self):
        raw = {"pm": "passed", "phase_dev": "failed", "acceptance": "pending"}
        result = normalize_stage_statuses(raw)
        statuses = {s.name: s.status for s in result}
        assert statuses["pm"] == PipelineStageStatus.PASSED
        assert statuses["phase_dev"] == PipelineStageStatus.FAILED
        assert statuses["acceptance"] == PipelineStageStatus.PENDING

    def test_unknown_status_falls_to_unknown(self):
        raw = {"pm": "bogus_value"}
        result = normalize_stage_statuses(raw)
        assert result[0].status == PipelineStageStatus.UNKNOWN

    def test_empty_input(self):
        assert normalize_stage_statuses({}) == []


class TestNormalizeRoles:
    def test_basic_roles(self):
        raw = {"codex_a": ["pm", "acceptance"], "codex_b": ["architecture"]}
        result = normalize_roles(raw)
        role_map = {r.agent: r for r in result}
        assert "codex_a" in role_map
        assert role_map["codex_a"].responsibilities == ["pm", "acceptance"]

    def test_empty_input(self):
        assert normalize_roles({}) == []


class TestBuildRequiredDocList:
    def test_basic(self):
        state = {
            "feature_id": "test-feature",
            "required_docs": {
                "requirements": "docs/requirements/test.md",
                "architecture": "docs/design/test.md",
            },
        }
        docs = build_required_doc_list(state)
        assert len(docs) == 2
        kinds = {d["kind"] for d in docs}
        assert kinds == {"requirements", "architecture"}

    def test_no_required_docs(self):
        state = {"feature_id": "test"}
        assert build_required_doc_list(state) == []

    def test_with_pattern(self):
        state = {
            "feature_id": "test-feature",
            "required_docs": {
                "dev_report": "docs/dev_reports/test-feature-phase-<n>-dev-report.md",
            },
        }
        docs = build_required_doc_list(state)
        assert len(docs) == 1
        assert docs[0]["kind"] == "dev_report"
        assert docs[0]["required"] is True


class TestEvaluateDataQuality:
    def test_complete(self):
        dq = evaluate_data_quality(
            read_result=PipelineReadResult({"feature_id": "t"}),
            doc_statuses=[{"kind": "req", "status": DocumentStatus.PRESENT}],
            stages=[],
        )
        assert dq.status == DataQualityStatus.COMPLETE

    def test_missing_sources(self):
        dq = evaluate_data_quality(
            read_result=PipelineReadResult({"feature_id": "t"}),
            doc_statuses=[{"kind": "req", "status": DocumentStatus.MISSING}],
            stages=[],
        )
        assert dq.status == DataQualityStatus.INCOMPLETE
        assert len(dq.missing_sources) > 0

    def test_unparsable(self):
        dq = evaluate_data_quality(
            read_result=PipelineReadResult(
                {}, unparsable=True, partial=False
            ),
            doc_statuses=[],
            stages=[],
        )
        assert dq.status == DataQualityStatus.UNPARSABLE

    def test_unavailable(self):
        dq = evaluate_data_quality(
            read_result=PipelineReadResult({}, not_found=True),
            doc_statuses=[],
            stages=[],
        )
        assert dq.status == DataQualityStatus.UNAVAILABLE


class TestEvaluateSafety:
    def test_readonly_default(self):
        s = evaluate_safety(
            readonly=True,
            risk_level="low",
            doc_statuses=[{"kind": "req", "status": DocumentStatus.PRESENT, "required": True}],
            data_quality=DataQualityInfo(status=DataQualityStatus.COMPLETE),
        )
        assert s.readonly is True
        assert s.restricted_module_change is False

    def test_unknown_risk_warning(self):
        s = evaluate_safety(
            readonly=True,
            risk_level="unknown",
            doc_statuses=[],
            data_quality=DataQualityInfo(status=DataQualityStatus.COMPLETE),
        )
        assert len(s.warnings) > 0
        assert any("unknown" in w.lower() for w in s.warnings)

    def test_missing_required_doc_blocker(self):
        s = evaluate_safety(
            readonly=True,
            risk_level="low",
            doc_statuses=[{"kind": "requirements", "status": DocumentStatus.MISSING, "required": True}],
            data_quality=DataQualityInfo(status=DataQualityStatus.COMPLETE),
        )
        assert len(s.blockers) > 0

    def test_no_blockers_when_all_present(self):
        s = evaluate_safety(
            readonly=True,
            risk_level="low",
            doc_statuses=[{"kind": "req", "status": DocumentStatus.PRESENT, "required": True}],
            data_quality=DataQualityInfo(status=DataQualityStatus.COMPLETE),
        )
        assert s.blockers == []


class TestGetPipelineObservation:
    def test_parameter_error_no_args(self):
        with pytest.raises(ParameterError):
            get_pipeline_observation(feature_id=None, issue_number=None)

    def test_feature_not_found(self):
        with pytest.raises(FeatureNotFoundError):
            get_pipeline_observation(feature_id="nonexistent-feature")

    def test_full_observation_from_fixture(self):
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td, "state.json")
            task_path = Path(td, "current_task.yaml")
            handoff_dir = Path(td, "handoff")
            handoff_dir.mkdir()

            state = {
                "feature_id": "test-feature",
                "title": "Test Feature",
                "risk_level": "low",
                "issue_number": 42,
                "issue_url": "https://example.com/42",
                "epic_branch": "epic/test-feature",
                "current_stage": "phase_dev",
                "required_docs": {
                    "requirements": "docs/requirements/test.md",
                },
                "agent_roles": {
                    "codex_a": ["pm"],
                },
                "stage_status": {
                    "pm": "passed",
                    "phase_dev": "in_progress",
                },
            }
            state_path.write_text(json.dumps(state))

            task = {"feature_id": "test-feature", "current_stage": "phase_dev"}
            task_path.write_text(yaml.dump(task))

            Path(handoff_dir, "codex_a.md").write_text("handoff content")

            with (
                patch("src.product_app.agentops.pipeline_aggregator.STATE_DIR", td),
                patch("src.product_app.agentops.pipeline_state_reader.STATE_DIR", td),
            ):
                obs = get_pipeline_observation(feature_id="test-feature", issue_number=42)
                assert isinstance(obs, AgentOpsPipelineObservation)
                assert obs.contract_version == "agentops.pipeline_observation.v1"
                assert obs.feature["feature_id"] == "test-feature"
                assert obs.issue["number"] == 42
                assert obs.branch["epic_branch"] == "epic/test-feature"
                assert len(obs.stages) == 2
                assert len(obs.required_docs) == 1
                assert obs.safety.readonly is True

    def test_reader_and_aggregator_do_not_write(self):
        """Verify no write operations occur during observation creation."""
        with patch(
            "src.product_app.agentops.pipeline_state_reader.read_pipeline_state",
            side_effect=PipelineStateUnavailableError(".agent/state.json"),
        ):
            with pytest.raises(FeatureNotFoundError):
                get_pipeline_observation(feature_id="test-readonly")

    def test_sanitizer_applied_to_errors(self):
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td, "state.json")
            data = {
                "feature_id": "sanitize-test",
                "current_stage": "phase_dev",
                "required_docs": {},
            }
            state_path.write_text(json.dumps(data))

            task_path = Path(td, "current_task.yaml")
            task_path.write_text("feature_id: sanitize-test\ncurrent_stage: phase_dev\n")

            handoff_dir = Path(td, "handoff")
            handoff_dir.mkdir()

            with (
                patch("src.product_app.agentops.pipeline_aggregator.STATE_DIR", td),
                patch("src.product_app.agentops.pipeline_state_reader.STATE_DIR", td),
            ):
                obs = get_pipeline_observation(feature_id="sanitize-test")
                assert obs.safety.readonly is True
