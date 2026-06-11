from __future__ import annotations


class FakeRouter:
    def chat_json(self, *, system_prompt: str, user_prompt: str, schema_name: str):
        assert "do not output BUY or SELL" in system_prompt
        return {
            "status": "ok",
            "hypotheses": [
                {
                    "hypothesis_id": "FD_TEST_001",
                    "name": "theme_momentum_candidate",
                    "description": "Theme momentum may explain recent strength.",
                    "theme_tags": ["ai_chip"],
                    "evidence": ["factor_summary.momentum positive"],
                    "source": ["factor_summary"],
                    "confidence": 0.55,
                    "risk_notes": ["Data may be delayed."],
                }
            ],
        }


class FakeRouterExplain:
    def chat_json(self, *, system_prompt: str, user_prompt: str, schema_name: str):
        return {
            "status": "ok",
            "explanation": "Signal was produced by deterministic rules.",
            "evidence": ["data_health OK"],
            "risk_notes": ["No direct trading decision from LLM."],
        }


def test_factor_discovery_agent_does_not_emit_trade_decision():
    from src.agent_orchestrator.factor_discovery_agent import FactorDiscoveryAgent

    result = FactorDiscoveryAgent(router=FakeRouter()).discover(
        symbols=["600000.SH"],
        context={"factor_summary": {"momentum": 0.1}},
    )

    text = str(result).upper()
    assert "BUY" not in text
    assert "SELL" not in text
    assert result["hypotheses"][0]["confidence"] == 0.55


def test_signal_explanation_agent_keeps_original_signal_type():
    from src.agent_orchestrator.signal_explanation_agent import SignalExplanationAgent

    signal = {"signal_id": "SIG_TEST_001", "signal_type": "hold"}
    result = SignalExplanationAgent(router=FakeRouterExplain()).explain(signal)

    assert result["signal_id"] == "SIG_TEST_001"
    assert result["original_signal_type"] == "hold"
    assert result["decision_source"] == "quant_rules_and_risk_gate"
