# market-data-relay-provider-contract Requirements

## User Goal

建设 V16.2 Market Data Relay & Provider Contract，为产品级行情数据访问提供统一、可审计、可治理的 Relay 层与 Provider 契约。

用户希望系统不再让策略、信号、产品 API 或未来 Agent 直接依赖零散的 raw market provider，而是通过统一入口获取行情数据，并明确知道每次数据响应的来源、freshness、quality status、fallback 状态和失败原因。

本功能的核心目标是让后续 AgentOps、行情健康、信号生成、回测、Risk Sentinel、Alpha 研究和未来 Paper Trading 能基于可信的数据契约工作，而不是基于不透明、不可追踪、不可治理的数据调用。

本需求对应路线图：

```text
V16.2 Market Data Relay & Provider Contract
```

产品原则：

```text
数据、工具和证据不可信之前，不得建设交易智能。
```

本阶段仅定义需求，不实现架构、代码或测试。

## Functional Requirements

### 1. Market Data Relay 统一产品入口

系统必须提供产品级行情 Relay 能力，供 `/product/**` 产品工作流使用。

Relay 应覆盖以下最小数据访问场景：

```text
单标的最新行情
多标的最新行情
历史 K 线 / bars
行情 Provider 健康状态
数据质量状态查询
Provider fallback / degradation 状态查询
```

产品 API 必须保持在：

```text
/product/**
```

不得新增平行业务前缀，例如：

```text
/api/**
```

除非当前架构文档明确批准例外。

### 2. Provider Contract 标准化

每个市场数据 Provider 必须遵守统一 Provider Contract。

Contract 至少需要描述：

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

Provider 返回的数据必须经过统一结构化封装，不允许产品层直接消费 provider-specific raw response。

### 3. 数据质量字段

所有 Relay 返回给产品工作流的行情响应必须携带数据质量元信息。

最小字段包括：

```text
source_provider
source_priority
as_of
received_at
freshness_seconds
is_stale
is_realtime
is_demo
is_mock
is_fallback
quality_status
quality_reason
provider_latency_ms
request_id
```

`quality_status` 至少需要支持：

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

### 4. Fail-closed 行为

当 `allow_demo=False` 或 live-data 产品路径要求真实数据时：

```text
demo 数据不得返回为 live 数据
mock 数据不得返回为 live 数据
stale 数据不得进入 signal 或 real trading 路径
fallback 数据必须显式标记
provider 全部失败时必须返回 fail-closed 错误
```

Fail-closed 响应必须包含可诊断原因，但不得泄露 secret、token、cookie、账户凭据或 provider 私密配置。

### 5. Provider Priority 与 Fallback Governance

Relay 必须支持 Provider 优先级治理。

需求包括：

```text
按市场、资产类型、数据类型配置 provider priority
主 provider 失败时按规则 fallback
fallback 必须记录 source_provider 和 fallback reason
fallback 不得伪装成 primary live data
fallback 是否允许进入下游 workflow 必须由数据质量门禁决定
```

对于 signal、real trading、position sizing、risk-sensitive workflow：

```text
fallback 默认不得自动视为可交易级 live 数据
stale / mock / demo / invalid 数据必须阻断
```

### 6. Provider Health 与 Observability

系统必须提供可观测的 Provider 健康状态。

最小能力包括：

```text
provider availability
last_success_at
last_failure_at
consecutive_failures
latency summary
error category summary
circuit breaker status
fallback activation count
data freshness summary
```

这些状态应可被 AgentOps Control Tower 或 Streamlit Dashboard 展示。

当前 Streamlit Dashboard 仍是有效产品入口，不得标记为 legacy、deprecated 或待删除。

### 7. Market Data Relay 审计日志

Relay 必须能为每次关键行情请求生成审计记录。

审计记录至少包含：

```text
request_id
caller_context
endpoint
symbols
market
provider_selected
provider_attempts
fallback_used
quality_status
error_code
created_at
latency_ms
```

审计日志不得包含 secret、token、cookie、账户凭据或完整敏感 auth header。

### 8. 下游边界要求

以下模块不得直接调用 raw market provider：

```text
strategy_engine
signal generation workflow
product API routes
Risk Sentinel
future position sizing
future paper trading
future broker shadow
future alpha workflow
```

它们必须通过 `LiveDataService`、Market Data Relay 或当前架构批准的产品服务访问行情数据。

### 9. UI / Dashboard 行为

本功能涉及 UI 时，默认使用当前 Streamlit Dashboard。

Dashboard 或产品页面应能展示：

```text
Provider 健康状态
当前 primary provider
fallback 是否启用
数据 freshness
quality_status
最近错误摘要
stale / unavailable / mock / demo 状态
```

不得用纯绿色成功状态展示 degraded、fallback、mock、demo 或 stale 数据。

### 10. Artifact 输出

本功能最终阶段应产生以下文档或证据：

```text
docs/requirements/20260625-market-data-relay-provider-contract-requirements.md
docs/design/20260625-market-data-relay-provider-contract-architecture.md
docs/dev_plans/20260625-market-data-relay-provider-contract-team-plan.md
docs/dev_reports/20260625-market-data-relay-provider-contract-phase-<n>-dev-report.md
docs/test_reports/20260625-market-data-relay-provider-contract-phase-<n>-test-report.md
docs/review/20260625-market-data-relay-provider-contract-opencode-lead-review.md
docs/review/20260625-market-data-relay-provider-contract-codex-review-r1.md
docs/acceptance/20260625-market-data-relay-provider-contract-acceptance.md
```

如生成用户指南，应使用：

```text
docs/user_guides/20260625-market-data-relay-provider-contract-user-guide.md
```

### 11. Agent 解读边界

LLM / Agent 可以读取 Relay 提供的结构化健康状态、数据质量摘要和错误摘要，用于生成研究解释、运维摘要或风险提示。

LLM / Agent 不得：

```text
直接决定买入
直接决定卖出
直接决定最终仓位
覆盖 risk veto
将 fallback / stale / mock / demo 数据解释为真实 live 交易依据
绕过 Provider Contract 读取 raw provider
```

## Non-functional Requirements

### 1. 可靠性

Relay 应对 provider timeout、provider 返回空数据、字段缺失、异常值、认证失败、限流、网络错误和格式变化具备明确处理路径。

系统不得因单个 Provider 异常导致产品 API 返回未结构化异常或误导性成功响应。

### 2. 可测试性

所有 Provider Contract、Relay response mapping、fallback、stale、mock、demo、timeout、invalid response、permission denied 行为必须可用确定性测试验证。

外部 Provider 必须在单元测试中 mock。

### 3. 可观测性

Relay 必须产生足够诊断信息，支持定位：

```text
哪个 provider 被选中
哪个 provider 失败
是否发生 fallback
数据是否 stale
失败是否来自认证、限流、网络、解析、空数据或质量门禁
```

### 4. 安全性

不得在日志、错误响应、审计记录、Dashboard 或报告中泄露：

```text
.env 内容
API key
token
cookie
账户凭据
券商凭据
完整认证 header
```

所有 secrets 必须来自环境变量。

### 5. 兼容性

本功能应尊重现有 FastAPI app factory：

```text
src/api/app.py:create_app()
```

并保持当前 Streamlit Dashboard 作为有效产品入口。

不得破坏现有启动方式：

```text
python main.py api
python main.py dashboard
python main.py signal
scripts/start.sh
start.bat
```

### 6. 性能

Relay 应避免不必要的重复 Provider 调用。

缓存策略必须显式标记 cache 来源、时间戳和 freshness，不得把过期 cache 伪装成 live data。

### 7. 可扩展性

Provider Contract 应支持未来扩展到：

```text
A 股
港股
未来多市场
指数
行业数据
基本面数据入口的相似 contract pattern
```

但本阶段不要求实现所有未来市场。

### 8. 文档要求

后续开发报告必须包含：

```text
Requirement document path
Architecture document path
Roadmap section reference
Changed files
Feature-to-code mapping
Added or updated tests
Exact commands and results
Data source and data-quality handling
API contract impact
UI impact
Agent / LLM boundary impact
Skipped or not-run items with reasons
Remaining risks
Whether real trading capability is affected
Safety confirmation
```

## Acceptance Criteria

### 1. 产品入口验收

通过验收时，产品级行情访问必须位于 `/product/**` 命名空间下。

验收检查：

```text
未新增未批准的 /api/** 平行业务入口
现有 Streamlit Dashboard 未被标记为 legacy、deprecated 或待删除
FastAPI app factory 仍可加载
```

### 2. Provider Contract 验收

至少一个现有或新增市场数据 Provider 被纳入标准 Provider Contract。

验收检查：

```text
Provider metadata 完整
Provider response 被标准化
provider-specific raw response 未泄露到产品工作流
错误映射稳定
timeout / empty / malformed response 有明确结果
```

### 3. Relay 数据质量验收

Relay 返回响应必须包含数据质量字段。

验收检查字段：

```text
source_provider
as_of
received_at
freshness_seconds
is_stale
is_demo
is_mock
is_fallback
quality_status
quality_reason
request_id
```

缺失任一关键字段不得通过验收。

### 4. Fail-closed 验收

当 live 数据不可用或 `allow_demo=False` 时：

```text
demo 数据不得作为 live 返回
mock 数据不得作为 live 返回
stale 数据不得进入 signal / real trading 路径
provider 全失败必须返回 fail-closed 错误
错误响应必须可诊断且不泄露 secret
```

### 5. Fallback 验收

当 primary provider 失败且 fallback 被允许时：

```text
fallback provider 被显式标记
quality_status 显示 FALLBACK 或 DEGRADED
fallback reason 可见
fallback 数据不得伪装为 primary live
risk-sensitive workflow 默认不能无门禁使用 fallback 数据
```

### 6. Provider Health 验收

系统必须能查询或展示 provider 健康状态。

验收内容包括：

```text
availability
last_success_at
last_failure_at
consecutive_failures
latency
error category
circuit breaker status
fallback count
freshness summary
```

### 7. Dashboard / UI 验收

如本功能实现 UI，则必须通过 Streamlit smoke 或等效检查。

UI 必须清晰区分：

```text
OK
STALE
DEGRADED
FALLBACK
UNAVAILABLE
MOCK
DEMO
```

不得把 degraded、fallback、mock、demo 或 stale 状态展示为普通成功 live 状态。

### 8. 测试验收

必须包含 normal 和 negative paths 测试。

最小测试范围：

```text
valid latest quote
valid multi-symbol quote
valid history bars
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
```

涉及 `src/data_gateway/`、`src/product_app/market_data/`、`src/api/` 或 signal path 时，必须包含负向测试。

### 9. 回归命令验收

开发阶段必须至少运行并记录：

```bash
git status --short --branch
git diff --stat
./.venv/bin/python -m ruff check <touched-python-files-and-tests>
./.venv/bin/python -m py_compile <touched-src-python-files>
./.venv/bin/python -m pytest <related-test-files> -q --basetemp=runtime/pytest-tmp-market-data-relay-provider-contract
git diff --check
```

如触碰 provider hubs、product routes、data contracts、strategy signal path、risk-sensitive workflow 或 shared models，必须运行更广泛回归：

```bash
./.venv/bin/python -m pytest tests -q --tb=short --basetemp=runtime/pytest-tmp-market-data-relay-provider-contract-full
```

若 broad checks 因历史无关问题失败，必须如实记录失败、说明无关性，并提供 touched-scope 测试结果。

### 10. 文档验收

最终验收前必须具备中文证据文档：

```text
requirements
architecture
dev report
test report
review report
acceptance report
```

文档必须说明：

```text
变更范围
测试命令
测试结果
数据质量处理
fallback 行为
安全确认
真实交易能力是否受影响
最终结论
```

### 11. 用户可见成功标准

用户在产品侧应能确认：

```text
当前行情数据来自哪个 Provider
数据是否新鲜
数据是否 fallback
数据是否 mock / demo
Provider 是否健康
失败时为什么失败
系统不会把不可信数据伪装成 live 数据
```

## Safety Constraints

### 1. 真实交易安全

本功能不得新增真实自动交易能力。

不得新增、启用或绕过任何真实 order path。

不得改变以下原则：

```text
默认不允许真实自动交易
Risk Agent / Risk Engine 拥有一票否决权
所有真实订单必须人工确认
LLM 不得直接决定买入、卖出、最终仓位或真实订单
```

### 2. 数据安全

数据源失败默认阻断 signal 和 real trading 路径。

当数据质量为以下任一状态时，不得进入 signal 或 real trading 路径：

```text
STALE
UNAVAILABLE
INVALID
MOCK
DEMO
```

Fallback 数据必须由明确的数据质量门禁判断是否可用于非交易研究场景；不得默认用于交易级决策。

### 3. Provider 边界

产品 live workflow 必须使用产品 API、Provider Contract、Relay 和数据质量门禁。

不得从以下模块直接调用 raw market provider：

```text
strategy_engine
risk_engine
execution_engine
product API route
model gateway
decision snapshot
position sizing
backtest product workflow
risk sentinel
alpha workflow
```

除非当前架构文档明确批准并保留等价质量门禁。

### 4. Stock Pool 与 Risk 边界

本功能不得削弱股票池过滤。

不得允许以下标的绕过既有禁止规则：

```text
创业板
科创板
ST
退市整理股票
BAN 股票池
```

除非未来已批准策略明确变更。

### 5. Demo / Mock / Cache / Fallback 标识

以下数据不得伪装为真实 live data：

```text
demo
mock
fixture
paper trading
cache
stale
fallback
shadow data
```

当 `allow_demo=False` 时，产品 live-data 路径不得返回 demo 数据。

### 6. Secret 保护

不得提交或输出：

```text
.env
API key
token
cookie
账户凭据
券商凭据
provider secret
```

错误响应、审计日志、Dashboard、开发报告和测试报告必须脱敏。

### 7. LLM 权限边界

LLM 只能生成结构化研究、解释、标签、排序、摘要和解读。

LLM 不得：

```text
写入 final buy / sell / order 字段
覆盖 quality_status
覆盖 risk veto
将 degraded 数据解释为确定性交易信号
绕过 Relay 读取 raw provider
伪造研究证据或信号置信度
```

### 8. Manual Approval 边界

以下情况需要人工审批或额外审查：

```text
restricted-module 变更
live-trading 相关变更
risk-policy-change
execution-policy-change
main merge when auto-merge gate fails
codex review fails three times
```

本功能风险等级当前为：

```text
unknown
```

因此架构和开发阶段必须显式判断是否触碰 restricted modules。

### 9. Acceptance 拒绝条件

出现以下任一情况，验收必须拒绝：

```text
/product/** API 规则被违反
Streamlit 被未经批准标记为 legacy / deprecated / 待删除
raw provider 被产品或 signal workflow 直接调用
响应缺少数据质量字段
mock / demo / stale / fallback 被伪装为 live
provider 全失败时未 fail closed
错误或日志泄露 secret
LLM 获得买入 / 卖出 / 下单 / 仓位决策权
缺少负向测试
缺少中文 dev / test / acceptance 证据
未经批准新增真实订单能力
```