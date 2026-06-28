from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class OpsSectionStatus(BaseModel):
    name: str
    available: bool = False
    status: str = "unknown"
    note: str = ""


class OpsSummary(BaseModel):
    contract_version: str = "ops_summary.v1"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    readonly: bool = True
    repo_root: str = ""
    sections: list[OpsSectionStatus] = Field(default_factory=list)
    runtime_profiles: list[dict] = Field(default_factory=list)
    quality_summary: dict = Field(default_factory=dict)
    overall_status: str = "unknown"
    warnings: list[str] = Field(default_factory=list)
