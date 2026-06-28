"""Read-only AgentOps API routes — Pipeline 观测契约聚合 API.

Only registers GET endpoints. No write operations.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Path
from fastapi.responses import JSONResponse

from src.product_app.agent_runtime import resolve_agent_runtime
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
from src.product_app.agentops.remote_context import build_remote_context_snapshot
from src.product_app.ops_summary import build_ops_summary
from src.product_app.quality_index import build_quality_summary

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


def _model_dump_json_safe(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return value
    return {"value": value}


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
    "/summary",
    summary="Get readonly AgentOps operations summary",
)
def get_ops_summary() -> dict:
    try:
        return _model_dump_json_safe(build_ops_summary())
    except AgentOpsError as e:
        return _error_response(e)
    except Exception as e:
        return _error_response(e)


@router.get(
    "/runtime/{stage}",
    summary="Get readonly Agent runtime profile by stage",
)
def get_runtime_profile(
    stage: str = Path(..., description="Agent pipeline stage id"),
) -> dict:
    try:
        return _model_dump_json_safe(resolve_agent_runtime(stage))
    except AgentOpsError as e:
        return _error_response(e)
    except Exception as e:
        return _error_response(e)


@router.get(
    "/quality",
    summary="Get readonly AgentOps quality summary",
)
def get_quality_summary() -> dict:
    try:
        return _model_dump_json_safe(build_quality_summary())
    except AgentOpsError as e:
        return _error_response(e)
    except Exception as e:
        return _error_response(e)


@router.get(
    "/remote",
    summary="Get readonly AgentOps remote context snapshot",
)
def get_remote_context() -> dict:
    try:
        return _model_dump_json_safe(build_remote_context_snapshot())
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
