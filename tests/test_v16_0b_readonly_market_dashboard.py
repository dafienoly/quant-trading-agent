"""Tests for V16.0b readonly market dashboard."""
from __future__ import annotations

from fastapi.testclient import TestClient
from src.api.app import create_app

client = TestClient(create_app())


def test_quote_health_endpoint():
    r = client.get("/product/quote-health")
    assert r.status_code in (200, 503)
    data = r.json()
    assert "results" in data


def test_refresh_status_endpoint():
    r = client.get("/product/refresh-status")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") in ("IDLE", "SUCCEEDED", "FAILED")


def test_signal_observation_endpoint_returns_observations():
    r = client.get("/product/signal-observation")
    assert r.status_code == 200
    data = r.json()
    assert "observations" in data
    assert isinstance(data["observations"], list)
    for obs in data["observations"]:
        assert "symbol" in obs
        assert "status" in obs
        assert "health" in obs
