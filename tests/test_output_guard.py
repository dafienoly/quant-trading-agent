"""Tests for the deterministic AI output guard (output_guard.py)."""

from __future__ import annotations

from src.agent_orchestrator.output_guard import sanitize_llm_output


class TestOutputGuard:
    """Test the deterministic sanitize_llm_output function."""

    def test_passes_safe_output(self):
        """Normal safe output should pass through unchanged."""
        raw = {
            "status": "ok",
            "hypotheses": [
                {
                    "hypothesis_id": "FD_001",
                    "name": "momentum_candidate",
                    "description": "A factor hypothesis.",
                    "evidence": ["data shows trend"],
                    "confidence": 0.55,
                }
            ],
        }
        result = sanitize_llm_output(raw)
        assert result["blocked"] is False
        assert result["sanitized"] == raw

    def test_passes_unavailable_status(self):
        """Output with unavailable status should pass through."""
        raw = {"status": "unavailable", "reason": "missing_api_key"}
        result = sanitize_llm_output(raw)
        assert result["blocked"] is False
        assert result["sanitized"] == raw

    def test_blocks_BUY_in_hypothesis_name(self):
        """Output containing BUY in a hypothesis name is blocked."""
        raw = {"status": "ok", "hypotheses": [{"name": "BUY_signal_candidate", "confidence": 0.9}]}
        result = sanitize_llm_output(raw)
        assert result["blocked"] is True
        assert any("BUY" in r for r in result["block_reasons"])

    def test_blocks_SELL_in_hypothesis_name(self):
        raw = {"status": "ok", "hypotheses": [{"name": "SELL_stock", "confidence": 0.8}]}
        result = sanitize_llm_output(raw)
        assert result["blocked"] is True
        assert any("SELL" in r for r in result["block_reasons"])

    def test_blocks_forbidden_top_level_key(self):
        """Output with a forbidden top-level key (e.g. order_type) is blocked."""
        raw = {"status": "ok", "hypotheses": [], "order_type": "limit"}
        result = sanitize_llm_output(raw)
        assert result["blocked"] is True
        assert any("order_type" in r for r in result["block_reasons"])

    def test_blocks_order_payload_key(self):
        raw = {"status": "ok", "order_payload": {"symbol": "600000.SH", "quantity": 100}}
        result = sanitize_llm_output(raw)
        assert result["blocked"] is True

    def test_blocks_nested_forbidden_key(self):
        """Output with a forbidden key nested inside a dict is blocked."""
        raw = {
            "status": "ok",
            "candidates": [{"symbol": "600000.SH", "order_type": "market"}],
        }
        result = sanitize_llm_output(raw)
        assert result["blocked"] is True
        assert any("order_type" in r for r in result["block_reasons"])

    def test_blocks_forbidden_value_pattern(self):
        """String values containing 'place order' are blocked."""
        raw = {
            "status": "ok",
            "advice": "You should place order for 600000.SH at market price.",
        }
        result = sanitize_llm_output(raw)
        assert result["blocked"] is True

    def test_blocks_position_size_value(self):
        """String values containing position allocation are blocked."""
        raw = {"status": "ok", "note": "Allocate position=5000 shares to 600000.SH"}
        result = sanitize_llm_output(raw)
        assert result["blocked"] is True

    def test_blocks_execute_order_instruction(self):
        """String values containing 'execute order' are blocked."""
        raw = {"status": "ok", "instruction": "Submit order for 100 shares."}
        result = sanitize_llm_output(raw)
        assert result["blocked"] is True

    def test_blocks_at_market_price_instruction(self):
        raw = {"status": "ok", "advice": "Buy at market price."}
        result = sanitize_llm_output(raw)
        assert result["blocked"] is True

    def test_blocks_nested_list_item_with_buy(self):
        """List items containing BUY should trigger block."""
        raw = {
            "status": "ok",
            "candidates": [
                {"symbol": "600000.SH", "reason": "This is a BUY candidate."},
            ],
        }
        result = sanitize_llm_output(raw)
        assert result["blocked"] is True

    def test_handles_non_dict_input(self):
        """Non-dict input is wrapped and passed through."""
        result = sanitize_llm_output(["a", "b"])
        assert result["blocked"] is False
        assert result["sanitized"] == {"data": ["a", "b"]}
        assert len(result["warnings"]) == 1

    def test_blocks_trade_decision_value(self):
        """trade_decision key is blocked."""
        raw = {"status": "ok", "trade_decision": "BUY"}
        result = sanitize_llm_output(raw)
        assert result["blocked"] is True

    def test_blocks_position_weight_key(self):
        raw = {"status": "ok", "position_weight": 0.5}
        result = sanitize_llm_output(raw)
        assert result["blocked"] is True

    def test_blocks_execution_plan_key(self):
        raw = {"status": "ok", "execution_plan": "buy 100 shares"}
        result = sanitize_llm_output(raw)
        assert result["blocked"] is True

    def test_case_insensitive_key_matching(self):
        """Forbidden keys should be matched case-insensitively."""
        raw = {"status": "ok", "Order_Type": "limit"}
        result = sanitize_llm_output(raw)
        assert result["blocked"] is True


class TestOutputGuardHostileAPIIntegration:
    """Hostile fake router scenarios proving unsafe output is blocked."""

    def test_hostile_factor_discovery_emitting_BUY(self):
        """Hostile factor discovery output with BUY should be blocked."""
        from src.agent_orchestrator.factor_discovery_agent import FactorDiscoveryAgent

        class _HostileRouter:
            def chat_json(self, **kwargs):
                return {
                    "status": "ok",
                    "hypotheses": [
                        {
                            "hypothesis_id": "FD_HOSTILE_001",
                            "name": "BUY_signal",
                            "description": "This stock is a BUY",
                            "confidence": 0.95,
                        }
                    ],
                }

        result = FactorDiscoveryAgent(router=_HostileRouter()).discover(
            symbols=["600000.SH"]
        )
        assert result["status"] == "blocked_by_guard"
        assert any("BUY" in r for r in result.get("block_reasons", []))

    def test_hostile_recommendation_emitting_SELL(self):
        """Hostile recommendation output with SELL should be blocked."""
        from src.agent_orchestrator.recommendation_agent import RecommendationAgent

        class _HostileRouter:
            def chat_json(self, **kwargs):
                return {
                    "status": "ok",
                    "candidates": [
                        {
                            "symbol": "600000.SH",
                            "rank": 1,
                            "research_reason": "SELL this stock immediately",
                            "confidence": 0.9,
                        }
                    ],
                }

        result = RecommendationAgent(router=_HostileRouter()).recommend(
            symbols=["600000.SH"]
        )
        assert result["status"] == "blocked_by_guard"
        assert any("SELL" in r for r in result.get("block_reasons", []))

    def test_hostile_recommendation_emitting_order_type(self):
        """Hostile recommendation with order_type fields should be blocked."""
        from src.agent_orchestrator.recommendation_agent import RecommendationAgent

        class _HostileRouter:
            def chat_json(self, **kwargs):
                return {
                    "status": "ok",
                    "candidates": [
                        {
                            "symbol": "600000.SH",
                            "rank": 1,
                            "order_type": "limit",
                            "order_quantity": 1000,
                        }
                    ],
                }

        result = RecommendationAgent(router=_HostileRouter()).recommend(
            symbols=["600000.SH"]
        )
        assert result["status"] == "blocked_by_guard"

    def test_hostile_signal_explanation_emitting_BUY(self):
        """Hostile signal explanation output with BUY should be blocked."""
        from src.agent_orchestrator.signal_explanation_agent import SignalExplanationAgent

        class _HostileRouter:
            def chat_json(self, **kwargs):
                return {
                    "status": "ok",
                    "explanation": "This signal suggests you should BUY.",
                    "risk_notes": ["No risk"],
                }

        signal = {"signal_id": "SIG_001", "signal_type": "hold"}
        result = SignalExplanationAgent(router=_HostileRouter()).explain(signal)
        assert result["status"] == "blocked_by_guard"
        assert any("BUY" in r for r in result.get("block_reasons", []))

    def test_api_factor_discovery_guard_blocks_buy(self):
        """API-level output guard blocks BUY from factor discovery."""
        from src.agent_orchestrator.output_guard import sanitize_llm_output

        raw = {"status": "ok", "hypotheses": [{"name": "BUY_stock_now", "confidence": 0.9}]}
        result = sanitize_llm_output(raw)
        assert result["blocked"] is True
        assert any("BUY" in r for r in result["block_reasons"])

    def test_api_recommendation_guard_blocks_order_type(self):
        """API-level output guard blocks order_type from recommendation."""
        from src.agent_orchestrator.output_guard import sanitize_llm_output

        raw = {"status": "ok", "candidates": [{"symbol": "600000.SH", "order_type": "market"}]}
        result = sanitize_llm_output(raw)
        assert result["blocked"] is True
        assert any("order_type" in r for r in result["block_reasons"])
