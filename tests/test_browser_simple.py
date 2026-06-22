"""Simplified Browser E2E test for Streamlit Dashboard.

默认跳过。启用：RUN_BROWSER_E2E=1 pytest tests/test_browser_simple.py -q
"""
from __future__ import annotations

import os

import pytest

RUN_E2E = os.environ.get("RUN_BROWSER_E2E") == "1"
PRODUCT_DASHBOARD_URL = os.environ.get("PRODUCT_DASHBOARD_URL", "http://localhost:8501")

pytestmark = pytest.mark.skipif(not RUN_E2E, reason="设置 RUN_BROWSER_E2E=1 以启用浏览器 E2E")


def test_streamlit_loads():
    """Test that Streamlit dashboard loads without error."""
    try:
        from playwright.sync_api import sync_playwright, Error as PwError
    except ImportError:
        pytest.skip("playwright 未安装：pip install playwright && playwright install chromium")

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True, timeout=15000)
        except PwError as exc:
            pytest.skip(f"chromium 启动失败（可能未安装）：{exc}")

        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page_errors = []
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        page.goto(PRODUCT_DASHBOARD_URL, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(3000)

        browser.close()

        assert len(page_errors) == 0, f"页面 JS 错误：{page_errors}"
