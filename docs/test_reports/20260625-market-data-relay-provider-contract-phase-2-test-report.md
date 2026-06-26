# Phase 2 测试报告 — Provider Registry + Adapter (Slice B)

## 基本信息

| 项目 | 值 |
|------|-----|
| 需求文档 | `docs/requirements/2026-06-25-market-data-relay-provider-contract-requirements.md` |
| 架构文档 | `docs/design/2026-06-25-market-data-relay-provider-contract-architecture.md` |
| 团队计划 | `docs/dev_plans/20260625-market-data-relay-provider-contract-team-plan.md` |
| 开发报告 | `docs/dev_reports/20260625-market-data-relay-provider-contract-phase-2-dev-report.md` |
| 路线图 | V16.2 Market Data Relay & Provider Contract |
| 测试阶段 | Phase 2 — Provider Registry + Adapter（Slice B） |
| 测试工程师 | OpenCode Test Engineer (`claude_tester`) |

## 测试环境

| 项目 | 值 |
|------|-----|
| base branch | `epic/20260625-market-data-relay-provider-contract-run-28168858781` |
| base commit | `e7dcedc` |
| temporary test branch | `test/market-data-relay/phase-2-tester-20260626-0159` (已删除) |
| Python 版本 | 3.14.4 (系统 `python3`，无 `.venv`) |
| 平台 | Linux (WSL) |
| 测试框架 | pytest 9.1.1 |
| 静态检查 | ruff (pyproject.toml) |

## 测试范围与不测范围

### 测试范围
- `src/product_app/market_data/provider_registry.py` — ProviderRegistry 注册与选择
- `src/product_app/market_data/adapters.py` — MarketDataAdapter 抽象基类、EastmoneyRealtimeAdapter、AkShareRealtimeAdapter
- `tests/test_market_data_provider_registry.py` (12 tests)
- `tests/test_market_data_adapters.py` (16 tests)
- Phase 1 合约/质量/错误模块回归 (70 tests)
- 既有 market_data 调用面回归 (17 tests)

### 不测范围（合理排除）
- API 路由（Phase 4 范围）
- Streamlit UI（Phase 5 范围）
- `fetch_bars` 实现（Phase 3 范围，Phase 2 故意抛 NotImplementedError）
- 真实 Provider 网络集成（属 acceptance 范围，测试全用 mock hub）
- `fallback_allowed=False` 过滤逻辑（Phase 3 Relay 编排范围）
- 广回归 `pytest tests`（Phase 2 不触碰 API entrypoint）

## 需求覆盖矩阵

| 需求 ID | 需求 | 覆盖测试 | 状态 |
|---------|------|----------|------|
| §2 Provider Contract 标准化 | Provider metadata 完整、标准化 response | test_contract_property, test_selected_provider_fields | PASS |
| §2 Provider Contract 标准化 | Error mapping 稳定 | test_fetch_latest_quote_raises_on_empty_data, test_fetch_latest_quote_raises_on_failed_status | PASS |
| §3 数据质量字段 | source_provider, quality_status, request_id, is_fallback, provider_latency_ms | test_fetch_latest_quote_quality_metadata, test_fallback_priority_sets_is_fallback, test_request_id_unique_per_call | PASS |
| §4 Fail-closed | 空数据/失败不返回伪成功 | test_fetch_latest_quote_raises_on_empty_data, test_fetch_latest_quote_raises_on_failed_status, test_fetch_latest_quotes_empty_data_raises | PASS |
| §5 Provider Priority | 按 priority 排序 | test_select_returns_sorted_by_priority | PASS |
| §5 Provider Priority | 按 market/asset_type/endpoint 过滤 | test_select_filters_by_market, test_select_filters_by_asset_type, test_select_filters_by_endpoint | PASS |
| §8 下游边界 | Adapter 不绕过 Provider Contract | 全量测试 — adapter 仅经 hub 调用 provider | PASS |
| Safety §2 data security | secret 不泄露 | grep 验证无 secret/token/password | PASS |
| Safety §3 provider boundary | adapter 是批准的桥接层 | 架构审查 — import raw provider 仅在 adapter 层 | PASS |

## 执行命令与结果

### 命令 1: 开发报告声明命令复跑

```bash
python3 -m ruff check \
  src/product_app/market_data/provider_registry.py \
  src/product_app/market_data/adapters.py \
  tests/test_market_data_provider_registry.py \
  tests/test_market_data_adapters.py
```
**结果**: `All checks passed!`

```bash
python3 -m py_compile \
  src/product_app/market_data/provider_registry.py \
  src/product_app/market_data/adapters.py
```
**结果**: 两次编译均无输出（成功）

```bash
python3 -m pytest \
  tests/test_market_data_provider_registry.py \
  tests/test_market_data_adapters.py \
  -q --basetemp=runtime/pytest-tmp-market-data-relay-provider-contract
```
**结果**: `28 passed in 1.63s` （与开发报告一致 ✓）

### 命令 2: Phase 1 合约回归

```bash
python3 -m pytest \
  tests/test_market_data_contracts.py \
  tests/test_market_data_quality.py \
  tests/test_market_data_errors.py \
  -q --tb=short
```
**结果**: `98 passed in 1.90s` — Phase 1 无回归

### 命令 3: Phase 1+2 全量市场数据测试

```bash
python3 -m pytest tests/test_market_data_*.py -q --tb=short
```
**结果**: `126 passed in 2.33s` — 全绿

### 命令 4: 既有调用面回归

```bash
python3 -m pytest \
  tests/test_product_market_data.py \
  tests/test_realtime_provider.py \
  -q --tb=short \
  -k "not aktools_provider_fetches_realtime_quotes_from_http_mapping"
```
**结果**: `17 passed, 1 deselected` — 既有 market_data 调用面无回归

被跳过的 `test_aktools_provider_fetches_realtime_quotes_from_http_mapping` 因环境缺少 `socksio` 包（SOCKS5 代理依赖）失败，为**预存在环境问题**，与 Phase 2 改动无关。该测试在 Phase 1 测试报告中同样被标记为环境依赖 skip。

### 命令 5: 空白符检查

```bash
git diff --check
```
**结果**: 仅 `.agent/gates/stage_start_gate.json` 的预存在 CRLF warning，非 Phase 2 新增

### 命令 6: 安全扫描

```bash
# secret/credential 泄露检查
grep -nE 'api.?key|token|secret|password|cookie|credential' \
  src/product_app/market_data/provider_registry.py \
  src/product_app/market_data/adapters.py \
  tests/test_market_data_provider_registry.py \
  tests/test_market_data_adapters.py
```
**结果**: `No secrets found`

```bash
# restricted module 触碰检查
git diff --name-only origin/epic/...HEAD -- \
  src/risk_engine/ src/execution_engine/ src/stock_pool/ \
  src/strategy_engine/ src/backtest_engine/ src/data_gateway/
```
**结果**: 无任何 diff — 未触碰受限模块

## 团队计划 Tester Checks 逐项验证

| # | 检查项 | 验证方式 | 结果 |
|---|--------|----------|------|
| 1 | `ProviderRegistry.select` 返回空列表于未知条件 | `test_select_no_match_returns_empty`, `test_select_empty_registry_returns_empty` | PASS |
| 2 | 返回按 priority 排序 | `test_select_returns_sorted_by_priority` | PASS |
| 3 | adapter mock: valid → MarketQuote + quality_status=OK | `test_fetch_latest_quote_returns_market_quote`, `test_fetch_latest_quote_quality_metadata` | PASS |
| 4 | 空 DataFrame/失败 → MarketDataUnavailableError | `test_fetch_latest_quote_raises_on_empty_data`, `test_fetch_latest_quote_raises_on_failed_status` | PASS |
| 5 | is_fallback 随 priority 正确 | `test_fallback_priority_sets_is_fallback` (priority=2 → is_fallback=True) | PASS |
| 6 | 多标的: 全部成功场景 | `test_fetch_latest_quotes_all_succeed` (两adapter各1) | PASS |
| 7 | adapter 不暴露 provider-specific raw response | 代码审查 — MarketQuote 仅含标准化字段 | PASS |
| 8 | 未修改 src/data_gateway/ | git diff 确认 0 变更 | PASS |
| 9 | 未 import raw provider 到 src/api/ | git diff 确认 Phase 2 未新增 api/ 文件 | PASS |
| 10 | `fetch_bars` 抛 NotImplementedError | `test_fetch_bars_not_implemented` | PASS |
| 11 | `request_id` 每次调用唯一 | `test_request_id_unique_per_call` | PASS |

## 测试覆盖详细统计

### 正常路径 (normal paths)：全部覆盖
- ProviderRegistry 单/多注册、按 market/asset_type/endpoint/granularity 过滤、priority 排序
- EastmoneyRealtimeAdapter 单标的/多标的正常返回
- AkShareRealtimeAdapter 单标的/多标的正常返回
- DataQualityMetadata 字段完整性、is_fallback 标记、request_id 唯一性

### 负向路径 (negative paths)：覆盖
- 空 registry select → `[]`
- 无匹配 select → `[]`
- 空 DataFrame → `MarketDataUnavailableError`
- 失败 status → `MarketDataUnavailableError`
- 抽象基类不可直接实例化 → `TypeError`
- `fetch_bars` 未实现 → `NotImplementedError`

### 负向路径缺口（合理，属于后续阶段）
- 部分多标的失败（item_errors 填充）— Phase 3 Relay 范围
- `fallback_allowed=False` 过滤 — Phase 3 Relay 范围
- provider timeout/网络异常 → error_mapping — Phase 3 Relay 范围
- risk_sensitive_allowed 阻断 — Phase 3 Relay 范围

## 缺陷列表

无 S0/S1/S2/S3 缺陷发现。

## feedback bug 文件

无缺陷，未生成 feedback bug 文件。

## 剩余风险

1. **缺失 socksio 环境依赖**：环境缺少 `socksio` 包导致 `AkToolsProvider` 测试（`test_aktools_provider_fetches_realtime_quotes_from_http_mapping`）无法运行。为预存在环境问题，不影响 Phase 2 交付。建议运维安装 `httpx[socks]`。

2. **`fetch_bars` 未实现**：Phase 3 需补齐。Phase 2 合理推迟，已用 `NotImplementedError` 显式标注。

3. **`SelectedProvider.adapter` 类型为 `Any`**：Phase 3 设置 adapter 实例时需确保类型安全。

4. **多标的部分失败场景未覆盖**：当前 adapter 采用全量成功或全量失败的简化模型。Phase 3 Relay 需实现单标的级别的 item_errors 和 summary 逐项计数。

5. **仅 mock 测试，无真实 provider 集成**：按架构要求，真实 provider smoke test 属于 acceptance 范围。

## Safety Confirmation

| 检查项 | 结果 |
|--------|------|
| 是否新增真实交易能力 | 否 |
| 是否绕过 risk | 否 |
| 是否绕过 stock-pool filtering | 否 |
| 是否绕过 human confirmation | 否 |
| 是否绕过 Provider Contract | 否（adapter 严格使用 Phase 1 contract 模型） |
| 是否绕过 Tool Registry | 否（本功能不涉及 Tool Registry） |
| 是否绕过 fail-closed behavior | 否（空数据/失败显式抛 `MarketDataUnavailableError`） |
| 是否泄露 secret | 否（代码中无 secret 处理路径，grep 验证通过） |
| 是否修改受限模块 | 否（`src/risk_engine/`、`src/execution_engine/`、`src/stock_pool/`、`src/strategy_engine/`、`src/backtest_engine/`、`src/data_gateway/` 均无变更） |
| Streamlit 是否被标记 legacy/deprecated | 否 |
| 是否新增 /api/** 并行前缀 | 否 |
| 产品 API 是否位于 /product/** | 是（Phase 2 不新增 API 路由，Phase 1 验证通过） |
| 是否包含 normal 和 negative tests | 是（10 normal + 6 negative 覆盖） |

## 最终结论

**PASS**

- 28/28 Phase 2 测试通过（与开发报告一致）
- 126/126 Phase 1+2 组合测试全绿
- 17/17 既有调用面回归通过（1 个预存在环境依赖 skip）
- ruff 0 errors, py_compile 通过
- 无 secret 泄露
- 未触碰受限模块
- 所有 Safety Confirmation 项均为"否"
- 团队计划 Tester Checks 11/11 项通过
- 向下游路由回 OpenCode Developer 执行 Phase 3
