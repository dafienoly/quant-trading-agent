from __future__ import annotations

from typing import Any


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
        return self._router.chat_json(
            system_prompt=_RECOMMEND_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            schema_name="research_recommendation",
        )
