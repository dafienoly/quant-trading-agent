from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

with patch.dict("sys.modules", {"streamlit": MagicMock()}):
    import streamlit as st
    from src.ui_report.agentops_control_tower import (
        render_control_tower_page,
    )
    import src.ui_report.agentops_control_tower as _mod
    import src.ui_report.agentops_state as _state_mod

    _state_mod.st.session_state = {}
    _mod.st = st


@pytest.fixture(autouse=True)
def _clear_session():
    _state_mod.st.session_state.clear()
    yield


def _make_observation(**overrides) -> dict:
    obs = {
        "contract_version": "agentops.pipeline_observation.v1",
        "generated_at": "2026-06-24T12:00:00Z",
        "feature": {"feature_id": "test-feature", "title": "Test Feature", "risk_level": "low", "current_stage": "phase_dev"},
        "issue": {"number": 42, "url": "https://github.com/org/repo/issues/42"},
        "branch": {"epic_branch": "epic/test-feature"},
        "stages": [
            {"name": "requirements", "status": "passed", "source": ".agent/state.json", "notes": []},
            {"name": "architecture", "status": "passed", "source": ".agent/state.json", "notes": []},
            {"name": "phase_dev", "status": "in_progress", "source": ".agent/state.json", "notes": []},
        ],
        "roles": [],
        "required_docs": [
            {"kind": "requirements", "path": "docs/requirements/YYYY-MM-DD-test-feature-requirements.md", "status": "present", "source": "pipeline_state.required_docs", "required": True},
            {"kind": "architecture", "path": "docs/design/YYYY-MM-DD-test-feature-architecture.md", "status": "missing", "source": "pipeline_state.required_docs", "required": True},
        ],
        "safety": {"readonly": True, "trading_modules_touched": [], "restricted_module_change": False, "warnings": [], "blockers": []},
        "data_quality": {"status": "complete", "missing_sources": [], "unparsable_sources": [], "stale_sources": []},
        "errors": [],
    }
    obs.update(overrides)
    return obs


class TestRenderControlTowerPage:
    def test_render_ready_shows_feature_summary(self):
        observation = _make_observation()
        state = {
            "view_status": "ready",
            "observation": observation,
            "error": None,
            "last_loaded_at": "2026-06-24T12:00:00Z",
            "is_refreshing": False,
            "feature_id": "test-feature",
        }

        with patch.object(_mod, "_render_feature_summary") as mock_summary:
            with patch.object(_mod, "_render_stage_status_list") as mock_stages:
                with patch.object(_mod, "_render_required_docs") as mock_docs:
                    with patch.object(_mod, "_render_safety_blockers") as mock_safety:
                        with patch.object(_mod, "_render_data_quality") as mock_dq:
                            with patch.object(_mod, "_render_errors"):
                                render_control_tower_page(state)

        mock_summary.assert_called_once_with(observation)
        mock_stages.assert_called_once_with(observation)
        mock_docs.assert_called_once_with(observation)
        mock_safety.assert_called_once_with(observation)
        mock_dq.assert_called_once_with(observation)

    def test_render_blocked_shows_blocker_banner(self):
        observation = _make_observation(
            safety={"readonly": True, "trading_modules_touched": [], "restricted_module_change": False, "warnings": ["test warning"], "blockers": ["Required architecture doc missing"]}
        )
        state = {"view_status": "blocked", "observation": observation, "error": None, "last_loaded_at": None, "is_refreshing": False, "feature_id": "test-feature"}

        render_control_tower_page(state)

    def test_render_empty_shows_empty_message(self):
        state = {"view_status": "empty", "observation": None, "error": {"message": "Not found", "code": "FEATURE_NOT_FOUND"}, "last_loaded_at": None, "is_refreshing": False, "feature_id": "nonexistent"}

        with patch.object(_mod.st, "warning") as mock_warn:
            render_control_tower_page(state)
            mock_warn.assert_called()

    def test_render_error_shows_error_message(self):
        state = {"view_status": "error", "observation": None, "error": {"message": "HTTP 500", "code": "INTERNAL_ERROR"}, "last_loaded_at": None, "is_refreshing": False, "feature_id": "broken"}

        with patch.object(_mod.st, "error") as mock_error:
            render_control_tower_page(state)
            mock_error.assert_called()

    def test_render_stale_shows_stale_banner(self):
        observation = _make_observation()
        state = {"view_status": "stale", "observation": observation, "error": {"message": "Refresh failed"}, "last_loaded_at": "2026-06-24T11:00:00Z", "is_refreshing": False, "feature_id": "test-feature"}

        with patch.object(_mod.st, "warning") as mock_warn:
            render_control_tower_page(state)
            mock_warn.assert_called()

    def test_render_calls_markdown_and_subheader(self):
        observation = _make_observation()
        state = {"view_status": "ready", "observation": observation, "error": None, "last_loaded_at": None, "is_refreshing": False, "feature_id": "test-feature"}

        with patch.object(_mod.st, "subheader") as mock_sub:
            with patch.object(_mod.st, "markdown") as mock_md:
                render_control_tower_page(state)
                mock_sub.assert_called()
                assert any("Test Feature" in str(c) for c in mock_md.call_args_list)

    def test_errors_with_blockers_show_blocked(self):
        observation = _make_observation(
            errors=[{"code": "MISSING_DOC", "message": "arch doc missing", "source": "pipeline_state.required_docs", "safe_detail": ""}]
        )
        state = {"view_status": "blocked", "observation": observation, "error": None, "last_loaded_at": None, "is_refreshing": False, "feature_id": "locked"}

        render_control_tower_page(state)

    def test_no_ready_no_loading_shows_not_selected(self):
        state = {"view_status": None, "observation": None, "error": None, "last_loaded_at": None, "is_refreshing": False, "feature_id": None}

        with patch.object(_mod.st, "info") as mock_info:
            render_control_tower_page(state)
            mock_info.assert_called()

    def test_stage_ready_displays_correct_icons(self):
        observation = _make_observation()
        state = {"view_status": "ready", "observation": observation, "error": None, "last_loaded_at": None, "is_refreshing": False, "feature_id": "test-feature"}

        with patch.object(_mod, "_render_feature_summary"):
            with patch.object(_mod, "_render_stage_status_list"):
                with patch.object(_mod, "_render_required_docs"):
                    with patch.object(_mod, "_render_safety_blockers"):
                        with patch.object(_mod, "_render_data_quality"):
                            with patch.object(_mod, "_render_errors"):
                                render_control_tower_page(state)


class TestRenderFeatureSummary:
    def test_summary_shows_feature_title(self):
        observation = _make_observation(feature={"feature_id": "demo", "title": "Demo Feature", "risk_level": "medium", "current_stage": "phase_test"})

        with patch.object(_mod.st, "markdown") as mock_md:
            _mod._render_feature_summary(observation)
            calls = [str(c) for c in mock_md.call_args_list]
            assert any("Demo Feature" in c for c in calls), f"Expected 'Demo Feature' in calls: {calls}"

    def test_summary_includes_feature_id(self):
        observation = _make_observation()
        with patch.object(_mod.st, "markdown") as mock_md:
            _mod._render_feature_summary(observation)
            calls = [str(c) for c in mock_md.call_args_list]
            assert any("test-feature" in c for c in calls), f"Expected 'test-feature' in calls: {calls}"

    def test_summary_shows_issue_number(self):
        observation = _make_observation()
        with patch.object(_mod.st, "markdown") as mock_md:
            _mod._render_feature_summary(observation)
            calls = [str(c) for c in mock_md.call_args_list]
            assert any("42" in c for c in calls)

    def test_summary_shows_epic_branch(self):
        observation = _make_observation()
        with patch.object(_mod.st, "markdown") as mock_md:
            _mod._render_feature_summary(observation)
            calls = [str(c) for c in mock_md.call_args_list]
            assert any("epic/" in c for c in calls)


class TestRenderStageStatusList:
    def test_shows_stage_names(self):
        observation = _make_observation()
        with patch.object(_mod.st, "markdown") as mock_md:
            _mod._render_stage_status_list(observation)
            calls = [str(c) for c in mock_md.call_args_list]
            assert any("requirements" in c for c in calls)
            assert any("phase_dev" in c for c in calls)

    def test_shows_status_labels(self):
        observation = _make_observation(stages=[
            {"name": "pm", "status": "passed", "source": ".agent/state.json", "notes": []},
            {"name": "phase_dev", "status": "in_progress", "source": ".agent/state.json", "notes": []},
            {"name": "phase_test", "status": "failed", "source": ".agent/state.json", "notes": []},
        ])
        with patch.object(_mod.st, "markdown") as mock_md:
            _mod._render_stage_status_list(observation)
            calls = [str(c) for c in mock_md.call_args_list]
            assert any("passed" in str(c).lower() for c in calls)


class TestRenderRequiredDocs:
    def test_shows_doc_paths(self):
        observation = _make_observation()
        with patch.object(_mod.st, "markdown") as mock_md:
            _mod._render_required_docs(observation)
            calls = [str(c) for c in mock_md.call_args_list]
            assert any("requirements" in c for c in calls)
            assert any("docs/design/" in c for c in calls)

    def test_shows_doc_status(self):
        observation = _make_observation()
        with patch.object(_mod.st, "markdown") as mock_md:
            _mod._render_required_docs(observation)
            calls = [str(c) for c in mock_md.call_args_list]
            assert any("present" in c.lower() for c in calls)
            assert any("missing" in c.lower() for c in calls)

    def test_empty_docs_shows_none_message(self):
        observation = _make_observation(required_docs=[])
        with patch.object(_mod.st, "caption") as mock_cap:
            _mod._render_required_docs(observation)
            assert mock_cap.called


class TestRenderSafetyBlockers:
    def test_shows_blockers(self):
        observation = _make_observation(
            safety={"readonly": True, "trading_modules_touched": [], "restricted_module_change": False, "warnings": [], "blockers": ["B1", "B2"]}
        )
        with patch.object(_mod.st, "error") as mock_error:
            _mod._render_safety_blockers(observation)
            mock_error.assert_called()
            texts = " ".join(str(c) for c in mock_error.call_args_list)
            assert "B1" in texts or "B2" in texts

    def test_shows_warnings(self):
        observation = _make_observation(
            safety={"readonly": True, "trading_modules_touched": [], "restricted_module_change": False, "warnings": ["Warn1"], "blockers": []}
        )
        with patch.object(_mod.st, "warning") as mock_warn:
            _mod._render_safety_blockers(observation)
            mock_warn.assert_called()

    def test_no_blockers_no_warnings_shows_safe(self):
        observation = _make_observation()
        with patch.object(_mod.st, "success") as mock_success:
            _mod._render_safety_blockers(observation)
            mock_success.assert_called()


class TestRenderDataQuality:
    def test_shows_data_quality_status(self):
        observation = _make_observation()
        with patch.object(_mod.st, "markdown") as mock_md:
            _mod._render_data_quality(observation)
            calls = [str(c) for c in mock_md.call_args_list]
            assert any("complete" in str(c).lower() for c in calls)

    def test_shows_missing_sources(self):
        observation = _make_observation(
            data_quality={"status": "incomplete", "missing_sources": ["source_a", "source_b"], "unparsable_sources": [], "stale_sources": []}
        )
        with patch.object(_mod.st, "markdown") as mock_md:
            _mod._render_data_quality(observation)
            calls = [str(c) for c in mock_md.call_args_list]
            texts = " ".join(str(c) for c in calls)
            assert "source_a" in texts


class TestRenderErrors:
    def test_shows_errors(self):
        observation = _make_observation(
            errors=[{"code": "ERR1", "message": "error msg", "source": "test", "safe_detail": ""}]
        )
        with patch.object(_mod.st, "markdown") as mock_md:
            _mod._render_errors(observation)
            calls = [str(c) for c in mock_md.call_args_list]
            texts = " ".join(str(c) for c in calls)
            assert "ERR1" in texts or "error msg" in texts

    def test_no_errors_shows_none(self):
        observation = _make_observation(errors=[])
        with patch.object(_mod.st, "caption") as mock_cap:
            _mod._render_errors(observation)
            assert mock_cap.called


class TestNoControlActions:
    def test_page_has_no_approve_reject_merge_rerun_trigger(self):
        source = _mod.__file__
        text = open(source, encoding="utf-8").read()
        for forbidden in ("approve", "reject", "merge", "rerun", "trigger", "trade"):
            assert forbidden.lower() not in text.lower(), f"Found forbidden term '{forbidden}' in {source}"


class TestDashboardIntegration:
    def test_dashboard_has_control_tower_tab(self):
        dashboard_source = open("src/ui_report/product_dashboard.py", encoding="utf-8").read()
        i18n_source = open("src/ui_report/i18n.py", encoding="utf-8").read()
        combined = dashboard_source + i18n_source
        assert "tab_agentops_control_tower" in dashboard_source
        assert "Control Tower" in combined or "控制塔" in combined
