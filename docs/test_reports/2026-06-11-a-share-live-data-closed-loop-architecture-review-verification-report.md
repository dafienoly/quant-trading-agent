# A股主板实盘数据闭环 — 架构 Review 修复验证报告

> 角色：Test Engineer Agent
> 日期：2026-06-11
> 架构 Review 报告：`docs/review/2026-06-11-a-share-live-data-closed-loop-architecture-review.md`
> 修复报告：`docs/dev_reports/2026-06-11-a-share-live-data-closed-loop-architecture-review-fix-report.md`
> 遵守规范：`AGENT_DEVELOPMENT_PIPELINE.md` §10 阶段 4

---

## 1. 验证范围

| 缺陷 ID | 等级 | 描述 | 验证结果 |
|---|---|---|---|
| S1 | 严重 | LiveSignalOrchestrator 未调用 get_realtime_quotes，行情数据缺失时信号未被阻断 | **PASS** |
| S2 | 重要 | 延迟合约断裂 — DataHealthGate 未收到 provider_delay | **PASS** |
| S2 | 重要 | Dashboard 缺少 Live Data 诊断 Tab | **PASS** |

---

## 2. S1 验证：实时行情接入信号编排 — PASS

### 代码审查

`live_signal_orchestrator.py:123-148`：

```python
# ── 1. 获取实时行情 ──────────────────────────────────────
data_service = self._get_data_service()
quotes_result = data_service.get_realtime_quotes(symbols, allow_demo=False)

# ── 6. 评估数据健康（使用真实行情结果）────────────────────
quotes_for_gate = {
    "data_status": quotes_result.get("data_status", "FAILED"),
    "provider_delay": quotes_result.get("data_delay_report", {}).get("max_delay_seconds"),
}
health_decision = self._health_gate.evaluate(
    quotes_result=quotes_for_gate,
    ...
)
```

关键修复点：
1. `get_realtime_quotes(symbols, allow_demo=False)` — 行情不允许 demo ✓
2. `quotes_for_gate` 传递给 DataHealthGate — 行情 FAILED → allow_signal=False ✓
3. `provider_delay` 从 `data_delay_report.max_delay_seconds` 提取 ✓
4. 信号 evidence 包含 `quotes_status` 和 `provider_chain.quotes` ✓

### 新增回归测试

| 测试 | 结果 | 验证内容 |
|---|---|---|
| `test_signal_blocked_when_quotes_failed_daily_ok` | PASS | 行情 FAILED 但日线/基本面 OK → 信号 blocked |
| `test_signal_blocked_when_quotes_delay_exceeds_threshold` | PASS | 延迟 200s 超过 LEVEL_1 阈值 120s → 信号 blocked, data_status=WARN |
| `test_signal_evidence_includes_quotes_provider_chain` | PASS | 信号 evidence 包含 quotes provider chain |

### API E2E 验证

```
POST /product/signal/draft?symbols=600000.SH&start_date=2025-06-01&end_date=2025-06-10
→ 200 OK, status=blocked, is_demo=False
```

**结论：S1 已正确修复。实时行情已接入信号编排，行情失败时信号被阻断。**

---

## 3. S2 验证：延迟合约对齐 — PASS

### 代码审查

`live_signal_orchestrator.py:147`：

```python
"provider_delay": quotes_result.get("data_delay_report", {}).get("max_delay_seconds"),
```

`DataHealthGate.evaluate()` 接收 `quotes_result["provider_delay"]` 并与模式阈值比较：
- LEVEL_1_SIGNAL_ONLY: 120s
- LEVEL_2_SEMI_AUTO: 30s
- LEVEL_3_FULL_AUTO: 5s

### 回归测试

`test_signal_blocked_when_quotes_delay_exceeds_threshold`：延迟 200s → blocked, data_status=WARN ✓

**结论：S2 延迟合约已正确对齐。**

---

## 4. S2 验证：Dashboard Live Data Tab — PASS

### 代码审查

`product_dashboard.py` 新增 `render_live_data()` 函数，包含 4 个子面板：
1. Provider Diagnosis — 调用 `/product/live-data/diagnose`
2. Live Quotes — 调用 `/product/live-data/quotes`
3. Signal Draft — 调用 `/product/signal/draft`
4. Research Context — 调用 `/product/live-data/research-context`

Tab 注册在 `main()` 函数中，位于 "System" 之后。

### 浏览器 E2E 验证

```
Tabs (20): ['System', 'Live Data', 'Realtime Market', 'Watchlist', ...]

Live Data tab 内容检查:
  PASS - Provider Diagnosis: found
  PASS - Live Quotes: found
  PASS - Signal Draft: found
  PASS - Research Context: found
  No page errors on Live Data tab
```

**结论：S2 Dashboard Live Data Tab 已正确实现。**

---

## 5. 全量测试结果

### 自动化测试

```
538 passed, 2 failed, 1 warning

失败项（预存问题，非本次引入）:
- test_product_market_data.py::test_fetch_product_quotes_records_feedback_on_provider_failure
- test_product_realtime_api.py::test_product_quotes_endpoint_falls_back_to_demo_and_records_feedback
```

### 静态检查

```
ruff check src/product_app/ src/data_gateway/ src/api/ src/ui_report/
2 errors in dashboard.py (未使用 import，非本次修改文件)
本次修改文件: All checks passed
```

### API 端点 E2E（14 个端点）

```
14/14 PASS (100%)

关键端点:
- /product/signal/draft → 200 OK, status=blocked, is_demo=False
- /product/live-data/providers → 200 OK
- /product/live-data/diagnose → 200 OK
- /product/live-data/research-context → 200 OK
```

### 浏览器 E2E

```
4/4 PASS
- Streamlit health: PASS
- 无 DuplicateElementId: PASS
- 无 stException 元素: PASS
- Dashboard tabs (20): PASS

Live Data tab 内容检查: 4/4 PASS
- Provider Diagnosis: found
- Live Quotes: found
- Signal Draft: found
- Research Context: found
- 无页面错误
```

### 安全与风控回归

| 检查项 | 结果 |
|---|---|
| is_demo 全链路 False | PASS |
| 数据失败 fail closed | PASS — quotes FAILED → blocked |
| 无硬编码 API Key | PASS |
| 创业板/科创板/ST 拒绝 | PASS |
| Risk Agent 一票否决未绕过 | PASS |
| 无真实自动下单 | PASS |
| Demo 数据不进入信号链路 | PASS |
| 财务缺失保留 NaN | PASS |

---

## 6. 测试门禁评估

| 门禁条件 | 结果 |
|---|---|
| 所有 MUST 功能通过 | **PASS** |
| 无 S0/S1/S2 阻断缺陷 | **PASS** — 0 个阻断缺陷 |
| 核心交易安全回归通过 | **PASS** |
| 前端改动有浏览器渲染验证 | **PASS** — 4/4 E2E + Live Data tab 4/4 |
| API 改动有 HTTP 级验证 | **PASS** — 14/14 通过 |
| 数据源改动有 mock 和异常路径测试 | **PASS** — 3 个新回归测试 |
| ruff 静态检查 | **PASS**（本次修改文件无错误） |

---

## 7. 剩余风险（非阻断）

1. **2 个预存测试失败**（S3）：`test_product_market_data.py` 和 `test_product_realtime_api.py` 因 `is_trading_hours()` mock 不完整，非本次引入
2. **`dashboard.py` 未使用 import**（S4）：2 个 ruff F401 错误，非本次修改文件
3. **`/product/live-data/quotes` 非交易时段超时**：东方财富 API 响应慢，建议增加超时降级
4. **`/product/live-data/diagnose` 非交易时段耗时**：需 60s 超时，建议异步化

---

## 8. 结论

**所有架构 Review 缺陷（S1/S2）已修复，538 回归测试通过，API E2E 14/14 通过，浏览器 E2E 4/4 通过 + Live Data tab 4/4 内容检查通过，安全与风控 8/8 通过。**

**架构 Review 修复验证通过，建议进入下一阶段。**
