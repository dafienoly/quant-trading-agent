from __future__ import annotations

from src.product_app.agentops.pipeline_contracts import (
    AgentOpsPipelineObservation,
    ControlTowerViewStatus,
    DataQualityInfo,
    DataQualityStatus,
    DocumentStatus,
    ErrorInfo,
    PipelineStageInfo,
    PipelineStageStatus,
    RoleInfo,
    SafetyInfo,
)


class TestPipelineStageStatus:
    def test_values(self):
        assert PipelineStageStatus.PENDING == "pending"
        assert PipelineStageStatus.IN_PROGRESS == "in_progress"
        assert PipelineStageStatus.PASSED == "passed"
        assert PipelineStageStatus.FAILED == "failed"
        assert PipelineStageStatus.BLOCKED == "blocked"
        assert PipelineStageStatus.SKIPPED == "skipped"
        assert PipelineStageStatus.UNKNOWN == "unknown"

    def test_unknown_fallback(self):
        assert PipelineStageStatus("nonexistent") == PipelineStageStatus.UNKNOWN


class TestDocumentStatus:
    def test_values(self):
        assert DocumentStatus.PRESENT == "present"
        assert DocumentStatus.MISSING == "missing"
        assert DocumentStatus.STALE == "stale"
        assert DocumentStatus.UNREADABLE == "unreadable"
        assert DocumentStatus.UNKNOWN == "unknown"

    def test_unknown_fallback(self):
        assert DocumentStatus("garbage") == DocumentStatus.UNKNOWN


class TestDataQualityStatus:
    def test_values(self):
        assert DataQualityStatus.COMPLETE == "complete"
        assert DataQualityStatus.INCOMPLETE == "incomplete"
        assert DataQualityStatus.UNAVAILABLE == "unavailable"
        assert DataQualityStatus.UNPARSABLE == "unparsable"
        assert DataQualityStatus.STALE == "stale"
        assert DataQualityStatus.UNKNOWN == "unknown"

    def test_unknown_fallback(self):
        assert DataQualityStatus("bogus") == DataQualityStatus.UNKNOWN


class TestControlTowerViewStatus:
    def test_values(self):
        assert ControlTowerViewStatus.READY == "ready"
        assert ControlTowerViewStatus.EMPTY == "empty"
        assert ControlTowerViewStatus.STALE == "stale"
        assert ControlTowerViewStatus.ERROR == "error"
        assert ControlTowerViewStatus.BLOCKED == "blocked"


class TestErrorInfo:
    def test_minimal(self):
        err = ErrorInfo(code="NOT_FOUND", message="not found", source="test.yaml")
        assert err.code == "NOT_FOUND"
        assert err.message == "not found"
        assert err.source == "test.yaml"
        assert err.safe_detail == ""

    def test_full(self):
        err = ErrorInfo(
            code="PARSE_FAILED",
            message="parse failed",
            source=".agent/state.json",
            safe_detail="YAML error at line 3",
        )
        assert err.safe_detail == "YAML error at line 3"


class TestPipelineStageInfo:
    def test_minimal(self):
        stage = PipelineStageInfo(name="phase_dev", status=PipelineStageStatus.PENDING)
        assert stage.name == "phase_dev"
        assert stage.status == PipelineStageStatus.PENDING
        assert stage.source == ""
        assert stage.notes == []

    def test_full(self):
        stage = PipelineStageInfo(
            name="phase_dev",
            status=PipelineStageStatus.FAILED,
            source=".agent/current_task.yaml",
            notes=["Missing required doc"],
        )
        assert stage.notes == ["Missing required doc"]


class TestRoleInfo:
    def test_minimal(self):
        role = RoleInfo(agent="codex_a", responsibilities=["pm"])
        assert role.agent == "codex_a"
        assert role.responsibilities == ["pm"]
        assert role.status == ""

    def test_full(self):
        role = RoleInfo(
            agent="codex_a",
            responsibilities=["pm", "acceptance"],
            status="passed",
        )
        assert role.status == "passed"


class TestSafetyInfo:
    def test_defaults(self):
        s = SafetyInfo()
        assert s.readonly is True
        assert s.trading_modules_touched == []
        assert s.restricted_module_change is False
        assert s.warnings == []
        assert s.blockers == []

    def test_with_values(self):
        s = SafetyInfo(
            readonly=True,
            trading_modules_touched=[],
            restricted_module_change=False,
            warnings=["Unknown risk level"],
            blockers=["Required doc missing: requirements"],
        )
        assert s.blockers == ["Required doc missing: requirements"]


class TestDataQualityInfo:
    def test_defaults(self):
        dq = DataQualityInfo()
        assert dq.status == DataQualityStatus.UNKNOWN
        assert dq.missing_sources == []
        assert dq.unparsable_sources == []
        assert dq.stale_sources == []

    def test_with_values(self):
        dq = DataQualityInfo(
            status=DataQualityStatus.INCOMPLETE,
            missing_sources=["docs/requirements/missing.md"],
        )
        assert dq.missing_sources == ["docs/requirements/missing.md"]


class TestAgentOpsPipelineObservation:
    def test_contract_version(self):
        obs = AgentOpsPipelineObservation(
            feature={"feature_id": "test", "title": "", "risk_level": "low", "current_stage": ""},
            issue={"number": 1, "url": ""},
            branch={"epic_branch": ""},
        )
        assert obs.contract_version == "agentops.pipeline_observation.v1"

    def test_generated_at_is_set(self):
        from datetime import datetime

        obs = AgentOpsPipelineObservation(
            feature={"feature_id": "test", "title": "", "risk_level": "low", "current_stage": ""},
            issue={"number": 1, "url": ""},
            branch={"epic_branch": ""},
        )
        assert isinstance(obs.generated_at, datetime)
        assert obs.generated_at.tzinfo is not None

    def test_full_observation(self):
        obs = AgentOpsPipelineObservation(
            contract_version="agentops.pipeline_observation.v1",
            feature={
                "feature_id": "test-feature",
                "title": "Test Feature",
                "risk_level": "low",
                "current_stage": "phase_dev",
            },
            issue={"number": 42, "url": "https://github.com/example/issue/42"},
            branch={"epic_branch": "epic/2026-test-feature"},
            stages=[
                PipelineStageInfo(name="pm", status=PipelineStageStatus.PASSED),
                PipelineStageInfo(name="phase_dev", status=PipelineStageStatus.FAILED),
            ],
            roles=[
                RoleInfo(agent="codex_a", responsibilities=["pm"]),
            ],
            required_docs=[
                {
                    "kind": "requirements",
                    "path": "docs/requirements/test.md",
                    "status": DocumentStatus.PRESENT,
                    "source": "pipeline_state.required_docs",
                    "required": True,
                }
            ],
            safety=SafetyInfo(readonly=True),
            data_quality=DataQualityInfo(status=DataQualityStatus.COMPLETE),
            errors=[ErrorInfo(code="NONE", message="", source="")],
        )
        assert obs.feature["feature_id"] == "test-feature"
        assert len(obs.stages) == 2
        assert len(obs.required_docs) == 1
        assert obs.required_docs[0]["status"] == DocumentStatus.PRESENT

    def test_empty_stages_default(self):
        obs = AgentOpsPipelineObservation(
            feature={"feature_id": "test", "title": "", "risk_level": "low", "current_stage": ""},
            issue={"number": 1, "url": ""},
            branch={"epic_branch": ""},
        )
        assert obs.stages == []
        assert obs.roles == []
        assert obs.required_docs == []
        assert obs.errors == []
