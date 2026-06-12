"""Simplified Browser E2E test for Streamlit Dashboard"""
import sys
import time
import traceback

def test_streamlit_loads():
    """Test that Streamlit dashboard loads without StreamlitDuplicateElementId error"""
    from playwright.sync_api import sync_playwright
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        
        # Collect page errors
        page_errors = []
        page.on("pageerror", lambda err: page_errors.append(str(err)))
        
        print("Navigating to Streamlit...")
        response = page.goto("http://localhost:8502", timeout=60000, wait_until="domcontentloaded")
        print(f"HTTP status: {response.status if response else 'None'}")
        
        # Wait for Streamlit app to render (it does multiple re-renders)
        print("Waiting for Streamlit to render...")
        try:
            page.wait_for_selector("[data-testid='stSidebar']", timeout=30000)
            print("Sidebar found")
        except Exception as e:
            print(f"Sidebar not found: {e}")
        
        # Wait additional time for full render
        time.sleep(8)
        
        # Take screenshot
        page.screenshot(path="runtime/dashboard_screenshot.png", full_page=True)
        print("Screenshot saved")
        
        # Check for StreamlitDuplicateElementId or other exceptions
        body_html = page.content()
        
        # Check for error elements
        error_elements = page.locator("[data-testid='stException']").all()
        if error_elements:
            for i, el in enumerate(error_elements):
                try:
                    txt = el.inner_text(timeout=3000)
                    print(f"Exception {i}: {txt[:300]}")
                except:
                    pass
        
        # Check page_errors for StreamlitDuplicateElementId
        duplicate_errors = [e for e in page_errors if "DuplicateElementId" in e or "duplicate" in e.lower()]
        if duplicate_errors:
            print(f"FOUND StreamlitDuplicateElementId errors: {duplicate_errors}")
            browser.close()
            return False
        
        # Check body text for error indicators
        body_text = page.locator("body").inner_text(timeout=5000)
        if "StreamlitDuplicateElementId" in body_text or "DuplicateElementId" in body_text:
            print(f"FOUND StreamlitDuplicateElementId in page text!")
            browser.close()
            return False
        
        # Check if tabs rendered
        tabs = page.locator("[data-testid='stTabs'] button").all()
        tab_names = []
        for t in tabs:
            try:
                tab_names.append(t.inner_text(timeout=3000))
            except:
                tab_names.append("(unknown)")
        print(f"Tabs found: {tab_names}")
        
        # Click each tab and check for errors
        tab_errors = []
        for i, tab in enumerate(tabs):
            try:
                tab.click()
                time.sleep(3)
                exc = page.locator("[data-testid='stException']").all()
                if exc:
                    err_text = exc[0].inner_text(timeout=3000)[:200]
                    tab_errors.append(f"Tab '{tab_names[i]}': {err_text}")
                    print(f"  ERROR on tab '{tab_names[i]}': {err_text[:100]}")
                else:
                    print(f"  Tab '{tab_names[i]}': OK")
            except Exception as e:
                tab_errors.append(f"Tab '{tab_names[i]}': {str(e)[:100]}")
                print(f"  Tab '{tab_names[i]}': CLICK ERROR - {str(e)[:100]}")
        
        # Take final screenshot
        page.screenshot(path="runtime/dashboard_all_tabs.png", full_page=True)
        
        browser.close()
        
        if tab_errors:
            print(f"\nTab errors found: {tab_errors}")
            return False
        
        print("\nAll tabs OK!")
        return True

if __name__ == "__main__":
    try:
        success = test_streamlit_loads()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"FATAL: {e}")
        traceback.print_exc()
        sys.exit(1)
