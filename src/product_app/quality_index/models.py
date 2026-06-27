from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class QualityState(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    INVALID = "invalid"
    UNKNOWN = "unknown"


class QualityPriority(str, Enum):
    P0 = "p0"
    P1 = "p1"
    P2 = "p2"
    P3 = "p3"
    UNKNOWN = "unknown"


class QualityItem(BaseModel):
    item_id: str = ""
    state: QualityState = QualityState.UNKNOWN
    priority: QualityPriority = QualityPriority.UNKNOWN
    source_stage: str = ""
    route_back_to: str = ""
    related_paths: list[str] = Field(default_factory=list)
    item_path: str = ""
    title: str = ""
    safe_summary: str = ""
    created_at: str = ""
    resolved_at: str = ""
    parse_notes: list[str] = Field(default_factory=list)


class QualitySummary(BaseModel):
    contract_version: str = "quality_index.summary.v1"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    readonly: bool = True
    scanned_roots: list[str] = Field(default_factory=list)
    total_count: int = 0
    open_count: int = 0
    resolved_count: int = 0
    invalid_count: int = 0
    priority_counts: dict[str, int] = Field(default_factory=dict)
    state_counts: dict[str, int] = Field(default_factory=dict)
    items: list[QualityItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
