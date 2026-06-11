# A股主板实盘数据闭环 — 架构 Review 整改报告

> 角色：Developer Agent
> 日期：2026-06-11
> Review 报告：`docs/review/2026-06-11-a-share-live-data-closed-loop-architecture-review.md`
> 遵守规范：`AGENT_DEVELOPMENT_PIPELINE.md` §11 阶段 5

---

## 1. 整改范围

根据架构 Review 报告 §2 阻断性发现，本次整改覆盖以下项目：

| 发现 ID | 等级 | 描述 | 状态 |
|---|---|---|---|
| S1 | S1 | LiveSignalOrchestrator 绕过实时行情健康检查，行情失败时仍可生成信号草稿 | **已修复** |
| S2 | S2 | Dashboard 仍使用 legacy/demo 路径，未接入 live closed-loop 端点 | **已修复** |
| S2 | S2 | 数据延迟门控未与 LiveDataService quote 结果结构对齐 | **已修复** |

---

## 2. S1 修复详情：LiveSignalOrchestrator 必须调用 get_realtime_quotes

### 根因

`LiveSignalOrchestrator.generate_signal_draft()` 只调用 `get_daily_bars()` 和 `get_fundamentals()`，然后在 `DataHealthGate.evaluate()` 中硬编码 `quotes_result={"data_status": "OK"}`。当实时行情 provider 不可用或返回异常数据时，信号草稿仍然可以生成，违反了 fail-closed 核心承诺。

### 修复内容

**`src/product_app/live_signal_orchestrator.py`**：

1. 在 `generate_signal_draft()` 中新增步骤 1：调用 `data_service.get_realtime_quotes(symbols, allow_demo=False)`
2. 从 `quotes_result` 提取 `data_status` 和 `provider_delay`（从 `data_delay_report.max_delay_seconds`），传递给 `DataHealthGate.evaluate()`
3. 信号证据（evidence）中新增 `quotes` provider chain、`quotes_status`、`delay_evidence`、`feedback_bug_id`
4. 当 `quotes_result.data_status=FAILED` 时，`DataHealthGate` 正确阻断信号

### 回归测试

新增 3 个测试：

- `test_signal_blocked_when_quotes_failed_daily_ok`：quotes FAILED + daily/fundamentals OK → blocked
- `test_signal_blocked_when_quotes_delay_exceeds_threshold`：延迟 200s 超过 LEVEL_1 阈值 120s → blocked
- `test_signal_evidence_includes_quotes_provider_chain`：信号证据包含 quotes provider chain

---

## 3. S2 修复详情：Dashboard 接入 live closed-loop 端点

### 根因

`product_dashboard.py` 的 Market 页面仍使用 AkShare/AkTools provider 选择 + demo fallback，Factor 页面调用 `/product/factors/compute`（demo），Backtest 页面调用 `/product/jobs/backtest/start`（demo），Signal 页面从 dashboard 读取 demo signals。没有接入 `/product/live-data/*` 和 `/product/signal/draft` 端点。

### 修复内容

**`src/ui_report/product_dashboard.py`**：

1. 新增 `render_live_data()` 函数，包含以下区域：
   - **Provider Diagnosis**：调用 `/product/live-data/diagnose`
   - **Provider Status**：展示 `/product/live-data/providers` 返回的 provider 健康状态
   - **Realtime Quotes (Live)**：调用 `/product/live-data/quotes`，展示 `data_status` 和 fail-closed 状态
   - **Signal Draft (Live)**：调用 `/product/signal/draft`，展示 blocked/draft 状态和数据健康证据
   - **Research Context (Live)**：调用 `/product/live-data/research-context`，展示完整数据健康决策
2. 在 `main()` 的 tabs 中新增 "Live Data" tab（位于 System 之后）
3. Live Data 页面默认真实数据，不使用 demo fallback
4. 数据失败时显示 `danger` banner，明确标注 "Signal generation is BLOCKED"

---

## 4. S2 修复详情：延迟契约对齐

### 根因

`DataHealthGate.evaluate()` 读取 `quotes_result.provider_delay`，但 `LiveDataService.get_realtime_quotes()` 返回的延迟数据在 `data_delay_report.max_delay_seconds`。由于 `LiveSignalOrchestrator` 之前硬编码 `quotes_result={"data_status": "OK"}`，延迟阈值从未被应用。

### 修复内容

1. **`src/product_app/live_signal_orchestrator.py`**：从 `quotes_result` 提取 `provider_delay` 映射到 `DataHealthGate` 期望的格式：
   ```python
   quotes_for_gate = {
       "data_status": quotes_result.get("data_status", "FAILED"),
       "provider_delay": quotes_result.get("data_delay_report", {}).get("max_delay_seconds"),
   }
   ```

2. **`src/product_app/live_data_service.py`**：`build_research_context()` 同样修复：
   - 新增 `get_realtime_quotes()` 调用
   - 映射 `provider_delay` 从 `data_delay_report.max_delay_seconds`
   - 返回结构新增 `quotes` 相关字段（quotes 数据、provider chain、delay report 等）

---

## 5. 回归测试结果

### 新增功能测试（129 个）

```
tests/test_live_data_mapper.py   — 51 PASSED
tests/test_live_data_service.py  — 21 PASSED
tests/test_stock_pool_service.py — 19 PASSED
tests/test_live_signal.py        — 17 PASSED  (+3 新增)
tests/test_search_evidence.py    — 21 PASSED

合计: 129 passed, 0 failed
```

### 全量回归测试（540 个）

```
538 passed, 2 failed, 1 warning
```

2 个失败为预存 BUG-003（`test_product_market_data.py`、`test_product_realtime_api.py`），非本次引入。

### 静态检查

```
ruff check src/product_app/live_signal_orchestrator.py src/product_app/live_data_service.py src/ui_report/product_dashboard.py
All checks passed!
```

---

## 6. 修改文件清单

| 文件 | 修改类型 | 说明 |
|---|---|---|
| `src/product_app/live_signal_orchestrator.py` | 修改 | S1: 新增 get_realtime_quotes 调用，映射 provider_delay，更新 evidence |
| `src/product_app/live_data_service.py` | 修改 | S2: build_research_context 新增 quotes 调用和延迟映射 |
| `src/ui_report/product_dashboard.py` | 修改 | S2: 新增 Live Data tab，接入 live closed-loop 端点 |
| `tests/test_live_signal.py` | 修改 | S1: 新增 3 个回归测试，更新 mock |
| `tests/test_live_data_service.py` | 修改 | 修复 _daily_hub → _daily_bars_hub，更新 build_research_context 测试 |

---

## 7. 测试门禁重新评估

| 门禁条件 | 修复前 | 修复后 |
|---|---|---|
| 实时行情失败时信号必须被阻断 | FAIL (绕过) | **PASS** |
| Dashboard 接入 live closed-loop 端点 | FAIL (legacy/demo) | **PASS** |
| 延迟阈值正确应用于信号路径 | FAIL (未接入) | **PASS** |
| 所有 MUST 功能通过 | PARTIAL | **PASS** |
| 无 S0/S1/S2 阻断缺陷 | FAIL (1 S1, 2 S2) | **PASS** |
| ruff 静态检查 | PASS | **PASS** |

---

## 8. 禁止项确认

- [x] 未启用真实自动下单
- [x] 未提交密钥、券商账号、Cookie、Token
- [x] 未绕过 Risk Agent 一票否决
- [x] 未将 Demo fallback 伪装成真实数据
- [x] 未放宽需求、风控、执行、数据契约
- [x] is_demo 全链路 False
- [x] 数据失败 fail closed

---

## 9. 结论

**所有架构 Review 阻断性发现已修复，538 回归测试通过，ruff 检查通过。建议重新提交架构 Review。**
