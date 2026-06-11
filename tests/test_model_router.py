from __future__ import annotations

from src.llm.model_router import ModelRouter


def test_model_router_defaults_to_deepseek_v4_flash(monkeypatch):
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    config = ModelRouter().get_config()

    assert config.provider == "deepseek"
    assert config.model == "deepseek-v4-flash"
    assert config.api_key_present is True


def test_model_router_accepts_llm_model_override(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "future-model")
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("LLM_API_KEY_ENV", "DEEPSEEK_API_KEY")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    config = ModelRouter().get_config()

    assert config.model == "future-model"
    assert config.api_key_present is True


def test_model_router_reports_missing_key(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY_ENV", "DEEPSEEK_API_KEY")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    config = ModelRouter().get_config()

    assert config.api_key_present is False


def test_llm_status_endpoint(monkeypatch):
    from fastapi.testclient import TestClient
    from src.api.app import app

    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("LLM_MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("LLM_API_KEY_ENV", "DEEPSEEK_API_KEY")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    client = TestClient(app)
    response = client.get("/product/llm/status")

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "deepseek"
    assert body["model"] == "deepseek-v4-flash"
    assert body["api_key_present"] is True
    assert body["trade_decision_enabled"] is False
