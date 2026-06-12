"""DeepSeek Agent Runtime — Pydantic schemas for request/response/error models.

All JSON output from DeepSeek is validated through schemas defined here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field


# ============================================================
# Task Profile
# ============================================================


@dataclass(frozen=True)
class LLMTaskProfile:
    """Immutable profile describing how a task should call the LLM.

    Each Agent task (bugfix analysis, signal explanation, …) declares
    one profile so the Runtime knows which capabilities to enable.
    """

    name: str
    thinking_enabled: bool = False
    reasoning_effort: Literal["high", "max"] = "high"
    json_output: bool = True
    timeout_seconds: int = 45
    max_retries: int = 3
    max_tool_rounds: int = 4
    allow_tools: bool = False


# Built-in profiles — one constant per task type.
PROFILES: dict[str, LLMTaskProfile] = {
    "bugfix_analysis": LLMTaskProfile(
        name="bugfix_analysis",
        thinking_enabled=True,
        reasoning_effort="high",
        json_output=True,
        timeout_seconds=60,
        max_retries=3,
        max_tool_rounds=4,
        allow_tools=True,
    ),
    "bugfix_proposal": LLMTaskProfile(
        name="bugfix_proposal",
        thinking_enabled=True,
        reasoning_effort="high",
        json_output=True,
        timeout_seconds=60,
        max_retries=3,
        max_tool_rounds=4,
        allow_tools=True,
    ),
    "factor_hypothesis": LLMTaskProfile(
        name="factor_hypothesis",
        thinking_enabled=True,
        reasoning_effort="high",
        json_output=True,
        timeout_seconds=45,
        max_retries=3,
        max_tool_rounds=2,
        allow_tools=True,
    ),
    "recommendation_research": LLMTaskProfile(
        name="recommendation_research",
        thinking_enabled=True,
        reasoning_effort="high",
        json_output=True,
        timeout_seconds=45,
        max_retries=3,
        max_tool_rounds=2,
        allow_tools=True,
    ),
    "signal_explanation": LLMTaskProfile(
        name="signal_explanation",
        thinking_enabled=False,
        reasoning_effort="high",
        json_output=True,
        timeout_seconds=30,
        max_retries=2,
        max_tool_rounds=0,
        allow_tools=False,
    ),
}


def get_profile(name: str) -> LLMTaskProfile:
    """Look up a profile by name; raises KeyError for unknown names."""
    if name not in PROFILES:
        raise KeyError(f"Unknown LLM task profile: {name!r}. Available: {list(PROFILES)}")
    return PROFILES[name]


# ============================================================
# Request / Response
# ============================================================


class DeepSeekRequest(BaseModel):
    """Complete request payload for a single LLM call or multi-round session."""

    profile: str
    schema_name: str
    system_prompt: str
    user_prompt: str
    conversation_id: str | None = None
    tools: list[str] = Field(default_factory=list)
    json_schema: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeepSeekResult(BaseModel):
    """Unified result from DeepSeekRuntime.

    ``status != "ok"`` must be treated as failure by calling layers.
    """

    status: Literal[
        "ok",
        "unavailable",
        "timeout",
        "invalid_response",
        "tool_error",
        "api_error",
    ]
    data: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    provider: str = "deepseek"
    model: str = ""
    conversation_id: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)



# ============================================================
# BugFix Agent Schemas
# ============================================================


class BugFixAnalysis(BaseModel):
    """Structured output from BugFixAgent.analyze()."""

    status: str = "ok"
    root_cause: str
    affected_files: list[str] = Field(default_factory=list)
    fix_steps: list[str] = Field(default_factory=list)
    risk_level: str = "medium"
    estimated_impact: str = ""
    needs_human_review: bool = True
    evidence: list[dict[str, str]] = Field(default_factory=list)


class CodeChange(BaseModel):
    """A single code change within a fix proposal."""

    file_path: str
    change_type: Literal["add", "modify", "delete"]
    diff: str = ""
    reason: str = ""


class BugFixProposal(BaseModel):
    """Structured output from BugFixAgent.propose_fix()."""

    status: str = "ok"
    fix_description: str
    code_changes: list[CodeChange] = Field(default_factory=list)
    risk_level: str = "medium"
    estimated_impact: str = ""
    test_suggestions: list[str] = Field(default_factory=list)
    requires_approval: bool = True


# ============================================================
# Schema Registry — maps schema_name to Pydantic model class
# ============================================================
# Used by DeepSeekRuntime to validate JSON output at the framework
# layer before returning ``status="ok"``.

SCHEMA_REGISTRY: dict[str, type[BaseModel]] = {
    "bugfix_analysis": BugFixAnalysis,
    "bugfix_proposal": BugFixProposal,
}


def validate_schema(schema_name: str, data: dict[str, Any]) -> dict[str, Any]:
    """Validate *data* against the registered schema for *schema_name*.

    Returns:
        The validated dict (with defaults filled in).

    Raises:
        KeyError: if *schema_name* is not in the registry.
        pydantic.ValidationError: if validation fails.
    """
    model_cls = SCHEMA_REGISTRY[schema_name]
    validated = model_cls(**data)
    return validated.model_dump()
