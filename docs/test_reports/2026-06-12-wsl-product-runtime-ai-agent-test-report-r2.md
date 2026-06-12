# WSL Product Runtime & AI Agent — Test Report R2

日期：2026-06-12
角色：Test Engineer Agent
分支：`feature/quant-factor-v1`

## 输入文档

| 文档 | 路径 |
|------|------|
| 需求 | `docs/requirements/2026-06-11-wsl-product-runtime-ai-agent-requirements.md` |
| 架构 | `docs/design/2026-06-11-wsl-product-runtime-ai-agent-architecture.md` |
| R1 修复开发报告 | `docs/dev_reports/2026-06-12-arch-review-fix-dev-report.md` |
| R2 架构审查 | `docs/review/2026-06-12-wsl-product-runtime-ai-agent-architecture-review-r2.md` |
| R2 修复开发报告 | `docs/dev_reports/2026-06-12-arch-review-r2-fix-dev-report.md` |
| R1 测试报告 | `docs/test_reports/2026-06-12-wsl-product-runtime-ai-agent-test-report.md` |

## 测试环境

- **操作系统:** Linux (WSL2) 6.6.87.2-microsoft-standard-WSL2
- **Python:** 3.13.5 — `.venv/bin/python`
- **openai:** v2.41.1（已安装）
- **playwright:** 未安装（预存问题）

## 测试范围

### 本轮重点

1. **S2: Output guard 大小写不敏感性修复验证**
   - 小写 `buy`/`sell` 拦截
   - 混合大小写拦截
   - 通用决策字段检查（`action`/`decision`/`recommendation`/`judgment`/`suggestion`）
   - 安全术语免误判（`buyback`, `seller concentration`）
   - 嵌套/列表/中文上下文场景

2. **S2: 边缘测试文件为已提交代码**（非临时文件）
   - 17 个边缘测试已直接加入 `tests/test_output_guard.py`（`TestOutputGuardEdgeCases` 类）
   - 所有 R2 审查中的假阴性实例均已覆盖

### 不测范围

- E2E API smoke（需要外部服务 :8001）
- Streamlit 浏览器渲染（需要 playwright）
- WSL shell 脚本 smoke
- 实时数据闭环回归（预存问题 `test_product_market_data.py`/`test_product_realtime_api.py`）

---

## R2 阻断项验证

### S2: Output guard 仍允许直接买卖建议 — **已修复**

**实现:**
1. BUY/SELL 正则添加 `re.IGNORECASE`：
   ```python
   re.compile(r'(?:\b|_)BUY(?:\b|_)', re.IGNORECASE)
   re.compile(r'(?:\b|_)SELL(?:\b|_)', re.IGNORECASE)
   ```
2. 新增 `_GENERIC_DECISION_KEYS = {"action", "decision", "recommendation", "judgment", "suggestion"}`
3. 新增 `_find_generic_decision_values()` 函数，捕获通用字段中的买卖值
4. 新增 `exempt_keys` 参数，避免系统元数据字段误判

**R2 审查精确实例验证（全部通过）:**

| 输入 | 期望 | 实际 | 拦截方式 |
|------|------|------|----------|
| `"you should buy this stock"` | blocked=True | blocked=True | 正则 BUY + IGNORECASE |
| `"you should sell this stock"` | blocked=True | blocked=True | 正则 SELL + IGNORECASE |
| `{"action": "buy"}` | blocked=True | blocked=True | 正则 BUY + IGNORECASE |
| `{"decision": "sell"}` | blocked=True | blocked=True | 正则 SELL + IGNORECASE |
| `{"recommendation": "buy 600000.SH"}` | blocked=True | blocked=True | 正则 BUY + IGNORECASE |
| `{"suggestion": "sell signal detected"}` | blocked=True | blocked=True | 正则 SELL + IGNORECASE |
| `{"reason": "Buy this stock now"}`（混合大小写） | blocked=True | blocked=True | 正则 BUY + IGNORECASE |
| `{"analysis": {"verdict": "buy"}}`（嵌套） | blocked=True | blocked=True | 正则 BUY + IGNORECASE |

**安全术语未误判（全部通过）:**

| 输入 | blocked |
|------|---------|
| `"Company announced a buyback program"` | False |
| `"seller concentration is high"` | False |
| `{"hypotheses": [{"name": "buyback_yield_factor"}]}` | False |

**测试覆盖:** `test_output_guard.py::TestOutputGuardEdgeCases` — 17 个边缘测试

**结果: PASS**

### S2: 测试报告引用不存在的文件 — **已修复**

边缘测试已直接写入 `tests/test_output_guard.py`，为已提交代码（`TestOutputGuardEdgeCases` 类，248-361 行）。不再依赖临时文件。

**结果: PASS**

---

## 需求覆盖矩阵

| ID | 需求 | 覆盖 | 状态 |
|----|------|------|------|
| F-001 | AkTools 兼容 | `test_aktools_compat_app.py` | PASS |
| F-002/F-003/F-004 | WSL 启动/停止/重启 | `test_product_process_manager.py` | PASS |
| F-005 | 路径 `/` 风格 | `.env.example`, `summarize_feedback_bugs.py` | PASS |
| F-006 | DeepSeek 默认模型 deepseek-v4-flash | `test_model_router.py` | PASS |
| F-007 | Model router 配置 + 缺 key 降级 | `test_model_router.py` (7 tests) | PASS |
| F-008 | AI 因子挖掘 + output guard | `test_output_guard.py` + `test_ai_research_agents.py` | PASS |
| F-009 | AI 研究推荐 + output guard | `test_output_guard.py` + `test_ai_research_agents.py` | PASS |
| F-010 | AI 信号解释（真实信号） | `test_product_routes.py` (3 tests) | PASS |
| F-011 | BugFix 提案校验 | `test_bug_auto_fix.py` | PASS |
| F-012 | Feedback Bug 分类 | `test_feedback_bug_summary.py` | PASS |
| F-013 | Dashboard 运行状态 + LLM 状态 | `test_product_routes.py` (4 tests) | PASS |

---

## 测试命令与结果

### 静态检查

```bash
.venv/bin/python -m ruff check src/agent_orchestrator/output_guard.py \
  src/api/product_routes.py tests/test_output_guard.py tests/test_product_routes.py
# 结果: PASS

.venv/bin/python -m py_compile src/agent_orchestrator/output_guard.py src/api/product_routes.py
# 结果: PASS
```

### 开发者测试套

```bash
.venv/bin/python -m pytest tests/test_output_guard.py tests/test_model_router.py \
  tests/test_ai_research_agents.py tests/test_product_routes.py \
  tests/test_bug_auto_fix.py tests/test_live_signal.py \
  -q --basetemp=runtime/pytest-tmp-arch-r2
```
**结果: 105 passed, 1 warning**（StarletteDeprecationWarning — 预存）

| 测试文件 | 数量 |
|----------|------|
| `test_output_guard.py` | 40（23 original + 17 edge case） |
| `test_model_router.py` | 7 |
| `test_ai_research_agents.py` | 2 |
| `test_product_routes.py` | 8 |
| `test_bug_auto_fix.py` | 27 |
| `test_live_signal.py` | 21 |

### 需求验收回归

```bash
.venv/bin/python -m pytest tests/test_bug_auto_fix.py tests/test_live_signal.py \
  tests/test_live_data_service.py tests/test_product_dashboard_source.py \
  tests/test_aktools_compat_app.py tests/test_product_process_manager.py \
  -q --basetemp=runtime/pytest-tmp-arch-r2-broad
```
**结果: 78 passed, 1 warning**

### 全量回归（排除预存失败）

```bash
.venv/bin/python -m pytest tests --ignore=tests/test_product_api_e2e.py \
  --ignore=tests/test_browser_simple.py -q --tb=short \
  --basetemp=runtime/pytest-tmp-arch-r2-full
```
**结果: 645 passed, 2 failed, 1 warning**

- 645 passed
- 2 failed（**预存，非本次修改引入**）：
  - `test_product_market_data.py::test_fetch_product_quotes_records_feedback_on_provider_failure` — demo fallback feedback 记录问题
  - `test_product_realtime_api.py::test_product_quotes_endpoint_falls_back_to_demo_and_records_feedback` — 同上
- 1 warning（StarletteDeprecationWarning — 预存）

### R2 假阴性精确实例验证

```python
# 11 个精确实例全部 PASS
# 参见上文 R2 阻断项验证章节
```

---

## 缺陷列表

| ID | 严重度 | 描述 | 状态 |
|----|--------|------|------|
| D-001 | S4 | CJK 字符环绕 BUY/SELL 时 `\b` 边界不匹配（Python Unicode word char 行为） | 已知剩余风险 |
| D-002 | S4 | `ai_signal_explain` 路由未对 orchestrator 调用加 try/except | 已知剩余风险 |
| D-003 | S4 | `test_product_market_data` / `test_product_realtime_api` 存在 pre-existing failure | 预存问题 |

### D-001 详情

`\b` 在 Python 3 Unicode 模式下将 CJK 字符视为 `\w`，因此 `BUY` 前后为中文时不触发 `\b` 边界。本次 R2 修复了字母大小写的问题，但 CJK 边界问题仍需另一种模式（如无边界匹配或 `re.ASCII`）。

防御纵深：
- Agent 层守卫 + API 层守卫双重拦截
- 通用决策字段检查拦截 `action`/`decision` 等
- `_FORBIDDEN_KEYS` 拦截 `trade_decision`/`order_type` 等结构化字段

---

## 剩余风险

| 风险 | 描述 | 缓解措施 |
|------|------|----------|
| Output guard 假阴性 | CJK 环绕的 BUY/SELL 不触发 `\b` | 多层防御（正则 + 通用字段 + 禁止键） |
| Output guard 假阳性 | 合法研究内容含 "sell" 被误拦 | 返回 `blocked_by_guard` + `block_reasons`，可调试调优 |
| WSL smoke 缺口 | 未在本 session 运行 `scripts/start.sh` | 路由变更已通过 TestClient 覆盖 |
| 预存依赖缺口 | playwright 未安装 | 非本次引入 |

## 安全确认

- [x] 默认不启用真实自动交易（`ENABLE_LIVE_TRADING=false`）
- [x] Risk Agent 一票否决未被绕过（未修改 `risk_engine/`）
- [x] 未提交密钥
- [x] LLM 不能直接决定买卖 — output guard 大小写不敏感 + 通用决策字段拦截
- [x] 信号解释仅对已有信号工作（缺失返回 404）
- [x] 缺少 openai 包正常降级（unavailable 状态）
- [x] 股票池过滤器未被绕过
- [x] 数据 fail-closed 未被绕过
- [x] 未启用真实交易能力

## 最终结论

**PASS**

R2 架构审查的 2 个 S2 阻断项均已修复并验证通过：

1. **大小写不敏感 BUY/SELL 检测** — `re.IGNORECASE` + `_GENERIC_DECISION_KEYS` 检查，覆盖小写、混合大小写、通用字段、嵌套结构。R2 列出的 8 个假阴性例全部拦截，3 个安全术语全部放行。
2. **边缘测试文件已提交** — 17 个边缘测试直接写入 `tests/test_output_guard.py`，不再依赖临时文件。

测试证据：
- 开发者测试套：105 passed
- 需求验收回归：78 passed
- 全量回归：645 passed（2 个预存失败，非本次引入）
- R2 精确实例验证：11/11 PASS
- 静态检查：全部通过
