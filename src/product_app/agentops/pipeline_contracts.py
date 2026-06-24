from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class _DefaultUnknown(str, Enum):
    @classmethod
    def _missing_(cls, value: object) -> _DefaultUnknown | None:
        return cls.UNKNOWN


class PipelineStageStatus(_DefaultUnknown):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"
    UNKNOWN = "unknown"


class DocumentStatus(_DefaultUnknown):
    PRESENT = "present"
    MISSING = "missing"
    STALE = "stale"
    UNREADABLE = "unreadable"
    UNKNOWN = "unknown"


class DataQualityStatus(_DefaultUnknown):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    UNAVAILABLE = "unavailable"
    UNPARSABLE = "unparsable"
    STALE = "stale"
    UNKNOWN = "unknown"


class ControlTowerViewStatus(str, Enum):
    READY = "ready"
    EMPTY = "empty"
    STALE = "stale"
    ERROR = "error"
    BLOCKED = "blocked"


class ErrorInfo(BaseModel):
    code: str = ""
    message: str = ""
    source: str = ""
    safe_detail: str = ""


class PipelineStageInfo(BaseModel):
    name: str
    status: PipelineStageStatus = PipelineStageStatus.UNKNOWN
    source: str = ""
    notes: list[str] = Field(default_factory=list)


class RoleInfo(BaseModel):
    agent: str
    responsibilities: list[str] = Field(default_factory=list)
    status: str = ""


class SafetyInfo(BaseModel):
    readonly: bool = True
    trading_modules_touched: list[str] = Field(default_factory=list)
    restricted_module_change: bool = False
    warnings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)


class DataQualityInfo(BaseModel):
    status: DataQualityStatus = DataQualityStatus.UNKNOWN
    missing_sources: list[str] = Field(default_factory=list)
    unparsable_sources: list[str] = Field(default_factory=list)
    stale_sources: list[str] = Field(default_factory=list)


class AgentOpsPipelineObservation(BaseModel):
    contract_version: str = "agentops.pipeline_observation.v1"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    feature: dict[str, Any]
    issue: dict[str, Any]
    branch: dict[str, Any]
    stages: list[PipelineStageInfo] = Field(default_factory=list)
    roles: list[RoleInfo] = Field(default_factory=list)
    required_docs: list[dict[str, Any]] = Field(default_factory=list)
    safety: SafetyInfo = Field(default_factory=SafetyInfo)
    data_quality: DataQualityInfo = Field(default_factory=DataQualityInfo)
    errors: list[ErrorInfo] = Field(default_factory=list)
