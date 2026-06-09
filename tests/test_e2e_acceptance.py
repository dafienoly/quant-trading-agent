"""Phase 5.5 产品交付端到端验收测试

验证所有产品功能端到端可用：
1. FastAPI 产品端点 (11个)
2. Streamlit 产品面板 (9个Tab)
3. 服务管理器
4. 健康检查
5. 配置中心
6. 反馈系统
7. Demo 数据

此文件不使用 pytest test_ 前缀，仅通过 __main__ 运行。
"""
import json
import os
import sys
import time
import traceback

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import requests

BASE_API = "http://localhost:8001"
BASE_UI = "http://localhost:8501"
SCREENSHOT_DIR = "screenshots"

PASSED = 0
FAILED = 0
ERRORS = []


def check(name, condition, detail=""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  [PASS] {name}")
    else:
        FAILED += 1
        msg = f"  [FAIL] {name} — {detail}"
        print(msg)
        ERRORS.append(msg)


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ============================================================
# 1. FastAPI 产品端点测试
# ============================================================
def verify_api_endpoints():
    section("1. FastAPI 产品端点测试")

    # 1.1 系统健康
    try:
        r = requests.get(f"{BASE_API}/product/health", timeout=5)
        check("/product/health 返回200", r.status_code == 200, f"status={r.status_code}")
        if r.status_code == 200:
            data = r.json()
            check("健康状态为ok", data.get("status") == "ok", f"status={data.get('status')}")
            check("包含api_status", "api_status" in data, f"keys={list(data.keys())}")
            check("包含data_source状态", "data_source" in data, f"keys={list(data.keys())}")
            check("包含is_demo标记", "is_demo" in data, f"keys={list(data.keys())}")
    except Exception as e:
        check("/product/health", False, str(e))

    # 1.2 配置
    try:
        r = requests.get(f"{BASE_API}/product/config", timeout=5)
        check("/product/config 返回200", r.status_code == 200, f"status={r.status_code}")
        if r.status_code == 200:
            data = r.json()
            config = data.get("config", {})
            check("配置包含MAX_TRADING_LEVEL", "MAX_TRADING_LEVEL" in config, f"keys={list(config.keys())[:5]}")
            check("交易级别为LEVEL_1_SIGNAL_ONLY",
                 config.get("MAX_TRADING_LEVEL") == "LEVEL_1_SIGNAL_ONLY",
                 f"level={config.get('MAX_TRADING_LEVEL')}")
    except Exception as e:
        check("/product/config", False, str(e))

    # 1.3 仪表板
    try:
        r = requests.get(f"{BASE_API}/product/dashboard", timeout=5)
        check("/product/dashboard 返回200", r.status_code == 200, f"status={r.status_code}")
        if r.status_code == 200:
            data = r.json()
            check("仪表板包含is_demo字段", "is_demo" in data, f"keys={list(data.keys())}")
            check("仪表板包含quotes数据", "quotes" in data, f"keys={list(data.keys())}")
            check("Demo模式返回行情数据", len(data.get("quotes", [])) > 0, f"quotes={len(data.get('quotes', []))}")
    except Exception as e:
        check("/product/dashboard", False, str(e))

    # 1.4 作业管理
    try:
        r = requests.get(f"{BASE_API}/product/jobs", timeout=5)
        check("/product/jobs 返回200", r.status_code == 200, f"status={r.status_code}")
        if r.status_code == 200:
            data = r.json()
            jobs = data.get("jobs", [])
            check("作业列表非空", len(jobs) > 0, f"jobs={len(jobs)}")
            job_names = [j.get("name") for j in jobs]
            check("包含quote_refresh作业", "quote_refresh" in job_names, f"names={job_names}")
            check("包含signal_generation作业", "signal_generation" in job_names, f"names={job_names}")
            check("包含risk_snapshot作业", "risk_snapshot" in job_names, f"names={job_names}")
    except Exception as e:
        check("/product/jobs", False, str(e))

    # 1.5 启动作业
    try:
        r = requests.post(f"{BASE_API}/product/jobs/quote_refresh/start", timeout=5)
        check("启动quote_refresh返回200", r.status_code == 200, f"status={r.status_code}")
        if r.status_code == 200:
            data = r.json()
            check("启动状态为ok", data.get("status") == "ok", f"status={data.get('status')}")
    except Exception as e:
        check("启动quote_refresh", False, str(e))

    # 1.6 停止作业
    try:
        r = requests.post(f"{BASE_API}/product/jobs/quote_refresh/stop", timeout=5)
        check("停止quote_refresh返回200", r.status_code == 200, f"status={r.status_code}")
    except Exception as e:
        check("停止quote_refresh", False, str(e))

    # 1.7 反馈系统
    try:
        r = requests.get(f"{BASE_API}/product/feedback", timeout=5)
        check("/product/feedback 返回200", r.status_code == 200, f"status={r.status_code}")
        if r.status_code == 200:
            data = r.json()
            check("反馈包含count字段", "count" in data, f"keys={list(data.keys())}")
    except Exception as e:
        check("/product/feedback", False, str(e))

    # 1.8 因子计算
    try:
        r = requests.post(f"{BASE_API}/product/factors/compute?symbols=600519", timeout=10)
        check("/product/factors/compute 返回200", r.status_code == 200, f"status={r.status_code}")
    except Exception as e:
        check("/product/factors/compute", False, str(e))

    # 1.9 回测启动
    try:
        r = requests.post(f"{BASE_API}/product/jobs/backtest/start?start_date=20250101&end_date=20250301", timeout=10)
        check("/product/jobs/backtest/start 返回200", r.status_code == 200, f"status={r.status_code}")
    except Exception as e:
        check("/product/jobs/backtest/start", False, str(e))

    # 1.10 配置更新
    try:
        r = requests.post(f"{BASE_API}/product/config?key=TEST_KEY&value=test_value", timeout=5)
        check("POST /product/config 返回200", r.status_code == 200, f"status={r.status_code}")
    except Exception as e:
        check("POST /product/config", False, str(e))

    # 1.11 配置恢复默认
    try:
        r = requests.post(f"{BASE_API}/product/config/restore-defaults", timeout=5)
        check("/product/config/restore-defaults 返回200", r.status_code == 200, f"status={r.status_code}")
    except Exception as e:
        check("/product/config/restore-defaults", False, str(e))

    # 1.12 核心交易端点
    try:
        r = requests.get(f"{BASE_API}/health", timeout=5)
        check("/health 返回200", r.status_code == 200, f"status={r.status_code}")
    except Exception as e:
        check("/health", False, str(e))

    try:
        r = requests.get(f"{BASE_API}/risk/status", timeout=5)
        check("/risk/status 返回200", r.status_code == 200, f"status={r.status_code}")
        if r.status_code == 200:
            data = r.json()
            check("风控通过", data.get("risk_pass") == True, f"risk_pass={data.get('risk_pass')}")
    except Exception as e:
        check("/risk/status", False, str(e))

    try:
        r = requests.get(f"{BASE_API}/signals/latest", timeout=5)
        check("/signals/latest 返回200", r.status_code == 200, f"status={r.status_code}")
    except Exception as e:
        check("/signals/latest", False, str(e))


# ============================================================
# 2. Streamlit 产品面板测试
# ============================================================
def verify_streamlit_dashboard():
    section("2. Streamlit 产品面板测试")

    # 2.1 页面可访问
    try:
        r = requests.get(BASE_UI, timeout=10)
        check("Streamlit 面板可访问 (200)", r.status_code == 200, f"status={r.status_code}")
    except Exception as e:
        check("Streamlit 面板可访问", False, str(e))
        return

    # 2.2 页面内容验证
    try:
        content = r.text
        check("页面包含Streamlit标记", "streamlit" in content.lower(), "未找到streamlit标记")
        check("页面包含HTML结构", "<!doctype html" in content.lower() or "<html" in content.lower(), "未找到HTML结构")
    except Exception as e:
        check("页面内容验证", False, str(e))

    # 2.3 Streamlit API 端点
    try:
        r = requests.get(f"{BASE_UI}/_stcore/health", timeout=5)
        check("Streamlit health端点正常", r.status_code == 200, f"status={r.status_code}")
    except Exception as e:
        check("Streamlit health端点", False, str(e))


# ============================================================
# 3. Demo 数据验证
# ============================================================
def verify_demo_data():
    section("3. Demo 数据验证")

    try:
        from src.product_app.demo_data import (
            get_demo_quotes, get_demo_signals, get_demo_factors,
            get_demo_account, is_demo_mode
        )

        quotes = get_demo_quotes()
        check("Demo行情数据非空", len(quotes) > 0, f"quotes={len(quotes)}")
        if quotes:
            q = quotes[0]
            q_dict = q.model_dump() if hasattr(q, 'model_dump') else q
            check("行情包含symbol", "symbol" in q_dict, f"keys={list(q_dict.keys())}")
            check("行情包含last_price", "last_price" in q_dict, f"keys={list(q_dict.keys())}")

        signals = get_demo_signals()
        check("Demo信号数据非空", len(signals) > 0, f"signals={len(signals)}")

        factors = get_demo_factors()
        check("Demo因子数据非空", len(factors) > 0, f"factors={len(factors)}")

        account = get_demo_account()
        check("Demo账户数据非空", account is not None, "account is None")
        if account:
            a_dict = account.model_dump() if hasattr(account, 'model_dump') else account
            check("账户包含total_assets", "total_assets" in a_dict, f"keys={list(a_dict.keys())}")

        demo = is_demo_mode()
        check("Demo模式检测正常", isinstance(demo, bool), f"is_demo_mode={demo}")
    except Exception as e:
        check("Demo数据模块", False, str(e))
        traceback.print_exc()


# ============================================================
# 4. 服务管理器验证
# ============================================================
def verify_service_manager():
    section("4. 服务管理器验证")

    try:
        from src.product_app.service_manager import get_service_manager

        sm = get_service_manager()
        check("ServiceManager实例化成功", sm is not None, "None")

        jobs = sm.list_jobs()
        check("作业列表非空", len(jobs) > 0, f"jobs={len(jobs)}")

        job_names = [j.get("name") for j in jobs]
        expected_jobs = ["quote_refresh", "watchlist_monitor", "signal_generation",
                        "risk_snapshot", "backtest", "feedback_compaction"]
        for name in expected_jobs:
            check(f"包含{name}作业", name in job_names, f"names={job_names}")

        # 测试作业状态查询
        status = sm.get_job_status("quote_refresh")
        check("查询作业状态成功", status is not None, "None")
    except Exception as e:
        check("ServiceManager", False, str(e))
        traceback.print_exc()


# ============================================================
# 5. 健康服务验证
# ============================================================
def verify_health_service():
    section("5. 健康服务验证")

    try:
        from src.product_app.health import get_health_service

        hs = get_health_service()
        check("HealthService实例化成功", hs is not None, "None")

        health = hs.get_system_health()
        check("系统健康检查返回数据", health is not None, "None")
        if health:
            check("包含overall_status", "overall_status" in health, f"keys={list(health.keys())}")
            check("包含components", "components" in health, f"keys={list(health.keys())}")
            if "components" in health:
                components = health.get("components", {})
                expected_components = ["api", "data_source", "risk_engine", "jobs", "storage", "feedback"]
                for comp in expected_components:
                    check(f"包含{comp}组件", comp in components, f"comps={list(components.keys())}")
    except Exception as e:
        check("HealthService", False, str(e))
        traceback.print_exc()


# ============================================================
# 6. 配置服务验证
# ============================================================
def verify_config_service():
    section("6. 配置服务验证")

    try:
        from src.product_app.config_service import get_config_service

        cs = get_config_service()
        check("ConfigService实例化成功", cs is not None, "None")

        config = cs.get_config()
        check("获取配置成功", config is not None, "None")
        if config:
            check("配置包含MAX_TRADING_LEVEL", "MAX_TRADING_LEVEL" in config, f"keys={list(config.keys())[:5]}")

        # 测试配置掩码 (get_config 默认 masked=True)
        masked = cs.get_config(masked=True)
        check("获取掩码配置成功", masked is not None, "None")

        # 测试配置更新
        result = cs.update_config("TEST_KEY", "test_value")
        check("更新配置成功", result, f"result={result}")

        # 测试配置验证
        validation = cs.validate_config()
        check("配置验证成功", validation is not None, f"validation={validation}")
    except Exception as e:
        check("ConfigService", False, str(e))
        traceback.print_exc()


# ============================================================
# 7. 反馈服务验证
# ============================================================
def verify_feedback_service():
    section("7. 反馈服务验证")

    try:
        from src.product_app.feedback import get_feedback_service

        fs = get_feedback_service()
        check("FeedbackService实例化成功", fs is not None, "None")

        bugs = fs.get_bug_index()
        check("Bug列表查询成功", isinstance(bugs, list), f"type={type(bugs)}")

        # 测试提交bug
        bug_id = fs.write_bug_report(
            component="test",
            title="E2E测试Bug",
            summary="端到端测试自动提交的Bug报告",
            severity="low",
        )
        check("提交Bug成功", bug_id is not None, f"bug_id={bug_id}")

        if bug_id:
            # 测试更新Bug状态
            result = fs.update_bug_status(bug_id, "triaged")
            check("更新Bug状态成功", result, f"result={result}")
    except Exception as e:
        check("FeedbackService", False, str(e))
        traceback.print_exc()


# ============================================================
# 8. 启动脚本验证
# ============================================================
def verify_scripts():
    section("8. 启动脚本验证")

    scripts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts")
    expected_scripts = ["bootstrap.py", "start_product.py", "stop_product.py"]

    for script in expected_scripts:
        path = os.path.join(scripts_dir, script)
        check(f"脚本{script}存在", os.path.exists(path), f"path={path}")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            check(f"{script}非空", len(content) > 100, f"len={len(content)}")


# ============================================================
# 9. 产品路由完整性验证
# ============================================================
def verify_product_routes():
    section("9. 产品路由完整性验证")

    try:
        r = requests.get(f"{BASE_API}/openapi.json", timeout=5)
        check("OpenAPI schema可访问", r.status_code == 200, f"status={r.status_code}")
        if r.status_code == 200:
            schema = r.json()
            paths = schema.get("paths", {})
            product_paths = [p for p in paths if p.startswith("/product")]
            check("产品路由数量>=10", len(product_paths) >= 10,
                 f"count={len(product_paths)}, paths={product_paths}")

            expected_routes = [
                "/product/health",
                "/product/dashboard",
                "/product/config",
                "/product/jobs",
                "/product/feedback",
            ]
            for route in expected_routes:
                check(f"路由{route}存在", route in paths, f"missing={route}")
    except Exception as e:
        check("产品路由验证", False, str(e))


# ============================================================
# 主测试入口
# ============================================================
if __name__ == "__main__":
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    print("=" * 60)
    print("  Phase 5.5 产品交付端到端验收测试")
    print("=" * 60)

    verify_api_endpoints()
    verify_streamlit_dashboard()
    verify_demo_data()
    verify_service_manager()
    verify_health_service()
    verify_config_service()
    verify_feedback_service()
    verify_scripts()
    verify_product_routes()

    print("\n" + "=" * 60)
    print(f"  测试结果: {PASSED} 通过, {FAILED} 失败")
    print("=" * 60)

    if ERRORS:
        print("\n失败项:")
        for err in ERRORS:
            print(err)

    sys.exit(0 if FAILED == 0 else 1)
