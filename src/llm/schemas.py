"""DeepSeek Runtime 的请求、结果和结构化输出模型。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


@dataclass(frozen=True)
class LLMTaskProfile:
    """定义单类任务允许启用的模型能力。"""

    name: str
    thinking_enabled: bool = False
    reasoning_effort: Literal["high", "max"] = "high"
    allow_tools: bool = False


PROFILES: dict[str, LLMTaskProfile] = {
    "bugfix_analysis": LLMTaskProfile(
        name="bugfix_analysis",
        thinking_enabled=True,
        allow_tools=True,
    ),
    "bugfix_proposal": LLMTaskProfile(
        name="bugfix_proposal",
        thinking_enabled=True,
        allow_tools=True,
    ),
    "factor_hypothesis": LLMTaskProfile(
        name="factor_hypothesis",
        thinking_enabled=True,
        allow_tools=False,
    ),
    "recommendation_research": LLMTaskProfile(
        name="recommendation_research",
        thinking_enabled=True,
        allow_tools=False,
    ),
    "signal_explanation": LLMTaskProfile(name="signal_explanation"),
    "compat": LLMTaskProfile(name="compat"),
}


def get_profile(name: str) -> LLMTaskProfile:
    """返回已注册 profile；未知 profile 必须由调用层拒绝。"""

    return PROFILES[name]


class DeepSeekRequest(BaseModel):
    """一次结构化模型调用的完整输入。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    profile: str = Field(min_length=1)
    schema_name: str = Field(min_length=1)
    system_prompt: str = Field(min_length=1)
    user_prompt: str = Field(min_length=1)
    conversation_id: str | None = None
    tools: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


ResultStatus = Literal[
    "ok",
    "unavailable",
    "timeout",
    "invalid_response",
    "tool_error",
    "api_error",
]


class DeepSeekResult(BaseModel):
    """Runtime 统一结果；非 ``ok`` 状态不得携带成功数据。"""

    model_config = ConfigDict(extra="forbid")

    status: ResultStatus
    data: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    provider: str = "deepseek"
    model: str = ""
    conversation_id: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_result_shape(self) -> DeepSeekResult:
        if self.status == "ok" and self.data is None:
            raise ValueError("ok result requires data")
        if self.status != "ok":
            self.data = None
            if self.error is None:
                raise ValueError("error result requires error details")
        return self


class StrictOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")


RiskLevel = Literal["low", "medium", "high", "critical"]


class BugFixEvidence(StrictOutput):
    source: str
    summary: str


class BugFixAnalysis(StrictOutput):
    status: Literal["ok"] = "ok"
    root_cause: str = Field(min_length=1)
    affected_files: list[str] = Field(default_factory=list)
    fix_steps: list[str] = Field(min_length=1)
    risk_level: RiskLevel
    estimated_impact: str = Field(min_length=1)
    needs_human_review: Literal[True] = True
    evidence: list[BugFixEvidence] = Field(default_factory=list)


class CodeChange(StrictOutput):
    file_path: str = Field(min_length=1)
    change_type: Literal["add", "modify", "delete"]
    diff: str = ""
    reason: str = Field(min_length=1)


class BugFixProposal(StrictOutput):
    status: Literal["ok"] = "ok"
    fix_description: str = Field(min_length=1)
    code_changes: list[CodeChange] = Field(min_length=1)
    risk_level: RiskLevel
    estimated_impact: str = Field(min_length=1)
    test_suggestions: list[str] = Field(min_length=1)
    requires_approval: Literal[True] = True


class FactorHypothesis(StrictOutput):
    hypothesis_id: str = ""
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    theme_tags: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(min_length=1)
    source: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    risk_notes: list[str] = Field(min_length=1)


class FactorDiscoveryOutput(StrictOutput):
    status: Literal["ok"] = "ok"
    hypotheses: list[FactorHypothesis] = Field(min_length=1, max_length=3)


class ResearchRecommendationOutput(StrictOutput):
    status: Literal["ok"] = "ok"
    rankings: list[dict[str, Any]] = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(min_length=1)
    disclaimer: str = Field(min_length=1)


class SignalExplanationOutput(StrictOutput):
    status: Literal["ok"] = "ok"
    explanation: str = Field(min_length=1)
    evidence: list[str] = Field(min_length=1)
    risk_notes: list[str] = Field(min_length=1)
    decision_source: Literal["quant_rules_and_risk_gate"] = "quant_rules_and_risk_gate"


SCHEMA_REGISTRY: dict[str, type[BaseModel]] = {
    "bugfix_analysis": BugFixAnalysis,
    "bugfix_proposal": BugFixProposal,
    "factor_discovery": FactorDiscoveryOutput,
    "research_recommendation": ResearchRecommendationOutput,
    "signal_explanation": SignalExplanationOutput,
}


def get_schema(schema_name: str) -> type[BaseModel]:
    """返回已注册输出模型。"""

    return SCHEMA_REGISTRY[schema_name]


def schema_json(schema_name: str) -> str:
    """返回稳定排序的 JSON schema 文本，用于 prompt prefix。"""

    schema = get_schema(schema_name).model_json_schema()
    return json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def validate_schema(schema_name: str, data: dict[str, Any]) -> dict[str, Any]:
    """校验并返回补齐默认值后的普通字典。"""

    return get_schema(schema_name).model_validate(data).model_dump(mode="json")
