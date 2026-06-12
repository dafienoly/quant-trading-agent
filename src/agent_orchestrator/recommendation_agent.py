from __future__ import annotations

from typing import Any

from src.agent_orchestrator.output_guard import sanitize_llm_output


_RECOMMEND_SYSTEM_PROMPT = """You are a research recommendation assistant.
Analyze the provided stock data and generate research rankings.

Rules:
- do not output BUY or SELL
- do not create orders
- do not bypass risk checks
- return JSON only
- output "Research ranking only. Not a trading instruction." in disclaimer
- confidence is research confidence only
"""


class RecommendationAgent:
    def __init__(self, router: Any) -> None:
        self._router = router

    def recommend(self, symbols: list[str], context: dict | None = None) -> dict:
        user_prompt = (
            f"Symbols: {symbols}\n"
            f"Context: {context}\n"
            "Generate research rankings with evidence and risk notes."
        )
        raw = self._router.chat_json(
            system_prompt=_RECOMMEND_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            schema_name="research_recommendation",
        )
        guard_result = sanitize_llm_output(raw)
        if guard_result["blocked"]:
            return {
                "status": "blocked_by_guard",
                "disclaimer": "Research ranking only. Not a trading instruction.",
                "message": "LLM output contained forbidden trade-decision content",
                "block_reasons": guard_result["block_reasons"],
                "original_data": guard_result["sanitized"],
            }
        result = guard_result["sanitized"]
        if guard_result["warnings"]:
            result.setdefault("warnings", []).extend(guard_result["warnings"])
        return result
