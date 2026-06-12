"""Model Router — configuration and legacy chat_json compatibility.

``ModelRouter`` provides env-based provider/model config and a
``chat_json()`` method that now delegates to ``DeepSeekRuntime``.

All new code should use ``DeepSeekRuntime`` directly.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from loguru import logger


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str
    api_base: str
    api_key_env: str
    api_key_present: bool


class ModelRouter:
    """Legacy configuration and compatibility router.

    Kept for existing consumer code paths (e.g. ``/product/llm/status``).
    Prefer ``DeepSeekRuntime`` for all new LLM calls.
    """

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
        )

    def chat_json(self, *, system_prompt: str, user_prompt: str, schema_name: str) -> dict[str, Any]:
        """Compatibility wrapper that delegates to DeepSeekRuntime.

        New code should call ``DeepSeekRuntime.chat_json()`` directly.
        """
        config = self.get_config()
        api_key = os.getenv(config.api_key_env, "").strip()
        if not api_key:
            return {"status": "unavailable", "reason": "missing_api_key", "schema": schema_name}

        try:
            from src.llm.deepseek_runtime import DeepSeekRuntime
            from src.llm.schemas import DeepSeekRequest

            runtime = DeepSeekRuntime(router=self)
            result = runtime.chat_json(
                DeepSeekRequest(
                    profile="compat",
                    schema_name=schema_name,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                )
            )

            if result.status == "ok" and result.data is not None:
                result.data.setdefault("llm_model", config.model)
                result.data.setdefault("llm_provider", config.provider)
                return result.data

            error_reason = result.error.get("reason", result.status) if result.error else result.status
            return {"status": result.status, "reason": error_reason, "schema": schema_name}

        except Exception as exc:
            logger.error("ModelRouter.chat_json failed: {}", exc)
            return {"status": "unavailable", "reason": str(exc), "schema": schema_name}
