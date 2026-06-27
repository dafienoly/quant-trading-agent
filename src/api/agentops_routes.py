"""Read-only AgentOps API routes — Pipeline 观测契约聚合 API.

Only registers GET endpoints. No write operations.
"""

from __future__ import annotations

from fastapi import APIRouter, Path
from fastapi.responses import JSONResponse

from src.product_app.agentops.pipeline_aggregator import (
    get_agentops_health,
    get_pipeline_observation,
)
from src.product_app.agentops.pipeline_contracts import (
    AgentOpsHealth,
    AgentOpsPipelineObservation,
)
from src.product_app.agentops.pipeline_errors import (
    ERROR_CODE_MAP,
    AgentOpsError,
    FeatureNotFoundError,
    ParameterError,
    PipelineStateUnavailableError,
    PipelineStateUnparsableError,
)
from src.product_app.agentops.pipeline_sanitizer import sanitize_error_message

router = APIRouter()

_ERROR_STATUS_MAP: dict[type[AgentOpsError], int] = {
    ParameterError: 422,
    FeatureNotFoundError: 404,
    PipelineStateUnavailableError: 503,
    PipelineStateUnparsableError: 422,
}


def _get_error_status(exc: AgentOpsError) -> int:
    for exc_type, status in _ERROR_STATUS_MAP.items():
        if isinstance(exc, exc_type):
            return status
    return 500


def _error_response(exc: AgentOpsError | Exception) -> JSONResponse:
    if isinstance(exc, AgentOpsError):
        status = _get_error_status(exc)
        code = ERROR_CODE_MAP.get(type(exc), "INTERNAL_ERROR")
        source = exc.source if hasattr(exc, "source") else ""
    else:
        status = 500
        code = "INTERNAL_ERROR"
        source = ""
    safe_message = sanitize_error_message(str(exc))
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": safe_message,
                "source": source,
                "safe_detail": safe_message,
            }
        },
    )


@router.get(
    "/health",
    response_model=AgentOpsHealth,
    summary="Get readonly AgentOps Control Tower health",
)
def get_health() -> AgentOpsHealth | dict:
    try:
        return get_agentops_health()
    except AgentOpsError as e:
        return _error_response(e)
    except Exception as e:
        return _error_response(e)


@router.get(
    "/pipelines/{feature_id}",
    response_model=AgentOpsPipelineObservation,
    summary="Get pipeline observation by feature_id",
)
def get_pipeline_by_feature_id(
    feature_id: str = Path(..., description="Feature identifier"),
) -> AgentOpsPipelineObservation | dict:
    try:
        return get_pipeline_observation(feature_id=feature_id, issue_number=None)
    except AgentOpsError as e:
        return _error_response(e)
    except Exception as e:
        return _error_response(e)


@router.get(
    "/pipelines/by-issue/{issue_number}",
    response_model=AgentOpsPipelineObservation,
    summary="Get pipeline observation by issue number",
)
def get_pipeline_by_issue_number(
    issue_number: int = Path(..., description="Issue number", ge=1),
) -> AgentOpsPipelineObservation | dict:
    try:
        return get_pipeline_observation(feature_id=None, issue_number=issue_number)
    except AgentOpsError as e:
        return _error_response(e)
    except Exception as e:
        return _error_response(e)
