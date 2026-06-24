from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from .pipeline_contracts import (
    AgentOpsPipelineObservation,
    DataQualityInfo,
    DataQualityStatus,
    DocumentStatus,
    ErrorInfo,
    PipelineStageInfo,
    PipelineStageStatus,
    RoleInfo,
    SafetyInfo,
)
from .pipeline_errors import (
    FeatureNotFoundError,
    ParameterError,
)
from .pipeline_sanitizer import sanitize_repo_relative_path
from .pipeline_state_reader import (
    ResolvedTarget,
    check_doc_status_readonly,
    read_handoff_files,
    read_pipeline_state,
    resolve_target,
)

STATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "..",
    ".agent",
)


def normalize_stage_statuses(
    raw: dict[str, str],
) -> list[PipelineStageInfo]:
    stages: list[PipelineStageInfo] = []
    for name, status_str in raw.items():
        try:
            status = PipelineStageStatus(status_str)
        except ValueError:
            status = PipelineStageStatus.UNKNOWN
        stages.append(
            PipelineStageInfo(name=name, status=status, source=".agent/state.json")
        )
    return stages


def normalize_roles(
    raw: dict[str, list[str]],
) -> list[RoleInfo]:
    return [
        RoleInfo(agent=agent, responsibilities=resp)
        for agent, resp in raw.items()
    ]


def build_required_doc_list(state: dict[str, Any]) -> list[dict[str, Any]]:
    required_docs_raw = state.get("required_docs", {})
    if not isinstance(required_docs_raw, dict):
        return []
    docs: list[dict[str, Any]] = []
    for kind, raw_path in required_docs_raw.items():
        path_str = str(raw_path)
        docs.append(
            {
                "kind": kind,
                "path": path_str,
                "status": DocumentStatus.UNKNOWN,
                "source": "pipeline_state.required_docs",
                "required": True,
            }
        )
    return docs


def evaluate_data_quality(
    read_result: Any,
    doc_statuses: list[dict[str, Any]],
    stages: list[PipelineStageInfo],
) -> DataQualityInfo:
    if read_result.not_found:
        return DataQualityInfo(
            status=DataQualityStatus.UNAVAILABLE,
            missing_sources=[".agent/state.json"],
        )
    if read_result.unparsable and not read_result.partial:
        return DataQualityInfo(
            status=DataQualityStatus.UNPARSABLE,
            unparsable_sources=[".agent/state.json"],
        )
    missing = [
            d.get("path", d.get("kind", "unknown"))
            for d in doc_statuses
            if d.get("status") in (DocumentStatus.MISSING, DocumentStatus.UNREADABLE)
        ]
    if missing:
        return DataQualityInfo(
            status=DataQualityStatus.INCOMPLETE,
            missing_sources=missing,
        )
    return DataQualityInfo(status=DataQualityStatus.COMPLETE)


def evaluate_safety(
    readonly: bool,
    risk_level: str,
    doc_statuses: list[dict[str, Any]],
    data_quality: DataQualityInfo,
) -> SafetyInfo:
    warnings: list[str] = []
    blockers: list[str] = []

    if risk_level == "unknown" or not risk_level:
        warnings.append("Unknown risk level")

    for doc in doc_statuses:
        if doc.get("required") and doc.get("status") in (
            DocumentStatus.MISSING,
            DocumentStatus.UNREADABLE,
        ):
            blockers.append(f"Required doc missing: {doc.get('kind', 'unknown')}")

    if data_quality.status in (
        DataQualityStatus.UNAVAILABLE,
        DataQualityStatus.UNPARSABLE,
    ):
        blockers.append(f"Data quality is {data_quality.status.value}")

    return SafetyInfo(
        readonly=readonly,
        trading_modules_touched=[],
        restricted_module_change=False,
        warnings=warnings,
        blockers=blockers,
    )


def _read_state_files(
    state_dir: str, target: ResolvedTarget
) -> tuple[dict[str, Any], list[ErrorInfo]]:
    errors: list[ErrorInfo] = []

    state_json_path = os.path.join(state_dir, "state.json")
    read_result = read_pipeline_state(state_json_path, required=False)
    state = read_result.state
    if read_result.unparsable and read_result.partial:
        errors.append(
            ErrorInfo(
                code="PIPELINE_STATE_PARTIAL",
                message="Pipeline state partially unparsable",
                source=sanitize_repo_relative_path(state_json_path),
                safe_detail="Returning partial data",
            )
        )

    # Read current_task.yaml for extra context
    task_path = os.path.join(state_dir, "current_task.yaml")
    task_result = read_pipeline_state(task_path, required=False)
    if task_result.state and not state.get("current_stage"):
        state["current_stage"] = task_result.state.get("current_stage")

    # Read handoff files for stage context
    handoff_dir = os.path.join(state_dir, "handoff")
    handoff_files = read_handoff_files(handoff_dir)
    state["_handoff_files"] = handoff_files

    return state, errors


def _check_feature_match(
    state: dict[str, Any], target: ResolvedTarget
) -> bool:
    if target.feature_id:
        return state.get("feature_id") == target.feature_id
    if target.issue_number is not None:
        return state.get("issue_number") == target.issue_number
    return False


def get_pipeline_observation(
    feature_id: str | None = None,
    issue_number: int | None = None,
) -> AgentOpsPipelineObservation:
    target = resolve_target(feature_id=feature_id, issue_number=issue_number)

    if target.invalid:
        raise ParameterError("feature_id or issue_number is required")

    state_dir = os.path.abspath(STATE_DIR)
    state, errors = _read_state_files(state_dir, target)

    if not state or (_check_feature_match(state, target) is False):
        raise FeatureNotFoundError(
            feature_id or str(issue_number or "unknown")
        )

    feature = {
        "feature_id": state.get("feature_id", ""),
        "title": state.get("title", ""),
        "risk_level": state.get("risk_level", ""),
        "current_stage": state.get("current_stage", ""),
    }

    issue = {
        "number": state.get("issue_number", 0),
        "url": state.get("issue_url", ""),
    }

    branch = {"epic_branch": state.get("epic_branch", "")}

    raw_stages = state.get("stage_status", {})
    if not isinstance(raw_stages, dict):
        raw_stages = {}
    stages = normalize_stage_statuses(raw_stages)

    raw_roles = state.get("agent_roles", {})
    if not isinstance(raw_roles, dict):
        raw_roles = {}
    roles = normalize_roles(raw_roles)

    required_docs = build_required_doc_list(state)
    for doc in required_docs:
        doc_status = check_doc_status_readonly(doc["path"])
        doc["status"] = doc_status

    data_quality = evaluate_data_quality(
        read_result=type("obj", (), {
            "not_found": False,
            "unparsable": False,
            "partial": False,
        })(),
        doc_statuses=required_docs,
        stages=stages,
    )

    if not state:
        data_quality.status = DataQualityStatus.UNAVAILABLE

    risk_level = state.get("risk_level", "unknown") or "unknown"
    safety = evaluate_safety(
        readonly=True,
        risk_level=risk_level,
        doc_statuses=required_docs,
        data_quality=data_quality,
    )

    return AgentOpsPipelineObservation(
        contract_version="agentops.pipeline_observation.v1",
        generated_at=datetime.now(timezone.utc),
        feature=feature,
        issue=issue,
        branch=branch,
        stages=stages,
        roles=roles,
        required_docs=required_docs,
        safety=safety,
        data_quality=data_quality,
        errors=errors,
    )
