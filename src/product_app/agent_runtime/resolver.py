from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from typing import Mapping

from .contracts import (
    AgentRuntimeProfile,
    RuntimeAuditSummary,
    RuntimeMode,
    RuntimeProvider,
    RuntimeSafety,
)

_TRUE_VALUES = {"1", "true", "yes", "on", "enabled"}
_FALSE_VALUES = {"0", "false", "no", "off", "disabled"}


@dataclass(frozen=True)
class StageRuntimeSpec:
    stage: str
    provider: RuntimeProvider
    command_env_var: str = ""
    fallback_command_env_vars: tuple[str, ...] = ()
    real_flag_env_var: str = ""
    strict_flag_env_var: str = ""
    timeout_env_var: str = ""
    default_timeout_seconds: int | None = None
    model: str = ""
    variant: str = ""
    source: str = ""
    team_stage: bool = False
    audit_notes: tuple[str, ...] = field(default_factory=tuple)


_STAGE_SPECS: dict[str, StageRuntimeSpec] = {
    "codex_pm": StageRuntimeSpec(
        stage="codex_pm",
        provider=RuntimeProvider.CODEX,
        command_env_var="CODEX_A_PM_AGENT_COMMAND",
        real_flag_env_var="AGENT_REAL_CODEX_PM",
        strict_flag_env_var="AGENT_REAL_CODEX_PM_STRICT",
        source=".github/workflows/agent-stage-runner.yml",
    ),
    "codex_architect": StageRuntimeSpec(
        stage="codex_architect",
        provider=RuntimeProvider.CODEX,
        command_env_var="CODEX_B_ARCHITECT_AGENT_COMMAND",
        real_flag_env_var="AGENT_REAL_CODEX_ARCHITECT",
        strict_flag_env_var="AGENT_REAL_CODEX_ARCHITECT_STRICT",
        source=".github/workflows/agent-stage-runner.yml",
    ),
    "codex_reviewer": StageRuntimeSpec(
        stage="codex_reviewer",
        provider=RuntimeProvider.CODEX,
        command_env_var="CODEX_B_REVIEW_AGENT_COMMAND",
        fallback_command_env_vars=("REVIEW_AGENT_COMMAND",),
        real_flag_env_var="AGENT_REAL_CODEX_REVIEWER",
        strict_flag_env_var="AGENT_REAL_CODEX_REVIEWER_STRICT",
        source=".github/workflows/agent-stage-runner.yml",
    ),
    "codex_acceptance": StageRuntimeSpec(
        stage="codex_acceptance",
        provider=RuntimeProvider.CODEX,
        command_env_var="CODEX_A_ACCEPTANCE_AGENT_COMMAND",
        fallback_command_env_vars=("ACCEPTANCE_AGENT_COMMAND",),
        real_flag_env_var="AGENT_REAL_CODEX_ACCEPTANCE",
        strict_flag_env_var="AGENT_REAL_CODEX_ACCEPTANCE_STRICT",
        source=".github/workflows/agent-stage-runner.yml",
    ),
    "claude_lead_plan": StageRuntimeSpec(
        stage="claude_lead_plan",
        provider=RuntimeProvider.OPENCODE,
        timeout_env_var="AGENT_LEAD_STAGE_TIMEOUT_SECONDS",
        default_timeout_seconds=1200,
        model="opencode-go/deepseek-v4-pro",
        variant="max",
        source="scripts/run-team-stage.ps1 -> scripts/run-pipeline-team-agent.sh",
        team_stage=True,
        audit_notes=("Team stage uses OpenCode runner despite legacy claude_* stage name.",),
    ),
    "claude_lead_review": StageRuntimeSpec(
        stage="claude_lead_review",
        provider=RuntimeProvider.OPENCODE,
        timeout_env_var="AGENT_LEAD_STAGE_TIMEOUT_SECONDS",
        default_timeout_seconds=1200,
        model="opencode-go/deepseek-v4-pro",
        variant="max",
        source="scripts/run-team-stage.ps1 -> scripts/run-pipeline-team-agent.sh",
        team_stage=True,
        audit_notes=("Team stage uses OpenCode runner despite legacy claude_* stage name.",),
    ),
    "postmortem": StageRuntimeSpec(
        stage="postmortem",
        provider=RuntimeProvider.OPENCODE,
        timeout_env_var="AGENT_LEAD_STAGE_TIMEOUT_SECONDS",
        default_timeout_seconds=1200,
        model="opencode-go/deepseek-v4-pro",
        variant="max",
        source="scripts/run-team-stage.ps1 -> scripts/run-pipeline-team-agent.sh",
        team_stage=True,
    ),
    "claude_developer": StageRuntimeSpec(
        stage="claude_developer",
        provider=RuntimeProvider.OPENCODE,
        timeout_env_var="AGENT_DEVELOPER_STAGE_TIMEOUT_SECONDS",
        default_timeout_seconds=2400,
        model="opencode-go/deepseek-v4-flash",
        variant="max",
        source="scripts/run-team-stage.ps1 -> scripts/run-pipeline-team-agent.sh",
        team_stage=True,
        audit_notes=("Team stage uses OpenCode runner despite legacy claude_* stage name.",),
    ),
    "bugfix": StageRuntimeSpec(
        stage="bugfix",
        provider=RuntimeProvider.OPENCODE,
        timeout_env_var="AGENT_DEVELOPER_STAGE_TIMEOUT_SECONDS",
        default_timeout_seconds=2400,
        model="opencode-go/deepseek-v4-flash",
        variant="max",
        source="scripts/run-team-stage.ps1 -> scripts/run-pipeline-team-agent.sh",
        team_stage=True,
    ),
    "claude_tester": StageRuntimeSpec(
        stage="claude_tester",
        provider=RuntimeProvider.OPENCODE,
        timeout_env_var="AGENT_TESTER_STAGE_TIMEOUT_SECONDS",
        default_timeout_seconds=1800,
        model="opencode-go/deepseek-v4-flash",
        variant="max",
        source="scripts/run-team-stage.ps1 -> scripts/run-pipeline-team-agent.sh",
        team_stage=True,
        audit_notes=("Team stage uses OpenCode runner despite legacy claude_* stage name.",),
    ),
    "runtime_preflight": StageRuntimeSpec(
        stage="runtime_preflight",
        provider=RuntimeProvider.OPENCODE,
        timeout_env_var="AGENT_PREFLIGHT_TIMEOUT_SECONDS",
        default_timeout_seconds=180,
        source="scripts/run-team-stage.ps1 -PreflightOnly",
        team_stage=True,
    ),
}


def _env_value(env: Mapping[str, str], name: str) -> str:
    return str(env.get(name, "") or "")


def _truthy(env: Mapping[str, str], name: str) -> bool:
    return _env_value(env, name).strip().lower() in _TRUE_VALUES


def _falsey(env: Mapping[str, str], name: str) -> bool:
    value = _env_value(env, name).strip().lower()
    return bool(value) and value in _FALSE_VALUES


def _configured(env: Mapping[str, str], name: str) -> bool:
    return bool(_env_value(env, name).strip())


def _safe_fingerprint(value: str) -> str:
    if not value:
        return ""
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"sha256:{digest}"


def _timeout(env: Mapping[str, str], spec: StageRuntimeSpec) -> int | None:
    if not spec.timeout_env_var:
        return spec.default_timeout_seconds
    raw = _env_value(env, spec.timeout_env_var).strip()
    if not raw:
        return spec.default_timeout_seconds
    if raw.isdigit() and int(raw) > 0:
        return int(raw)
    return spec.default_timeout_seconds


def _command(env: Mapping[str, str], spec: StageRuntimeSpec) -> tuple[bool, str, list[str], list[str]]:
    configured_inputs: list[str] = []
    missing_inputs: list[str] = []
    fallback_inputs: list[str] = []
    names = [spec.command_env_var, *spec.fallback_command_env_vars]
    for index, name in enumerate(n for n in names if n):
        if _configured(env, name):
            configured_inputs.append(name)
            if index > 0:
                fallback_inputs.append(name)
            return True, _env_value(env, name), configured_inputs, fallback_inputs
        missing_inputs.append(name)
    return False, "", configured_inputs, fallback_inputs


def _mode(
    *,
    env: Mapping[str, str],
    spec: StageRuntimeSpec,
    dry_run: bool,
    command_configured: bool,
    command_value: str,
) -> RuntimeMode:
    if dry_run:
        return RuntimeMode.DRY_RUN
    command_lower = command_value.lower()
    if "dry-run" in command_lower or "dry_run" in command_lower:
        return RuntimeMode.DRY_RUN
    if "mock" in command_lower or "smoke" in command_lower:
        return RuntimeMode.MOCK
    if spec.team_stage:
        return RuntimeMode.REAL
    if spec.real_flag_env_var and _truthy(env, spec.real_flag_env_var) and command_configured:
        return RuntimeMode.REAL
    if spec.real_flag_env_var and _falsey(env, spec.real_flag_env_var):
        return RuntimeMode.DISABLED
    if command_configured:
        return RuntimeMode.UNKNOWN
    return RuntimeMode.DISABLED


def resolve_agent_runtime(
    stage: str,
    *,
    env: Mapping[str, str] | None = None,
    dry_run: bool = False,
) -> AgentRuntimeProfile:
    """Resolve a read-only Agent runtime profile for *stage*.

    The resolver never executes command values and never returns raw command text.
    It only reports whether a command-like input is configured and emits a stable
    non-secret fingerprint for auditing drift.
    """

    env_map = env or os.environ
    spec = _STAGE_SPECS.get(stage)
    if spec is None:
        audit = RuntimeAuditSummary(
            status="unknown_stage",
            notes=["Stage is not registered in Agent Runtime Abstraction."],
        )
        safety = RuntimeSafety(
            safe_to_execute=False,
            warnings=["Unknown runtime stage."],
            blockers=["Runtime stage is not registered."],
        )
        return AgentRuntimeProfile(
            stage=stage,
            provider=RuntimeProvider.UNKNOWN,
            mode=RuntimeMode.UNKNOWN,
            audit=audit,
            safety=safety,
        )

    command_configured, command_value, configured_inputs, fallback_inputs = _command(env_map, spec)
    mode = _mode(
        env=env_map,
        spec=spec,
        dry_run=dry_run,
        command_configured=command_configured,
        command_value=command_value,
    )
    strict_enabled = _truthy(env_map, spec.strict_flag_env_var) if spec.strict_flag_env_var else False
    real_enabled = _truthy(env_map, spec.real_flag_env_var) if spec.real_flag_env_var else mode == RuntimeMode.REAL
    missing_inputs = [
        name
        for name in [spec.command_env_var, *spec.fallback_command_env_vars]
        if name and name not in configured_inputs
    ]

    notes = [*spec.audit_notes]
    if mode == RuntimeMode.UNKNOWN:
        notes.append("Command is configured but explicit real/mock/dry-run status is unclear.")
    elif mode == RuntimeMode.DISABLED:
        notes.append("Runtime is disabled or command input is missing.")
    elif mode == RuntimeMode.MOCK:
        notes.append("Runtime command appears to be mock/smoke style.")
    elif mode == RuntimeMode.DRY_RUN:
        notes.append("Runtime is dry-run; no Agent command should execute.")
    else:
        notes.append("Runtime profile resolves to real execution mode.")

    blockers: list[str] = []
    warnings: list[str] = []
    if mode in {RuntimeMode.DISABLED, RuntimeMode.UNKNOWN}:
        warnings.append(f"Runtime mode is {mode.value}.")
    if strict_enabled and mode != RuntimeMode.REAL:
        blockers.append("Strict mode requires a real runtime profile.")

    safe_to_execute = mode == RuntimeMode.REAL and not blockers
    audit = RuntimeAuditSummary(
        status=mode.value,
        notes=notes,
        configured_inputs=configured_inputs,
        missing_inputs=missing_inputs,
        fallback_inputs=fallback_inputs,
    )
    safety = RuntimeSafety(
        safe_to_execute=safe_to_execute,
        warnings=warnings,
        blockers=blockers,
    )

    return AgentRuntimeProfile(
        stage=stage,
        provider=spec.provider,
        mode=mode,
        command_env_var=spec.command_env_var,
        fallback_command_env_vars=list(spec.fallback_command_env_vars),
        command_configured=command_configured or spec.team_stage,
        command_fingerprint=_safe_fingerprint(command_value),
        real_flag_env_var=spec.real_flag_env_var,
        real_enabled=real_enabled,
        strict_flag_env_var=spec.strict_flag_env_var,
        strict_enabled=strict_enabled,
        timeout_env_var=spec.timeout_env_var,
        timeout_seconds=_timeout(env_map, spec),
        model=spec.model,
        variant=spec.variant,
        source=spec.source,
        audit=audit,
        safety=safety,
    )
