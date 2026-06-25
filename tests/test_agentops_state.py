from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Patch streamlit before importing the module under test
with patch.dict("sys.modules", {"streamlit": MagicMock()}):
    from src.ui_report.agentops_state import (
        clear,
        load_by_feature_id,
        load_by_issue_number,
        refresh,
    )
    import src.ui_report.agentops_state as _mod

    # Make st.session_state a regular dict for testing
    _mod.st.session_state = {}


@pytest.fixture(autouse=True)
def _clear_session_state():
    _mod.st.session_state.clear()
    yield


def _make_observation(**overrides) -> dict:
    obs = {
        "contract_version": "agentops.pipeline_observation.v1",
        "generated_at": "2026-06-24T12:00:00Z",
        "feature": {"feature_id": "test-feature", "title": "Test Feature", "risk_level": "low", "current_stage": "phase_dev"},
        "issue": {"number": 42, "url": ""},
        "branch": {"epic_branch": "epic/test-feature"},
        "stages": [],
        "roles": [],
        "required_docs": [],
        "safety": {"readonly": True, "trading_modules_touched": [], "restricted_module_change": False, "warnings": [], "blockers": []},
        "data_quality": {"status": "complete", "missing_sources": [], "unparsable_sources": [], "stale_sources": []},
        "errors": [],
    }
    obs.update(overrides)
    return obs


class TestLoadByFeatureId:
    def test_200_returns_ready(self):
        observation = _make_observation()
        with patch.object(_mod, "requests") as mock_requests:
            mock_requests.get.return_value.status_code = 200
            mock_requests.get.return_value.json.return_value = observation

            result = load_by_feature_id("test-feature")

        assert result["view_status"] == "ready"
        assert result["observation"] == observation
        assert result["error"] is None
        assert result["last_loaded_at"] is not None
        assert result["is_refreshing"] is False
        mock_requests.get.assert_called_once()

    def test_200_with_blockers_returns_blocked(self):
        observation = _make_observation(
            safety={"readonly": True, "trading_modules_touched": [], "restricted_module_change": False, "warnings": ["test warning"], "blockers": ["blocker one", "blocker two"]}
        )
        with patch.object(_mod, "requests") as mock_requests:
            mock_requests.get.return_value.status_code = 200
            mock_requests.get.return_value.json.return_value = observation

            result = load_by_feature_id("test-feature")

        assert result["view_status"] == "blocked"
        assert result["observation"] == observation
        assert result["error"] is None

    def test_404_returns_empty(self):
        with patch.object(_mod, "requests") as mock_requests:
            mock_requests.get.return_value.status_code = 404

            result = load_by_feature_id("nonexistent")

        assert result["view_status"] == "empty"
        assert result["observation"] is None
        assert result["error"] is not None

    def test_500_returns_error(self):
        with patch.object(_mod, "requests") as mock_requests:
            mock_requests.get.return_value.status_code = 500
            mock_requests.get.return_value.json.return_value = {"error": {"code": "INTERNAL_ERROR", "message": "Internal error"}}

            result = load_by_feature_id("test-feature")

        assert result["view_status"] == "error"
        assert result["observation"] is None
        assert result["error"] is not None

    def test_network_error_returns_error(self):
        with patch.object(_mod, "requests") as mock_requests:
            mock_requests.get.side_effect = Exception("Connection refused")

            result = load_by_feature_id("test-feature")

        assert result["view_status"] == "error"
        assert result["observation"] is None
        assert result["error"] is not None

    def test_422_returns_error(self):
        with patch.object(_mod, "requests") as mock_requests:
            mock_requests.get.return_value.status_code = 422
            mock_requests.get.return_value.json.return_value = {"error": {"code": "PIPELINE_STATE_UNPARSABLE", "message": "unparsable"}}

            result = load_by_feature_id("test-feature")

        assert result["view_status"] == "error"

    def test_error_safe_detail_no_secrets(self):
        with patch.object(_mod, "requests") as mock_requests:
            mock_requests.get.return_value.status_code = 500
            mock_requests.get.return_value.json.return_value = {
                "error": {"code": "INTERNAL_ERROR", "message": "/mnt/d/actions-runner/secret.key", "safe_detail": "/mnt/d/actions-runner/secret.key"}
            }

            result = load_by_feature_id("test-feature")

        assert result["view_status"] == "error"
        error_str = str(result["error"])
        assert "/mnt/d" not in error_str

    def test_caches_same_feature_id(self):
        with patch.object(_mod, "requests") as mock_requests:
            mock_requests.get.return_value.status_code = 200
            mock_requests.get.return_value.json.return_value = _make_observation()

            result1 = load_by_feature_id("cached-feature")
            result2 = load_by_feature_id("cached-feature")

        assert result1["view_status"] == result2["view_status"]
        assert result1["observation"] == result2["observation"]
        assert mock_requests.get.call_count == 1

    def test_different_features_separate_requests(self):
        with patch.object(_mod, "requests") as mock_requests:
            mock_requests.get.return_value.status_code = 200
            mock_requests.get.return_value.json.return_value = _make_observation()

            load_by_feature_id("feature-a")
            load_by_feature_id("feature-b")

        assert mock_requests.get.call_count == 2


class TestLoadByIssueNumber:
    def test_200_returns_ready(self):
        with patch.object(_mod, "requests") as mock_requests:
            mock_requests.get.return_value.status_code = 200
            mock_requests.get.return_value.json.return_value = _make_observation()

            result = load_by_issue_number(42)

        assert result["view_status"] == "ready"
        assert result["observation"] is not None
        assert result["error"] is None

    def test_404_returns_empty(self):
        with patch.object(_mod, "requests") as mock_requests:
            mock_requests.get.return_value.status_code = 404

            result = load_by_issue_number(999)

        assert result["view_status"] == "empty"
        assert result["observation"] is None

    def test_network_error_returns_error(self):
        with patch.object(_mod, "requests") as mock_requests:
            mock_requests.get.side_effect = Exception("Timeout")

            result = load_by_issue_number(42)

        assert result["view_status"] == "error"
        assert result["observation"] is None


class TestRefresh:
    def test_refresh_without_previous_data_raises(self):
        with pytest.raises(RuntimeError):
            refresh()

    def test_refresh_success_returns_ready(self):
        observation = _make_observation()
        with patch.object(_mod, "requests") as mock_requests:
            mock_requests.get.return_value.status_code = 200
            mock_requests.get.return_value.json.return_value = observation

            load_by_feature_id("test-feature")
            result = refresh()

        assert result["view_status"] == "ready"
        assert result["observation"] == observation
        assert mock_requests.get.call_count == 2

    def test_refresh_failure_with_previous_data_returns_stale(self):
        with patch.object(_mod, "requests") as mock_requests:
            mock_requests.get.return_value.status_code = 200
            mock_requests.get.return_value.json.return_value = _make_observation()

            load_by_feature_id("test-feature")

            mock_requests.get.return_value.status_code = 500
            mock_requests.get.return_value.json.return_value = {"error": {"code": "INTERNAL_ERROR", "message": "fail"}}

            result = refresh()

        assert result["view_status"] == "stale"
        assert result["observation"] is not None
        assert result["error"] is not None


class TestClear:
    def test_clear_resets_state(self):
        with patch.object(_mod, "requests") as mock_requests:
            mock_requests.get.return_value.status_code = 200
            mock_requests.get.return_value.json.return_value = _make_observation()

            load_by_feature_id("test-feature")
            result = clear()

        assert result["view_status"] is None
        assert result["observation"] is None
        assert result["error"] is None
        assert result["last_loaded_at"] is None
        assert result["is_refreshing"] is False


class TestOnlyReads:
    def test_only_get_requests(self):
        source = _mod.__file__
        text = open(source, encoding="utf-8").read()
        assert "requests.get" in text
        assert "requests.post" not in text
        assert "requests.put" not in text
        assert "requests.delete" not in text
        assert "requests.patch" not in text

    def test_uses_correct_api_path(self):
        with patch.object(_mod, "requests") as mock_requests:
            mock_requests.get.return_value.status_code = 200
            mock_requests.get.return_value.json.return_value = _make_observation()

            load_by_feature_id("my-feature")

            url = mock_requests.get.call_args[0][0]
            assert "my-feature" in url
            assert "/product/agentops/" in url

    def test_uses_by_issue_api_path(self):
        with patch.object(_mod, "requests") as mock_requests:
            mock_requests.get.return_value.status_code = 200
            mock_requests.get.return_value.json.return_value = _make_observation()

            load_by_issue_number(77)

            url = mock_requests.get.call_args[0][0]
            assert "77" in url
            assert "by-issue" in url
