# market-data-relay-provider-contract Architecture

## Architecture Summary

本架构对应路线图 `V16.2 Market Data Relay & Provider Contract`，目标是在现有产品体系内建设统一、可审计、可治理的行情数据 Relay 层与 Provider Contract，使 `/product/**` 产品工作流、Streamlit Dashboard、未来 AgentOps、Risk Sentinel、Alpha 研究、回测、position sizing 和 paper trading 均通过受控数据入口访问行情数据。

本阶段不新增真实交易能力，不改变 risk、execution、stock-pool 或 human confirmation 边界，不允许 LLM 直接生成买入、卖出、最终仓位或真实订单。

设计原则：

```text
1. 产品行情访问统一进入 /product/**。
2. 产品层不得消费 provider-specific raw response。
3. 所有行情响应必须携带 data quality metadata。
4. stale / mock / demo / invalid 数据默认 fail closed。
5. fallback 必须显式标记，不得伪装为 primary live data。
6. signal、real trading、risk-sensitive workflow 不得绕过数据质量门禁。
7. Streamlit Dashboard 继续作为有效产品入口。
8. 审计日志和错误响应必须可诊断但不得泄露 secret。
```

推荐目标文档路径：

```text
docs/design/2026-06-25-market-data-relay-provider-contract-architecture.md
```

与流水线状态中 `required_docs.architecture` 存在命名差异：

```text
docs/design/20260625-market-data-relay-provider-contract-architecture.md
```

OpenCode Lead 在 team plan 阶段必须统一实际落盘路径；若流水线以 `required_docs.architecture` 为准，应在报告中说明本架构内容来源与路径差异，避免验收脚本找不到文档。

## Module Plan

### 1. 新增产品行情模块

建议新增模块：

```text
src/product_app/market_data/
├── __init__.py
├── contracts.py
├── quality.py
├── relay.py
├── provider_registry.py
├── health.py
├── audit.py
├── cache.py
└── errors.py
```

模块职责：

```text
contracts.py
  定义 Provider Contract、Provider capability、Provider response wrapper、标准 quote / bar schema。

quality.py
  定义 QualityStatus、DataQualityMetadata、质量门禁规则、stale/mock/demo/fallback 判定。

relay.py
  提供 MarketDataRelay，统一处理 provider selection、timeout、fallback、response mapping、quality gate、audit。

provider_registry.py
  管理 provider priority、market_scope、asset_type、endpoint、granularity 和 fallback eligibility。

health.py
  聚合 provider availability、latency、failure、circuit breaker、freshness summary 和 fallback activation count。

audit.py
  生成脱敏审计事件，记录 request_id、caller_context、endpoint、symbols、provider attempts、quality_status 和 latency。

cache.py
  管理显式标记的缓存响应，缓存不得伪装为 live data。

errors.py
  定义统一错误类型和 provider error mapping。
```

### 2. Provider Contract 模型

Provider Contract 必须至少包含：

```text
provider_id
provider_name
market_scope
supported_asset_types
supported_granularities
supported_endpoints
auth_requirement
rate_limit_policy
timeout_policy
freshness_policy
cache_policy
fallback_eligibility
quality_status_mapping
error_mapping
```

建议使用 Pydantic 模型或现有项目兼容的数据模型：

```python
class MarketDataProviderContract(BaseModel):
    provider_id: str
    provider_name: str
    market_scope: list[str]
    supported_asset_types: list[str]
    supported_granularities: list[str]
    supported_endpoints: list[str]
    auth_requirement: AuthRequirement
    rate_limit_policy: RateLimitPolicy
    timeout_policy: TimeoutPolicy
    freshness_policy: FreshnessPolicy
    cache_policy: CachePolicy
    fallback_eligibility: FallbackEligibility
    quality_status_mapping: dict[str, QualityStatus]
    error_mapping: dict[str, ProviderErrorCategory]
```

Provider implementation 不直接暴露给产品路由。Relay 只接收标准化 provider adapter 输出。

### 3. 标准行情响应模型

建议最小响应模型：

```python
class DataQualityMetadata(BaseModel):
    source_provider: str
    source_priority: int
    as_of: datetime
    received_at: datetime
    freshness_seconds: float
    is_stale: bool
    is_realtime: bool
    is_demo: bool
    is_mock: bool
    is_fallback: bool
    quality_status: QualityStatus
    quality_reason: str
    provider_latency_ms: float | None
    request_id: str

class MarketQuote(BaseModel):
    symbol: str
    market: str
    asset_type: str
    price: Decimal | None
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    previous_close: Decimal | None = None
    volume: int | None = None
    currency: str | None = None
    quality: DataQualityMetadata

class MarketBar(BaseModel):
    symbol: str
    market: str
    granularity: str
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int | None
    quality: DataQualityMetadata
```

批量响应必须允许每个 symbol 拥有独立 quality metadata，因为 provider 可能对部分标的返回 stale、missing 或 invalid。

### 4. 产品 API 路由

建议新增或扩展：

```text
src/api/routes/product/market_data.py
```

路由必须挂载在 `/product/**` 下，建议 endpoint：

```text
GET /product/market/latest/{symbol}
POST /product/market/latest
GET /product/market/bars/{symbol}
GET /product/market/providers/health
GET /product/market/providers/quality
GET /product/market/providers/fallback
```

不得新增未批准的平行业务前缀，例如：

```text
/api/market/**
/api/provider/**
```

FastAPI app factory 保持：

```text
src/api/app.py:create_app()
```

产品路由只依赖 `MarketDataRelay` 或 service helper，不直接 import raw provider。

### 5. 与现有 LiveDataService 的关系

如果当前仓库已有 `LiveDataService`，本功能应采用兼容演进方式：

```text
短期：
  LiveDataService 可作为 MarketDataRelay 的 facade 或被 Relay 包装，避免破坏现有调用方。

中期：
  产品 live workflow 统一使用 MarketDataRelay。
  LiveDataService 保留为兼容层，但不得绕过 Provider Contract 和 quality gate。

禁止：
  strategy_engine、signal workflow 或 product route 直接调用 raw provider。
```

OpenCode Developer 实现前必须搜索现有 live data、provider hub、data gateway、product route 和 signal 调用路径，列出 touched files 和迁移范围。

### 6. Provider Registry 与 fallback governance

Provider priority 配置维度：

```text
market
asset_type
endpoint
granularity
provider_id
priority
fallback_allowed
risk_sensitive_allowed
```

fallback 规则：

```text
1. Relay 根据 market、asset_type、endpoint、granularity 读取 provider priority。
2. 按 priority 尝试 primary provider。
3. provider timeout、auth failure、rate limit、empty、malformed、invalid response 根据 error_mapping 转换为标准错误。
4. 如果 fallback_allowed=True，且错误类别允许 fallback，则尝试下一个 provider。
5. fallback 响应必须设置 is_fallback=True。
6. quality_status 必须为 FALLBACK 或 DEGRADED，除非下游明确只查询健康状态。
7. risk-sensitive workflow 默认不得自动使用 fallback 数据。
```

伪代码：

```python
def get_latest_quote(symbol, market, caller_context, allow_demo=False):
    request_id = new_request_id()
    providers = registry.select(
        market=market,
        asset_type="equity",
        endpoint="latest_quote",
    )

    attempts = []
    for priority, provider in providers:
        started = monotonic()
        try:
            raw = provider.fetch_latest_quote(symbol, timeout=provider.timeout_policy)
            normalized = mapper.normalize_quote(raw)
            quality = quality_evaluator.evaluate(
                normalized=normalized,
                contract=provider.contract,
                priority=priority,
                request_id=request_id,
                is_fallback=priority != 1,
                allow_demo=allow_demo,
                caller_context=caller_context,
            )

            if quality_gate.blocks(quality, caller_context):
                attempts.append(blocked_attempt(provider, quality))
                continue

            audit.record_success(request_id, attempts, provider, quality)
            health.record_success(provider, latency_ms=elapsed_ms(started))
            return quote_with_quality(normalized, quality)

        except ProviderError as exc:
            mapped = error_mapper.map(exc, provider.contract)
            attempts.append(failed_attempt(provider, mapped))
            health.record_failure(provider, mapped)
            if not fallback_policy.can_continue(mapped, caller_context):
                break

    audit.record_fail_closed(request_id, attempts)
    raise MarketDataUnavailableError(
        request_id=request_id,
        safe_reason=safe_error_summary(attempts),
    )
```

### 7. 数据质量门禁

`QualityStatus` 至少支持：

```text
OK
STALE
DEGRADED
FALLBACK
UNAVAILABLE
INVALID
MOCK
DEMO
```

质量门禁建议分层：

```text
research_readonly
  可读取 OK、DEGRADED、FALLBACK，但必须显示 quality_status。
  MOCK、DEMO 只能在 allow_demo=True 且 caller_context 明确为 demo/research 时允许。

dashboard_observability
  可展示所有状态，但必须区分颜色和标签，不得把 fallback/stale/mock/demo 显示为普通 live 成功。

signal_generation
  只允许 OK 且 is_stale=False、is_mock=False、is_demo=False、quality_status 不为 FALLBACK/DEGRADED/INVALID/UNAVAILABLE。
  fallback 是否允许必须由未来明确架构批准，本阶段默认阻断。

real_trading
  本功能不新增真实交易能力。
  若未来接入，默认只允许 OK live data，并继续要求 risk veto 和 human confirmation。
```

门禁伪代码：

```python
def blocks(quality, caller_context):
    if quality.quality_status in {"UNAVAILABLE", "INVALID"}:
        return True

    if caller_context in {"signal_generation", "real_trading", "position_sizing"}:
        if quality.is_stale or quality.is_mock or quality.is_demo:
            return True
        if quality.is_fallback:
            return True
        if quality.quality_status != "OK":
            return True

    if not caller_context.allow_demo and quality.is_demo:
        return True

    if not caller_context.allow_mock and quality.is_mock:
        return True

    return False
```

### 8. Provider Health 与 observability

`health.py` 应聚合以下指标：

```text
provider_id
availability
last_success_at
last_failure_at
consecutive_failures
latency_p50_ms
latency_p95_ms
latency_last_ms
error_category_summary
circuit_breaker_status
fallback_activation_count
freshness_summary
updated_at
```

health 状态可以先使用内存聚合，后续可扩展到持久化存储。若本阶段使用内存状态，开发报告必须说明进程重启后状态丢失，不可作为长期审计存储。

### 9. 审计日志

审计事件模型：

```python
class MarketDataAuditEvent(BaseModel):
    request_id: str
    caller_context: str
    endpoint: str
    symbols: list[str]
    market: str | None
    provider_selected: str | None
    provider_attempts: list[ProviderAttempt]
    fallback_used: bool
    quality_status: QualityStatus | None
    error_code: str | None
    created_at: datetime
    latency_ms: float
```

脱敏规则：

```text
不得记录 API key、token、cookie、账户凭据、券商凭据、完整 auth header。
provider error detail 只保留标准 error category、safe message 和 request_id。
```

### 10. Streamlit Dashboard

UI 默认使用当前 Streamlit Dashboard。

建议新增或扩展页面区域：

```text
Provider Health
Data Quality
Fallback Status
Recent Market Data Errors
```

展示规则：

```text
OK:
  可显示为正常状态。

STALE / DEGRADED / FALLBACK:
  显示为 warning，不得显示为纯绿色成功 live。

UNAVAILABLE / INVALID:
  显示为 error。

MOCK / DEMO:
  显示为 demo/mock 标签，禁止显示为 live。
```

本功能不得将 Streamlit 标记为：

```text
legacy
deprecated
待删除
```

## Technical Decisions

### 1. 技术选型

采用现有 Python + FastAPI + Streamlit 技术栈，不新增 React + Vite + TypeScript 前端基线。

理由：

```text
1. 当前 Streamlit Dashboard 仍是有效产品入口。
2. 本功能重点是数据契约、质量门禁、provider governance 和可观测性。
3. AgentOps、行情健康和 provider 状态展示适合先在 Streamlit 内完成。
4. React 基线尚未稳定，不应为本功能引入额外前端复杂度。
```

### 2. API 命名空间

所有产品行情 API 位于：

```text
/product/market/**
```

禁止新增：

```text
/api/market/**
/api/provider/**
/market/**
```

除非后续架构文档明确批准。

### 3. Contract first

Provider 适配必须先定义 Contract，再接入具体 provider。

开发顺序：

```text
1. 定义 contract / quality / error / response schema。
2. 为至少一个现有 provider 编写 adapter。
3. 将 provider raw response 映射为标准 response。
4. 通过 Relay 暴露给产品服务。
5. 添加产品 API。
6. 添加 Dashboard 展示。
7. 补齐 normal 和 negative tests。
```

### 4. Error mapping

Provider 错误统一映射为：

```text
AUTH_FAILED
RATE_LIMITED
TIMEOUT
NETWORK_ERROR
EMPTY_RESPONSE
MALFORMED_RESPONSE
MISSING_FIELD
INVALID_VALUE
STALE_DATA
PROVIDER_UNAVAILABLE
UNKNOWN_PROVIDER_ERROR
```

产品错误响应必须包含：

```text
request_id
error_code
quality_status
safe_reason
provider_attempt_count
fallback_used
```

不得包含 provider secret、原始 auth header、`.env` 内容或完整 raw response。

### 5. Cache 策略

缓存必须显式携带：

```text
cache_hit
cache_created_at
cache_age_seconds
source_provider
quality_status
is_stale
```

缓存不得把过期数据伪装为 live。

如果 cache 超过 freshness_policy：

```text
research_readonly:
  可返回但必须标记 STALE，且 UI 必须 warning。

signal_generation / real_trading:
  必须 fail closed。
```

### 6. Circuit breaker

本阶段可实现轻量 circuit breaker：

```text
closed:
  正常尝试 provider。

open:
  provider 连续失败达到阈值后短期跳过。

half_open:
  冷却时间后允许一次探测请求。
```

若实现成本过高，可先记录 `circuit_breaker_status="not_implemented"`，但 Provider Health API 字段必须保留，且开发报告说明未实现范围。验收若要求 circuit breaker 行为，则必须补实现和测试。

### 7. 多 symbol 处理

多标的 latest quote 不应因为单个 symbol 失败而默认全部伪成功。

推荐响应：

```text
results:
  每个 symbol 返回 quote 或 item-level error。
summary:
  total
  ok_count
  failed_count
  degraded_count
  fallback_count
request_quality:
  聚合质量状态
```

对于 signal/risk-sensitive caller：

```text
任一 required symbol 数据质量不合格时，调用方必须 fail closed 或拒绝继续生成信号。
```

### 8. 与 restricted modules 的关系

本功能直接触碰或可能触碰：

```text
src/data_gateway/
src/product_app/market_data/
src/api/
src/ui_report/
```

可能间接影响：

```text
src/strategy_engine/
src/risk_engine/
src/backtest_engine/
src/product_app/risk_sentinel/
src/product_app/alpha/
```

开发阶段不得修改真实 execution path，不得新增真实订单能力。若必须修改 `src/risk_engine/`、`src/execution_engine/`、`src/stock_pool/` 或 signal path，必须在 dev report 中标记 restricted-module，并增加负向测试。

## Safety Impact

### 1. 真实交易能力

本功能不新增真实自动交易能力。

禁止变更：

```text
Risk Engine 一票否决权
human confirmation
execution policy
真实 order path
broker credential handling
stock-pool eligibility rules
LEVEL_3_AUTO 暴露规则
```

任何实现如果新增真实订单路径、自动执行路径、绕过人工确认或允许 LLM 写入 order 字段，必须拒绝。

### 2. Fail-closed 安全边界

以下状态不得进入 signal 或 real trading 路径：

```text
STALE
UNAVAILABLE
INVALID
MOCK
DEMO
```

默认也不得让 fallback 自动进入 risk-sensitive workflow：

```text
FALLBACK
DEGRADED
```

fallback 可用于只读研究、dashboard observability 或运维诊断，但必须显式标记。

### 3. Provider 边界

以下模块不得直接调用 raw market provider：

```text
strategy_engine
signal generation workflow
product API routes
risk_engine
execution_engine
model gateway
decision snapshot
position sizing
backtest product workflow
risk sentinel
alpha workflow
paper trading
broker shadow
```

它们必须使用：

```text
LiveDataService
MarketDataRelay
经过本架构批准的 product market data service
```

### 4. LLM / Agent 权限边界

LLM / Agent 可以读取：

```text
quality_status
freshness summary
provider health
fallback reason
safe error summary
```

LLM / Agent 不得：

```text
覆盖 quality_status
覆盖 risk veto
直接决定买入、卖出、最终仓位或真实订单
把 fallback / stale / mock / demo 解释为 live trading 依据
绕过 Relay 读取 raw provider
伪造研究证据或 signal confidence
```

### 5. Secret 保护

所有 provider secret 必须来自环境变量。

禁止输出到：

```text
日志
审计事件
错误响应
Dashboard
dev report
test report
review report
acceptance report
```

脱敏函数必须覆盖：

```text
api_key
apikey
token
cookie
secret
authorization
auth
password
broker credential
```

### 6. Stock Pool 与 Risk 边界

本功能不得削弱或绕过以下规则：

```text
不得买入创业板、科创板、ST、退市整理股票，除非未来批准策略明确变更。
BAN 股票池不得生成买入信号。
Risk Agent / Risk Engine 拥有一票否决权。
```

Market Data Relay 只提供数据质量可信入口，不提供交易许可。

## Development Guidance

### 1. OpenCode Lead 阶段计划建议

建议拆分为 1 个主阶段，内部按 slice 执行：

```text
Phase 1: Market Data Relay & Provider Contract Foundation
```

Phase 1 内部 slice：

```text
Slice A: schema and contract
  contracts.py、quality.py、errors.py
  单元测试覆盖枚举、质量门禁、错误映射、secret redaction。

Slice B: provider adapter and registry
  provider_registry.py
  至少接入一个现有 provider adapter。
  测试 provider metadata、priority、fallback eligibility。

Slice C: relay service
  relay.py、audit.py、health.py、cache.py
  测试 valid quote、multi-symbol quote、bars、timeout、empty、malformed、stale、fallback、fail-closed。

Slice D: product API
  /product/market/** routes。
  测试 HTTP contract、invalid symbol、auth failure mapping、secret not leaked。

Slice E: Streamlit observability
  Provider health、quality_status、fallback status、recent error summary。
  smoke test 或等效检查。
```

OpenCode Lead 必须在 team plan 中明确：

```text
1. 实际 architecture doc path。
2. touched restricted modules。
3. 每个 slice 的 owner 和测试命令。
4. 是否需要 broad regression。
5. 不新增真实交易能力的确认方式。
```

### 2. OpenCode Developer 实现前检查

实现前必须运行并记录：

```bash
git status --short --branch
git diff --stat
```

实现前必须搜索：

```text
LiveDataService
raw provider imports
data_gateway provider calls
/product routes
signal generation market data calls
Streamlit market data displays
```

Developer 必须识别并记录：

```text
touched files
restricted modules
测试范围
是否影响 API contract
是否影响 UI
是否影响 signal/risk-sensitive path
```

### 3. 实现边界

Developer 允许修改或新增：

```text
src/product_app/market_data/
src/api/routes/product/
src/api/app.py 或 route registration 相关文件
src/data_gateway/ provider adapter 层
src/ui_report/ provider health 展示相关文件
tests/ 对应单元和 API 测试
docs/dev_reports/
```

Developer 不应修改：

```text
src/execution_engine/ 真实下单路径
真实 broker credential 逻辑
risk policy 语义
stock-pool 禁止规则
LEVEL_3_AUTO 暴露逻辑
```

若确需触碰 restricted modules，必须：

```text
1. 在 dev report 标记 restricted-module。
2. 添加 normal 和 negative tests。
3. 说明未绕过 risk、stock-pool、human confirmation、provider contracts 和 fail-closed。
4. 等待额外 review。
```

### 4. 最小测试矩阵

必须包含 normal paths：

```text
valid latest quote
valid multi-symbol quote
valid history bars
provider health query
provider quality query
fallback status query
```

必须包含 negative paths：

```text
invalid symbol
empty provider response
missing fields
stale data
mock data
demo data
fallback data
provider timeout
provider malformed payload
provider unavailable
permission denied / auth failure
fail-closed behavior
secret not leaked
cache stale behavior
risk-sensitive caller blocks fallback
risk-sensitive caller blocks stale/mock/demo
```

API 测试必须验证：

```text
路由位于 /product/**
未新增未批准 /api/** 平行业务入口
错误响应包含 request_id 和 safe_reason
错误响应不包含 secret
数据质量字段完整
```

Dashboard 测试或 smoke 必须验证：

```text
OK、STALE、DEGRADED、FALLBACK、UNAVAILABLE、MOCK、DEMO 可区分
degraded/fallback/mock/demo/stale 不显示为普通 live 成功
Streamlit 未被标记为 legacy/deprecated/待删除
```

### 5. 推荐测试命令

Developer 阶段至少运行：

```bash
git status --short --branch
git diff --stat
./.venv/bin/python -m ruff check <touched-python-files-and-tests>
./.venv/bin/python -m py_compile <touched-src-python-files>
./.venv/bin/python -m pytest <related-test-files> -q --basetemp=runtime/pytest-tmp-market-data-relay-provider-contract
git diff --check
```

若触碰 provider hubs、product routes、data contracts、strategy signal path、risk-sensitive workflow 或 shared models，必须运行：

```bash
./.venv/bin/python -m pytest tests -q --tb=short --basetemp=runtime/pytest-tmp-market-data-relay-provider-contract-full
```

若 broad checks 因历史无关问题失败，必须如实记录失败、失败摘要、无关性判断，并额外提供 touched-scope 通过证据。

### 6. OpenCode Tester 指导

Tester 必须创建临时本地 test 分支进行验证，测试结束回到原开发分支并删除临时分支。

测试报告必须包含：

```text
Requirement path
Architecture path
Development report path
Roadmap section reference
Test environment
Scope and out-of-scope
Requirement coverage matrix
Commands and results
API/UI/data-source/provider evidence
Data-quality and fail-closed evidence
Defect list with severity
Feedback bug paths if generated
Remaining risk
Final result: PASS / PASS_WITH_NOTES / REJECTED
```

Tester 必须重点拒绝以下情况：

```text
/product/** API 规则被违反
Streamlit 被标记为 legacy/deprecated/待删除
raw provider 被 product route 或 signal workflow 直接调用
响应缺少数据质量字段
mock/demo/stale/fallback 被伪装为 live
provider 全失败未 fail closed
错误或日志泄露 secret
LLM 获得买卖或下单决策权
缺少负向测试
缺少中文 dev/test evidence
未经批准新增真实订单能力
```

### 7. 开发报告要求

Developer 必须生成：

```text
docs/dev_reports/20260625-market-data-relay-provider-contract-phase-1-dev-report.md
```

报告必须包含：

```text
Requirement document path
Architecture document path
Roadmap section reference
Changed files
Feature-to-code mapping
Added or updated tests
Exact commands and results
Data source and data-quality handling
Provider priority and fallback behavior
API contract impact
UI impact
Agent / LLM boundary impact
Skipped or not-run items with reasons
Remaining risks
Whether real trading capability is affected
Safety confirmation
```

Safety confirmation 必须明确回答：

```text
是否新增真实交易能力：否
是否绕过 risk：否
是否绕过 stock-pool filtering：否
是否绕过 human confirmation：否
是否绕过 Provider Contract：否
是否绕过 Tool Registry：否
是否绕过 fail-closed behavior：否
是否泄露 secret：否
```

### 8. Reviewer / Acceptance 关注点

Codex Review 必须检查：

```text
是否符合 V16.2 roadmap
产品 API 是否位于 /product/**
是否保留 Streamlit
是否使用 Provider Contract 而不是 raw provider
响应是否包含 data quality metadata
stale/mock/demo/fallback 是否 fail closed 或显式标记
fallback 是否受控
risk-sensitive workflow 是否默认阻断不可信数据
LLM 是否只做解释和摘要
是否未新增真实 order path
normal 和 negative tests 是否充分
中文 dev/test/acceptance 证据是否完整
manual merge 和 human confirmation 边界是否保留
```

Acceptance 必须拒绝：

```text
只在 mock 模式工作但未说明限制
缺少 fail-closed 证据
fallback 被显示为 live
provider 全失败仍返回成功
缺少数据质量字段
缺少负向测试
缺少中文文档证据
未经批准触碰真实交易能力
```