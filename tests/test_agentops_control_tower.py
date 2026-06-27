from __future__ import annotations

import json
from pathlib import Path

from src.product_app.agentops import pipeline_aggregator as aggregator


def _write_state(agent_dir: Path, state: dict) -> None:
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "state.json").write_text(
        json.dumps(state, ensure_ascii=False),
        encoding="utf-8",
    )


def test_agentops_health_reports_empty_when_state_missing(tmp_path, monkeypatch):
    agent_dir = tmp_path / ".agent"
    monkeypatch.setattr(aggregator, "STATE_DIR", str(agent_dir))

    health = aggregator.get_agentops_health()

    assert health.readonly is True
    assert health.status.value == "empty"
    assert "/product/agentops/health" in health.available_routes
    assert health.observed_sources


def test_pipeline_observation_includes_ready_summary(tmp_path, monkeypatch):
    agent_dir = tmp_path / ".agent"
    req_doc = tmp_path / "docs" / "requirements" / "r0-2.md"
    req_doc.parent.mkdir(parents=True, exist_ok=True)
    req_doc.write_text("# R0.2 requirements\n\n内容完整。", encoding="utf-8")
    _write_state(
        agent_dir,
        {
            "feature_id": "r0-2-agentops",
            "title": "R0.2 AgentOps",
            "issue_number": 102,
            "issue_url": "https://example.invalid/issues/102",
            "risk_level": "low",
            "current_stage": "acceptance",
            "epic_branch": "feat/r0.2-agentops-control-tower",
            "stage_status": {
                "pm": "passed",
                "architecture": "passed",
                "acceptance": "passed",
            },
            "agent_roles": {
                "pm": ["requirements"],
                "architect": ["design"],
            },
            "required_docs": {
                "requirements": str(req_doc),
            },
        },
    )
    monkeypatch.setattr(aggregator, "STATE_DIR", str(agent_dir))

    observation = aggregator.get_pipeline_observation(feature_id="r0-2-agentops")

    assert observation.contract_version == "agentops.pipeline_observation.v2"
    assert observation.pipeline_instance.feature_id == "r0-2-agentops"
    assert observation.pipeline_instance.issue_number == 102
    assert observation.pipeline_instance.required_docs_total == 1
    assert observation.pipeline_instance.required_docs_present == 1
    assert observation.pipeline_instance.stage_counts["passed"] == 3
    assert observation.readiness.status.value == "ready"
    assert observation.readiness.confidence == "high"
    assert observation.safety.readonly is True


def test_pipeline_observation_blocks_when_required_doc_missing(tmp_path, monkeypatch):
    agent_dir = tmp_path / ".agent"
    missing_doc = tmp_path / "docs" / "requirements" / "missing.md"
    _write_state(
        agent_dir,
        {
            "feature_id": "missing-doc-feature",
            "title": "Missing Doc Feature",
            "issue_number": 103,
            "risk_level": "low",
            "current_stage": "architecture",
            "stage_status": {
                "pm": "passed",
                "architecture": "in_progress",
            },
            "required_docs": {
                "requirements": str(missing_doc),
            },
        },
    )
    monkeypatch.setattr(aggregator, "STATE_DIR", str(agent_dir))

    observation = aggregator.get_pipeline_observation(issue_number=103)

    assert observation.data_quality.status.value == "incomplete"
    assert observation.pipeline_instance.required_docs_missing == 1
    assert observation.readiness.status.value == "blocked"
    assert observation.readiness.missing_docs == [str(missing_doc)]
    assert observation.readiness.blockers
    assert "Required doc missing" in observation.readiness.next_action


def test_pipeline_observation_reports_failed_stage_as_blocker(tmp_path, monkeypatch):
    agent_dir = tmp_path / ".agent"
    req_doc = tmp_path / "docs" / "requirements" / "ok.md"
    req_doc.parent.mkdir(parents=True, exist_ok=True)
    req_doc.write_text("# ok", encoding="utf-8")
    _write_state(
        agent_dir,
        {
            "feature_id": "failed-stage-feature",
            "title": "Failed Stage Feature",
            "issue_number": 104,
            "risk_level": "low",
            "current_stage": "test",
            "stage_status": {
                "pm": "passed",
                "test": "failed",
            },
            "required_docs": {
                "requirements": str(req_doc),
            },
        },
    )
    monkeypatch.setattr(aggregator, "STATE_DIR", str(agent_dir))

    observation = aggregator.get_pipeline_observation(feature_id="failed-stage-feature")

    assert observation.readiness.status.value == "blocked"
    assert observation.readiness.failed_stages == ["test"]
    assert any("Failed stages" in blocker for blocker in observation.readiness.blockers)
