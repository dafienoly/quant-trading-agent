from __future__ import annotations

from src.product_app.agentops.pipeline_errors import (
    AgentOpsError,
    FeatureNotFoundError,
    ParameterError,
    PipelineStateUnavailableError,
    PipelineStateUnparsableError,
    to_error_info,
)


class TestAgentOpsError:
    def test_base_exception(self):
        err = AgentOpsError("base error")
        assert str(err) == "base error"
        assert isinstance(err, Exception)

    def test_with_source(self):
        err = AgentOpsError("test", source=".agent/current_task.yaml")
        assert err.source == ".agent/current_task.yaml"


class TestParameterError:
    def test_default(self):
        err = ParameterError("invalid param")
        assert "invalid param" in str(err)
        assert err.source == ""


class TestFeatureNotFoundError:
    def test_default(self):
        err = FeatureNotFoundError("test-feature")
        assert "test-feature" in str(err)
        assert err.source == ""


class TestPipelineStateUnavailableError:
    def test_default(self):
        err = PipelineStateUnavailableError(".agent/state.json")
        assert ".agent/state.json" in str(err)


class TestPipelineStateUnparsableError:
    def test_default(self):
        err = PipelineStateUnparsableError(".agent/current_task.yaml")
        assert ".agent/current_task.yaml" in str(err)
        assert err.source == ".agent/current_task.yaml"

    def test_with_partial(self):
        err = PipelineStateUnparsableError("file.yaml", partial=True)
        assert err.partial is True


class TestToErrorInfo:
    def test_parameter_error(self):
        err = ParameterError("feature_id is required")
        info = to_error_info(err)
        assert info.code == "PARAMETER_ERROR"
        assert info.message == "feature_id is required"
        assert info.source == ""

    def test_feature_not_found(self):
        err = FeatureNotFoundError("my-feature")
        info = to_error_info(err)
        assert info.code == "FEATURE_NOT_FOUND"
        assert "my-feature" in info.message

    def test_pipeline_state_unavailable(self):
        err = PipelineStateUnavailableError(".agent/state.json")
        info = to_error_info(err)
        assert info.code == "PIPELINE_STATE_UNAVAILABLE"
        assert ".agent/state.json" in info.safe_detail

    def test_pipeline_state_unparsable(self):
        err = PipelineStateUnparsableError("file.yaml")
        info = to_error_info(err)
        assert info.code == "PIPELINE_STATE_UNPARSABLE"
        assert "file.yaml" in info.safe_detail

    def test_generic_exception(self):
        info = to_error_info(ValueError("something"))
        assert info.code == "INTERNAL_ERROR"
        assert "something" in info.message
