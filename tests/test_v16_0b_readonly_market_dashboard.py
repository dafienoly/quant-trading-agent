"""Tests for V16.0b readonly market dashboard."""
from __future__ import annotations

from fastapi.testclient import TestClient
from src.api.app import create_app

client = TestClient(create_app())


def test_quote_health_endpoint():
    r = client.get("/product/quote-health")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "OK", f"expected OK, got {data}"
    assert "results" in data
    assert isinstance(data["results"], dict)


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

def test_quotes_snapshot_endpoint():
    r = client.get("/product/quotes-snapshot")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") in ("OK", "ERROR")


def test_quote_refresh_trigger():
    r = client.post("/product/quote-refresh")
    assert r.status_code == 200
    assert r.json().get("status") in ("OK", "ERROR")


def test_refresh_status_updates_after_trigger():
    # Arrange
    from src.product_app.service_manager import get_service_manager
    sm = get_service_manager()
    # Act
    sm._execute_job("quote_refresh", {"symbols": ""})
    status = sm.get_refresh_status()
    # Assert
    assert status.get("status") in ("SUCCEEDED", "FAILED")
    if status["status"] == "SUCCEEDED":
        assert isinstance(status.get("data"), list)
