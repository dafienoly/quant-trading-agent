# Phase 3 测试报告 — Relay + Audit + Health + Cache（Slice C）

## 基本信息

| 项目 | 值 |
|------|-----|
| 需求文档 | `docs/requirements/2026-06-25-market-data-relay-provider-contract-requirements.md` |
| 架构文档 | `docs/design/2026-06-25-market-data-relay-provider-contract-architecture.md` |
| 团队计划 | `docs/dev_plans/20260625-market-data-relay-provider-contract-team-plan.md` |
| 开发报告 | `docs/dev_reports/20260625-market-data-relay-provider-contract-phase-3-dev-report.md` |
| 路线图 | V16.2 Market Data Relay & Provider Contract |
| 测试阶段 | Phase 3 — Relay + Audit + Health + Cache（Slice C） |
| 测试工程师 | OpenCode Test Engineer (`claude_tester`) |

## 测试环境

| 项目 | 值 |
|------|-----|
| base branch | `epic/20260625-market-data-relay-provider-contract-run-28168858781` |
| base commit | `2224ad4` |
| temporary test branch | `test/market-data-relay-provider-contract-phase-3-tester-20260626-0218`（已删除） |
| Python 版本 | 3.14.4（系统 `python3`，无 `.venv`） |
| 平台 | Linux (WSL) |
| 测试框架 | pytest 9.1.1 |
| 静态检查 | ruff（pyproject.toml） |

## 测试范围与不测范围

### 测试范围

| 文件 | 说明 |
|------|------|
| `src/product_app/market_data/relay.py` | MarketDataRelay 统一编排入口 |
| `src/product_app/market_data/audit.py` | AuditRecorder 与 MarketDataAuditEvent |
| `src/product_app/market_data/health.py` | ProviderHealthAggregator 内存聚合 |
| `src/product_app/market_data/cache.py` | MarketDataCache 与 CachedEntry |
| `src/product_app/market_data/__init__.py` | Phase 3 符号 re-export |
| `src/product_app/market_data/provider_registry.py` | adapter 槽位新增（Phase 2 变更回归） |
| `tests/test_market_data_audit.py` | 7 tests |
| `tests/test_market_data_health.py` | 10 tests |
| `tests/test_market_data_cache.py` | 9 tests |
| `tests/test_market_data_relay.py` | 14 tests |
| Phase 1–2 市场数据回归 | `tests/test_market_data_*.py`（166 tests） |
| 既有产品服务回归 | `tests/test_live_data_service.py` + `tests/test_quote_health.py`（34 tests） |
| 全量回归 | `pytest tests`（1322 passed） |
| 静态检查 + py_compile | ruff / py_compile 全部通过 |

### 不测范围（合理排除）

| 项 | 原因 |
|----|------|
| `fetch_bars` 中 bars 为空列表时的 quality gate 行为 | bars 为空时回退到 QualityStatus.OK，属设计意图；Adapter 层已保证非空 |
| 永久审计存储 | Health 为内存聚合，`snapshot()` 仅反映当前进程状态（开发报告已记录） |
| Circuit breaker 集成 | ProviderHealthAggregator 含 `circuit_breaker_status` 字段但基于内部 consecutive_failures；既有 ProviderCircuitBreaker 可作增强 |
| 真实 Provider 网络集成 | 属 acceptance 范围，测试全用 mock/fake adapter |
| API 路由（`/product/market/**`） | Phase 4 范围 |
| Streamlit UI（可观测页面） | Phase 5 范围 |
| `socksio` 缺失导致的 6 个既有测试失败 | 环境依赖问题，与 Phase 3 无关 |
| `aktools` 模块缺失导致的 2 个既有测试失败 | 环境依赖问题，与 Phase 3 无关 |

## 需求覆盖矩阵

### 核心功能需求

| 需求 ID | 需求 | 覆盖测试 | 状态 |
|---------|------|----------|------|
| §1 Market Data Relay 统一入口 | 单标最新行情 | `test_get_latest_quote_success` | PASS |
| §1 Market Data Relay 统一入口 | 多标最新行情 | `test_get_latest_quotes_success` | PASS |
| §1 Market Data Relay 统一入口 | 历史 K 线 | `test_get_bars_success` | PASS |
| §3 数据质量字段 | source_provider, as_of, is_stale, is_fallback 等 | `test_get_latest_quote_success`, `test_get_latest_quote_fallback_success` | PASS |
| §4 Fail-closed | 数据不可用时返回 fail-closed 错误 | `test_get_latest_quote_fail_closed`, `test_get_latest_quote_all_fail`, `test_selected_providers_none_raises` | PASS |
| §4 Fail-closed | demo 数据不得作为 live 返回 | `test_allow_demo_false_blocks_demo` | PASS |
| §5 Provider Priority & Fallback | fallback 成功时标记 is_fallback | `test_get_latest_quote_fallback_success` | PASS |
| §5 Provider Priority & Fallback | all fail 时记录所有 attempts | `test_get_latest_quote_all_fail` | PASS |
| §6 Provider Health | availability、latency、error category、circuit breaker | `test_*` 10 tests in health | PASS |
| §6 Provider Health | fallback activation count | `test_fallback_activation_count` | PASS |
| §7 审计日志 | request_id、caller_context、provider_attempts、quality_status | `test_audit_error_code_on_failure` + audit 7 tests | PASS |
| §7 审计日志 | secret 脱敏 | `test_audit_recorder_redacts_secret`, `test_redact_in_recorder` | PASS |

### 数据安全需求

| 需求 ID | 需求 | 覆盖测试 | 状态 |
|---------|------|----------|------|
| §4 | stale 数据 signal/real_trading/position_sizing 阻断 | `test_signal_generation_blocks_non_ok`, `test_cache_stale_fail_closed_for_signal`, cache 6 tests | PASS |
| §4 | allow_demo=False 阻断 demo | `test_allow_demo_false_blocks_demo` | PASS |
| §5 | fallback 数据显式标记不伪装 | `test_get_latest_quote_fallback_success`（is_fallback=True） | PASS |
| §6 | Secret 不得泄露 | `test_audit_recorder_redacts_secret`, `test_redact_in_recorder`, errors 7 redact tests | PASS |
| §6 | 错误响应可诊断且不泄露 secret | `test_str_does_not_contain_secret`, `test_serialization_no_secret`（Phase 1 errors tests） | PASS |

### 负向测试覆盖

| 测试场景 | 测试 | 状态 |
|----------|------|------|
| 无注册 Provider | `test_selected_providers_none_raises` | PASS |
| 单 Provider 失败 | `test_get_latest_quote_fail_closed` | PASS |
| 所有 Provider 失败 | `test_get_latest_quote_all_fail` | PASS |
| 质量门禁阻断（STALE） | `test_signal_generation_blocks_non_ok` | PASS |
| 质量门禁阻断（DEMO） | `test_allow_demo_false_blocks_demo` | PASS |
| cache STALE — research 返回 stale | `test_stale_returns_stale_for_research`, `test_cache_hit_returns_stale_for_research` | PASS |
| cache STALE — signal 阻断 | `test_cache_stale_fail_closed_for_signal` | PASS |
| 审计错误码记录 | `test_audit_error_code_on_failure` | PASS |
| request_id 唯一性 | `test_request_id_unique` | PASS |
| redact_secret 脱敏 | Phase 1 errors 10 tests（全部通过） | PASS |

## 命令与结果

### 命令 1：ruff 静态检查

```bash
python3 -m ruff check \
  src/product_app/market_data/relay.py \
  src/product_app/market_data/audit.py \
  src/product_app/market_data/health.py \
  src/product_app/market_data/cache.py \
  src/product_app/market_data/__init__.py \
  src/product_app/market_data/provider_registry.py \
  tests/test_market_data_relay.py \
  tests/test_market_data_audit.py \
  tests/test_market_data_health.py \
  tests/test_market_data_cache.py
```

**结果：** All checks passed（0 错误）

### 命令 2：py_compile

```bash
python3 -m py_compile \
  src/product_app/market_data/relay.py \
  src/product_app/market_data/audit.py \
  src/product_app/market_data/health.py \
  src/product_app/market_data/cache.py \
  src/product_app/market_data/__init__.py \
  src/product_app/market_data/provider_registry.py
```

**结果：** 无输出（全部通过）

### 命令 3：Phase 3 专用测试

```bash
python3 -m pytest tests/test_market_data_audit.py \
  tests/test_market_data_health.py \
  tests/test_market_data_cache.py \
  tests/test_market_data_relay.py \
  -v --tb=short --basetemp=runtime/pytest-tmp-market-data-relay-provider-contract-phase3
```

**结果：** 40 passed（10 health + 9 cache + 7 audit + 14 relay）

### 命令 4：既有产品数据入口回归

```bash
python3 -m pytest tests/test_live_data_service.py tests/test_quote_health.py \
  -q --tb=short --basetemp=runtime/pytest-tmp-market-data-relay-provider-contract-relay-regression
```

**结果：** 34 passed（无回归性失败）

### 命令 5：Phase 3 + 回归合并测试

```bash
python3 -m pytest tests/test_live_data_service.py tests/test_quote_health.py \
  tests/test_market_data_audit.py tests/test_market_data_health.py \
  tests/test_market_data_cache.py tests/test_market_data_relay.py \
  -q --tb=short --basetemp=runtime/pytest-tmp-market-data-relay-provider-contract-phase3-full
```

**结果：** 74 passed

### 命令 6：全部市场数据模块测试

```bash
python3 -m pytest tests/test_market_data_*.py -v --tb=short --basetemp=runtime/pytest-tmp-market-data-all
```

**结果：** 166 passed（Phase 1 70 + Phase 2 56 + Phase 3 40）

### 命令 7：全量回归

```bash
python3 -m pytest tests -q --tb=short --basetemp=runtime/pytest-tmp-market-data-relay-provider-contract-full
```

**结果：** 1322 passed, 6 failed, 6 skipped, 3 warnings

6 个失败均为预存环境依赖问题，与 Phase 3 无关：

| 失败测试 | 根因 |
|----------|------|
| `test_aktools_compat_app` ×2 | `ModuleNotFoundError: No module named 'aktools'` |
| `test_eastmoney_provider` ×2 | `ImportError: Using SOCKS proxy, but the 'socksio' package is not installed` |
| `test_live_data_mapper::test_name` | 同上 socksio |
| `test_realtime_provider::test_aktools_provider` | 同上 socksio |

### 命令 8：git diff --check

```bash
git diff --check
```

**结果：** 无 trailing whitespace / 无 indent 问题（仅预存 CRLF warning，属 WSL 环境行为）

### 命令 9：ruff 全局检查（mkt_data 模块 + 测试）

```bash
python3 -m ruff check src/product_app/market_data/ tests/test_market_data_*.py
```

**结果：** All checks passed

## API / UI / 数据源 / 安全 Smoke 证据

### API Smoke

- Phase 4 API 路由（`/product/market/**`）尚未实现，非本阶段范围
- FastAPI app factory 可正常导入加载（Phase 1–2 已验证，Phase 3 未触及路由层）

### UI 影响

- 无 UI 变更（Phase 5 范围）
- Streamlit Dashboard 未被标记为 legacy/deprecated
- `__init__.py` 顶层 `fetch_product_quotes` 函数未被修改（界面入口不变）

### 数据源

- MarketDataRelay 不直接调用 raw provider，通过 registry + adapter 调用
- Relay 对每个返回 quote/bar 注入 DataQualityMetadata
- Fallback、stale、demo、mock 数据均通过 QualityGate 门禁
- `_select_providers` 在 registry 为 None 时返回空列表，抛出 MarketDataUnavailableError（fail-closed）

### 安全确认

| 检查项 | 结果 |
|--------|------|
| AuditRecorder 对所有 attempt 的 safe_reason 执行 redact_secret | PASS（`audit.py:93-95`） |
| MarketDataUnavailableError 的 __str__/__repr__/model_dump 不含 secret | PASS（Phase 1 errors tests） |
| 审计事件不包含完整 auth header 或 key | PASS |
| `_select_providers` 异常被静默捕获不扩散 | PASS（设计意图，见剩余风险 #2） |
| 未新增真实交易能力 | PASS |
| 未触碰 `src/risk_engine/`、`src/execution_engine/`、`src/stock_pool/` | PASS |
| 未绕过 Risk、Stock Pool、Human Confirmation、Provider Contract | PASS |

## 缺陷列表

无 S0/S1/S2 缺陷发现。

### S3 建议

| ID | 描述 | 状态 |
|----|------|------|
| S3-01 | Relay 中 `_select_providers` 的 `try/except Exception: pass` 静默吞掉 registry 异常，可能导致注册配置错误时无法诊断。开发报告已记录为设计选择（"防止注册异常扩散到数据请求层"）。建议后续添加 warn 级日志。 | 不阻断 |
| S3-02 | Relay 将非 `MarketDataUnavailableError` 的通用 Exception 统一归为 `UNKNOWN_PROVIDER_ERROR`，缺少 `PERMISSION_DENIED`/`AUTH_FAILURE` 等细粒度分类。ProviderErrorCategory 枚举已预留相关值，可在后续重构中增强。 | 不阻断 |

### 测试覆盖缺口（非阻断）

| 缺口 | 说明 |
|------|------|
| `get_latest_quotes` fallback 路径 | 未显式覆盖（与 `get_latest_quote` fallback 逻辑模式相同） |
| `get_bars` fallback 路径 | 未显式覆盖（同上） |
| Relay 的 `_select_providers` registry 抛异常路径 | 异常被静默捕获，无法在测试中验证行为 |

## 剩余风险

1. **Health 数据进程内存**：ProviderHealthAggregator 为内存聚合，`snapshot()` 仅反映当前进程状态，进程重启后历史数据丢失。长期来看需持久化存储支持。
2. **Registry 异常静默**：`_select_providers` 的 `try/except Exception: pass` 会在 registry 配置错误时无任何信号返回，可能导致"无可用 Provider"误诊。开发报告已记录此风险。
3. **Cache 默认 FreshnessPolicy**：`_DEFAULT_FRESHNESS` 为 30s fresh / 300s stale，生产环境可能需要按 symbol/market 差异化配置。
4. **ProviderErrorCategory 细粒度**：当前 relay 只区分 `PROVIDER_UNAVAILABLE` 和 `UNKNOWN_PROVIDER_ERROR`，未来可细化为 `PERMISSION_DENIED`、`AUTH_FAILURE`、`RATE_LIMITED`、`TIMEOUT` 等。

## 最终结论

**PASS**

Phase 3 全部 40 个专项测试通过，34 个既有产品服务测试无回归，166 个市场数据模块测试全绿，全量回归 1322 个测试中 6 个失败均为预存环境依赖问题（与 Phase 3 无关）。ruff 静态检查和 py_compile 无错误。安全约束验证通过：fail-closed、secret 脱敏、demo/stale/mock 阻断行为正确。未触碰 restricted modules，未新增真实交易能力，未泄露 secret。
