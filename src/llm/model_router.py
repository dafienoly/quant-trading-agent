from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str
    api_base: str
    api_key_env: str
    api_key_present: bool
    timeout_seconds: float
    max_retries: int
    max_concurrency: int
    max_tool_rounds: int
    thinking_default: bool
    thinking_effort: str


class ModelRouter:
    def get_config(self) -> LLMConfig:
        provider = os.getenv("LLM_PROVIDER", "deepseek").strip() or "deepseek"
        model = (
            os.getenv("LLM_MODEL")
            or os.getenv("DEEPSEEK_MODEL")
            or "deepseek-v4-flash"
        ).strip()
        api_base = (
            os.getenv("LLM_API_BASE")
            or os.getenv("DEEPSEEK_API_BASE")
            or "https://api.deepseek.com"
        ).strip()
        api_key_env = os.getenv("LLM_API_KEY_ENV", "DEEPSEEK_API_KEY").strip()
        return LLMConfig(
            provider=provider,
            model=model,
            api_base=api_base,
            api_key_env=api_key_env,
            api_key_present=bool(os.getenv(api_key_env, "").strip()),
            timeout_seconds=_positive_float("LLM_TIMEOUT_SECONDS", 45.0),
            max_retries=_positive_int("LLM_MAX_RETRIES", 3),
            max_concurrency=_positive_int("LLM_MAX_CONCURRENCY", 2),
            max_tool_rounds=_positive_int("LLM_TOOL_MAX_ROUNDS", 4),
            thinking_default=_env_bool("LLM_THINKING_DEFAULT", False),
            thinking_effort=_thinking_effort(),
        )

    def chat_json(self, *, system_prompt: str, user_prompt: str, schema_name: str) -> dict[str, Any]:
        """兼容旧 Agent 接口，并将实际调用委托给统一 Runtime。"""

        config = self.get_config()
        api_key = os.getenv(config.api_key_env, "").strip()
        if not api_key:
            return {"status": "unavailable", "reason": "missing_api_key", "schema": schema_name}

        try:
            from src.llm.deepseek_runtime import DeepSeekRuntime
            from src.llm.schemas import DeepSeekRequest
        except ModuleNotFoundError as exc:
            return {
                "status": "unavailable",
                "reason": "runtime_dependency_not_installed",
                "message": str(exc),
                "schema": schema_name,
            }

        profile_by_schema = {
            "factor_discovery": "factor_hypothesis",
            "research_recommendation": "recommendation_research",
            "signal_explanation": "signal_explanation",
        }
        result = DeepSeekRuntime(router=self).chat_json(
            DeepSeekRequest(
                profile=profile_by_schema.get(schema_name, "compat"),
                schema_name=schema_name,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        )
        if result.status == "ok" and result.data is not None:
            data = dict(result.data)
            data.setdefault("llm_model", config.model)
            data.setdefault("llm_provider", config.provider)
            return data
        reason = result.error.get("reason", result.status) if result.error else result.status
        return {"status": result.status, "reason": reason, "schema": schema_name}


def _positive_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _positive_float(name: str, default: float) -> float:
    try:
        return max(0.001, float(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "enabled", "on"}


def _thinking_effort() -> str:
    value = os.getenv("LLM_THINKING_EFFORT", "high").strip().lower()
    return value if value in {"high", "max"} else "high"
