"""LLM routing utilities and DeepSeek Agent Runtime.

``ModelRouter`` provides config and legacy chat_json().
``DeepSeekRuntime`` provides the unified async-first calling framework.
"""
from src.llm.model_router import LLMConfig, ModelRouter

__all__ = ["LLMConfig", "ModelRouter"]
