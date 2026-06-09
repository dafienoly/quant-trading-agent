"""浏览器端到端测试 — 产品面板全流程验证"""
import pytest
import time

SCREENSHOT_DIR = "screenshots"


def _chromium_available():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
            return True
    except Exception:
        return False


# 浏览器测试需要 Playwright chromium 已安装
# 安装命令: python -m playwright install chromium
pytestmark = pytest.mark.skipif(
    not _chromium_available(),
    reason="Playwright chromium 未安装，运行 python -m playwright install chromium"
)

def test_product_dashboard():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1366, "height": 768})

        # 1. 访问 Streamlit 产品面板
        print("1. 访问产品面板...")
        page.goto("http://localhost:8501", timeout=30000)
        page.wait_for_load_state("networkidle", timeout=30000)
        time.sleep(5)  # Streamlit 需要额外渲染时间
        page.screenshot(path=f"{SCREENSHOT_DIR}/01_home.png", full_page=True)
        print("   截图: 01_home.png")

        # 2. 验证页面标题
        title = page.title()
        print(f"   页面标题: {title}")
        assert "量化" in title or "Quant" in title or "product" in title.lower() or "Streamlit" in title, f"标题不符: {title}"

        # 3. 验证系统状态 Tab 存在
        print("2. 验证 Tab 结构...")
        tabs = page.locator("[data-testid='stTabs'] button").all()
        tab_texts = [t.text_content() for t in tabs]
        print(f"   Tabs: {tab_texts}")
        assert len(tabs) >= 5, f"Tab 数量不足: {len(tabs)}"

        # 4. 点击实时行情 Tab
        print("3. 测试实时行情 Tab...")
        for tab in tabs:
            text = tab.text_content() or ""
            if "行情" in text or "Market" in text:
                tab.click()
                time.sleep(2)
                page.screenshot(path=f"{SCREENSHOT_DIR}/02_market.png", full_page=True)
                print("   截图: 02_market.png")
                break

        # 5. 点击信号中心 Tab
        print("4. 测试信号中心 Tab...")
        tabs = page.locator("[data-testid='stTabs'] button").all()
        for tab in tabs:
            text = tab.text_content() or ""
            if "信号" in text or "Signal" in text:
                tab.click()
                time.sleep(2)
                page.screenshot(path=f"{SCREENSHOT_DIR}/03_signals.png", full_page=True)
                print("   截图: 03_signals.png")
                break

        # 6. 点击配置中心 Tab
        print("5. 测试配置中心 Tab...")
        tabs = page.locator("[data-testid='stTabs'] button").all()
        for tab in tabs:
            text = tab.text_content() or ""
            if "配置" in text or "Config" in text:
                tab.click()
                time.sleep(2)
                page.screenshot(path=f"{SCREENSHOT_DIR}/04_config.png", full_page=True)
                print("   截图: 04_config.png")
                break

        # 7. 点击反馈中心 Tab
        print("6. 测试反馈中心 Tab...")
        tabs = page.locator("[data-testid='stTabs'] button").all()
        for tab in tabs:
            text = tab.text_content() or ""
            if "反馈" in text or "Feedback" in text:
                tab.click()
                time.sleep(2)
                page.screenshot(path=f"{SCREENSHOT_DIR}/05_feedback.png", full_page=True)
                print("   截图: 05_feedback.png")
                break

        browser.close()
        print("\n浏览器端到端测试通过！")


def test_api_endpoints():
    """测试 FastAPI 产品端点"""
    import requests

    base = "http://localhost:8001"
    print("\n7. 测试 API 端点...")

    # Health
    r = requests.get(f"{base}/product/health", timeout=5)
    assert r.status_code == 200, f"/product/health 失败: {r.status_code}"
    data = r.json()
    print(f"   /product/health: {data.get('status')}")

    # Config
    r = requests.get(f"{base}/product/config", timeout=5)
    assert r.status_code == 200, f"/product/config 失败: {r.status_code}"
    data = r.json()
    print(f"   /product/config: {list(data.get('config', {}).keys())[:5]}...")

    # Dashboard
    r = requests.get(f"{base}/product/dashboard", timeout=5)
    assert r.status_code == 200, f"/product/dashboard 失败: {r.status_code}"
    data = r.json()
    print(f"   /product/dashboard: is_demo={data.get('is_demo')}, quotes={len(data.get('quotes', []))}")

    # Jobs
    r = requests.get(f"{base}/product/jobs", timeout=5)
    assert r.status_code == 200, f"/product/jobs 失败: {r.status_code}"
    data = r.json()
    print(f"   /product/jobs: {len(data.get('jobs', []))} 个作业")

    # Start a job
    r = requests.post(f"{base}/product/jobs/quote_refresh/start", timeout=5)
    assert r.status_code == 200, f"启动作业失败: {r.status_code}"
    data = r.json()
    print(f"   启动 quote_refresh: {data.get('status')}")

    # Feedback
    r = requests.get(f"{base}/product/feedback", timeout=5)
    assert r.status_code == 200, f"/product/feedback 失败: {r.status_code}"
    data = r.json()
    print(f"   /product/feedback: {data.get('count')} 个 Bug")

    print("\nAPI 端点测试通过！")


if __name__ == "__main__":
    import os
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    test_api_endpoints()
    test_product_dashboard()
    print("\n全部端到端测试通过！")
