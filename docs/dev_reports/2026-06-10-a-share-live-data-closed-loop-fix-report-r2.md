# A股主板实盘数据闭环 — 整改报告（第二轮）

> 角色：BugFix Developer Agent
> 日期：2026-06-11
> 验证报告：`docs/test_reports/2026-06-10-a-share-live-data-closed-loop-fix-verification-report.md`
> 遵守规范：`AGENT_DEVELOPMENT_PIPELINE.md` §11 阶段 5

---

## 1. 整改范围

根据验证测试报告 §9 缺陷列表，本次整改覆盖以下项目：

| 缺陷 ID | 等级 | 描述 | 状态 |
|---|---|---|---|
| BUG-004 | S2 | `provider_diagnostics_service.py` `fetch_with_fallback()` 参数传递方式错误 | **已修复** |
| BUG-005 | S2 | `/product/live-data/research-context` 返回 numpy.bool 无法被 Pydantic 序列化 | **已修复** |
| BUG-006 | S3 | 搜索 Provider 测试环境变量泄漏导致 4 个测试失败 | **已修复** |

---

## 2. BUG-004 修复详情

### 根因

`provider_diagnostics_service.py:104` 调用 `hub.fetch_with_fallback(capability=capability, fetch_fn_name=fetch_fn_name, *fetch_args, required_fields=required_fields)` 时，`capability` 和 `fetch_fn_name` 被作为关键字参数传递，但 `DataProviderHub.fetch_with_fallback()` 的签名要求它们为位置参数（`*args` 展开后与关键字参数冲突）。

### 修复内容

**`src/product_app/provider_diagnostics_service.py:104`**：将 `capability` 和 `fetch_fn_name` 改为位置参数传递：

```python
# 修复前
result = hub.fetch_with_fallback(
    capability=capability,
    fetch_fn_name=fetch_fn_name,
    *fetch_args,
    required_fields=required_fields,
)

# 修复后
result = hub.fetch_with_fallback(
    capability,
    fetch_fn_name,
    *fetch_args,
    required_fields=required_fields,
)
```

### 验证

- `test_live_data_service.py::TestProviderDiagnosticsService::test_diagnose_returns_structure` PASSED
- 537 回归测试全部通过

---

## 3. BUG-005 修复详情

### 根因

`/product/live-data/research-context` 端点返回的 JSON 中包含 `numpy.bool_`、`numpy.int64`、`numpy.float64` 等类型，FastAPI/Pydantic 无法序列化这些类型，导致 500 错误。具体来源：

1. `_records_from_frame()` — DataFrame 转 dict 时保留 numpy 标量类型
2. `_build_quality_report()` — `critical_fields_ok` 可能是 `numpy.bool_`
3. `_build_missing_report()` — `coverage` 字典值可能是 `numpy.bool_`

### 修复内容

**`src/product_app/live_data_service.py`** — 三处修复：

1. **`_records_from_frame()`**：增加 numpy 类型转 Python 原生类型的逻辑：
   ```python
   if hasattr(value, "item"):
       # numpy scalar (numpy.bool_, numpy.int64, numpy.float64 等)
       converted_row[str(key)] = value.item()
   ```

2. **`_build_quality_report()`**：显式 `bool()` 包装：
   ```python
   "critical_fields_ok": bool(result.status == "ok" and len(records) > 0),
   ```

3. **`_build_missing_report()`**：显式 `bool()` 包装 coverage 值：
   ```python
   "coverage": {f: bool(ok) for f, ok in coverage.items()},
   ```

### 验证

- `test_live_data_service.py::TestLiveDataAPI::test_research_context_endpoint` PASSED
- 537 回归测试全部通过

---

## 4. BUG-006 修复详情

### 根因

`TavilyProvider.__init__(api_key="")` 中 `self._api_key = api_key or TAVILY_API_KEY`，当 `api_key=""` 时空字符串为 falsy，fallback 到环境变量 `TAVILY_API_KEY`。如果环境中恰好设置了 `TAVILY_API_KEY`（如 CI/CD），测试中 `TavilyProvider(api_key="")` 会意外读取到真实 API Key，导致 `is_configured` 返回 `True` 而非预期的 `False`。

同样的问题存在于 `AnySearchProvider` 和 `FirecrawlProvider`。

### 修复内容

**`src/product_app/search_provider_hub.py`** — 三个 Provider 的 `__init__` 方法统一修改：

```python
# 修复前
def __init__(self, api_key: str = ""):
    self._api_key = api_key or TAVILY_API_KEY

# 修复后
def __init__(self, api_key: str | None = None):
    self._api_key = api_key if api_key is not None else TAVILY_API_KEY
```

这样 `api_key=""` 时不再 fallback 到环境变量，只有 `api_key=None`（默认值）才会读取环境变量。

### 验证

- `test_search_evidence.py::TestTavilyProvider::test_not_configured_without_key` PASSED
- `test_search_evidence.py::TestAnySearchProvider::test_not_configured_without_key` PASSED
- `test_search_evidence.py::TestFirecrawlProvider::test_not_configured_without_key` PASSED
- 537 回归测试全部通过

---

## 5. 回归测试结果

### 新增功能测试（126 个）

```
tests/test_live_data_mapper.py   — 51 PASSED
tests/test_live_data_service.py  — 21 PASSED
tests/test_stock_pool_service.py — 19 PASSED
tests/test_live_signal.py        — 14 PASSED
tests/test_search_evidence.py    — 21 PASSED

合计: 126 passed, 0 failed
```

### 全量回归测试（537 个）

```
537 passed, 0 failed, 1 warning
```

### 静态检查

```
ruff check src/product_app/provider_diagnostics_service.py src/product_app/live_data_service.py src/product_app/search_provider_hub.py
All checks passed!
```

---

## 6. 修改文件清单

| 文件 | 修改类型 | 说明 |
|---|---|---|
| `src/product_app/provider_diagnostics_service.py` | 修改 | BUG-004: `fetch_with_fallback` 参数改为位置传递 |
| `src/product_app/live_data_service.py` | 修改 | BUG-005: numpy 类型转 Python 原生类型 |
| `src/product_app/search_provider_hub.py` | 修改 | BUG-006: `api_key` 参数改为 `str \| None` + `is not None` 检查 |

---

## 7. 测试门禁重新评估

| 门禁条件 | 修复前 | 修复后 |
|---|---|---|
| 所有 MUST 功能通过 | PARTIAL | **PASS** |
| 无 S0/S1/S2 阻断缺陷 | FAIL (2 S2) | **PASS** |
| 核心交易安全回归通过 | PASS | **PASS** |
| API 改动有 HTTP 级验证 | PARTIAL | **PASS** |
| 数据源改动有 mock 和异常路径测试 | PASS | **PASS** |
| 搜索增强降级测试 | PARTIAL (环境泄漏) | **PASS** |
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

**所有 S2 阻断缺陷已修复，S3 环境泄漏已修复，537 回归测试全部通过，ruff 检查通过。建议进入架构 Review 阶段。**
