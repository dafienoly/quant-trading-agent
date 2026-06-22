"""产品 API 端到端测试。
默认跳过（需要运行中的 API 服务）。
启用：RUN_PRODUCT_E2E=1 python -m pytest tests/test_product_api_e2e.py -q
"""
from __future__ import annotations
import os

import pytest
import requests

BASE = os.environ.get("PRODUCT_API_BASE_URL", "http://localhost:8001")
RUN_E2E = os.environ.get("RUN_PRODUCT_E2E") == "1"

pytestmark = pytest.mark.skipif(not RUN_E2E, reason="设置 RUN_PRODUCT_E2E=1 以启用")


def _get(path: str) -> dict:
    r = requests.get(f"{BASE}{path}", timeout=5)
    r.raise_for_status()
    return r.json()


def test_health():
    h = _get("/product/health")
    assert h.get("status") is not None


def test_config():
    c = _get("/product/config")
    assert "config" in c


def test_dashboard():
    d = _get("/product/dashboard")
    assert "is_demo" in d


def test_jobs():
    j = _get("/product/jobs")
    assert "jobs" in j


def test_quote_refresh():
    r = requests.post(f"{BASE}/product/jobs/quote_refresh/start", timeout=5)
    assert r.status_code == 200
