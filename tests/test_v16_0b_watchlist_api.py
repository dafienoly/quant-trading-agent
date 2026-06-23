"""Tests for V16.0b watchlist API."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from src.api.app import create_app

client = TestClient(create_app())


def test_get_watchlist_empty():
    Path(".agent/watchlist.txt").unlink(missing_ok=True)
    r = client.get("/product/watchlist")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


def test_update_watchlist():
    r = client.put("/product/watchlist?symbols=000001.SZ&symbols=000002.SZ")
    assert r.status_code == 200
    data = r.json()
    assert "000001.SZ" in data["symbols"]
    assert "000002.SZ" in data["symbols"]


def test_watchlist_rejects_duplicate():
    r = client.put("/product/watchlist?symbols=000001.SZ&symbols=000001.SZ")
    assert r.status_code == 200
    data = r.json()
    assert "重复代码" in str(data["errors"])
    assert len(data["symbols"]) == 1


def test_watchlist_rejects_invalid():
    r = client.put("/product/watchlist?symbols=NOT!VALID")
    data = r.json()
    assert "非法代码" in str(data["errors"])
