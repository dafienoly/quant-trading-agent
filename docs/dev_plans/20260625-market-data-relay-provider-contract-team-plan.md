# Team Plan: Market Data Relay & Provider Contract — 统一行情 Relay、Provider 契约与数据质量门禁

> **给执行 Agent：** 本计划由 OpenCode Team Leader（`claude_lead_plan` 阶段，运行时 `opencode-go/glm-5.2` + superpowers）产出，按阶段串行执行。每个阶段由 OpenCode Developer（`claude_developer`，运行时 `opencode-go/deepseek-v4-flash`，`variant=max`，build Agent + superpowers）实现并自测，再由 OpenCode Test Engineer（`claude_tester`，运行时 `opencode-go/deepseek-v4-pro`，`variant=max` + superpowers）在临时 `test/...` 分支验证。任一阶段测试通过后路由回 OpenCode Developer 执行下一阶段，直到全部阶段完成。阶段顺序不得跳跃。

**Goal:** 为产品级行情数据访问建设统一、可审计、可治理的 Market Data Relay 与 Provider Contract，使 `/product/**` 工作流、Streamlit Dashboard 与未来 AgentOps/Risk Sentinel/Alpha/回测/position sizing/paper trading 均通过受控入口获取行情，并明确每次响应的来源、freshness、quality_status、fallback 状态与失败原因。

**Architecture:** `docs/design/2026-06-25-market-data-relay-provider-contract-architecture.md`（流水线 `required_docs.architecture` 记录为 `docs/design/20260625-...`，命名差异见下文“Repo Findings”第 6 条；gate 以 glob 兼容两种命名，已 PASS）。

**Tech Stack:** 后端 Python 3.10+ / FastAPI / Pydantic / loguru；前端沿用当前 Streamlit Dashboard（不引入 React）。复用既有 `src/data_gateway/` provider 实现、`DataProviderHub`、`ProviderCircuitBreaker`、`LiveDataService`，不重写。

## Inputs Reviewed

| Document | Path |
|---|---|
| Requirements | `docs/requirements/2026-06-25-market-data-relay-provider-contract-requirements.md` |
| Architecture | `docs/design/2026-06-25-market-data-relay-provider-contract-architecture.md` |
| Root AGENTS | `AGENTS.md` |
| Design AGENTS | `docs/design/AGENTS.md` |
| Agent Pipeline | `docs/process/AGENT_DEVELOPMENT_PIPELINE.md` |
| Branch Workflow | `docs/process/BRANCH_WORKFLOW.md` |
| Automation Architecture | `docs/pipeline/AGENT_AUTOMATION_ARCHITECTURE.md` |
| Auto Merge Policy | `docs/pipeline/AUTO_MERGE_POLICY.md` |
| Current task state | `.agent/current_task.yaml` / `.agent/state.json` |
| 前序团队计划（结构模板） | `docs/dev_plans/20260624-agentops-control-tower-foundationpipeline-api-re-team-plan.md` |

## Repo Findings by Team Leader

Leader 在拆分前已确认仓库现状，以下结论直接影响阶段划分与文件路径，Developer 不得偏离：

1. **新模块路径与既有 flat 文件冲突（关键）**：架构建议新增 `src/product_app/market_data/` 子包，但仓库已存在 flat 文件 `src/product_app/market_data.py`（221 行，产品级行情 facade，含 `fetch_product_quotes`、`build_realtime_provider`、`parse_symbols`、`default_symbols`、`is_trading_hours`、`now_text`、`records_from_frame`、`demo_quote_records`、`write_data_feedback`）。Python 中 `market_data.py` 与 `market_data/__init__.py` 不能稳定共存。**本计划采用架构指定路径**：Phase 1 创建 `src/product_app/market_data/` 子包，将既有 flat 文件内容迁移到 `src/product_app/market_data/legacy_facade.py`，删除 flat `market_data.py`，并由 `__init__.py` 重新导出全部既有公开符号以保证向后兼容。
2. **既有调用方必须不破坏（迁移面）**：`from src.product_app.market_data import ...` 的调用方包括 `src/api/product_routes.py`（`default_symbols`、`fetch_product_quotes`、`parse_symbols` 及两处内联 import）、`src/product_app/service_manager.py`（`fetch_product_quotes`）、`src/product_app/live_signal_orchestrator.py`（`fetch_product_quotes`），以及测试 `tests/test_product_market_data.py`、`tests/test_realtime_provider.py`、`tests/test_v16_0b_readonly_market_dashboard.py`、`tests/test_product_service_manager_quotes.py`。`__init__.py` 必须重新导出这些符号；Phase 1 必须运行这些既有测试证明零回归。
3. **既有 Provider 契约/调度层已存在，复用不重写**：`src/data_gateway/provider_contracts.py` 已定义 `DataCapability`（枚举）、`ProviderResult`（dataclass，含 `fallback_chain`）、`ProviderHealth`（dataclass）、`LiveDataProvider`（Protocol）。`src/data_gateway/provider_hub.py` 已实现 `DataProviderHub.fetch_with_fallback()`（按优先级尝试、空数据/缺字段降级、全失败返回 `status="failed"`）与 `ProviderCircuitBreaker`（closed/open/half_open）。`src/product_app/live_data_service.py`（748 行）是既有产品数据入口，含 provider hub 构建、熔断、demo fallback、fail-closed、Feedback Bug 写入。**本计划在产品层新增 Provider Contract / 质量门禁 / Relay，包装并复用上述既有设施，不修改 `src/data_gateway/` provider 实现**（见 Safety 第 4 条）。
4. **API 路由为 flat 结构（非嵌套）**：`src/api/` 下无 `routes/product/` 子目录，既有路由为 `src/api/product_routes.py`（单 `APIRouter`，已注册 `prefix="/product"`）与 `src/api/agentops_routes.py`（`prefix="/product/agentops"`）。架构建议的 `src/api/routes/product/market_data.py` 与仓库约定不符。**本计划采用 flat 路由 `src/api/market_data_routes.py`**，在 `src/api/app.py:create_app()` 内以 `app.include_router(market_data_router, prefix="/product/market", tags=["market"])` 注册，与 `agentops_routes.py` 完全同模式。
5. **既有产品行情端点（共存，本功能不删除）**：`src/api/product_routes.py` 已有 `GET /product/quotes`、`GET /product/quotes-snapshot`、`POST /product/quote-refresh`、`GET /product/quote-health`、`GET /product/live-data/providers`、`GET /product/live-data/diagnose`、`GET /product/live-data/quotes`。架构 §5 将 LiveDataService→Relay 的统一视为“中期”目标。**本计划新增 `/product/market/**` 命名空间为增量，不删除/不改写既有 `/product/quotes`、`/product/live-data/*` 端点**；既有端点的迁移属非目标。
6. **日期命名约定**：`docs/requirements`、`docs/design`、`docs/dev_plans` 实际文件使用 `2026-06-25`（带分隔符）；`docs/dev_reports`、`docs/test_reports`、`docs/review`、`docs/acceptance` 报告使用 `20260625`（无分隔符），与 `.agent/state.json` 的 `required_docs` 一致。`pm_gate.json` / `architecture_gate.json` 以 glob 匹配，对两种命名均兼容且已 PASS。本团队计划文件按 handoff 指定为 `docs/dev_plans/20260625-market-data-relay-provider-contract-team-plan.md`；各阶段 dev/test 报告使用 `20260625-...-phase-<n>-...` 无分隔符命名。
7. **测试为 flat 结构**：仓库测试为 `tests/test_*.py`（如 `tests/test_product_market_data.py`、`tests/test_live_data_service.py`、`tests/test_realtime_provider.py`），不存在 `tests/product_app/` 或 `tests/api/` 子目录。本计划测试文件采用 flat 命名。
8. **Streamlit 仍是有效入口**：`src/ui_report/product_dashboard.py`（38KB，含 `render_market()`、`render_live_data()`、`render_system()`）已展示 provider/quote。`src/ui_report/agentops_control_tower.py` 为前序 V16.1 产物。本功能新增 `src/ui_report/market_data_health.py` 并在 dashboard 最小化接线，不标记 Streamlit 为 legacy/deprecated/待删除。

## Scope

1. 新增 `src/product_app/market_data/` 子包：contracts / quality / errors / provider_registry / adapters / relay / audit / health / cache / legacy_facade。
2. 定义 Provider Contract、DataQualityMetadata、MarketQuote/MarketBar、QualityStatus 枚举、错误映射、secret 脱敏。
3. 实现数据质量门禁：按 caller_context（research_readonly / dashboard_observability / signal_generation / real_trading）分层阻断 stale/mock/demo/fallback/invalid/unavailable。
4. 实现 MarketDataRelay：provider 选择、timeout、fallback、response mapping、quality gate、audit、health 记录、fail-closed。
5. 新增 `/product/market/**` 产品 API（latest/bars/providers health/quality/fallback），与既有 `/product/quotes`、`/product/live-data/*` 共存。
6. 新增 Streamlit 行情可观测页面：Provider Health / Data Quality / Fallback Status / Recent Errors，区分 OK/STALE/DEGRADED/FALLBACK/UNAVAILABLE/MOCK/DEMO。
7. 每阶段产出中文 dev/test 报告，最终回归与文档齐备。

## Non-Goals

- 不新增真实交易、模拟交易、纸面交易或任何下单/撤单/审批入口；不触碰 `src/execution_engine/`、`src/risk_engine/` 真实下单/风控语义、`src/stock_pool/` 禁止规则、`LEVEL_3_AUTO` 暴露逻辑。
- 不修改 `src/data_gateway/` 既有 provider 实现（`akshare_provider.py`、`aktools_provider.py`、`eastmoney_provider.py`、`realtime_provider.py`、`provider_hub.py`、`provider_contracts.py`、`live_data_mapper.py`、`column_mapper.py`）；新 adapter 位于产品层包装既有 provider。若实现中发现必须修改 data_gateway provider，立即停止并升级为 restricted-module 变更（人工审批 + 架构复审 + 负向测试）。
- 不删除/不改写既有 `/product/quotes`、`/product/quotes-snapshot`、`/product/quote-refresh`、`/product/quote-health`、`/product/live-data/*` 端点；既有端点向 Relay 的迁移是中期目标，本功能只做增量。
- 不把 `LiveDataService` 标记为 deprecated；Relay 与 LiveDataService 共存，LiveDataService 继续作为兼容层。
- 不引入 React/Vite/TypeScript 前端基线；UI 沿用 Streamlit。
- 不新增 `/api/**`、`/market/**` 等未批准平行业务前缀。
- 不把 mock/demo/fixture/cache/stale/fallback/shadow 数据表现为真实 live 数据。
- 不自动合并 main，不执行 `git commit/push/merge`（GitHub Stage Runner 管理提交）。

## Safety Constraints（全阶段适用）

1. **不新增真实交易能力**：不得新增真实 order path、不得绕过 risk 一票否决、不得绕过人工确认、不得让 LLM 写入 buy/sell/order/position 字段。本功能仅提供数据质量可信入口，不提供交易许可。
2. **fail-closed**：`quality_status` 为 `STALE`/`UNAVAILABLE`/`INVALID`/`MOCK`/`DEMO` 不得进入 signal/real_trading/position_sizing 路径；`FALLBACK`/`DEGRADED` 默认不进入 risk-sensitive workflow（除非未来架构明确批准）；provider 全失败必须返回 `MarketDataUnavailableError` 结构化错误，不得伪装成功。
3. **Provider 边界**：`strategy_engine`、`signal generation`、`product API routes`、`risk_engine`、`execution_engine`、`model gateway`、`decision snapshot`、`position sizing`、`backtest product workflow`、`risk sentinel`、`alpha workflow`、`paper trading`、`broker shadow` 不得直接调用 raw provider；必须经 `MarketDataRelay`/`LiveDataService`/架构批准的产品服务。本计划新增的 `/product/market/**` 路由只依赖 Relay，不 import raw provider。
4. **不触碰 restricted modules（默认）**：`src/risk_engine/`、`src/execution_engine/`、`src/stock_pool/`、`src/backtest_engine/`、`src/strategy_engine/`、`src/factor_engine/` 一律不修改、不引入依赖。`src/data_gateway/` 既有文件不修改（新 adapter 在产品层包装）。`src/api/app.py` 仅追加一行 router 注册。如必须触碰，立即停止并升级为 restricted-module 变更。
5. **Secret 保护**：所有 provider secret 来自环境变量；审计事件、错误响应、health、Dashboard、dev/test/review/acceptance 报告一律脱敏。脱敏覆盖 `api_key`/`apikey`/`token`/`cookie`/`secret`/`authorization`/`auth`/`password`/broker credential；错误响应只保留 `request_id`、`error_code`、`quality_status`、`safe_reason`、`provider_attempt_count`、`fallback_used`，不含原始 auth header/`.env`/完整 raw response。
6. **不暴露 `LEVEL_3_AUTO`** 为普通用户可选项。
7. **不自动合并 main**，不执行 `git commit/push/merge`（GitHub Stage Runner 管理提交）； Tester 在临时 `test/...` 分支验证，结束回到原分支并删除临时分支，不在原开发分支改业务代码。
8. **不得删除/弱化/跳过失败测试**来制造通过；不得用 mock/demo/stale/fallback 冒充 live；所有核心行为变更必须有测试证据。

## Global Constraints

- Python 3.10+；静态检查 `ruff`（配置 `pyproject.toml`）与 `py_compile`。
- 测试 `pytest`；外部 provider 必须在单元/API 测试中 mock，确定性测试不依赖真实网络。
- API 测试用 `fastapi.testclient.TestClient`，目标 `src.api.app.create_app`（或 `app`）。触及共享 API entrypoint（`src/api/app.py`）须追加更广回归。
- 测试隔离：统一传 `--basetemp=runtime/pytest-tmp-market-data-relay-provider-contract`（广回归用 `...-full`）。
- 运行环境若无 `.venv/bin/python`，记录并以 `python3` 等效运行；报告中写明实际命令与结果。
- 代码标识、JSON key、环境变量、第三方术语保留英文；用户可见输出与新增文档默认中文。
- 所有新 Pydantic 模型使用 `from __future__ import annotations`；`Decimal` 用于价格字段；`datetime` 使用 aware datetime（UTC 或带 tz），时区/单位在 contracts 中明确。

## Pipeline 状态与阶段映射

- 架构文档建议“拆分为 1 个主阶段，内部按 slice A–E 执行：Phase 1: Market Data Relay & Provider Contract Foundation”。
- 本计划将该“Phase 1（Foundation）”拆分为 **5 个有序交付阶段**（team plan Phase 1–5），每个交付阶段对应一个独立的 dev→test 循环，并产出 `docs/dev_reports/20260625-market-data-relay-provider-contract-phase-<n>-dev-report.md` 与 `docs/test_reports/20260625-market-data-relay-provider-contract-phase-<n>-test-report.md`。
- 阶段↔slice 映射：**Phase 1 ↔ Slice A（schema/contract/quality/errors + 子包基线与 legacy 迁移）；Phase 2 ↔ Slice B（provider registry + adapter）；Phase 3 ↔ Slice C（relay + audit + health + cache）；Phase 4 ↔ Slice D（/product/market/** API）；Phase 5 ↔ Slice E（Streamlit observability）**。
- `.agent/state.json` 当前 `team_pipeline.total_phases=1`（CLI 默认）。本计划定义 5 个交付阶段；Stage Runner/CLI 在处理本计划时应将 `total_phases` 同步为 5。**Lead 不直接修改 `.agent/state.json`**（GitHub Stage Runner 管理提交与状态）。无论 state 中 `total_phases` 为何值，Developer/Test Engineer 严格按本计划“Gate after phase”路由：每阶段测试通过后路由回 OpenCode Developer 执行下一阶段，直至 Phase 5 测试通过。
- 任一阶段 Test Engineer 结论为 `REJECTED` → 路由回 OpenCode Developer 修复（`fix/market-data-relay/phase-<n>-<issue>` 分支），修复后重测，不跳阶段。

---

## Proposed Phases

### Phase 1 — 子包基线 + Schema/Contract/Quality/Errors（Slice A）

| Field | Value |
|---|---|
| **Scope** | 创建 `src/product_app/market_data/` 子包：将既有 flat `src/product_app/market_data.py` 迁移为 `src/product_app/market_data/legacy_facade.py`，删除 flat 文件，由 `__init__.py` 重新导出全部既有公开符号（零回归）。新增 `contracts.py`（QualityStatus 枚举、ProviderErrorCategory 枚举、AuthRequirement/RateLimitPolicy/TimeoutPolicy/FreshnessPolicy/CachePolicy/FallbackEligibility、MarketDataProviderContract、DataQualityMetadata、MarketQuote、MarketBar、ProviderAttempt、MultiSymbolQuoteResult）、`quality.py`（QualityGate + 质量评估器：stale/mock/demo/fallback 判定 + 按 caller_context 分层门禁）、`errors.py`（MarketDataUnavailableError + 错误映射 + safe_error_summary + secret 脱敏 helper）。先写失败测试再实现最小代码。 |
| **Non-Goals** | 不新增 provider registry/adapter（Phase 2）；不新增 Relay/audit/health/cache（Phase 3）；不新增 API 路由（Phase 4）；不新增 UI（Phase 5）；不修改 `src/data_gateway/`；不删除既有 `/product/quotes` 端点。 |
| **Owner** | OpenCode Developer（`claude_developer`，`opencode-go/deepseek-v4-flash`，`variant=max`，build Agent + superpowers） |
| **Branch** | `feat/market-data-relay/phase-1-contracts`（自 epic 分支） |
| **Restricted modules** | 不触碰任何受限模块。仅 `src/product_app/market_data/` 新建 + flat 文件迁移；`__init__.py` 兼容 re-export。触及既有 market_data 调用面，须跑既有 market_data 测试回归。 |
| **Dev report** | `docs/dev_reports/20260625-market-data-relay-provider-contract-phase-1-dev-report.md` |
| **Test report** | `docs/test_reports/20260625-market-data-relay-provider-contract-phase-1-test-report.md` |

**Files:**
- Create: `src/product_app/market_data/__init__.py`（re-export `fetch_product_quotes`、`build_realtime_provider`、`parse_symbols`、`default_symbols`、`is_trading_hours`、`now_text`、`records_from_frame`、`demo_quote_records`、`write_data_feedback`，并导出新 contracts/quality/errors 公开符号）
- Create: `src/product_app/market_data/legacy_facade.py`（由 flat `market_data.py` 原文迁移，逻辑不变）
- Delete: `src/product_app/market_data.py`（flat 文件，内容已迁入 `legacy_facade.py`）
- Create: `src/product_app/market_data/contracts.py`
- Create: `src/product_app/market_data/quality.py`
- Create: `src/product_app/market_data/errors.py`
- Create: `tests/test_market_data_contracts.py`
- Create: `tests/test_market_data_quality.py`
- Create: `tests/test_market_data_errors.py`

**Interfaces（契约形状，字段名严格对齐架构 §2/§3/§4/§7）:**
- 枚举 `QualityStatus`：`OK`/`STALE`/`DEGRADED`/`FALLBACK`/`UNAVAILABLE`/`INVALID`/`MOCK`/`DEMO`（str 枚举）。
- 枚举 `ProviderErrorCategory`：`AUTH_FAILED`/`RATE_LIMITED`/`TIMEOUT`/`NETWORK_ERROR`/`EMPTY_RESPONSE`/`MALFORMED_RESPONSE`/`MISSING_FIELD`/`INVALID_VALUE`/`STALE_DATA`/`PROVIDER_UNAVAILABLE`/`UNKNOWN_PROVIDER_ERROR`（str 枚举）。
- `MarketDataProviderContract(BaseModel)`：`provider_id`、`provider_name`、`market_scope: list[str]`、`supported_asset_types: list[str]`、`supported_granularities: list[str]`、`supported_endpoints: list[str]`、`auth_requirement: AuthRequirement`、`rate_limit_policy: RateLimitPolicy`、`timeout_policy: TimeoutPolicy`、`freshness_policy: FreshnessPolicy`、`cache_policy: CachePolicy`、`fallback_eligibility: FallbackEligibility`、`quality_status_mapping: dict[str, QualityStatus]`、`error_mapping: dict[str, ProviderErrorCategory]`。
- `DataQualityMetadata(BaseModel)`：`source_provider`、`source_priority: int`、`as_of: datetime`、`received_at: datetime`、`freshness_seconds: float`、`is_stale: bool`、`is_realtime: bool`、`is_demo: bool`、`is_mock: bool`、`is_fallback: bool`、`quality_status: QualityStatus`、`quality_reason: str`、`provider_latency_ms: float | None`、`request_id: str`。
- `MarketQuote(BaseModel)`：`symbol`、`market`、`asset_type`、`price: Decimal | None`、`open/high/low/previous_close: Decimal | None = None`、`volume: int | None = None`、`currency: str | None = None`、`quality: DataQualityMetadata`。
- `MarketBar(BaseModel)`：`symbol`、`market`、`granularity`、`timestamp: datetime`、`open/high/low/close: Decimal`、`volume: int | None`、`quality: DataQualityMetadata`。
- `ProviderAttempt(BaseModel)`：`provider_id`、`priority: int`、`error_category: ProviderErrorCategory | None`、`quality_status: QualityStatus | None`、`latency_ms: float | None`、`safe_reason: str`。
- `MultiSymbolQuoteResult(BaseModel)`：`results: list[MarketQuote]`、`item_errors: list[ItemError]`、`summary: {total, ok_count, failed_count, degraded_count, fallback_count}`、`request_quality: QualityStatus`、`request_id: str`。
- `QualityGate`：`blocks(quality: DataQualityMetadata, caller_context: CallerContext) -> bool`，行为严格对齐架构 §7 伪代码（UNAVAILABLE/INVALID 恒阻断；signal/real_trading/position_sizing 阻断 stale/mock/demo/fallback/非 OK；`allow_demo=False` 阻断 demo；`allow_mock=False` 阻断 mock）。
- `CallerContext`：`name: str`（`research_readonly`/`dashboard_observability`/`signal_generation`/`real_trading`/`position_sizing`）、`allow_demo: bool=False`、`allow_mock: bool=False`。
- `MarketDataUnavailableError(Exception)`：携带 `request_id`、`safe_reason`、`provider_attempts: list[ProviderAttempt]`、`fallback_used: bool`、`quality_status`；`__str__` 只输出安全摘要。
- `redact_secret(value: str) -> str`、`safe_error_summary(attempts) -> str`：覆盖 `api_key/apikey/token/cookie/secret/authorization/auth/password`。

**Self-test commands:**
```bash
git status --short --branch
git diff --stat
./.venv/bin/python -m ruff check src/product_app/market_data tests/test_market_data_contracts.py tests/test_market_data_quality.py tests/test_market_data_errors.py
./.venv/bin/python -m py_compile src/product_app/market_data/*.py
./.venv/bin/python -m pytest tests/test_market_data_contracts.py tests/test_market_data_quality.py tests/test_market_data_errors.py -q --basetemp=runtime/pytest-tmp-market-data-relay-provider-contract
# 迁移既有 flat 文件 → 既有调用面零回归：
./.venv/bin/python -m pytest tests/test_product_market_data.py tests/test_realtime_provider.py tests/test_v16_0b_readonly_market_dashboard.py tests/test_product_service_manager_quotes.py tests/test_quote_health.py -q --tb=short --basetemp=runtime/pytest-tmp-market-data-relay-provider-contract-legacy-regression
git diff --check
```

**Tester checks（OpenCode Test Engineer，临时 `test/market-data-relay/phase-1-<tester>-<timestamp>` 分支）:**
- 重跑 Developer 报告中的命令并比对结果；建立 requirement→test 覆盖矩阵（覆盖需求 §2 Contract、§3 数据质量字段、§4 Fail-closed、Safety §2/§5）。
- `QualityStatus`/`ProviderErrorCategory` 枚举值与架构 §4/§7 完全一致。
- `QualityGate.blocks()` 覆盖：UNAVAILABLE/INVALID 恒阻断；signal_generation 下 stale/mock/demo/fallback/非 OK 全阻断；`allow_demo=False` 阻断 demo；`allow_mock=False` 阻断 mock；research_readonly 允许 OK/DEGRADED/FALLBACK 但需可读 quality_status。
- `MarketDataUnavailableError` 序列化/`str` 不含 secret、auth header、完整 raw response。
- `redact_secret` 对 8 类敏感词均替换为 `<redacted>`；`safe_error_summary` 不泄露 provider 私密 detail。
- **零回归**：既有 `from src.product_app.market_data import fetch_product_quotes ...` 全部可用；`tests/test_product_market_data.py`、`tests/test_realtime_provider.py`、`tests/test_v16_0b_readonly_market_dashboard.py`、`tests/test_product_service_manager_quotes.py`、`tests/test_quote_health.py` 全绿。
- 验证 flat `src/product_app/market_data.py` 已删除、`legacy_facade.py` 存在、`__init__.py` re-export 完整（grep 调用方 import 不断）。
- 验证未触碰 restricted modules（grep `src/data_gateway/`、`src/risk_engine/`、`src/execution_engine/` 无 diff）。

**Release criteria:**
- 上述 pytest 全绿；`ruff`、`py_compile` 通过。
- 契约字段/枚举与架构 §2/§3/§4 一致；`MarketDataProviderContract` 13 字段齐备；`DataQualityMetadata` 14 字段齐备。
- fail-closed 与 secret 脱敏有测试证据；无未解释的 skipped/xfail/mock 真实网络。
- 既有 market_data 调用面零回归（5 个既有测试文件全绿）。
- 中文 dev report 含变更范围/测试命令/结果/安全确认（8 项安全问答全“否”于“是否绕过…”）/最终结论。
- 测试报告结论为 `PASS` 或 `PASS_WITH_NOTES` 且无 S0/S1/S2 阻断。

**Gate after phase:** 测试通过后路由回 OpenCode Developer 执行 Phase 2。

---

### Phase 2 — Provider Registry + Adapter（Slice B）

| Field | Value |
|---|---|
| **Scope** | 新增 `src/product_app/market_data/provider_registry.py`：`ProviderRegistry` 按 (market, asset_type, endpoint, granularity) 选择有序 provider 列表，读取 `MarketDataProviderContract` 的 priority 与 `fallback_eligibility`。新增 `src/product_app/market_data/adapters.py`：至少一个 adapter 包装既有 provider（推荐 `EastmoneyRealtimeAdapter` 包装 `src/data_gateway/eastmoney_provider.EastmoneyProvider` 与 `AkShareRealtimeAdapter` 包装 `src/data_gateway/realtime_provider.AkShareRealtimeProvider`），通过既有 `DataProviderHub.fetch_with_fallback()` 获取 `ProviderResult`，再映射为带 `DataQualityMetadata` 的 `MarketQuote`/`MarketBar`。adapter 不修改 `src/data_gateway/`，只在产品层持有 provider 实例并复用 hub。 |
| **Non-Goals** | 不实现 Relay 编排/fail-closed 总入口（Phase 3）；不新增 API（Phase 4）；不新增 UI（Phase 5）；不修改 `src/data_gateway/` provider 实现；不接入真实网络（测试全 mock）。 |
| **Owner** | OpenCode Developer |
| **Branch** | `feat/market-data-relay/phase-2-registry-adapter`（自 epic 分支，merge Phase 1 后） |
| **Restricted modules** | 不触碰受限模块。新文件仅在 `src/product_app/market_data/`。adapter 通过既有 hub 调用 provider，不 import raw provider 到 product route（adapter 是产品层内部组件，由 Relay 在 Phase 3 统一对外）。 |
| **Dev report** | `docs/dev_reports/20260625-market-data-relay-provider-contract-phase-2-dev-report.md` |
| **Test report** | `docs/test_reports/20260625-market-data-relay-provider-contract-phase-2-test-report.md` |

**Files:**
- Create: `src/product_app/market_data/provider_registry.py`
- Create: `src/product_app/market_data/adapters.py`
- Create: `tests/test_market_data_provider_registry.py`
- Create: `tests/test_market_data_adapters.py`

**Interfaces:**
- Consumes: Phase 1 的 `MarketDataProviderContract`、`DataQualityMetadata`、`MarketQuote`、`MarketBar`、`QualityStatus`、`ProviderErrorCategory`；既有 `src.data_gateway.provider_hub.DataProviderHub`、`ProviderCircuitBreaker`、`src.data_gateway.provider_contracts.DataCapability`/`ProviderResult`。
- Produces:
  - `ProviderRegistry.register(contract: MarketDataProviderContract, priority: int, fallback_allowed: bool, risk_sensitive_allowed: bool) -> None`
  - `ProviderRegistry.select(market: str, asset_type: str, endpoint: str, granularity: str | None = None) -> list[SelectedProvider]`（按 priority 升序；`SelectedProvider` 含 `contract`、`priority`、`fallback_allowed`、`risk_sensitive_allowed`、`adapter`）。
  - `MarketDataAdapter`（抽象基类）：`contract: MarketDataProviderContract`、`fetch_latest_quote(symbol: str, timeout: float | None) -> MarketQuote`、`fetch_latest_quotes(symbols: list[str], timeout) -> MultiSymbolQuoteResult`、`fetch_bars(symbol, granularity, start, end, timeout) -> list[MarketBar]`。
  - `EastmoneyRealtimeAdapter(MarketDataAdapter)` / `AkShareRealtimeAdapter(MarketDataAdapter)`：内部持有既有 provider 实例 + `DataProviderHub`，将 `ProviderResult`（DataFrame）经既有 `live_data_mapper` 映射后封装为 `MarketQuote`，并计算 `DataQualityMetadata`（`source_provider`、`source_priority`、`is_fallback=(priority!=1)`、`quality_status`、`request_id`、`freshness_seconds`、`provider_latency_ms`）。
- adapter 必须在 `ProviderResult.status=="failed"` 或空数据时抛 `MarketDataUnavailableError`（携带 attempts），不得返回伪成功。

**Self-test commands:**
```bash
git status --short --branch
git diff --stat
./.venv/bin/python -m ruff check src/product_app/market_data/provider_registry.py src/product_app/market_data/adapters.py tests/test_market_data_provider_registry.py tests/test_market_data_adapters.py
./.venv/bin/python -m py_compile src/product_app/market_data/provider_registry.py src/product_app/market_data/adapters.py
./.venv/bin/python -m pytest tests/test_market_data_provider_registry.py tests/test_market_data_adapters.py -q --basetemp=runtime/pytest-tmp-market-data-relay-provider-contract
git diff --check
```

**Tester checks:**
- `ProviderRegistry.select` 按 priority 排序；`fallback_allowed=False` 的 provider 不作为 fallback 候选；未知 (market,asset_type,endpoint) 返回空列表（不抛裸异常）。
- adapter mock 既有 provider/hub：valid DataFrame → `MarketQuote` 且 `quality_status=OK`、`is_fallback` 随 priority 正确；空 DataFrame/`ProviderResult.status="failed"` → `MarketDataUnavailableError`（含 attempts/safe_reason），不伪成功。
- timeout/异常经 `error_mapping` 映射为 `ProviderErrorCategory`；`is_fallback=True` 时 `quality_status=FALLBACK`。
- 多标的：单 symbol 失败 → `item_errors` 记录，其余 symbol 正常，`summary` 计数正确。
- adapter 不直接暴露 provider-specific raw response 字段到 `MarketQuote`（无 provider 私有列）。
- 验证未修改 `src/data_gateway/`（grep diff）；未 import raw provider 到 `src/api/`。

**Release criteria:**
- 上述 pytest 全绿；`ruff`、`py_compile` 通过。
- 至少一个现有 provider 被纳入标准 Contract 且 response 被标准化（满足需求验收 §2）。
- adapter error mapping 稳定；timeout/empty/malformed 有明确结果。
- 中文 dev/test report 齐备；测试结论 `PASS`/`PASS_WITH_NOTES` 且无 S0/S1/S2 阻断。

**Gate after phase:** 测试通过后路由回 OpenCode Developer 执行 Phase 3。

---

### Phase 3 — Relay + Audit + Health + Cache（Slice C）

| Field | Value |
|---|---|
| **Scope** | 新增 `relay.py`：`MarketDataRelay` 统一编排 `get_latest_quote`/`get_latest_quotes`/`get_bars`，串联 registry.select → adapter fetch → quality 评估 → `QualityGate.blocks` → audit 记录 + health 记录；fallback 按 `fallback_allowed` 与 `error_mapping` 决定是否继续；全失败 fail-closed 抛 `MarketDataUnavailableError`。新增 `audit.py`：`MarketDataAuditEvent` + `AuditRecorder`（脱敏，记录 request_id/caller_context/endpoint/symbols/market/provider_selected/provider_attempts/fallback_used/quality_status/error_code/created_at/latency_ms）。新增 `health.py`：`ProviderHealthAggregator`（内存聚合 availability/last_success_at/last_failure_at/consecutive_failures/latency_p50_ms/latency_p95_ms/latency_last_ms/error_category_summary/circuit_breaker_status/fallback_activation_count/freshness_summary/updated_at），复用既有 `ProviderCircuitBreaker` 的熔断状态。新增 `cache.py`：显式缓存（`cache_hit`/`cache_created_at`/`cache_age_seconds`/`source_provider`/`quality_status`/`is_stale`），cache 超 `freshness_policy` 时 research_readonly 返回 STALE、signal/real_trading fail-closed。 |
| **Non-Goals** | 不新增 API 路由（Phase 4）；不新增 UI（Phase 5）；不实现持久化审计存储（本阶段内存，dev report 说明进程重启丢失）；不修改 `src/data_gateway/`；不接入真实网络。 |
| **Owner** | OpenCode Developer |
| **Branch** | `feat/market-data-relay/phase-3-relay-audit-health-cache`（自 epic 分支，merge Phase 2 后） |
| **Restricted modules** | 不触碰受限模块。新文件仅在 `src/product_app/market_data/`。Relay 是产品层新统一入口，与 `LiveDataService` 共存（不删除/不标记 deprecated）。 |
| **Dev report** | `docs/dev_reports/20260625-market-data-relay-provider-contract-phase-3-dev-report.md` |
| **Test report** | `docs/test_reports/20260625-market-data-relay-provider-contract-phase-3-test-report.md` |

**Files:**
- Create: `src/product_app/market_data/relay.py`
- Create: `src/product_app/market_data/audit.py`
- Create: `src/product_app/market_data/health.py`
- Create: `src/product_app/market_data/cache.py`
- Create: `tests/test_market_data_relay.py`
- Create: `tests/test_market_data_audit.py`
- Create: `tests/test_market_data_health.py`
- Create: `tests/test_market_data_cache.py`

**Interfaces:**
- Consumes: Phase 1 contracts/quality/errors；Phase 2 `ProviderRegistry`/`MarketDataAdapter`；既有 `ProviderCircuitBreaker`。
- Produces:
  - `MarketDataRelay(registry, health, audit, cache, quality_gate)`：`get_latest_quote(symbol, market, caller_context, allow_demo=False) -> MarketQuote`、`get_latest_quotes(symbols, market, caller_context, allow_demo=False) -> MultiSymbolQuoteResult`、`get_bars(symbol, market, granularity, start, end, caller_context) -> list[MarketBar]`。
  - `MarketDataAuditEvent(BaseModel)`（字段见上）；`AuditRecorder.record_success/record_fail_closed`，`redact` 覆盖 8 类敏感词。
  - `ProviderHealthAggregator.record_success(provider_id, latency_ms)`/`record_failure(provider_id, error_category)`/`snapshot() -> dict[str, ProviderHealthSummary]`；`circuit_breaker_status` 来自既有 `ProviderCircuitBreaker.is_open()`。
  - `MarketDataCache`：`get(key, freshness_policy, caller_context) -> CachedEntry | None`、`set(key, entry)`；`CachedEntry` 携带 `cache_hit/cache_created_at/cache_age_seconds/source_provider/quality_status/is_stale`；stale cache 在 signal/real_trading 触发 fail-closed。
- Relay 伪代码严格对齐架构 §6：`request_id=new_request_id()` → `registry.select(...)` → 循环 adapter.fetch → quality 评估（`is_fallback=(priority!=1)`）→ `quality_gate.blocks` 则 attempts.append 并 continue → 否则 audit.record_success + health.record_success + return quote_with_quality；异常经 error_mapping → attempts.append + health.record_failure + `fallback_policy.can_continue` 决定是否 break；循环结束 `audit.record_fail_closed` + raise `MarketDataUnavailableError`。

**Self-test commands:**
```bash
git status --short --branch
git diff --stat
./.venv/bin/python -m ruff check src/product_app/market_data/relay.py src/product_app/market_data/audit.py src/product_app/market_data/health.py src/product_app/market_data/cache.py tests/test_market_data_relay.py tests/test_market_data_audit.py tests/test_market_data_health.py tests/test_market_data_cache.py
./.venv/bin/python -m py_compile src/product_app/market_data/relay.py src/product_app/market_data/audit.py src/product_app/market_data/health.py src/product_app/market_data/cache.py
./.venv/bin/python -m pytest tests/test_market_data_relay.py tests/test_market_data_audit.py tests/test_market_data_health.py tests/test_market_data_cache.py -q --basetemp=runtime/pytest-tmp-market-data-relay-provider-contract
# 触及产品数据入口（虽新增不删旧），追加既有 live data 回归：
./.venv/bin/python -m pytest tests/test_live_data_service.py tests/test_quote_health.py -q --tb=short --basetemp=runtime/pytest-tmp-market-data-relay-provider-contract-relay-regression
git diff --check
```

**Tester checks:**
- valid quote / valid multi-symbol quote / valid bars：返回带 quality 的响应，`request_id` 唯一非空，audit/health 记录成功。
- timeout / empty / malformed / provider unavailable / auth failure：经 error_mapping → fallback（若允许）→ fallback 响应 `is_fallback=True`/`quality_status=FALLBACK`/`DEGRADED`；全失败 → `MarketDataUnavailableError`，`fallback_used`/`provider_attempts`/`safe_reason` 完整，不伪成功。
- **fail-closed**：`caller_context=signal_generation` 下 stale/mock/demo/fallback/非 OK 全阻断（抛错或返回 UNAVAILABLE，不进入下游）；`allow_demo=False` 下 demo 阻断。
- **risk-sensitive caller blocks fallback/stale/mock/demo**（需求验收 §5、§8）：有专门测试用例。
- audit 事件不含 secret/auth header/完整 raw response；`redact` 覆盖 8 类敏感词。
- health snapshot 字段齐备（availability/latency_p50/p95/last/consecutive_failures/circuit_breaker_status/fallback_activation_count/freshness_summary/updated_at）；`circuit_breaker_status` 与既有 `ProviderCircuitBreaker` 一致。
- cache：hit 返回 `cache_hit=True` + `cache_age_seconds`；超 `freshness_policy` 时 research_readonly 返回 STALE、signal/real_trading fail-closed；cache 不伪装为 live。
- 内存健康状态：dev report 说明进程重启丢失，不作长期审计存储。
- 验证未修改 `src/data_gateway/`、`src/risk_engine/`、`src/execution_engine/`（grep diff）。

**Release criteria:**
- 上述 pytest 全绿（含既有 live data 回归）；`ruff`、`py_compile` 通过。
- 需求验收 §3（数据质量字段）、§4（Fail-closed）、§5（Fallback）、§6（Provider Health）、§7（审计）均有测试证据。
- fallback 受控、显式标记；risk-sensitive 默认阻断不可信数据。
- 中文 dev/test report 齐备；测试结论 `PASS`/`PASS_WITH_NOTES` 且无 S0/S1/S2 阻断。

**Gate after phase:** 测试通过后路由回 OpenCode Developer 执行 Phase 4。

---

### Phase 4 — Product API `/product/market/**`（Slice D）

| Field | Value |
|---|---|
| **Scope** | 新增 `src/api/market_data_routes.py`（flat `APIRouter()`，与 `agentops_routes.py` 同模式），端点：`GET /product/market/latest/{symbol}`、`POST /product/market/latest`（body: symbols+market+caller_context+allow_demo）、`GET /product/market/bars/{symbol}`（query: granularity/start/end）、`GET /product/market/providers/health`、`GET /product/market/providers/quality`、`GET /product/market/providers/fallback`。在 `src/api/app.py:create_app()` 内 product/agentops router 注册后追加 `app.include_router(market_data_router, prefix="/product/market", tags=["market"])`。路由只依赖 `MarketDataRelay`（通过 route-level helper 获取单例，便于测试 mock），不 import raw provider。错误映射为 400/422/404/503/500 + 结构化 `error` 体（`request_id`/`error_code`/`quality_status`/`safe_reason`/`provider_attempt_count`/`fallback_used`）。 |
| **Non-Goals** | 不删除/不改写既有 `/product/quotes`、`/product/quotes-snapshot`、`/product/quote-refresh`、`/product/quote-health`、`/product/live-data/*`；不新增 `/api/**`、`/market/**` 平行前缀；不新增 UI（Phase 5）；不修改 `src/data_gateway/`。 |
| **Owner** | OpenCode Developer |
| **Branch** | `feat/market-data-relay/phase-4-product-api`（自 epic 分支，merge Phase 3 后） |
| **Restricted modules** | 仅改 `src/api/app.py`（追加一行 router 注册）与新增 `src/api/market_data_routes.py`；不触碰受限模块。**触及共享 API entrypoint，须跑更广回归**（AGENTS.md §9）。 |
| **Dev report** | `docs/dev_reports/20260625-market-data-relay-provider-contract-phase-4-dev-report.md` |
| **Test report** | `docs/test_reports/20260625-market-data-relay-provider-contract-phase-4-test-report.md` |

**Files:**
- Create: `src/api/market_data_routes.py`
- Modify: `src/api/app.py`（在 agentops router 注册后追加 market router 注册一行）
- Create: `tests/test_market_data_routes.py`

**Interfaces:**
- Consumes: Phase 3 `MarketDataRelay`（通过 `_get_market_data_relay()` route-level helper，单例，测试以 `patch("src.api.market_data_routes._get_market_data_relay")` mock，与 `product_routes._get_live_data_service` 同模式）。
- Produces: HTTP 端点；200 返回 `MarketQuote`/`MultiSymbolQuoteResult`/`list[MarketBar]`/health/quality/fallback dict；错误返回 `{"error": {"request_id","error_code","quality_status","safe_reason","provider_attempt_count","fallback_used"}}`。
- 路由聚合逻辑写入 `market_data_routes.py`，不塞入 `product_routes.py`（避免路由文件臃肿，遵循架构 §4）。

**Self-test commands:**
```bash
git status --short --branch
git diff --stat
./.venv/bin/python -m ruff check src/api/market_data_routes.py src/api/app.py tests/test_market_data_routes.py
./.venv/bin/python -m py_compile src/api/market_data_routes.py src/api/app.py
./.venv/bin/python -m pytest tests/test_market_data_routes.py -q --basetemp=runtime/pytest-tmp-market-data-relay-provider-contract-api
# 触及共享 API entrypoint，追加更广回归：
./.venv/bin/python -m pytest tests/test_product_routes.py tests/test_live_data_service.py tests/test_agentops_routes.py -q --tb=short --basetemp=runtime/pytest-tmp-market-data-relay-provider-contract-api-regression
# 若 broad checks 因历史无关问题失败，按 AGENTS.md §9 如实记录失败+无关性判断，并额外提供 touched-scope 通过证据
git diff --check
```

**Tester checks:**
- `GET /product/market/latest/{symbol}` 成功返回 `MarketQuote`（含完整 `quality` 字段）；`POST /product/market/latest` 返回 `MultiSymbolQuoteResult`（含 `summary`/`request_quality`/`item_errors`）；`GET /product/market/bars/{symbol}` 返回 `list[MarketBar]`。
- `GET /product/market/providers/health`/`/quality`/`/fallback` 返回 health/quality/fallback 摘要。
- 参数格式错误→`422`；invalid symbol→`400`/`404`；provider 全失败→`503` `MarketDataUnavailableError` 结构化体；内部异常→`500` 错误体不含 traceback/secret/绝对路径。
- **路由位于 `/product/**`**：遍历 `app.routes` 断言 `/product/market/*` 存在；**未新增 `/api/**`、`/market/**` 平行前缀**（断言无 `/api/market`、`/api/provider`、裸 `/market` 路由）。
- 错误响应含 `request_id` + `safe_reason`；不含 secret/auth header/完整 raw response。
- 数据质量字段完整（`source_provider`/`as_of`/`received_at`/`freshness_seconds`/`is_stale`/`is_demo`/`is_mock`/`is_fallback`/`quality_status`/`quality_reason`/`request_id`）。
- route mock relay：断言未调用 raw provider、未触发交易/风控/执行模块、未写 bug 文件。
- 现有 `/product/quotes`、`/product/live-data/*`、`/product/agentops/*` 路由回归无回归性失败。
- Streamlit 未被标记 legacy/deprecated/待删除（grep）。

**Release criteria:**
- 上述 pytest 全绿（含 API 回归）；`ruff`、`py_compile` 通过。
- HTTP 状态映射稳定；错误体经脱敏；数据质量字段完整。
- 现有 product/agentops 路由无回归性失败（若有预存在无关失败，按 AGENTS.md §9 说明并缩窄重跑）。
- 中文 dev/test report 齐备；测试结论 `PASS`/`PASS_WITH_NOTES` 且无 S0/S1/S2 阻断。

**Gate after phase:** 测试通过后路由回 OpenCode Developer 执行 Phase 5。

---

### Phase 5 — Streamlit 行情可观测（Slice E）

| Field | Value |
|---|---|
| **Scope** | 新增 `src/ui_report/market_data_health.py`：渲染 Provider Health / Data Quality / Fallback Status / Recent Market Data Errors 四个区域，消费 `/product/market/providers/health`、`/quality`、`/fallback` 与 `GET /product/market/latest/{symbol}`（经既有 `_get` helper 调本地 FastAPI），区分 OK/STALE/DEGRADED/FALLBACK/UNAVAILABLE/MOCK/DEMO 的标签与颜色（OK 正常；STALE/DEGRADED/FALLBACK warning 不得纯绿；UNAVAILABLE/INVALID error；MOCK/DEMO 显式 demo/mock 标签禁止显示为 live）。在 `src/ui_report/product_dashboard.py` 最小化接线（新增一个 sidebar/route 入口指向新页面或新区块），不重写既有 `render_market()`/`render_live_data()`。 |
| **Non-Goals** | 不引入 React/Vite/TypeScript；不删除/不改写既有 `render_market()`/`render_live_data()`；不新增 approve/merge/rerun/trade 按钮；不修改 `src/data_gateway/`、`src/api/`（仅消费现有 `/product/market/**` 端点）；不在 UI 暴露 secret。 |
| **Owner** | OpenCode Developer |
| **Branch** | `feat/market-data-relay/phase-5-streamlit-observability`（自 epic 分支，merge Phase 4 后） |
| **Restricted modules** | 不触碰受限模块。仅 `src/ui_report/market_data_health.py` 新增 + `src/ui_report/product_dashboard.py` 最小接线。触及 UI entrypoint，须做 Streamlit smoke。 |
| **Dev report** | `docs/dev_reports/20260625-market-data-relay-provider-contract-phase-5-dev-report.md` |
| **Test report** | `docs/test_reports/20260625-market-data-relay-provider-contract-phase-5-test-report.md` |

**Files:**
- Create: `src/ui_report/market_data_health.py`
- Modify: `src/ui_report/product_dashboard.py`（最小化接线：注册新页面/入口，不动既有 render 函数）
- Create: `tests/test_market_data_health_ui.py`

**Interfaces:**
- Consumes: `/product/market/providers/health`、`/product/market/providers/quality`、`/product/market/providers/fallback`、`GET /product/market/latest/{symbol}`（经既有 `src/ui_report/product_dashboard.py` 的 `_get` helper 或等效 HTTP 调用，测试 mock HTTP）。
- Produces: `render_market_data_health(state: dict | None = None) -> None`（Streamlit 渲染函数）；`quality_status_to_label(status: QualityStatus) -> tuple[str, str]`（返回 (label, severity) 映射，供 UI 与测试断言）。
- 展示规则严格对齐架构 §10：OK 正常；STALE/DEGRADED/FALLBACK warning；UNAVAILABLE/INVALID error；MOCK/DEMO demo/mock 标签。

**Self-test commands:**
```bash
git status --short --branch
git diff --stat
./.venv/bin/python -m ruff check src/ui_report/market_data_health.py src/ui_report/product_dashboard.py tests/test_market_data_health_ui.py
./.venv/bin/python -m py_compile src/ui_report/market_data_health.py src/ui_report/product_dashboard.py
./.venv/bin/python -m pytest tests/test_market_data_health_ui.py -q --basetemp=runtime/pytest-tmp-market-data-relay-provider-contract-ui
# Streamlit smoke：导入 dashboard 主模块不报错（不启动浏览器）
./.venv/bin/python -m py_compile src/ui_report/product_dashboard.py
git diff --check
```

**Tester checks:**
- `quality_status_to_label`：OK→正常；STALE/DEGRADED/FALLBACK→warning（非纯绿成功）；UNAVAILABLE/INVALID→error；MOCK/DEMO→demo/mock 标签。
- `render_market_data_health` 在 mock HTTP（health/quality/fallback/latest）下完整渲染四个区域，不抛裸异常；loading/empty/error 状态可见。
- degraded/fallback/mock/demo/stale 不显示为普通 live 成功（断言 warning/error/demo 标签出现，纯绿成功文案不出现）。
- Streamlit 未被标记 legacy/deprecated/待删除（grep `src/ui_report/`）。
- UI 不暴露 secret/auth header/完整 raw response（mock 响应含假 secret 时断言被脱敏或不展示）。
- 不新增 approve/merge/rerun/trade 按钮文案或动作。
- 既有 `render_market()`/`render_live_data()` 未被破坏（`product_dashboard.py` 可导入、既有 render 函数签名不变）。

**Release criteria:**
- 上述 pytest 全绿；`ruff`、`py_compile` 通过；Streamlit smoke（模块可导入）通过。
- UI 清晰区分 7 种 quality_status；degraded/fallback/mock/demo/stale 不伪装为 live（满足需求验收 §7、§9）。
- 中文 dev/test report 齐备；测试结论 `PASS`/`PASS_WITH_NOTES` 且无 S0/S1/S2 阻断。

**Gate after phase:** Phase 5 测试通过 → 全部 5 个交付阶段完成 → 路由回 OpenCode Team Leader 做 `claude_lead_review`（产出 `docs/review/20260625-market-data-relay-provider-contract-opencode-lead-review.md`），随后进入 Codex B 架构 Review 与 Codex A PM 验收。

---

## Final Regression（Phase 5 通过后，由 Team Leader 在 lead review 前确认）

触碰 `src/api/app.py`（共享 entrypoint）、产品数据契约、provider hubs 调用面，按 AGENTS.md §9 须运行更广泛回归：

```bash
git status --short --branch
git diff --stat
./.venv/bin/python -m ruff check src/product_app/market_data src/api/market_data_routes.py src/api/app.py src/ui_report/market_data_health.py src/ui_report/product_dashboard.py tests/test_market_data_*.py
./.venv/bin/python -m py_compile src/product_app/market_data/*.py src/api/market_data_routes.py src/api/app.py src/ui_report/market_data_health.py src/ui_report/product_dashboard.py
./.venv/bin/python -m pytest tests -q --tb=short --basetemp=runtime/pytest-tmp-market-data-relay-provider-contract-full
git diff --check
```

若 broad checks 因无关历史问题失败，必须如实记录失败、失败摘要、无关性判断，并额外提供 touched-scope 通过证据；不得声称 full-project success。

## 受限模块声明（本功能）

- **直接触碰**：`src/product_app/market_data/`（新建子包 + 迁移 flat 文件）、`src/api/market_data_routes.py`（新建）、`src/api/app.py`（追加一行 router 注册）、`src/ui_report/market_data_health.py`（新建）、`src/ui_report/product_dashboard.py`（最小接线）。
- **包装复用不修改**：`src/data_gateway/`（provider 实现、`provider_contracts.py`、`provider_hub.py`、`live_data_mapper.py`）、`src/product_app/live_data_service.py`、`src/product_app/data_health_gate.py`、`src/product_app/provider_diagnostics_service.py`。
- **不触碰**：`src/risk_engine/`、`src/execution_engine/`、`src/stock_pool/`、`src/backtest_engine/`、`src/strategy_engine/`、`src/factor_engine/`、`src/product_app/agentops/`（前序 V16.1 产物）。
- 若任一阶段实现中发现必须修改 `src/data_gateway/` provider 实现或受限模块，立即停止，在 dev report 标记 `restricted-module`，升级为人工审批 + 架构复审 + 负向测试，不得擅自推进。

## 不新增真实交易能力确认方式

每个阶段 dev report 的 Safety confirmation 必须明确回答（全部为“否”于“是否绕过…”）：

```text
是否新增真实交易能力：否
是否绕过 risk：否
是否绕过 stock-pool filtering：否
是否绕过 human confirmation：否
是否绕过 Provider Contract：否
是否绕过 Tool Registry：否（本功能不涉及 Tool Registry）
是否绕过 fail-closed behavior：否
是否泄露 secret：否
```

## 交付物清单

| 阶段 | Dev report | Test report |
|---|---|---|
| Phase 1 | `docs/dev_reports/20260625-market-data-relay-provider-contract-phase-1-dev-report.md` | `docs/test_reports/20260625-market-data-relay-provider-contract-phase-1-test-report.md` |
| Phase 2 | `docs/dev_reports/20260625-market-data-relay-provider-contract-phase-2-dev-report.md` | `docs/test_reports/20260625-market-data-relay-provider-contract-phase-2-test-report.md` |
| Phase 3 | `docs/dev_reports/20260625-market-data-relay-provider-contract-phase-3-dev-report.md` | `docs/test_reports/20260625-market-data-relay-provider-contract-phase-3-test-report.md` |
| Phase 4 | `docs/dev_reports/20260625-market-data-relay-provider-contract-phase-4-dev-report.md` | `docs/test_reports/20260625-market-data-relay-provider-contract-phase-4-test-report.md` |
| Phase 5 | `docs/dev_reports/20260625-market-data-relay-provider-contract-phase-5-dev-report.md` | `docs/test_reports/20260625-market-data-relay-provider-contract-phase-5-test-report.md` |
| Lead Review | `docs/review/20260625-market-data-relay-provider-contract-opencode-lead-review.md`（Phase 5 通过后由 Team Leader 产出） | — |

## 需求覆盖映射（Leader 自检）

| 需求/架构条目 | 覆盖阶段 |
|---|---|
| 需求 §1 Relay 统一产品入口 + `/product/**` | Phase 3（Relay）+ Phase 4（API） |
| 需求 §2 Provider Contract 标准化 | Phase 1（contracts）+ Phase 2（registry/adapter） |
| 需求 §3 数据质量字段 | Phase 1（DataQualityMetadata）+ Phase 3（Relay 填充） |
| 需求 §4 Fail-closed | Phase 1（QualityGate）+ Phase 3（Relay fail-closed） |
| 需求 §5 Provider Priority 与 Fallback Governance | Phase 2（registry）+ Phase 3（Relay fallback） |
| 需求 §6 Provider Health 与 Observability | Phase 3（health）+ Phase 5（UI） |
| 需求 §7 审计日志 | Phase 3（audit） |
| 需求 §8 下游边界（不直接调 raw provider） | 全阶段（Safety §3 + Tester checks grep 验证） |
| 需求 §9 UI/Dashboard | Phase 5 |
| 需求 §10 Artifact 输出 | 交付物清单 |
| 需求 §11 Agent 解读边界 | 全阶段（Safety §1 + LLM 不写买卖字段） |
| 架构 §5 与 LiveDataService 关系 | Phase 3（Relay 与 LiveDataService 共存，不删除） |
| 架构 §6 Circuit breaker | Phase 3（复用既有 `ProviderCircuitBreaker`） |
| 架构 §11 多 symbol 处理 | Phase 1（MultiSymbolQuoteResult）+ Phase 3（Relay） |

> 本计划由 OpenCode Team Leader 在 `claude_lead_plan` 阶段产出，遵循 `writing-plans` superpowers 能力。计划落盘后由 GitHub Stage Runner 管理提交与推送；Leader 不执行 `git commit/push/merge`。后续 Developer/Test Engineer 严格按“Gate after phase”路由串行推进。
