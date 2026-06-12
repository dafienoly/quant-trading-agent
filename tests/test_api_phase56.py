"""API endpoint test for Phase 5.6 review"""
import requests
import json
import time

def main():
    base = "http://localhost:8099"
    
    print("=== Phase 5.6 API Endpoint Tests ===")
    
    # 1. Health
    r = requests.get(f"{base}/product/health", timeout=10)
    data = r.json()
    print(f"/product/health: {r.status_code} - status={data.get('status')}")
    
    # 2. Dashboard
    r = requests.get(f"{base}/product/dashboard", timeout=15)
    data = r.json()
    print(f"/product/dashboard: {r.status_code} - quotes={len(data.get('quotes', []))}, positions={len(data.get('positions', []))}")
    
    # 3. Config
    r = requests.get(f"{base}/product/config", timeout=10)
    data = r.json()
    print(f"/product/config: {r.status_code} - keys={len(data.get('config', {}))}")
    
    # 4. Feedback list
    r = requests.get(f"{base}/product/feedback", timeout=10)
    data = r.json()
    print(f"/product/feedback: {r.status_code} - bugs={data.get('count', 0)}")
    
    # 5. Create bug
    r = requests.post(f"{base}/product/feedback", 
                     json={"component": "audit_test", "message": "Phase 5.6 review test", "severity": "low"},
                     timeout=10)
    bug_id = r.json().get("bug_id")
    print(f"Create bug: {r.status_code} - {bug_id}")
    
    # 6. Get analysis
    r = requests.get(f"{base}/product/feedback/{bug_id}/analysis", timeout=10)
    analysis = r.json()
    ws = analysis.get("workflow_status", {})
    print(f"/analysis: {r.status_code} - status={ws.get('status')}, has_analysis={ws.get('has_analysis')}")
    
    # 7. Get fix-status
    r = requests.get(f"{base}/product/feedback/{bug_id}/fix-status", timeout=10)
    fs = r.json().get("fix_status", {})
    print(f"/fix-status: {r.status_code} - status={fs.get('status')}")
    
    # 8. Jobs
    r = requests.get(f"{base}/product/jobs", timeout=10)
    jobs = r.json().get("jobs", [])
    bug_job = next((j for j in jobs if j.get("name") == "bug_fix_agent"), None)
    print(f"/jobs: {r.status_code} - bug_fix_agent state={bug_job.get('state') if bug_job else 'NOT FOUND'}")
    
    # 9. Start bug_fix_agent
    r = requests.post(f"{base}/product/jobs/bug_fix_agent/start", timeout=10)
    print(f"/jobs/bug_fix_agent/start: {r.status_code} - {r.json().get('status')}")
    
    time.sleep(3)
    
    # 10. Check job after start
    r = requests.get(f"{base}/product/jobs", timeout=10)
    jobs = r.json().get("jobs", [])
    bug_job = next((j for j in jobs if j.get("name") == "bug_fix_agent"), None)
    if bug_job:
        print(f"After start: bug_fix_agent state={bug_job.get('state')}, last_result={bug_job.get('last_result')}")
    
    # 11. M1 State Machine Test - check if bug transitions properly
    print("\n=== M1 State Machine Test ===")
    r = requests.get(f"{base}/product/feedback", timeout=10)
    bugs = r.json().get("bugs", [])
    for bug in bugs:
        if bug.get("bug_id") == bug_id:
            print(f"Bug {bug_id}: status={bug.get('status')}")
            break
    
    print("\nAll API tests complete!")

if __name__ == "__main__":
    main()
