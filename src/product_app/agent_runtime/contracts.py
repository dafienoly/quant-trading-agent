from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class RuntimeMode(str, Enum):
    REAL = "real"
    DRY_RUN = "dry_run"
    MOCK = "mock"
    DISABLED = "disabled"
    UNKNOWN = "unknown"


class RuntimeProvider(str, Enum):
    CODEX = "codex"
    OPENCODE = "opencode"
    TEAM_STAGE_RUNNER = "team_stage_runner"
    GENERIC_COMMAND = "generic_command"
    UNKNOWN = "unknown"


class RuntimeSafety(BaseModel):
    readonly_profile: bool = True
    executes_command: bool = False
    secrets_redacted: bool = True
    command_value_exposed: bool = False
    safe_to_execute: bool = False
    warnings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)


class RuntimeAuditSummary(BaseModel):
    status: str = "unknown"
    notes: list[str] = Field(default_factory=list)
    configured_inputs: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    fallback_inputs: list[str] = Field(default_factory=list)


class AgentRuntimeProfile(BaseModel):
    contract_version: str = "agent_runtime.profile.v1"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    stage: str
    provider: RuntimeProvider = RuntimeProvider.UNKNOWN
    mode: RuntimeMode = RuntimeMode.UNKNOWN
    command_env_var: str = ""
    fallback_command_env_vars: list[str] = Field(default_factory=list)
    command_configured: bool = False
    command_fingerprint: str = ""
    real_flag_env_var: str = ""
    real_enabled: bool = False
    strict_flag_env_var: str = ""
    strict_enabled: bool = False
    timeout_env_var: str = ""
    timeout_seconds: int | None = None
    model: str = ""
    variant: str = ""
    source: str = ""
    audit: RuntimeAuditSummary = Field(default_factory=RuntimeAuditSummary)
    safety: RuntimeSafety = Field(default_factory=RuntimeSafety)
