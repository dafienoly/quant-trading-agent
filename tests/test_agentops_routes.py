"""Tests for agentops readonly API routes."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.app import app
from src.product_app.agentops.pipeline_contracts import (
    AgentOpsHealth,
    AgentOpsPipelineObservation,
    ControlTowerReadiness,
    ControlTowerViewStatus,
    DataQualityInfo,
    DataQualityStatus,
    DocumentStatus,
    PipelineInstanceSummary,
    PipelineStageInfo,
    PipelineStageStatus,
    ReadinessStatus,
    SafetyInfo,
)
from src.product_app.agentops.pipeline_errors import (
    FeatureNotFoundError,
    ParameterError,
    PipelineStateUnavailableError,
    PipelineStateUnparsableError,
)


def _make_sample_observation(feature_id: str = "test-feature") -> AgentOpsPipelineObservation:
    return AgentOpsPipelineObservation(
        feature={"feature_id": feature_id, "title": "Test Feature", "risk_level": "low", "current_stage": "dev"},
        issue={"number": 1, "url": ""},
        branch={"epic_branch": f"epic/{feature_id}"},
        pipeline_instance=PipelineInstanceSummary(
            instance_id=feature_id,
            feature_id=feature_id,
            issue_number=1,
            title="Test Feature",
            current_stage="dev",
            risk_level="low",
            stage_counts={"in_progress": 1},
            required_docs_total=1,
            required_docs_present=1,
            readonly=True,
        ),
        readiness=ControlTowerReadiness(
            status=ReadinessStatus.INCOMPLETE,
            next_action="Wait for in-progress stage to finish or inspect its handoff/report.",
            in_progress_stages=["dev"],
            confidence="medium",
        ),
        stages=[PipelineStageInfo(name="dev", status=PipelineStageStatus.IN_PROGRESS, source=".agent/state.json")],
        required_docs=[
            {"kind": "requirements", "path": "docs/requirements/test.md", "status": DocumentStatus.PRESENT, "source": "pipeline_state.required_docs", "required": True}
        ],
        safety=SafetyInfo(readonly=True),
        data_quality=DataQualityInfo(status=DataQualityStatus.COMPLETE),
    )


class TestAgentOpsRoutes:
    """Tests for /product/agentops endpoints."""

    def test_agentops_health_success(self):
        """GET /product/agentops/health returns readonly health metadata."""
        with patch("src.api.agentops_routes.get_agentops_health") as mock_health:
            mock_health.return_value = AgentOpsHealth(
                status=ControlTowerViewStatus.READY,
                readonly=True,
                available_routes=["/product/agentops/health"],
                observed_sources=[".agent/state.json"],
                notes=["AgentOps readonly routes are available."],
            )

            client = TestClient(app)
            response = client.get("/product/agentops/health")
            assert response.status_code == 200
            body = response.json()
            assert body["contract_version"] == "agentops.health.v1"
            assert body["readonly"] is True
            assert body["status"] == "ready"
            assert "/product/agentops/health" in body["available_routes"]

    def test_get_pipeline_by_feature_id_success(self):
        """GET /product/agentops/pipelines/{feature_id} returns 200 with observation."""
        with patch("src.api.agentops_routes.get_pipeline_observation") as mock_get:
            mock_get.return_value = _make_sample_observation("my-feature")

            client = TestClient(app)
            response = client.get("/product/agentops/pipelines/my-feature")
            assert response.status_code == 200
            body = response.json()
            assert body["contract_version"] == "agentops.pipeline_observation.v2"
            assert body["feature"]["feature_id"] == "my-feature"
            assert body["pipeline_instance"]["feature_id"] == "my-feature"
            assert body["readiness"]["status"] == "incomplete"

    def test_get_pipeline_by_issue_number_success(self):
        """GET /product/agentops/pipelines/by-issue/{issue_number} returns 200."""
        with patch("src.api.agentops_routes.get_pipeline_observation") as mock_get:
            mock_get.return_value = _make_sample_observation("issue-feature")

            client = TestClient(app)
            response = client.get("/product/agentops/pipelines/by-issue/42")
            assert response.status_code == 200
            body = response.json()
            assert body["contract_version"] == "agentops.pipeline_observation.v2"
            assert "readiness" in body
            assert "pipeline_instance" in body

    def test_missing_both_params_returns_422(self):
        """Missing both feature_id and issue_number returns 422."""
        with patch("src.api.agentops_routes.get_pipeline_observation") as mock_get:
            mock_get.side_effect = ParameterError("feature_id or issue_number is required")

            client = TestClient(app)
            response = client.get("/product/agentops/pipelines/")
            assert response.status_code == 404  # FastAPI path not found for trailing slash

    def test_feature_not_found_returns_404(self):
        """Non-existent feature_id returns 404."""
        with patch("src.api.agentops_routes.get_pipeline_observation") as mock_get:
            mock_get.side_effect = FeatureNotFoundError("nonexistent")

            client = TestClient(app)
            response = client.get("/product/agentops/pipelines/nonexistent")
            assert response.status_code == 404
            body = response.json()
            assert "error" in body
            assert body["error"]["code"] == "FEATURE_NOT_FOUND"

    def test_pipeline_state_unavailable_returns_503(self):
        """Data source unavailable returns 503."""
        with patch("src.api.agentops_routes.get_pipeline_observation") as mock_get:
            mock_get.side_effect = PipelineStateUnavailableError(".agent/state.json")

            client = TestClient(app)
            response = client.get("/product/agentops/pipelines/unavailable-test")
            assert response.status_code == 503
            body = response.json()
            assert body["error"]["code"] == "PIPELINE_STATE_UNAVAILABLE"

    def test_pipeline_state_unparsable_returns_422(self):
        """Unparsable state returns 422."""
        with patch("src.api.agentops_routes.get_pipeline_observation") as mock_get:
            mock_get.side_effect = PipelineStateUnparsableError(".agent/state.json")

            client = TestClient(app)
            response = client.get("/product/agentops/pipelines/unparsable-test")
            assert response.status_code == 422
            body = response.json()
            assert body["error"]["code"] == "PIPELINE_STATE_UNPARSABLE"

    def test_internal_error_returns_500_without_traceback(self):
        """Unexpected exception returns 500 with sanitized body (no traceback)."""
        with patch("src.api.agentops_routes.get_pipeline_observation") as mock_get:
            mock_get.side_effect = RuntimeError("Something went wrong")

            client = TestClient(app)
            response = client.get("/product/agentops/pipelines/crash-test")
            assert response.status_code == 500
            body = response.json()
            assert "error" in body
            assert body["error"]["code"] == "INTERNAL_ERROR"
            sensitive_patterns = ["traceback", "File ", "line ", "/mnt/", "C:\\"]
            raw = str(body).lower()
            for pat in sensitive_patterns:
                assert pat.lower() not in raw, f"Response contains sensitive pattern: {pat}"

    def test_agentops_router_only_has_get_methods(self):
        """Only GET methods are registered under /product/agentops prefix."""
        agentops_routes = []
        for r in app.router.routes:
            t = type(r).__name__
            if t == "_IncludedRouter" and r.include_context.prefix == "/product/agentops":
                agentops_routes.extend(r.include_context.included_router.routes)
        assert len(agentops_routes) > 0, "No agentops routes found"
        for route in agentops_routes:
            methods = getattr(route, "methods", set())
            assert methods == {"GET"} or methods == {"HEAD"}, f"Non-GET method on {route.path}: {methods}"

    def test_aggregator_called_with_correct_params(self):
        """get_pipeline_observation is called with correct feature_id."""
        with patch("src.api.agentops_routes.get_pipeline_observation") as mock_get:
            mock_get.return_value = _make_sample_observation("check-params")

            client = TestClient(app)
            response = client.get("/product/agentops/pipelines/check-params")
            assert response.status_code == 200
            mock_get.assert_called_once_with(feature_id="check-params", issue_number=None)

    def test_aggregator_called_with_issue_number(self):
        """get_pipeline_observation is called with correct issue_number."""
        with patch("src.api.agentops_routes.get_pipeline_observation") as mock_get:
            mock_get.return_value = _make_sample_observation("issue-test")

            client = TestClient(app)
            response = client.get("/product/agentops/pipelines/by-issue/99")
            assert response.status_code == 200
            mock_get.assert_called_once_with(feature_id=None, issue_number=99)
