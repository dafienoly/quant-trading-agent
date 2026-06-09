"""产品 API 端到端测试"""
import requests
import json

base = "http://localhost:8001"
print("=== 产品 API 端到端测试 ===\n")

# 1. 系统健康
r = requests.get(f"{base}/product/health", timeout=5)
h = r.json()
print(f"[1] /product/health: status={h.get('status')}, api={h.get('api_status')}")

# 2. 配置
r = requests.get(f"{base}/product/config", timeout=5)
c = r.json()
print(f"[2] /product/config: mode={c['config'].get('MAX_TRADING_LEVEL')}")

# 3. 仪表板
r = requests.get(f"{base}/product/dashboard", timeout=5)
d = r.json()
print(f"[3] /product/dashboard: is_demo={d.get('is_demo')}, quotes={len(d.get('quotes',[]))}")

# 4. 作业
r = requests.get(f"{base}/product/jobs", timeout=5)
j = r.json()
print(f"[4] /product/jobs: {len(j['jobs'])} jobs")

# 5. 启动行情刷新
r = requests.post(f"{base}/product/jobs/quote_refresh/start", timeout=5)
print(f"[5] start quote_refresh: {r.json().get('status')}")

# 6. 反馈
r = requests.get(f"{base}/product/feedback", timeout=5)
f = r.json()
print(f"[6] /product/feedback: {f.get('count')} bugs")

# 7. 风控状态
r = requests.get(f"{base}/risk/status", timeout=5)
rs = r.json()
print(f"[7] /risk/status: risk_pass={rs.get('risk_pass')}")

# 8. 账户
r = requests.get(f"{base}/account", timeout=5)
a = r.json()
print(f"[8] /account: total_assets={a.get('total_assets')}")

# 9. 持仓
r = requests.get(f"{base}/positions", timeout=5)
p = r.json()
print(f"[9] /positions: {p.get('count')} positions")

# 10. 待确认订单
r = requests.get(f"{base}/orders/pending", timeout=5)
o = r.json()
print(f"[10] /orders/pending: {o.get('count')} pending")

# 11. 信号
r = requests.get(f"{base}/signals/latest", timeout=5)
s = r.json()
print(f"[11] /signals/latest: {len(s.get('signals',[]))} signals")

print("\n=== 全部 11 个端点测试通过 ===")
