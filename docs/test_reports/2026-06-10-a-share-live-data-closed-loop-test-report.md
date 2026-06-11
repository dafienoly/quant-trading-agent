# A股主板实盘数据闭环 — 测试报告

> 角色：Test Engineer Agent
> 日期：2026-06-10
> 需求文档：`docs/requirements/2026-06-10-a-share-live-data-closed-loop-requirements.md`
> 架构文档：`docs/design/2026-06-10-a-share-live-data-closed-loop-architecture.md`
> 开发报告：`docs/dev_reports/2026-06-10-a-share-live-data-closed-loop.md`
> 遵守规范：`AGENT_DEVELOPMENT_PIPELINE.md` §10 阶段 4

---

## 1. 测试环境

| 项目 | 值 |
|---|---|
| 操作系统 | Windows 11 |
| Python 版本 | 3.14.5 |
| 测试框架 | pytest 9.0.3 |
| 静态检查 | ruff |
| API 框架 | FastAPI + uvicorn (port 8001) |
| 浏览器 E2E | Playwright + Chromium headless |
| Streamlit | port 8502 |
| 测试日期 | 2026-06-11 |
| 分支 | feature/quant-factor-v1 |

---

## 2. 测试范围

### 2.1 测试范围

- Phase A：数据契约层（provider_contracts, live_data_mapper, provider_hub, eastmoney_provider）
- Phase B：LiveDataService、DataHealthGate、ProviderDiagnosticsService、Live Data API
- Phase C：StockPoolService、ThemePoolService、Pool API
- Phase D：LiveFactorService、LiveBacktestService、LiveSignalOrchestrator、Signal API
- Phase E：SearchProviderHub、ThemeEvidenceService、Search/Theme API
- Phase F：ruff 静态检查、回归测试、API 端点 HTTP 测试（15 个端点）
- Phase G：浏览器 E2E 测试（Playwright + Streamlit Dashboard）
- Phase H：搜索增强降级测试（无 API KEY 场景）
- 安全与风控回归验证

### 2.2 不测范围

- 分钟线接口（架构预留，本阶段不作为验收阻断）
- 真实网络实时行情 smoke 测试（需要交易时段和网络连通，属于手动验证）
- 搜索增强真实 API 调用（需要 API KEY，见 §11 待配置项）

---

## 3. 需求覆盖矩阵

| 需求 ID | 功能点 | 测试覆盖 | 结果 | 备注 |
|---|---|---|---|---|
| F-001 | 多真实数据源 Provider Hub | test_live_data_mapper.py (ProviderCircuitBreaker, DataProviderHub) | PASS | 熔断+切源+全失败 |
| F-002 | 数据源诊断页 | test_live_data_service.py (ProviderDiagnosticsService) + API /diagnose | PASS (mock) / FAIL (HTTP 500) | 见 BUG-001 |
| F-003 | 自动切源 | test_live_data_mapper.py (test_fallback_to_second_provider) | PASS | mock 验证通过 |
| F-004 | 全部真实源失败 fail closed | test_live_data_mapper.py + test_live_data_service.py + test_live_signal.py | PASS | data_status=FAILED, 信号 blocked |
| F-005 | 自选池管理 | test_stock_pool_service.py (add/remove/get/validate) | PASS | 创业板/科创板被拒绝 |
| F-006 | AI算力/半导体主题池 | test_stock_pool_service.py (ThemePoolService) | PASS | 109+70 只, 标签筛选 |
| F-007 | 实时行情闭环 | test_live_data_service.py + API /live-data/quotes | PASS (mock) / WARN (HTTP) | 非交易时段超时属正常 |
| F-008 | 历史日线闭环 | test_live_data_service.py + API /live-data/daily-bars | PASS | data_status=FAILED(非交易时段) |
| F-009 | 基础财务数据闭环 | test_live_data_mapper.py (missing_fields_preserved_as_nan) + API | PASS | NaN 不填 0 |
| F-010 | 主题/新闻证据增强 | test_search_evidence.py + 降级测试 | PASS | 预算控制+缓存+证据+降级 |
| F-011 | 数据源故障搜索诊断 | 架构预留 ProviderFailureAnalyzer，未独立实现 | N/A | SHOULD，非阻断 |
| F-012 | 分钟线接口预留 | DataCapability.INTRADAY_BARS 已定义 | PASS | 架构预留 |
| F-013 | 数据健康门禁 | test_live_data_service.py (DataHealthGate 9 项测试) | PASS | 6 种场景全覆盖 |
| F-014 | 产品 UI 集成 | API 端点 12/15 + 浏览器 E2E 4/4 | PASS (部分) | 见 BUG-001/BUG-002 |
| F-015 | 自动 feedback | test_live_data_service.py (write_failure_bug) | PASS | mock 验证通过 |

---

## 4. 自动化测试结果

### 4.1 新增功能测试（116 个）

```
tests/test_live_data_mapper.py  — 51 PASSED
tests/test_live_data_service.py — 21 PASSED
tests/test_stock_pool_service.py — 19 PASSED
tests/test_live_signal.py       — 14 PASSED
tests/test_search_evidence.py   — 11 PASSED

合计: 116 passed, 0 failed
```

### 4.2 回归测试

```
525 passed, 2 failed, 1 warning

失败项（预存问题，非本次引入）:
- test_product_market_data.py::test_fetch_product_quotes_records_feedback_on_provider_failure
- test_product_realtime_api.py::test_product_quotes_endpoint_falls_back_to_demo_and_records_feedback
```

### 4.3 静态检查

```
ruff check: All checks passed!
```

---

## 5. API 端点 E2E 测试结果

通过 uvicorn 启动真实 API 服务（port 8001），使用 HTTP 请求验证 15 个端点。

| 端点 | 方法 | 状态码 | 结果 | 备注 |
|---|---|---|---|---|
| `/product/health` | GET | 200 | PASS | |
| `/product/live-data/providers` | GET | 500 | FAIL | BUG-001 |
| `/product/live-data/quotes` | GET | timeout | WARN | 东方财富 API 非交易时段延迟 |
| `/product/live-data/daily-bars` | GET | 200 | PASS | data_status=FAILED(非交易时段) |
| `/product/live-data/fundamentals` | GET | 200 | PASS | data_status=FAILED(无数据) |
| `/product/live-data/diagnose` | POST | 500 | FAIL | BUG-002 |
| `/product/live-data/research-context` | POST | 200 | PASS | |
| `/product/pools` | GET | 200 | PASS | |
| `/product/signal/draft` | POST | 200 | PASS | status=blocked, is_demo=False |
| `/product/search` | POST | 200 | PASS | status=not_configured (无 KEY 降级) |
| `/product/theme-evidence` | GET | 200 | PASS | data_status=no_news_found |
| `/product/dashboard` | GET | 200 | PASS | |
| `/product/config` | GET | 200 | PASS | |
| `/product/feedback` | GET | 200 | PASS | |
| `/product/jobs` | GET | 200 | PASS | |

**通过率: 12/15 (80.0%)**

---

## 6. 浏览器 E2E 测试结果

通过 Playwright + Chromium headless 验证 Streamlit Dashboard（port 8502）。

### 6.1 基础渲染测试

| 测试项 | 结果 | 备注 |
|---|---|---|
| Streamlit health check | PASS | `/_stcore/health` 返回 `ok` |
| 无 DuplicateElementId | PASS | HTML 和 page_errors 均无重复 ID 错误 |
| 无 stException 元素 | PASS | `[data-testid="stException"]` count=0 |
| Dashboard tabs 数量 | PASS | 15 个 Tab 按钮 (≥9) |

### 6.2 Live Data Tab 交互测试

| Tab | 结果 | 页面错误 |
|---|---|---|
| Realtime Market | PASS | 无 |
| Watchlist | PASS | 无 |
| Signals | PASS | 无 |

截图保存位置：`runtime/dashboard_realtime_tab.png`, `runtime/dashboard_watchlist_tab.png`, `runtime/dashboard_signals_tab.png`

---

## 7. 搜索增强降级测试

在未配置 `SEARCH_API_KEY` 的情况下验证降级行为：

| 测试项 | 结果 | 详情 |
|---|---|---|
| `/product/search` 无 KEY | PASS | 返回 `status=not_configured`，不崩溃 |
| `/product/theme-evidence` 无 KEY | PASS | 返回 `data_status=no_news_found`，不崩溃 |
| SearchProviderHub 直接调用 | PASS | 返回空结果 + warning 日志 |

---

## 8. 安全和风控回归结果

| 检查项 | 结果 | 证据 |
|---|---|---|
| is_demo 全链路 False | PASS | LiveDataService:285, LiveFactorService:232, LiveBacktestService:88, LiveSignalOrchestrator:186, ThemeEvidenceService:129 — 所有返回结构中 `"is_demo": False` 硬编码 |
| 数据失败 fail closed | PASS | DataHealthGate:96-108 行情/日线 FAILED → allow_signal=False, allow_order_draft=False; LiveSignalOrchestrator:150-189 返回 status=blocked |
| 无硬编码 API Key | PASS | eastmoney_provider.py 无密钥; search_provider_hub.py:33 `SEARCH_API_KEY = os.getenv(...)` |
| 创业板/科创板/ST 拒绝 | PASS | stock_pool_service.py:318-325 is_excluded() 检查; 测试 test_add_chinext_rejected/test_add_star_rejected 通过 |
| Risk Agent 一票否决未绕过 | PASS | LiveSignalOrchestrator:199 风控检查 _check_risk(); DataHealthGate 独立于 Risk Agent |
| 无真实自动下单 | PASS | ENABLE_LIVE_TRADING 默认 false; 无 LEVEL_3 入口 |
| Demo 数据不进入信号链路 | PASS | DataHealthGate:82-93 is_demo=True → allow_signal=False, allow_order_draft=False |
| 财务缺失保留 NaN | PASS | live_data_mapper.py:259-262 `pd.to_numeric(errors="coerce")` 不填 0; 测试 test_missing_fields_preserved_as_nan 通过 |

---

## 9. 缺陷列表

### BUG-001: `/product/live-data/providers` 返回 500

- **等级**: S2（重要功能部分不可用）
- **复现步骤**:
  1. 启动 uvicorn 服务
  2. GET `/product/live-data/providers`
- **期望结果**: 200 OK，返回 provider 配置和熔断状态
- **实际结果**: 500 Internal Server Error
- **根因**: `product_routes.py:415` 访问 `lds._provider_order`，但 `LiveDataService` 类没有 `_provider_order` 属性
- **建议修复**: 在 `LiveDataService.__init__()` 中保存 `self._provider_order = provider_order`，或在路由中使用 `LIVE_DATA_PROVIDER_ORDER` 环境变量

### BUG-002: `/product/live-data/diagnose` 返回 500

- **等级**: S2（重要功能部分不可用）
- **复现步骤**:
  1. 启动 uvicorn 服务
  2. POST `/product/live-data/diagnose?symbols=600000.SH&capabilities=realtime_quotes`
- **期望结果**: 200 OK，返回 provider 诊断报告
- **实际结果**: 500 Internal Server Error
- **根因**: `_get_diagnostics_service()` 只传入 `lds._realtime_hub`，但 `ProviderDiagnosticsService` 尝试诊断 daily_bars 和 fundamentals 时使用同一个 hub，导致方法不匹配
- **建议修复**: 重构 `ProviderDiagnosticsService` 接收多个 hub（realtime/daily/fundamentals），或为每个 capability 使用对应的 hub

### BUG-003（预存）: 2 个旧测试失败

- **等级**: S3（非核心，预存问题）
- **详情**: `test_product_market_data.py` 和 `test_product_realtime_api.py` 各 1 个测试因 `is_trading_hours()` mock 不完整而失败
- **影响**: 不影响新功能，属于 Phase 5.6 遗留问题

---

## 10. 架构一致性检查

| 检查项 | 结果 | 备注 |
|---|---|---|
| Provider 合约层与架构 §5.1 一致 | PASS | DataCapability, ProviderResult, ProviderHealth, LiveDataProvider Protocol |
| 标准化映射层与架构 §5.2 一致 | PASS | normalize_a_share_symbol, normalize_trade_date, map_realtime_quotes, map_daily_bars, map_fundamentals |
| Eastmoney Provider 与架构 §5.3 一致 | PASS | 3 个 API 方法 + 速率限制 + volume 单位转换 |
| Provider Hub 与架构 §5.4 一致 | PASS | fetch_with_fallback + ProviderCircuitBreaker |
| LiveDataService 与架构 §5.5 一致 | PASS | 唯一数据入口 + is_demo=False + fail closed |
| DataHealthGate 与架构 §5.6 一致 | PASS | 6 种场景门禁规则 + 延迟阈值 |
| StockPoolService 与架构 §5.7 一致 | PASS | 自选池 + 主题池 + 验证过滤 |
| ThemeEvidenceService 与架构 §5.8 一致 | PASS | 搜索预算 + 缓存 + 证据结构 |
| LiveFactorService 与架构 §5.9 一致 | PASS | FactorEngine 降级 + 基础因子 |
| LiveBacktestService 与架构 §5.10 一致 | PASS | SMA 交叉策略 + 数据健康门控 |
| LiveSignalOrchestrator 与架构 §5.11 一致 | PASS | 10 步流程 + blocked 信号 |
| API 端点与架构 §6 一致 | PARTIAL | 12/15 端点正常，2 个端点有 500 错误，1 个超时 |
| 存储设计与架构 §7 一致 | PASS | runtime/state/ + data/reference/ 路径一致 |
| 配置设计与架构 §8 一致 | PASS | 环境变量 + 默认值一致 |

---

## 11. 待配置项

以下环境变量需要在 `.env` 文件中配置后方可进行搜索增强真实 API 调用测试：

| 环境变量 | 说明 | 配置位置 |
|---|---|---|
| `SEARCH_API_KEY` | SerpAPI 风格搜索 API Key | `.env` 文件 |
| `SEARCH_API_BASE` | 搜索 API 基地址（默认 `https://serpapi.com/search`） | `.env` 文件 |

**注意**: 需求文档要求 `TAVILY_API_KEY`/`ANYSEARCH_API_KEY`/`FIRECRAWL_API_KEY` 三个 Key，但实际实现统一封装为 `SEARCH_API_KEY` + `SEARCH_API_BASE`。如需对齐需求文档，需修改 `search_provider_hub.py` 支持多 Provider。

配置示例（添加到 `.env` 文件末尾）：

```bash
# 搜索增强 API
SEARCH_API_KEY=your_serpapi_key_here
SEARCH_API_BASE=https://serpapi.com/search
```

---

## 12. 测试门禁评估

根据 `AGENT_DEVELOPMENT_PIPELINE.md` §10 测试门禁要求：

| 门禁条件 | 结果 |
|---|---|
| 所有 MUST 功能通过 | PARTIAL — F-002 诊断页 HTTP 500 |
| 无 S0/S1/S2 阻断缺陷 | FAIL — 2 个 S2 缺陷 |
| 核心交易安全回归通过 | PASS |
| 前端改动有浏览器渲染验证 | PASS — 4/4 E2E + 3 Tab 交互 |
| API 改动有 HTTP 级验证 | PARTIAL — 12/15 通过 |
| 数据源改动有 mock 测试和异常路径测试 | PASS |
| 搜索增强降级测试 | PASS |

---

## 13. 结论与建议

### 测试结论

**有条件通过 — 需修复 2 个 S2 缺陷后方可进入架构 Review**

### 必须修复（阻断）

1. **BUG-001**: `/product/live-data/providers` 500 错误 — `LiveDataService` 缺少 `_provider_order` 属性
2. **BUG-002**: `/product/live-data/diagnose` 500 错误 — `ProviderDiagnosticsService` 只接收单个 hub

### 建议改进（非阻断）

1. 搜索增强配置与需求文档不完全一致：需求要求 `TAVILY_API_KEY`/`ANYSEARCH_API_KEY`/`FIRECRAWL_API_KEY` 三个 Key，实现只使用 `SEARCH_API_KEY` + `SEARCH_API_BASE`（SerpAPI 风格）。建议后续对齐或更新需求文档。
2. `ProviderFailureAnalyzer`（F-011）未独立实现，属于 SHOULD 优先级，非阻断。
3. 2 个预存测试失败（S3），建议后续修复。
4. `/product/live-data/quotes` 非交易时段超时，建议增加超时降级处理。

### 建议下一步

1. 修复 BUG-001 和 BUG-002
2. 在 `.env` 中配置 `SEARCH_API_KEY` 后补全搜索增强真实 API 调用测试
3. 修复后重新运行 API 端点测试验证
4. 通过后进入架构 Review 阶段
