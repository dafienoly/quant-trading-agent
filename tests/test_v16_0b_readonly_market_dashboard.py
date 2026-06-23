"""Tests for V16.0b readonly market dashboard."""
from __future__ import annotations

from fastapi.testclient import TestClient
from src.api.app import create_app

client = TestClient(create_app())


def test_quote_health_endpoint():
    r = client.get("/product/quote-health")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert data["status"] in ("OK", "ERROR")


def test_refresh_status_endpoint():
    r = client.get("/product/refresh-status")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert len(data.get("status", "")) > 0


def test_signal_observation_endpoint_returns_list():
    r = client.get("/product/signal-observation")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert "observations" in data
    assert isinstance(data["observations"], list)
