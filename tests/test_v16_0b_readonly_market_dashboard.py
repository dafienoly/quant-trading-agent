"""Tests for V16.0b readonly market dashboard."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from src.api.app import create_app
    return TestClient(create_app())


@patch("src.product_app.market_data.fetch_product_quotes")
def test_quote_health_endpoint(mock_fpq, client):
    mock_fpq.return_value = {"quotes": [{"symbol": "000001.SZ"}], "status": "OK"}
    r = client.get("/product/quote-health")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "OK"


@patch("src.product_app.market_data.fetch_product_quotes")
def test_quotes_snapshot_endpoint(mock_fpq, client):
    mock_fpq.return_value = {"quotes": [{"symbol": "000001.SZ"}], "status": "OK"}
    r = client.get("/product/quotes-snapshot")
    assert r.status_code == 200


def test_refresh_status_endpoint(client):
    r = client.get("/product/refresh-status")
    assert r.status_code == 200
    assert r.json().get("status") in ("IDLE", "SUCCEEDED", "FAILED")


@patch("src.product_app.market_data.fetch_product_quotes")
def test_signal_observation_endpoint(mock_fpq, client):
    mock_fpq.return_value = {"quotes": [{"symbol": "000001.SZ"}], "status": "OK"}
    r = client.get("/product/signal-observation")
    assert r.status_code == 200
    data = r.json()
    assert "observations" in data
    for obs in data["observations"]:
        assert "symbol" in obs
        assert "status" in obs


@patch("src.product_app.service_manager.fetch_product_quotes")
def test_refresh_status_updates_after_trigger(mock_fpq, client):
    from src.product_app.service_manager import get_service_manager
    mock_fpq.return_value = {"quotes": [{"symbol": "000001.SZ"}], "status": "OK"}
    sm = get_service_manager()
    sm._execute_job("quote_refresh", {"symbols": ""})
    status = sm.get_refresh_status()
    assert status.get("status") in ("SUCCEEDED", "FAILED")
