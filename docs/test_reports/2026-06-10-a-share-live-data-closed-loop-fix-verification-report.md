# A股主板实盘数据闭环 — 修复验证报告

> 角色：Test Engineer Agent
> 日期：2026-06-11
> 修复报告：`docs/dev_reports/2026-06-10-a-share-live-data-closed-loop-fix-report.md`
> 原测试报告：`docs/test_reports/2026-06-10-a-share-live-data-closed-loop-test-report.md`
> 遵守规范：`AGENT_DEVELOPMENT_PIPELINE.md` §10 阶段 4

---

## 1. 验证范围

根据修复报告 §1-§5，本次验证覆盖以下修复项：

| 修复项 | 等级 | 描述 | 验证结果 |
|---|---|---|---|
| BUG-001 | S2 | `/product/live-data/providers` 返回 500 | **PASS** |
| BUG-002 | S2 | `/product/live-data/diagnose` 返回 500 | **FAIL** — 修复不完整，引入新回归 |
| SEARCH_API 架构 | S2 | 搜索配置与需求文档不一致 | **PASS** |
| ruff 静态检查 | S4 | 9 个 lint 错误 | **PASS** |

---

## 2. BUG-001 验证：PASS

### 代码审查

- `live_data_service.py:76-80`：新增 `self._provider_order` 属性 — 正确
- `product_routes.py:396`：`lds._daily_bars_hub` 替换 `lds._daily_hub` — 正确
- `product_routes.py:392`：`from src.data_gateway.provider_contracts import DataCapability` 替换 `__import__()` — 正确

### API E2E 验证

```
GET /product/live-data/providers → 200 OK
返回: status=ok, provider_order=["eastmoney","akshare","aktools"]
```

**结论：BUG-001 已正确修复。**

---

## 3. BUG-002 验证：FAIL

### 代码审查

- `provider_diagnostics_service.py:52-62`：接收 3 个 hub（realtime/daily_bars/fundamentals）— 正确
- `provider_diagnostics_service.py:64-67`：`_get_hub(capability)` 映射 — 正确
- `product_routes.py:381-385`：传入 3 个 hub — 正确

### API E2E 验证

```
POST /product/live-data/diagnose?symbols=600000.SH&capabilities=realtime_quotes → 500 Internal Server Error
```

### 根因分析

`provider_diagnostics_service.py:104` 调用 `hub.fetch_with_fallback()` 时参数传递方式错误：

```python
result = hub.fetch_with_fallback(
    capability=capability,        # 关键字参数
    fetch_fn_name=fetch_fn_name,  # 关键字参数
    *fetch_args,                  # 位置参数展开 → 第一个元素被赋给 capability
    required_fields=required_fields,
)
```

`fetch_with_fallback` 签名为 `(self, capability, fetch_fn_name, *args, required_fields=None)`。
当 `*fetch_args` 展开时，其第一个元素作为位置参数被赋给 `capability`，与已有的关键字参数 `capability=capability` 冲突，导致 `TypeError: got multiple values for argument 'capability'`。

### 正确调用方式

```python
result = hub.fetch_with_fallback(
    capability,
    fetch_fn_name,
    *fetch_args,
    required_fields=required_fields,
)
```

**结论：BUG-002 修复不完整，`ProviderDiagnosticsService.diagnose()` 中的 `fetch_with_fallback()` 调用方式错误，导致 500 回归。**

---

## 4. 新发现缺陷

### BUG-004: `/product/live-data/diagnose` 返回 500（BUG-002 修复引入的回归）

- **等级**: S2（重要功能部分不可用）
- **根因**: `provider_diagnostics_service.py:104` — `fetch_with_fallback()` 同时以关键字和位置参数传递 `capability`
- **修复方案**: 将 `capability=capability, fetch_fn_name=fetch_fn_name` 改为位置参数传递

### BUG-005: `/product/live-data/research-context` 返回 500

- **等级**: S2（重要功能部分不可用）
- **根因**: `numpy.bool` 类型无法被 Pydantic 序列化
- **错误堆栈**: `pydantic_core._pydantic_core.PydanticSerializationError: Unable to serialize unknown type: <class 'numpy.bool'>`
- **修复方案**: 在 `LiveDataService.build_research_context()` 返回前，将 numpy 类型转换为 Python 原生类型

### BUG-006: 搜索 Provider 测试环境变量泄漏

- **等级**: S3（测试质量，非功能缺陷）
- **根因**: `TavilyProvider(api_key="")` 中 `self._api_key = api_key or TAVILY_API_KEY`，当 `api_key=""` 时 fallback 到环境变量。`.env` 中已配置真实 API Key，导致 `is_configured` 返回 True
- **影响**: 4 个测试失败
- **修复方案**: 测试中使用 `unittest.mock.patch` mock 环境变量，或将 Provider 的 fallback 逻辑改为 `if api_key is not None` 而非 `or`

---

## 5. SEARCH_API 架构修复验证：PASS

### 代码审查

- `search_provider_hub.py`：3 个独立 Provider（Tavily/AnySearch/Firecrawl）— 正确
- 每个 Provider 有独立 API Key 和 Endpoint — 正确
- `SEARCH_PROVIDER_ORDER` 控制 fallback 顺序 — 正确
- 预算控制（`SEARCH_DAILY_CALL_BUDGET=2500`）和缓存（4 小时 TTL）— 正确

### API E2E 验证（真实 API 调用）

```
POST /product/search?query=AI芯片 → 200 OK, status=ok, provider=tavily, results_count>0
GET /product/theme-evidence?symbols=600584.SH → 200 OK, data_status=ok, is_demo=False
```

**结论：SEARCH_API 架构修复正确，真实 API 调用成功。**

---

## 6. 回归测试结果

### 自动化测试

```
533 passed, 4 failed, 1 warning

失败项（全部为搜索 Provider 测试环境变量泄漏，BUG-006）:
- test_search_evidence.py::TestTavilyProvider::test_not_configured_without_key
- test_search_evidence.py::TestTavilyProvider::test_search_raises_without_key
- test_search_evidence.py::TestAnySearchProvider::test_not_configured_without_key
- test_search_evidence.py::TestFirecrawlProvider::test_not_configured_without_key
```

注：原 BUG-003（2 个旧测试失败）已在本次修复中解决，525→533。

### 静态检查

```
ruff check src/product_app/ src/data_gateway/ src/api/
All checks passed!
```

### 浏览器 E2E

```
4/4 PASS
- Streamlit health: PASS
- 无 DuplicateElementId: PASS
- 无 stException 元素: PASS
- Dashboard tabs (15): PASS
```

### API 端点 E2E

```
12/14 PASS (85.7%)

失败:
- /product/live-data/diagnose → 500 (BUG-004)
- /product/live-data/research-context → 500 (BUG-005)
```

---

## 7. 安全与风控回归

| 检查项 | 结果 |
|---|---|
| is_demo 全链路 False | PASS |
| 数据失败 fail closed | PASS |
| 无硬编码 API Key | PASS |
| 创业板/科创板/ST 拒绝 | PASS |
| Risk Agent 一票否决未绕过 | PASS |
| 无真实自动下单 | PASS |
| Demo 数据不进入信号链路 | PASS |
| 财务缺失保留 NaN | PASS |

---

## 8. 测试门禁评估

| 门禁条件 | 结果 |
|---|---|
| 所有 MUST 功能通过 | **FAIL** — diagnose 和 research-context 仍 500 |
| 无 S0/S1/S2 阻断缺陷 | **FAIL** — 2 个 S2 缺陷（BUG-004/005） |
| 核心交易安全回归通过 | PASS |
| 前端改动有浏览器渲染验证 | PASS — 4/4 E2E |
| API 改动有 HTTP 级验证 | PARTIAL — 12/14 通过 |
| 数据源改动有 mock 和异常路径测试 | PASS |
| 搜索增强降级测试 | PASS |
| ruff 静态检查 | PASS |

---

## 9. 结论

**不能进入架构 Review — 需修复 2 个 S2 缺陷（BUG-004/005）后重新验证。**

### 必须修复（阻断）

1. **BUG-004**: `provider_diagnostics_service.py:104` — `fetch_with_fallback()` 参数传递方式错误，`capability` 同时作为位置和关键字参数
   - 修复方案：改为位置参数传递 `hub.fetch_with_fallback(capability, fetch_fn_name, *fetch_args, required_fields=required_fields)`

2. **BUG-005**: `research-context` 返回数据含 `numpy.bool` 类型，Pydantic 无法序列化
   - 修复方案：在返回前将 numpy 类型转换为 Python 原生类型（`bool(x)` / `int(x)` / `float(x)`）

### 建议修复（非阻断）

3. **BUG-006**: 搜索 Provider 测试环境变量泄漏 — 4 个测试失败
   - 修复方案：测试中 mock 环境变量，或将 Provider 构造函数的 fallback 逻辑改为显式检查

### 修复已验证通过

- BUG-001: `/product/live-data/providers` → 200 OK
- SEARCH_API 架构：3 个独立 Provider + 真实 API 调用成功
- ruff 静态检查：All checks passed
- 原 BUG-003（2 个旧测试失败）：已修复
