"""Browser E2E test for Streamlit Dashboard - Phase 5.6 Review
Quick version - only checks page load and DuplicateElementId, no tab clicking.
"""
import sys
import time

def main():
    from playwright.sync_api import sync_playwright
    
    results = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        
        page_errors = []
        page.on("pageerror", lambda err: page_errors.append(str(err)))
        
        # Test 1: Streamlit health check
        print("Test 1: Streamlit health check")
        try:
            page.goto("http://localhost:8502/_stcore/health", timeout=15000)
            health = page.inner_text("body", timeout=5000)
            if health == "ok":
                results.append(("Streamlit health", "PASS", None))
                print(f"  PASS - health={health}")
            else:
                results.append(("Streamlit health", "FAIL", f"health={health}"))
                print(f"  FAIL - health={health}")
        except Exception as e:
            results.append(("Streamlit health", "FAIL", str(e)))
            print(f"  FAIL - {e}")
        
        # Test 2: Dashboard loads without DuplicateElementId
        print("\nTest 2: Dashboard loads without DuplicateElementId")
        try:
            page.goto("http://localhost:8502", timeout=30000, wait_until="domcontentloaded")
            print("  Page loaded, waiting for render...")
            time.sleep(15)
            
            page.screenshot(path="runtime/dashboard_test.png", full_page=True)
            print("  Screenshot saved")
            
            body = page.content()
            has_dup_error = "DuplicateElementId" in body or "StreamlitDuplicateElementId" in body
            dup_page_errors = [e for e in page_errors if "Duplicate" in e or "duplicate" in e.lower()]
            
            if has_dup_error or dup_page_errors:
                results.append(("Dashboard no DuplicateElementId", "FAIL", 
                    f"HTML: {has_dup_error}, page_errors: {dup_page_errors[:2]}"))
                print(f"  FAIL - DuplicateElementId detected!")
            else:
                results.append(("Dashboard no DuplicateElementId", "PASS", None))
                print(f"  PASS - No DuplicateElementId error")
        except Exception as e:
            results.append(("Dashboard no DuplicateElementId", "FAIL", str(e)))
            print(f"  FAIL - {e}")
        
        # Test 3: No Streamlit exception elements visible
        print("\nTest 3: No Streamlit exception elements")
        try:
            selector = '[data-testid="stException"]'
            exc_count = page.locator(selector).count()
            if exc_count > 0:
                err_texts = []
                for i in range(min(exc_count, 3)):
                    try:
                        err_texts.append(page.locator(selector).nth(i).inner_text(timeout=3000)[:200])
                    except:
                        err_texts.append("(could not read)")
                results.append(("No stException elements", "FAIL", f"Found {exc_count}: {err_texts}"))
                print(f"  FAIL - {exc_count} exception elements found")
            else:
                results.append(("No stException elements", "PASS", None))
                print(f"  PASS - No exception elements")
        except Exception as e:
            results.append(("No stException elements", "FAIL", str(e)))
            print(f"  FAIL - {e}")
        
        # Test 4: Tabs count
        print("\nTest 4: Dashboard tabs count")
        try:
            tab_selector = '[data-testid="stTabs"] button'
            tab_count = page.locator(tab_selector).count()
            tab_names = []
            for i in range(tab_count):
                try:
                    tab_names.append(page.locator(tab_selector).nth(i).inner_text(timeout=3000))
                except:
                    tab_names.append("(unknown)")
            print(f"  Found {tab_count} tabs: {tab_names}")
            if tab_count >= 9:
                results.append(("Dashboard tabs count", "PASS", f"{tab_count} tabs"))
            else:
                results.append(("Dashboard tabs count", "FAIL", f"Expected >=9, got {tab_count}: {tab_names}"))
        except Exception as e:
            results.append(("Dashboard tabs count", "FAIL", str(e)))
            print(f"  FAIL - {e}")
        
        page.screenshot(path="runtime/dashboard_final.png", full_page=True)
        print("\nFinal screenshot saved")
        browser.close()
    
    # Summary
    print("\n" + "=" * 60)
    print("BROWSER E2E TEST SUMMARY")
    print("=" * 60)
    passed = sum(1 for _, s, _ in results if s == "PASS")
    failed = sum(1 for _, s, _ in results if s == "FAIL")
    
    for name, status, detail in results:
        icon = "PASS" if status == "PASS" else "FAIL"
        print(f"  [{icon}] {name}" + (f" - {detail}" if detail else ""))
    
    print(f"\nTotal: {len(results)} | Passed: {passed} | Failed: {failed}")
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
