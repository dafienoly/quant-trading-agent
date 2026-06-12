"""Tests for product_routes: runtime services, signal explain, AI guard."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from src.api.app import app


class TestRuntimeServices:
    """Tests for GET /product/runtime/services."""

    @patch("src.llm.model_router.ModelRouter.get_config")
    @patch("src.product_app.service_manager.get_service_manager")
    def test_runtime_services_includes_aktools_llm_dashboard(
        self, mock_svc_mgr, mock_config
    ):
        """Extended runtime services include akTools, LLM, dashboard fields."""
        mock_manager = MagicMock()
        mock_manager.list_jobs.return_value = []
        mock_svc_mgr.return_value = mock_manager

        mock_config.return_value = MagicMock(
            provider="deepseek",
            model="deepseek-v4-flash",
            api_key_present=True,
        )

        client = TestClient(app)
        response = client.get("/product/runtime/services")
        assert response.status_code == 200
        body = response.json()
        svc = body.get("services", {})
        assert "aktools" in svc
        assert "dashboard" in svc
        assert "llm" in svc
        assert "api" in svc
        assert "bug_fix_agent" in svc

    @patch("src.llm.model_router.ModelRouter.get_config")
    @patch("src.product_app.service_manager.get_service_manager")
    def test_runtime_services_llm_status_ok(
        self, mock_svc_mgr, mock_config
    ):
        """LLM status in runtime services shows provider and model."""
        mock_manager = MagicMock()
        mock_manager.list_jobs.return_value = []
        mock_svc_mgr.return_value = mock_manager

        mock_config.return_value = MagicMock(
            provider="deepseek",
            model="deepseek-v4-flash",
            api_key_present=True,
        )

        client = TestClient(app)
        response = client.get("/product/runtime/services")
        body = response.json()
        llm = body["services"]["llm"]
        assert llm["provider"] == "deepseek"
        assert llm["model"] == "deepseek-v4-flash"
        assert llm["api_key_present"] is True


class TestSignalExplainEndpoint:
    """Tests for POST /product/ai/signals/{signal_id}/explain."""

    def test_signal_explain_returns_not_found_for_missing_signal(self, monkeypatch):
        """Signal explanation returns not_found when signal does not exist."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
        monkeypatch.setenv("LLM_API_KEY_ENV", "DEEPSEEK_API_KEY")

        with patch("src.api.product_routes._get_live_signal_orchestrator") as mock_orch:
            mock_orchestrator = MagicMock()
            mock_orchestrator.get_signal_status.return_value = {
                "status": "not_found",
                "signal": None,
                "message": "Signal SIG_MISSING_001 not found",
            }
            mock_orch.return_value = mock_orchestrator

            client = TestClient(app)
            response = client.post("/product/ai/signals/SIG_MISSING_001/explain")
            assert response.status_code == 200  # FastAPI returns 200 for all routes
            body = response.json()
            assert body["status"] == "not_found"
            assert "not found" in body.get("message", "").lower()

    @patch("src.llm.model_router.ModelRouter.chat_json")
    def test_signal_explain_passes_real_signal_fields(self, mock_chat_json, monkeypatch):
        """Signal explanation passes real signal fields, not fabricated hold."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
        monkeypatch.setenv("LLM_API_KEY_ENV", "DEEPSEEK_API_KEY")

        mock_chat_json.return_value = {
            "status": "ok",
            "explanation": "Test explanation.",
            "evidence": ["test"],
            "risk_notes": ["test risk"],
        }

        with patch("src.api.product_routes._get_live_signal_orchestrator") as mock_orch:
            mock_orchestrator = MagicMock()
            mock_orchestrator.get_signal_status.return_value = {
                "status": "ok",
                "signal": {
                    "signal_id": "SIG_REAL_001",
                    "signal_type": "buy",  # real signal type, not fabricated "hold"
                    "status": "draft",
                    "confidence": 0.75,
                },
            }
            mock_orch.return_value = mock_orchestrator

            client = TestClient(app)
            response = client.post("/product/ai/signals/SIG_REAL_001/explain")
            assert response.status_code == 200
            body = response.json()
            # Verify it doesn't fabricate "hold" — original signal_type should be preserved
            assert body.get("original_signal_type") == "buy"
            assert body.get("signal_id") == "SIG_REAL_001"
            assert "disclaimer" in body

    @patch("src.llm.model_router.ModelRouter.chat_json")
    def test_signal_explain_preserves_original_signal_type_for_hold(
        self, mock_chat_json, monkeypatch
    ):
        """Hold signal type is preserved, not silently changed."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
        monkeypatch.setenv("LLM_API_KEY_ENV", "DEEPSEEK_API_KEY")

        mock_chat_json.return_value = {
            "status": "ok",
            "explanation": "Hold explanation.",
        }

        with patch("src.api.product_routes._get_live_signal_orchestrator") as mock_orch:
            mock_orchestrator = MagicMock()
            mock_orchestrator.get_signal_status.return_value = {
                "status": "ok",
                "signal": {
                    "signal_id": "SIG_HOLD_001",
                    "signal_type": "hold",
                    "status": "draft",
                    "confidence": 0.3,
                },
            }
            mock_orch.return_value = mock_orchestrator

            client = TestClient(app)
            response = client.post("/product/ai/signals/SIG_HOLD_001/explain")
            body = response.json()
            assert body.get("original_signal_type") == "hold"


class TestLLMStatusEndpoint:
    """Tests for GET /product/llm/status."""

    def test_llm_status_returns_config(self, monkeypatch):
        """LLM status returns provider, model, key info."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

        client = TestClient(app)
        response = client.get("/product/llm/status")
        assert response.status_code == 200
        body = response.json()
        assert "provider" in body
        assert "model" in body
        assert "api_key_present" in body
        assert body["trade_decision_enabled"] is False


class TestBugFixMergeEndpoints:
    """Tests for merge and cleanup-worktree endpoints."""

    @patch("src.api.product_routes._get_bug_fix_workflow")
    def test_merge_endpoint_calls_workflow_merge(self, mock_get_wf):
        """POST /feedback/{id}/merge calls workflow.merge_fix()."""
        mock_wf = MagicMock()
        mock_wf.merge_fix.return_value = {
            "status": "fixed",
            "bug_id": "BUG_TEST_001",
            "merge_result": {"merged": True, "merge_commit": "abc123"},
        }
        mock_get_wf.return_value = mock_wf
        client = TestClient(app)
        response = client.post("/product/feedback/BUG_TEST_001/merge?force=true")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "fixed"

    @patch("src.api.product_routes._get_bug_fix_workflow")
    def test_merge_refuses_without_force(self, mock_get_wf):
        """Merge without force=true returns proper result."""
        mock_wf = MagicMock()
        mock_wf.merge_fix.return_value = {
            "status": "error",
            "bug_id": "BUG_TEST_001",
            "merge_result": {"merged": False, "reason": "auto_merge_disabled"},
        }
        mock_get_wf.return_value = mock_wf
        client = TestClient(app)
        response = client.post("/product/feedback/BUG_TEST_001/merge")
        assert response.status_code == 200
        body = response.json()
        assert "merge_result" in body

    @patch("src.api.product_routes._get_bug_fix_workflow")
    def test_cleanup_returns_ok_for_known_bug(self, mock_get_wf):
        """cleanup-worktree returns properly for bug with worktree_path."""
        mock_wf = MagicMock()
        mock_wf.get_bug_report.return_value = {
            "bug_id": "BUG_TEST_CLEAN",
            "fix_worktree_path": "/tmp/test_worktree",
            "fix_branch": "bugfix/BUG_TEST_CLEAN-ts",
            "base_branch": "main",
            "base_sha": "abc",
        }
        mock_wf.branch_manager = MagicMock()
        mock_wf.branch_manager.cleanup_worktree.return_value = {"removed": True}
        mock_get_wf.return_value = mock_wf
        client = TestClient(app)
        response = client.post("/product/feedback/BUG_TEST_CLEAN/cleanup-worktree")
        assert response.status_code == 200
