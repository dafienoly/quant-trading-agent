from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping

from pydantic import BaseModel, Field

_PUBLIC_KEYS = ["repository", "run_id", "workflow", "branch", "commit"]


class RemoteContextSource(BaseModel):
    name: str = "remote_context"
    configured: bool = False
    readonly: bool = True
    observed_context: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class AgentOpsRemoteContextSnapshot(BaseModel):
    contract_version: str = "agentops.remote_context.v1"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    readonly: bool = True
    status: str = "empty"
    sources: list[RemoteContextSource] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def _safe_value(key: str, value: str) -> str:
    if key == "commit" and len(value) > 12:
        return value[:12]
    return value


def build_remote_context_snapshot(context: Mapping[str, str] | None = None) -> AgentOpsRemoteContextSnapshot:
    raw = context or {}
    observed = {
        key: _safe_value(key, str(raw.get(key, "") or ""))
        for key in _PUBLIC_KEYS
        if str(raw.get(key, "") or "")
    }
    configured = bool(observed.get("repository"))
    source = RemoteContextSource(
        configured=configured,
        observed_context=observed,
        warnings=[] if configured else ["No remote context provided."],
    )
    return AgentOpsRemoteContextSnapshot(
        status="ready" if configured else "empty",
        sources=[source],
        warnings=[] if configured else ["Remote context is unavailable."],
        notes=["Readonly contract.", "No network request is performed."],
    )
