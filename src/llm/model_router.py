from __future__ import annotations

import json
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
        )

    def chat_json(self, *, system_prompt: str, user_prompt: str, schema_name: str) -> dict[str, Any]:
        config = self.get_config()
        api_key = os.getenv(config.api_key_env, "").strip()
        if not api_key:
            return {"status": "unavailable", "reason": "missing_api_key", "schema": schema_name}

        # Lazy import: openai package may not be installed
        try:
            from openai import OpenAI
        except ModuleNotFoundError:
            return {
                "status": "unavailable",
                "reason": "openai_package_not_installed",
                "message": "The 'openai' package is required for LLM features. "
                "Install it with: pip install openai>=1.0",
                "schema": schema_name,
            }

        client = OpenAI(api_key=api_key, base_url=config.api_base)
        response = client.chat.completions.create(
            model=config.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        text = response.choices[0].message.content or ""
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            cleaned = text.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.strip("`").strip()
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:].strip()
            try:
                data = json.loads(cleaned)
            except json.JSONDecodeError:
                return {"status": "invalid_response", "raw": text, "schema": schema_name}
        if isinstance(data, dict):
            data.setdefault("llm_model", config.model)
            data.setdefault("llm_provider", config.provider)
            return data
        return {"status": "invalid_response", "raw": text, "schema": schema_name}
