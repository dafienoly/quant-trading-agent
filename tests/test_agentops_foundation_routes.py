from __future__ import annotations

from fastapi.testclient import TestClient
from unittest.mock import patch

from src.api.app import app


class TestAgentOpsFoundationRoutes:
    def test_get_ops_summary_success(self):
        with patch("src.api.agentops_routes.build_ops_summary") as mock_summary:
            mock_summary.return_value.model_dump.return_value = {
                "contract_version": "ops_summary.v1",
                "readonly": True,
                "sections": [],
                "overall_status": "pass",
            }

            client = TestClient(app)
            response = client.get("/product/agentops/summary")

            assert response.status_code == 200
            body = response.json()
            assert body["contract_version"] == "ops_summary.v1"
            assert body["readonly"] is True
            mock_summary.return_value.model_dump.assert_called_once_with(mode="json")

    def test_get_runtime_profile_success(self):
        with patch("src.api.agentops_routes.resolve_agent_runtime") as mock_runtime:
            mock_runtime.return_value.model_dump.return_value = {
                "contract_version": "agent_runtime.profile.v1",
                "stage": "codex_pm",
                "mode": "disabled",
                "command_env_var": "CODEX_A_PM_AGENT_COMMAND",
                "command_fingerprint": "",
            }

            client = TestClient(app)
            response = client.get("/product/agentops/runtime/codex_pm")

            assert response.status_code == 200
            body = response.json()
            assert body["contract_version"] == "agent_runtime.profile.v1"
            assert body["stage"] == "codex_pm"
            assert "Invoke-Expression" not in str(body)
            mock_runtime.assert_called_once_with("codex_pm")

    def test_get_quality_summary_success(self):
        with patch("src.api.agentops_routes.build_quality_summary") as mock_quality:
            mock_quality.return_value.model_dump.return_value = {
                "contract_version": "quality_index.summary.v1",
                "readonly": True,
                "total_count": 0,
                "open_count": 0,
            }

            client = TestClient(app)
            response = client.get("/product/agentops/quality")

            assert response.status_code == 200
            body = response.json()
            assert body["contract_version"] == "quality_index.summary.v1"
            assert body["readonly"] is True
            mock_quality.return_value.model_dump.assert_called_once_with(mode="json")

    def test_new_agentops_routes_are_get_only(self):
        routes = [
            route
            for route in app.router.routes
            if getattr(route, "path", "").startswith("/product/agentops/")
        ]
        paths = {route.path: getattr(route, "methods", set()) for route in routes}

        assert "/product/agentops/summary" in paths
        assert "/product/agentops/runtime/{stage}" in paths
        assert "/product/agentops/quality" in paths
        for path, methods in paths.items():
            assert methods == {"GET"} or methods == {"HEAD"}, f"Non-GET method on {path}: {methods}"

    def test_ops_summary_internal_error_is_sanitized(self):
        with patch("src.api.agentops_routes.build_ops_summary") as mock_summary:
            mock_summary.side_effect = RuntimeError("boom at C:\\secret\\path line 99")

            client = TestClient(app)
            response = client.get("/product/agentops/summary")

            assert response.status_code == 500
            body = response.json()
            raw = str(body).lower()
            assert body["error"]["code"] == "INTERNAL_ERROR"
            assert "c:\\secret" not in raw
            assert "traceback" not in raw
