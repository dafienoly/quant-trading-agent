from __future__ import annotations

from .pipeline_contracts import ErrorInfo


class AgentOpsError(Exception):
    def __init__(self, message: str, source: str = ""):
        super().__init__(message)
        self.source = source


class ParameterError(AgentOpsError):
    pass


class FeatureNotFoundError(AgentOpsError):
    pass


class PipelineStateUnavailableError(AgentOpsError):
    pass


class PipelineStateUnparsableError(AgentOpsError):
    def __init__(self, source: str, partial: bool = False):
        super().__init__(f"Pipeline state unparsable: {source}", source=source)
        self.partial = partial


ERROR_CODE_MAP: dict[type[AgentOpsError], str] = {
    ParameterError: "PARAMETER_ERROR",
    FeatureNotFoundError: "FEATURE_NOT_FOUND",
    PipelineStateUnavailableError: "PIPELINE_STATE_UNAVAILABLE",
    PipelineStateUnparsableError: "PIPELINE_STATE_UNPARSABLE",
}


def to_error_info(err: AgentOpsError | Exception) -> ErrorInfo:
    err_type = type(err)
    code = ERROR_CODE_MAP.get(err_type, "INTERNAL_ERROR")  # type: ignore[arg-type]
    source = getattr(err, "source", "")
    return ErrorInfo(
        code=code,
        message=str(err),
        source=source,
        safe_detail=str(err),
    )
