# A股主板实盘数据闭环 — 架构 Review R2 整改报告

> 角色：Developer Agent
> 日期：2026-06-11
> Review 报告：`docs/review/2026-06-11-a-share-live-data-closed-loop-architecture-review-r2.md`
> 遵守规范：`AGENT_DEVELOPMENT_PIPELINE.md` §11 阶段 5

---

## 1. 整改范围

根据架构 Review R2 报告 §2 阻断性发现，本次整改覆盖以下项目：

| 发现 ID | 等级 | 描述 | 状态 |
|---|---|---|---|
| S2-1 | S2 | Factor Lab / Backtest 页面仍调用 legacy demo 端点，未接入 live closed-loop | **已修复** |
| S2-2 | S2 | LEVEL_3_AUTO 选项仍出现在 UI 和 API 中，违反需求文档 §7.3 禁止项 | **已修复** |

---

## 2. S2-1 修复详情：Factor Lab / Backtest 接入 live closed-loop

### 根因

1. `product_dashboard.py` 的 Factor Lab 页面调用 `/product/factors/compute`（legacy demo 端点），Backtest 页面调用 `/product/jobs/backtest/start`（legacy demo 端点）
2. 缺少 `/product/live-factors/compute` 和 `/product/live-backtests/run` 两个 API 路由

### 修复内容

**1. 新增 API 路由（`src/api/product_routes.py`）**：

- `POST /product/live-factors/compute`：基于实时日线数据计算技术因子
  - 参数：`symbols`, `start_date`, `end_date`, `factor_names`
  - 调用 `LiveFactorService.get_factor_summary()`
  - 返回 `factors` 列表 + `data_health` + `data_status`

- `POST /product/live-backtests/run`：基于实时日线数据运行快速回测
  - 参数：`symbols`, `start_date`, `end_date`
  - 调用 `LiveBacktestService.get_backtest_summary()`
  - 返回 `results` + `strategy` + `data_status` + `health`

**2. 更新 Dashboard（`src/ui_report/product_dashboard.py`）**：

- **Factor Lab 页面**：
  - 标题改为 "Factor Lab (Live)"
  - 添加 caption "Technical factors computed from live daily bars. No demo fallback."
  - 按钮调用 `/product/live-factors/compute`
  - 展示 `data_status` 和 fail-closed 状态
  - 展示 SMA/RSI/MACD/BOLL 因子值
  - 添加 Data Health expander

- **Backtest 页面**：
  - 标题改为 "Backtest (Live)"
  - 添加 caption "Quick backtest on live daily bars. No demo fallback."
  - 按钮调用 `/product/live-backtests/run`
  - 展示 `data_status` 和 fail-closed 状态
  - 展示 total_return/max_drawdown/sharpe/win_rate
  - 添加 Data Health expander
  - 移除 commission/stamp/slippage 参数（live backtest 使用默认值）

---

## 3. S2-2 修复详情：LEVEL_3_AUTO 全链路拒绝

### 根因

需求文档 §7.3 明确禁止 LEVEL_3_AUTO（自动下单），但 UI 和 API 仍允许选择该模式。

### 修复内容

**三层拒绝**：

1. **API 路由层（`src/api/product_routes.py`）**：
   - `POST /product/signal/draft` 检查 `trading_mode == "LEVEL_3_AUTO"` 时直接返回 `{"status": "rejected", "message": "LEVEL_3_AUTO is not available..."}`

2. **Orchestrator 层（`src/product_app/live_signal_orchestrator.py`）**：
   - `generate_signal_draft()` 开头检查 `trading_mode == "LEVEL_3_AUTO"` 时返回 rejected 信号
   - 不进入数据获取和健康评估流程

3. **UI 层（`src/ui_report/product_dashboard.py`）**：
   - Signal Draft 的 trading_mode 下拉框只包含 `LEVEL_1_SIGNAL_ONLY` 和 `LEVEL_2_HUMAN_CONFIRM`
   - 移除 `LEVEL_3_AUTO` 选项

---

## 4. 回归测试结果

### 新增测试（4 个）

```
tests/test_live_signal.py::TestSignalAPI::test_level3_auto_rejected_by_api PASSED
tests/test_live_signal.py::TestSignalAPI::test_live_factors_compute_endpoint PASSED
tests/test_live_signal.py::TestSignalAPI::test_live_backtests_run_endpoint PASSED
tests/test_live_signal.py::TestLevel3AutoBlocked::test_orchestrator_rejects_level3_auto PASSED
```

### 全量回归测试（544 个）

```
544 passed, 0 failed, 1 warning
```

### 静态检查

```
ruff check src/api/product_routes.py src/product_app/live_signal_orchestrator.py src/ui_report/product_dashboard.py
All checks passed!
```

---

## 5. 修改文件清单

| 文件 | 修改类型 | 说明 |
|---|---|---|
| `src/api/product_routes.py` | 修改 | 新增 2 个 live API 路由 + LEVEL_3_AUTO 拒绝 |
| `src/product_app/live_signal_orchestrator.py` | 修改 | LEVEL_3_AUTO 拒绝 |
| `src/ui_report/product_dashboard.py` | 修改 | Factor/Backtest 接入 live 端点 + 移除 LEVEL_3_AUTO |
| `tests/test_live_signal.py` | 修改 | 新增 4 个测试 |

---

## 6. 测试门禁重新评估

| 门禁条件 | 修复前 | 修复后 |
|---|---|---|
| Factor/Backtest 接入 live closed-loop | FAIL (legacy demo) | **PASS** |
| LEVEL_3_AUTO 全链路拒绝 | FAIL (可选) | **PASS** |
| 所有 MUST 功能通过 | PARTIAL | **PASS** |
| 无 S0/S1/S2 阻断缺陷 | FAIL (2 S2) | **PASS** |
| ruff 静态检查 | PASS | **PASS** |

---

## 7. 禁止项确认

- [x] 未启用真实自动下单
- [x] LEVEL_3_AUTO 全链路拒绝（API + Orchestrator + UI）
- [x] 未提交密钥、券商账号、Cookie、Token
- [x] 未绕过 Risk Agent 一票否决
- [x] 未将 Demo fallback 伪装成真实数据
- [x] is_demo 全链路 False
- [x] 数据失败 fail closed

---

## 8. 结论

**所有架构 Review R2 阻断性发现已修复，544 回归测试通过，ruff 检查通过。建议重新提交架构 Review。**
