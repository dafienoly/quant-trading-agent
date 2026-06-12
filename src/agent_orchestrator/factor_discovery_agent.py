from __future__ import annotations

from typing import Any

from src.agent_orchestrator.output_guard import sanitize_llm_output


_DISCOVER_SYSTEM_PROMPT = """You are a quantitative factor research assistant.
Analyze the provided market context and generate structured factor hypotheses.

Rules:
- do not output BUY or SELL
- do not create orders
- do not bypass risk checks
- return JSON only
- do not output numerical factor values directly
- confidence is research confidence, not trading confidence
"""


class FactorDiscoveryAgent:
    def __init__(self, router: Any) -> None:
        self._router = router

    def discover(self, symbols: list[str], context: dict | None = None) -> dict:
        user_prompt = (
            f"Symbols: {symbols}\n"
            f"Context: {context}\n"
            "Generate up to 3 factor hypotheses with evidence and risk notes."
        )
        raw = self._router.chat_json(
            system_prompt=_DISCOVER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            schema_name="factor_discovery",
        )
        guard_result = sanitize_llm_output(raw)
        if guard_result["blocked"]:
            return {
                "status": "blocked_by_guard",
                "message": "LLM output contained forbidden trade-decision content",
                "block_reasons": guard_result["block_reasons"],
                "original_data": guard_result["sanitized"],
            }
        result = guard_result["sanitized"]
        if guard_result["warnings"]:
            result.setdefault("warnings", []).extend(guard_result["warnings"])
        return result
