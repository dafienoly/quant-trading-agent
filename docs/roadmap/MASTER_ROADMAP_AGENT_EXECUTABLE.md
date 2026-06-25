# Quant Trading Agent MASTER_ROADMAP

> 版本：Detailed Agent-Executable Roadmap  
> 目标：让 PM Agent、Architect Agent、Developer Agent、Tester Agent、Reviewer Agent、Acceptance Agent 能按本文档拆 Issue、写 spec、做设计、实现、测试、验收。  
> 原则：本文档不是愿景 PPT，而是 Agent 可执行的产品与架构路线。任何后续需求如果与本文冲突，以本文为准，除非新 Issue 明确修改本 Roadmap。

---

## 0. 一句话定位

Quant Trading Agent 不是一个“让 LLM 荐股”的玩具，而是一个面向 A 股科技成长投资的工程化系统：

```text
AgentOps 可观测
  -> 数据可信
  -> Provider 标准化
  -> 工具可注册可审计
  -> 模型调用受控
  -> 证据可复盘
  -> 仓位有上限
  -> 策略可验证
  -> 回测可解释
  -> 风险可预警
  -> Alpha 可持续跟踪
  -> 模拟交易
  -> 券商只读 Shadow
  -> 小额人工确认交易
```

系统长期服务的核心投资方向：

```text
半导体细分领域
光互联
光计算
存算 / 存算一体
大模型应用
```

但系统不能把“看好这些方向”当作结论，而要把它们变成可验证、可证伪、可回放、可跟踪的 Alpha 假设。

---

# 1. 当前项目事实与不可违背约束

## 1.1 当前有效产品入口

当前 Streamlit Dashboard 仍是有效产品入口，承载行情、信号、配置、反馈、回测等产品页面。

不得将 Streamlit 错误标记为：

```text
legacy
deprecated
待删除
```

## 1.2 产品 API 前缀

产品 API 统一挂载在：

```text
/product/**
```

后续新增产品级 API 必须使用：

```text
/product/agentops/**
/product/market/**
/product/tools/**
/product/model-gateway/**
/product/decisions/**
/product/position-sizing/**
/product/backtests/**
/product/risk-sentinel/**
/product/fundamental/**
/product/alpha/**
/product/paper-trading/**
/product/broker-shadow/**
```

除非经过 Architect 明确评审，不得新建风格割裂的业务前缀：

```text
/api/**
```

## 1.3 前端路线

当前仓库没有稳定 React/TypeScript 前端基线。  
因此所有涉及前端的 Issue 必须先判断采用：

```text
方案 A：沿用 Streamlit，快速接入现有产品入口；
方案 B：新增 React + Vite + TypeScript，用于长期独立控制台。
```

默认规则：

```text
AgentOps、行情、回测、Risk Sentinel 第一阶段优先 Streamlit；
当 React 基座真正完成并有 CI/E2E 后，再迁移复杂交互页面。
```

## 1.4 Agent Pipeline 事实

一次完整 Issue Pipeline 不是一个 workflow run，而是由多个 workflow runs、stage、PR validation、gate、artifact 和报告共同构成。

AgentOps 必须以 Pipeline Instance 为中心，而不是以单个 GitHub Actions run 为中心。

## 1.5 交易安全边界

当前阶段默认：

```text
LEVEL_1_SIGNAL_ONLY
```

V16 阶段不得接入真实交易。  
V17 之前不得自动下单。  
LLM 永远不得直接提交订单或覆盖风控。

---

# 2. 投资理论蒸馏：Alpha 投资风格分类器

系统必须先判断一个公司或标的属于哪类 Alpha，再选择对应数据、评分、持有逻辑、退出规则。

## 2.1 第一类：Quality Compounder Alpha，长期垄断复利型

核心三问：

```text
1. 垄断性
2. 定价权
3. 持续性
```

### 适用对象

```text
长期现金流稳定
行业格局清晰
竞争优势强
能长期保持高 ROE / ROIC
不依赖单一景气周期
```

### 垄断性观察维度

```text
市场份额
客户锁定
渠道控制
品牌心智
技术壁垒
成本优势
牌照资源
网络效应
生态绑定
供应链控制
替代难度
```

### 定价权观察维度

```text
毛利率稳定性
净利率稳定性
提价能力
成本转嫁能力
客户价格敏感度
竞品价格压力
产品差异化
合同条款
```

### 持续性观察维度

```text
需求稳定性
生命周期
监管风险
技术替代风险
管理层稳定性
现金流稳定性
资本开支压力
利润再投资能力
ROE / ROIC 稳定性
```

### 输出字段

```text
alpha_style = quality_compounder
monopoly_score
pricing_power_score
durability_score
quality_compounder_score
quality_alpha_rating
confirm_evidence_ids
disconfirm_evidence_ids
next_review_date
```

## 2.2 第二类：Prosperity Growth Alpha，景气成长型

核心三问：

```text
1. 宏观经济的稳定性
2. 行业整体的天花板
3. 业绩增速的确定性
```

这是当前系统最重点支持的类型，因为半导体细分、光互联、存算、大模型应用大多属于景气成长型 Alpha。

### 宏观稳定性观察维度

```text
利率环境
流动性
财政政策
产业政策
地缘风险
出口管制
AI 资本开支周期
云厂商资本开支
制造业景气
下游需求稳定性
```

### 行业天花板观察维度

```text
TAM
渗透率
国产替代空间
全球市场空间
技术升级周期
产品迭代速度
下游应用扩散
行业供需格局
产业链利润分配
```

### 业绩增速确定性观察维度

```text
收入增速
利润增速
订单
合同负债
毛利率
产能利用率
客户导入
产品结构
资本开支
同行验证
业绩预告
管理层指引
```

### 输出字段

```text
alpha_style = prosperity_growth
macro_stability_score
industry_ceiling_score
earnings_growth_certainty_score
prosperity_growth_score
growth_alpha_rating
confirm_evidence_ids
disconfirm_evidence_ids
next_review_date
```

## 2.3 股票池分层

```text
S：时代 Alpha 核心标的
A：高景气行业核心公司
B：主题弹性标的
C：短线交易观察
D：基本面证伪 / 降级观察
BAN：禁止池
```

交易系统必须读取股票池等级：

```text
S/A：允许进入中线/波段候选，但仍需风控和人工确认；
B：只做主题弹性，不允许长期死扛；
C：只观察或极小仓位；
D：不新增仓；
BAN：禁止买入信号。
```

---

# 3. 统一版本路线

```text
V16.1  AgentOps Control Tower Foundation
V16.2  Market Data Relay & Provider Contract
V16.3  Provider Test Suite & Fallback Governance
V16.4  Quant Tool Registry
V16.5  Model Gateway & Research Agent Layer
V16.6  Decision Snapshot & Evidence Engine
V16.7  Position Sizing Engine
V16.8  Strategy Validation Engine & Backtest Tearsheet
V16.9  Risk Sentinel MVP

V16.10 Strategic Alpha Map & Industry Ontology
V16.11 Fundamental Data Relay & Filing Intelligence
V16.12 Alpha Evidence Engine & Company Scoring
V16.13 Industry Chain Tracking & Catalyst Monitor
V16.14 Fundamental Alpha Portfolio & Watchlist

V17.0  Paper Trading & Human Confirmation
V17.1  Broker Readonly Shadow
V17.2  Small Size Human-Confirmed Trading
V17.3  LEVEL_3_AUTO Evaluation
```

---

# 4. V16.1 AgentOps Control Tower Foundation

## 目标

建立 Agent 自动开发控制塔基础层，用于观测 Issue Pipeline、Agent stage、workflow runs、PR、artifact、gate、执行模式和可信度。

核心关键词：

```text
只读
可观测
可追踪
fail-visible
不触碰交易能力
```

## 必须回答的问题

```text
Agent 是否真的执行？
Pipeline 当前跑到哪一步？
一次完整 Pipeline 由哪些 workflow runs 组成？
每个 stage 的输入、输出、gate、artifact 和日志在哪里？
执行模式是 real、dry-run、mock、fallback 还是 unknown？
当前 PR 是否具备人工合并条件？
页面是否能清楚显示 missing、unknown、blocked、failed？
```

## 数据需求

```text
.agent/current_task.yaml
.agent/state.json
.agent/handoff/*.md
.agent/gates/*.json
docs/requirements/*.md
docs/design/*.md
docs/dev_plans/*.md
docs/dev_reports/*.md
docs/test_reports/*.md
docs/review/*.md
docs/acceptance/*.md
GitHub Issue metadata
GitHub PR metadata
GitHub Actions runs/jobs/artifacts，后续增强
```

## 后端模块

```text
src/product_app/agentops/
├── pipeline_contracts.py
├── pipeline_state_reader.py
├── pipeline_aggregator.py
├── pipeline_errors.py
├── pipeline_sanitizer.py
└── trust_evaluator.py
```

## API

```text
GET /product/agentops/health
GET /product/agentops/pipelines
GET /product/agentops/pipelines/{feature_id}
GET /product/agentops/pipelines/by-issue/{issue_number}
GET /product/agentops/pipelines/{feature_id}/stages
GET /product/agentops/pipelines/{feature_id}/artifacts
```

## 数据模型

```text
AgentOpsPipelineObservation
  contract_version
  generated_at
  feature
  issue
  branch
  stages[]
  roles[]
  required_docs[]
  safety
  data_quality
  trust
  errors[]
```

```text
AgentOpsStageObservation
  stage_id
  display_role
  status
  execution_mode
  provider
  model
  source
  input_handoff
  output_artifacts
  gate
  changed_files
  test_evidence
  failure_summary
```

```text
AgentOpsTrustResult
  trust_status
  reasons[]
  blockers[]
  warnings[]
  needs_human_review
```

## UI

第一阶段优先 Streamlit。

页面至少展示：

```text
Feature Summary
Pipeline Timeline
Stage Status
Required Docs
Safety Blockers
Data Quality
Trust Reasons
Artifact Links
Failure Diagnostics
```

禁止展示或执行：

```text
approve
merge
rerun
trigger
label mutation
comment mutation
trade
order
```

## 验收标准

1. 可按 feature_id 或 issue_number 查询 AgentOps 状态。
2. API 只读，不执行任何写操作。
3. 页面可展示 feature、issue、branch、stage、role、required_docs、data_quality、safety。
4. 缺失文档显示 missing。
5. 缺失状态显示 unknown。
6. 阻塞原因显示 blocked。
7. API 失败页面不白屏。
8. 不把 demo/mock/fixture 显示成真实 pipeline 状态。
9. 不泄露 secrets、tokens、cookies、broker credentials、CI 凭证、环境变量。
10. 不触碰交易、风控、执行、行情、回测、策略、股票池等 restricted modules。
11. PR 保持人工合并，不自动合并 main。

---

# 5. V16.2 Market Data Relay & Provider Contract

## 目标

建立统一市场数据 API 和 Provider 标准化契约，让所有行情、指数、ETF、行业、历史数据都通过 Relay 统一输出。

## 核心问题

```text
行情从哪里来？
是否实时？
是否缓存？
是否 mock？
是否 stale？
是否可用于信号？
数据源失败原因是什么？
```

## 数据范围

第一批：

```text
A 股个股实时行情
A 股个股历史日线
A 股指数实时行情
A 股指数历史日线
ETF 实时行情
ETF 历史日线
行业/板块行情
交易日历
本地缓存数据
测试 fixture 数据
```

后续扩展：

```text
分钟线
资金流
涨跌停
停牌
复权因子
ETF IOPV / 溢价率
外盘映射
```

## Provider

```text
AkShareProvider
AKToolsProvider
EastMoneyProvider
LocalCacheProvider
ManualFixtureProvider，仅测试可用，不能冒充 live
```

## 数据模型

```text
MarketDataEnvelope
  request_id
  source
  provider_name
  data_type
  fetched_at
  latency_ms
  cached
  stale
  mock
  quality_status
  blocking_for_signal
  payload
  warnings[]
  errors[]
```

```text
QuoteSnapshot
  symbol
  name
  price
  prev_close
  open
  high
  low
  volume
  amount
  change
  pct_change
  timestamp
  trading_day
```

```text
BarSeries
  symbol
  frequency
  adjust
  bars[]
```

```text
DataSourceHealth
  provider_name
  status
  last_success_at
  last_error_at
  latency_ms
  rate_limit_status
  error_summary
```

## API

```text
GET /product/market/health
GET /product/market/sources
GET /product/market/quotes?symbols=
GET /product/market/indexes?symbols=
GET /product/market/etfs?symbols=
GET /product/market/bars?symbol=&start=&end=&frequency=&adjust=
GET /product/market/calendar?start=&end=
```

## 缓存与 fallback

```text
display_cache:
  页面展示可用。

analysis_cache:
  盘后分析和回放可用。

signal_cache:
  默认禁用，除非 freshness 明确满足。

execution_cache:
  禁止。
```

Fallback 规则：

```text
实时源失败 -> 本地缓存可展示，但 signal blocked；
多个实时源不一致 -> data_quality = inconsistent；
所有数据源失败 -> unavailable；
fixture 数据 -> 只能 test_mode。
```

## UI

Streamlit Dashboard 增加 Market Data Health：

```text
数据源状态
实时行情更新时间
缓存命中
stale 标记
错误摘要
信号阻断原因
```

## 验收标准

1. A 股个股、指数、ETF 可通过统一 API 查询。
2. 每条数据都能显示来源、时间戳、fetch 时间、延迟和质量状态。
3. 能明确区分 live/cache/mock/stale/error。
4. 数据源失败时返回明确错误，不静默降级。
5. stale/mock 数据可以用于展示或测试，但不得用于实盘信号。
6. 前端或 Streamlit 页面可看到数据源健康状态。
7. 不使用搜索 API 拉行情。
8. API Key 不得硬编码。
9. Provider 异常不导致页面白屏。
10. 所有 Provider 有 fixture 测试。

---

# 6. V16.3 Provider Test Suite & Fallback Governance

## 目标

建立 Provider 测试集、异常处理、fallback 治理和数据质量门禁，避免“能拉到一次数据”被误判为“数据源可靠”。

## 核心问题

```text
Provider 超时时怎么办？
字段缺失怎么办？
多个数据源不一致怎么办？
接口限流怎么办？
缓存多久算 stale？
哪些 fallback 可以展示？
哪些 fallback 可以参与信号？
mock 数据如何禁止进入 live？
```

## 测试范围

每个 Provider 必须覆盖：

```text
正常返回
空数据
字段缺失
字段类型异常
超时
限流
网络错误
编码错误
交易日非交易时段
停牌股票
涨跌停股票
指数数据
ETF 数据
缓存命中
缓存过期
fallback
```

## 数据质量门禁

```text
quality_status = complete:
  可用于展示、分析、候选信号。

quality_status = stale:
  可用于展示和复盘，不用于实盘信号。

quality_status = incomplete:
  可用于部分展示，不用于信号。

quality_status = unavailable:
  页面显示不可用，信号阻断。

quality_status = inconsistent:
  页面显示冲突，信号阻断，需要人工复核。

quality_status = mock:
  仅测试模式可用。
```

## 后端模块

```text
src/product_app/market_data/
├── provider_contracts.py
├── provider_registry.py
├── provider_health.py
├── fallback_policy.py
├── data_quality.py
└── cache_policy.py
```

## 可观测性

每个 Provider 调用必须记录：

```text
request_id
provider_name
symbol
data_type
started_at
completed_at
latency_ms
status
error_code
fallback_used
cache_status
blocking_for_signal
```

## 验收标准

1. 每个 Provider 有确定性 fixture。
2. 每个 Provider 有异常路径测试。
3. Provider 失败不会导致页面白屏。
4. fallback 后必须显示 fallback 来源和原因。
5. stale 数据默认阻断信号。
6. mock 数据不得出现在 live dashboard 中，除非显式测试模式。
7. Provider 变更必须跑 focused tests 和回归测试。
8. 数据质量门禁被测试覆盖。
9. 多源不一致时不得默默取平均。
10. 数据不可用时不得返回伪成功。

---

# 7. V16.4 Quant Tool Registry

## 目标

将行情、因子、风险、回测、报告和验证能力封装为可注册、可测试、可审计、可被 Agent 安全调用的工具。

## 核心动机

没有 Tool Registry 时：

```text
Agent 容易乱读文件；
模型容易绕过数据质量；
工具输出不可追踪；
失败不可定位；
前端和后端重复实现逻辑；
```

有 Tool Registry 后：

```text
每个工具有 schema；
每次调用有审计；
每个工具知道是否允许 stale/mock；
每个工具知道是否能产生信号；
Agent 只能调用白名单工具；
```

## 第一批工具

```text
get_realtime_quote
get_index_state
get_etf_snapshot
get_etf_premium
get_sector_strength
get_leader_stock_state
calculate_volume_price_features
calculate_intraday_trend
calculate_position_exposure
calculate_risk_score
generate_market_brief
generate_risk_report
run_backtest
get_backtest_result
get_equity_curve
get_drawdown_periods
get_regime_overlay
get_trade_records
get_position_attribution
```

## 工具契约

```text
tool_id
name
description
input_schema
output_schema
timeout_ms
allowed_data_quality
allow_stale
allow_mock
can_generate_signal
can_generate_order
requires_human_confirmation
restricted_module_touch
```

## 数据模型

```text
ToolDefinition
  tool_id
  name
  description
  input_schema
  output_schema
  permission
  data_quality_requirement
  timeout_ms
  retry_policy
```

```text
ToolExecutionLog
  request_id
  tool_id
  caller
  input_summary
  output_summary
  started_at
  completed_at
  latency_ms
  status
  error
  data_quality
  artifacts
```

## API

```text
GET  /product/tools
GET  /product/tools/{tool_id}
POST /product/tools/{tool_id}/run
GET  /product/tools/runs/{request_id}
```

第一阶段禁止 order 类工具。

## 验收标准

1. 每个工具有 schema。
2. 每个工具有测试 fixture。
3. 每次调用有 request_id。
4. 每次调用保存输入摘要、输出摘要、耗时和错误。
5. 工具失败不导致系统白屏。
6. 工具不能绕过数据质量检查。
7. 工具不能直接下单。
8. stale/mock 数据调用必须被显式记录。
9. Agent 只能调用白名单工具。
10. Tool 输出不能直接写入交易执行模块。

---

# 8. V16.5 Model Gateway & Research Agent Layer

## 目标

建立统一模型网关和研究 Agent 层，管理模型调用、prompt、stream、fallback、多语言、异常、成本和审计。

## 核心问题

```text
模型用了哪个 provider？
prompt 是哪个版本？
输出是否结构化？
fallback 是否发生？
模型失败是否降级？
成本是多少？
Agent 有没有越权？
LLM 输出有没有被误写进交易决策字段？
```

## 核心交付

```text
ModelGateway
PromptRegistry
StructuredOutputValidator
ModelFallbackPolicy
LLMCallAuditLog
Token/Cost Tracker
Stream handling
多语言输出策略
Agent tool-use policy
Research Agent layer
```

## 模型权限边界

LLM 可以输出：

```text
research_summary
news_summary
risk_explanation
candidate_ranking
factor_explanation
report_text
debug_suggestion
agent_interpretation
财报解读
行业研究摘要
```

LLM 不得输出或写入：

```text
final_buy_decision
final_sell_decision
final_position
order_request
broker_order
risk_override
```

## 数据模型

```text
ModelCallRequest
  request_id
  agent_id
  task_type
  prompt_version
  model_policy
  tool_context_ids
  language
```

```text
ModelCallResult
  request_id
  provider
  model
  prompt_version
  output_schema
  output
  validation_status
  fallback_used
  cost
  tokens
  latency_ms
  error
```

```text
PromptDefinition
  prompt_id
  version
  task_type
  input_schema
  output_schema
  allowed_tools
  forbidden_fields
```

## API

```text
POST /product/model-gateway/calls
GET  /product/model-gateway/calls/{request_id}
GET  /product/model-gateway/prompts
GET  /product/model-gateway/policies
GET  /product/model-gateway/usage
```

## 验收标准

1. 模型调用可追踪。
2. prompt 版本可追踪。
3. fallback 可追踪。
4. 结构化输出必须校验。
5. 模型失败可降级为无 LLM 摘要。
6. LLM 不能写最终买卖决策字段。
7. LLM 不能绕过 Risk Engine。
8. 所有 LLM 调用记录 token、cost、model、prompt_version 和 request_id。
9. Agent 越权调用工具必须被拒绝。
10. LLM 输出中的买卖建议必须被过滤或标记为 forbidden。

---

# 9. V16.6 Decision Snapshot & Evidence Engine

## 目标

建立交易证据与决策快照系统，用贝叶斯思想实现：

```text
先验 + 新证据 -> 后验评分 / 风险等级
```

本版本不直接下单，不直接生成最终订单。

## 核心问题

```text
这个信号为什么生成？
用了哪些数据？
数据当时是否 live？
哪些证据提高了评分？
哪些证据降低了评分？
信号是否被风控阻断？
未来表现如何？
```

## 核心数据模型

```text
DecisionSnapshot
EvidenceSnapshot
PriorStats
PosteriorScore
RiskEvidence
BlockedReason
SignalLabel
```

## 证据类型

```text
price_evidence
volume_evidence
sector_evidence
leader_stock_evidence
etf_premium_evidence
news_evidence
fundamental_evidence
risk_evidence
market_regime_evidence
portfolio_exposure_evidence
```

## DecisionSnapshot 字段

```text
snapshot_id
symbol
strategy_id
model_version
rule_version
universe_version
risk_version
market_snapshot_id
evidence_snapshot_id
score_breakdown
prior_score
posterior_score
risk_level
decision
blocked_reason
created_at
```

## 标签数据

每个信号后续必须计算：

```text
forward_return_1d
forward_return_3d
forward_return_5d
max_favorable_excursion
max_adverse_excursion
hit_stop_loss
hit_take_profit
next_open_gap
signal_success
```

## API

```text
POST /product/decisions/snapshots
GET  /product/decisions/snapshots/{snapshot_id}
GET  /product/decisions/snapshots?symbol=&strategy_id=
GET  /product/decisions/evidence/{evidence_id}
GET  /product/decisions/labels/{snapshot_id}
```

## 验收标准

1. 每个信号都有 input snapshot。
2. 每个信号都有 evidence snapshot。
3. 被阻断信号也必须记录。
4. 能基于历史分桶生成基础先验。
5. 能基于实时证据更新后验评分。
6. 能解释每个证据对评分的影响。
7. 数据不足时输出 unknown / needs_more_data，不伪造概率。
8. Agent 只能解释证据，不能直接决定买卖。
9. 信号标签能在未来回填。
10. 所有 snapshot 可回放。

---

# 10. V16.7 Position Sizing Engine

## 目标

用 fractional Kelly 思想结合硬风控生成风险调整后的最大允许仓位。

输出是：

```text
max_allowed_position
```

不是订单。

## 核心问题

```text
这个信号最多可以买多少？
胜率和盈亏比是否足够？
样本数量是否足够？
当前回撤是否需要降仓？
板块是否过度集中？
流动性是否允许？
是否触发日内亏损限制？
```

## 所需数据

```text
posterior_win_rate
average_win
average_loss
payoff_ratio
sample_count
confidence
volatility
ATR
liquidity
slippage_estimate
commission
tax
single_stock_exposure
sector_exposure
etf_overlap_exposure
cash_available
current_drawdown
daily_loss
consecutive_losses
```

## 仓位规则

```text
final_position = min(
  signal_position,
  fractional_kelly_position,
  single_stock_limit,
  sector_limit,
  liquidity_limit,
  drawdown_limit,
  daily_loss_limit,
  manual_confirm_limit
)
```

## 数据模型

```text
PositionSizingRequest
  snapshot_id
  symbol
  strategy_id
  posterior_score
  win_rate
  payoff_ratio
  account_state
  risk_state
  liquidity_state
```

```text
PositionSizingResult
  request_id
  max_allowed_position
  recommended_observation_position
  fractional_kelly_position
  risk_adjusted_position
  constraints_applied[]
  blockers[]
  warnings[]
```

## API

```text
POST /product/position-sizing/calculate
GET  /product/position-sizing/{request_id}
```

## 安全边界

```text
不提交订单
不修改持仓
不覆盖风控
不使用 full Kelly
不允许 LLM 直接写仓位
数据不足时仓位为 0 或观察仓
```

## 验收标准

1. 默认不使用 full Kelly。
2. 默认使用 1/4 Kelly 或更保守比例。
3. 数据不足时仓位为 0 或观察仓。
4. 风控限制优先于仓位模型。
5. Risk Agent 一票否决。
6. 输出为最大允许仓位，不提交订单。
7. 仓位建议必须保存计算依据和风险证据。
8. 板块集中度和流动性约束必须生效。
9. 当日亏损和回撤约束必须生效。
10. 所有计算结果可复盘。

---

# 11. V16.8 Strategy Validation Engine & Backtest Tearsheet

## 目标

建立策略验证与完整回测报告体系，使每个策略不仅能跑出收益曲线，还能生成接近 QuantStats tearsheet 级别的完整报告，并附带 Agent 中文解读说明。

本版本不是单纯前端图表改造，而是完整闭环：

```text
数据获取
  -> 数据质量检查
  -> 回测执行
  -> 指标计算
  -> 报告生成
  -> Agent 中文解读
  -> 前端展示与导出
```

## 报告内容

完整报告至少包含：

```text
报告元数据
策略配置
数据源和数据质量
核心绩效指标
策略净值 vs Benchmark
回撤曲线
年度收益 vs Benchmark
月度收益热力图
Return Quantiles
Worst 5 Drawdown Periods
Worst 10 Drawdowns
滚动收益
滚动波动率
滚动夏普
交易明细
调仓记录
持仓权重
行业 / 因子 / 个股归因
交易成本和滑点影响
Agent 中文解读说明
```

## 数据需求

```text
个股历史日线
Benchmark 历史日线
ETF 历史日线
行业指数历史数据
交易日历
复权因子
停牌数据
涨跌停数据
手续费、印花税、滑点配置
股票池历史成分
因子历史值
调仓日期
策略信号快照
交易和持仓快照
```

## API

```text
POST /product/backtests/run
GET  /product/backtests/{backtest_id}
GET  /product/backtests/{backtest_id}/metrics
GET  /product/backtests/{backtest_id}/equity
GET  /product/backtests/{backtest_id}/drawdowns
GET  /product/backtests/{backtest_id}/returns/monthly
GET  /product/backtests/{backtest_id}/returns/yearly
GET  /product/backtests/{backtest_id}/trades
GET  /product/backtests/{backtest_id}/positions
GET  /product/backtests/{backtest_id}/attribution
GET  /product/backtests/{backtest_id}/data-quality
GET  /product/backtests/{backtest_id}/agent-interpretation
GET  /product/backtests/{backtest_id}/report.html
GET  /product/backtests/{backtest_id}/artifacts
```

## Artifact

每次回测至少生成：

```text
backtest_result.json
metrics.json
equity_curve.csv
drawdowns.csv
monthly_returns.csv
yearly_returns.csv
trades.csv
positions.csv
data_quality.json
agent_interpretation.md
tearsheet.html
```

## UI

第一阶段可使用当前 Streamlit Dashboard 的回测实验室承载。

UI 至少包含：

```text
参数配置区
核心指标卡片
净值与 Benchmark 图
回撤图
年度收益表
月度收益热力图
Worst Drawdowns 表
Return Quantiles
交易明细
持仓与归因
数据质量
Agent 中文解读
报告下载入口
```

## 验收标准

1. 能基于标准回测结果生成完整 HTML tearsheet。
2. 能生成结构化 JSON/CSV artifact。
3. 能展示策略 vs Benchmark 的净值、回撤、年度收益、月度收益、分布和最差回撤。
4. 能生成 Agent 中文解读。
5. Agent 解读必须引用结构化 metrics 和 data_quality。
6. 数据缺失、stale、mock 或质量不足时，报告必须明确提示。
7. 回测结果可复现，必须保存 backtest_id、config、data_manifest 和 artifact list。
8. 前端页面失败时不得白屏。
9. HTML 报告可在页面内查看，也可下载。
10. 不接入真实交易，不生成真实订单，不改变风控或执行模块。
11. 样本不足的策略不得升级。
12. 样本外失败的策略不得升级。
13. shadow 结果不稳定的策略不得真实交易。
14. 策略验证报告必须包含交易成本后结果。
15. 不允许只基于少数成功案例判断策略有效。
16. 每次策略版本变更必须重置或分段统计验证结果。

---

# 12. V16.9 Risk Sentinel MVP

## 目标

基于 Market Data Relay、Provider Contract、Quant Tool Registry、Evidence Engine 建立半导体 / 科技主线风险预警 MVP。

本版本只做风险预警和辅助决策，不自动下单。

## 核心场景

```text
09:22 竞价建议
10:35 盘中跳水预警
14:45 尾盘过夜决策
```

## 数据范围

```text
半导体 ETF
ETF IOPV 与溢价率
半导体中军股
AI 服务器
PCB
光模块
高位风险温度计
指数与板块强弱
外盘半导体映射
新闻公告风险
用户持仓，后续接入
```

## 后端模块

```text
src/product_app/risk_sentinel/
├── sentinel_contracts.py
├── semiconductor_universe.py
├── intraday_risk_scoring.py
├── etf_premium_monitor.py
├── leader_stock_monitor.py
├── market_breadth_monitor.py
├── news_risk_monitor.py
└── report_generator.py
```

## 风险状态

```text
low_risk
divergence
jump_risk
high_risk
panic
```

中文解释：

```text
低风险
分歧风险
跳水预警
高危
踩踏/恐慌
```

## API

```text
GET /product/risk-sentinel/health
GET /product/risk-sentinel/semiconductor/snapshot
GET /product/risk-sentinel/semiconductor/report?time_window=0922
GET /product/risk-sentinel/semiconductor/report?time_window=1035
GET /product/risk-sentinel/semiconductor/report?time_window=1445
GET /product/risk-sentinel/alerts
```

## UI

Streamlit 页面至少包含：

```text
当前风险等级
风险评分拆解
ETF 溢价
中军股状态
板块强度
市场宽度
高位风险温度
新闻/公告风险
建议动作，但不下单
```

## 验收标准

1. 能生成竞价报告。
2. 能生成盘中跳水预警。
3. 能生成尾盘过夜决策。
4. 能解释核心证据和风险来源。
5. 所有报告只做辅助决策，不自动下单。
6. 数据异常时报告必须降级或阻断。
7. 每个报告都保存输入快照和证据快照。
8. 使用 stale/mock 数据时必须显式标记。
9. 风险评分有拆解。
10. 前端失败不白屏。

---

# 13. V16.10 Strategic Alpha Map & Industry Ontology

## 目标

建立长期 Alpha 地图和产业本体，把半导体细分、光互联、光计算、存算、大模型应用拆成可跟踪的产业链结构。

## 核心战略假设

```text
AI 基础设施和 AI 应用扩散仍处于长周期早中段。
半导体细分领域、光互联、光计算、存算、大模型应用，是后续最值得持续跟踪的核心方向。
这些方向虽然估值和股价已经不低，但如果产业趋势继续验证，核心 Alpha 标的仍可能继续创新高。
```

系统不能把这个判断当作结论，而要把它变成可验证、可证伪、可回放、可迭代的研究框架。

## 五大战略方向

```text
半导体细分领域：
  先进封装、HBM/存储、设备、材料、EDA/IP、模拟芯片、功率半导体、AI 芯片、封测、晶圆制造、PCB/CCL、服务器高速互联相关芯片、国产替代关键环节。

光互联：
  光模块、光芯片、光器件、硅光、高速连接器、CPO/LPO、交换机、数据中心网络、PCB/CCL、高速铜缆与光缆替代关系。

光计算：
  光子计算、硅光计算、光电混合计算、光 AI 加速器、片上光互联、光神经网络、相关材料和器件、论文专利、产业化进度。

存算 / 存算一体：
  存算一体芯片、近存计算、DRAM/HBM、NAND/SSD、新型存储、AI 推理芯片、边缘 AI、存储控制器、高带宽内存。

大模型应用：
  AI 办公、AI 编程、AI 教育、AI 医疗、AI 金融、AI 工业软件、AI 营销、AI 客服、AI 内容生成、AI 搜索、AI Agent、企业知识库、多模态应用、端侧 AI 应用。
```

## 核心交付

```text
Strategic Alpha Map
Industry Ontology
Sector / Subsector / Theme / Company 四级结构
产业链上中下游图谱
核心公司池
可观察指标字典
证实 / 证伪信号库
Alpha Thesis Card
Agent 中文行业研究摘要
股票池分层规则
```

## 数据模型

```text
StrategicTheme
  theme_id
  name
  description
  lifecycle_stage
  core_question
  key_drivers
  key_risks
  related_subsectors
  evidence_requirements
  last_reviewed_at
```

```text
IndustryNode
  node_id
  theme_id
  parent_node_id
  name
  layer
  upstream
  downstream
  key_products
  key_metrics
  related_companies
```

```text
AlphaThesisCard
  thesis_id
  theme_id
  title
  hypothesis
  confirm_signals
  disconfirm_signals
  key_companies
  key_data_sources
  confidence
  status
  next_review_date
```

## 验收标准

1. 五大战略方向均有产业图谱。
2. 每个方向至少拆成 5 个以上细分节点。
3. 每个节点都有核心公司池。
4. 每个节点都有证实和证伪信号。
5. 每个节点都有关键数据源。
6. Agent 可以生成中文行业摘要，但不能输出买卖建议。
7. 所有结论必须绑定 evidence source。
8. 缺少数据时显示 unknown，不得强行判断。

---

# 14. V16.11 Fundamental Data Relay & Filing Intelligence

## 目标

建立基本面数据接入和财报/公告/招股书解析能力，为长期 Alpha 研究提供数据基础。

## 数据范围

```text
招股说明书
年报
半年报
季报
业绩预告
业绩快报
公告
调研纪要
投资者关系纪要
行业政策
同行财报
估值数据
股价成交数据
专利
论文
产品发布
客户案例
```

## 核心交付

```text
Fundamental Data Provider
Filing Parser
Announcement Parser
IR / 调研纪要解析
Financial Statement Normalizer
Company Profile Normalizer
Industry Event Extractor
Filing Data Quality Report
Document Evidence Store
中文摘要生成
```

## 关键字段

```text
company_id
symbol
report_type
report_period
publish_date
source
document_url
document_hash
extracted_at
revenue
revenue_growth
net_profit
net_profit_growth
gross_margin
operating_margin
roe
roic
cash_flow
inventory
accounts_receivable
capex
rd_expense
contract_liability
customer_concentration
supplier_concentration
risk_factors
management_discussion
```

## 验收标准

1. 能解析至少一种年报或季报样例。
2. 能抽取核心财务字段。
3. 能生成中文财报摘要。
4. 能标记解析失败字段。
5. 能保存 document_hash 和 source。
6. 能与公司和行业节点关联。
7. Agent 摘要必须引用结构化字段。
8. 不输出买卖建议。

---

# 15. V16.12 Alpha Evidence Engine & Company Scoring

## 目标

建立 Alpha 证据引擎和公司评分体系，把财报、公告、行业数据、估值、行情和产业链信息转化为可追踪的 Alpha Score。

系统必须支持两套评分模型：

```text
QualityCompounderScore
ProsperityGrowthScore
```

## QualityCompounderScore

用于长期垄断复利型 Alpha：

```text
monopoly_score
pricing_power_score
durability_score
quality_compounder_score
```

## ProsperityGrowthScore

用于景气成长型 Alpha：

```text
macro_stability_score
industry_ceiling_score
earnings_growth_certainty_score
prosperity_growth_score
```

## 公司评分维度

```text
行业景气度
收入增速
利润增速
毛利率趋势
现金流质量
ROE / ROIC
研发强度
资本开支
订单 / 合同
客户质量
市场份额
竞争壁垒
技术路线
国产替代空间
估值合理性
财务风险
减持风险
监管风险
```

## 输出等级

```text
S：时代 Alpha 核心标的
A：高景气行业核心公司
B：主题弹性标的
C：短线交易观察
D：基本面证伪 / 降级观察
BAN：禁止池
```

## 基本面拐点规则

```text
收入增速连续下滑
利润增速连续下滑
毛利率恶化
经营现金流背离利润
存货异常上升
应收账款异常上升
合同负债下降
资本开支收缩
研发费用异常下降
客户集中风险上升
订单减少
管理层表述转保守
同行先行下修
产业价格下跌
估值显著透支
```

## 数据模型

```text
CompanyAlphaScore
  company_id
  symbol
  theme_id
  alpha_style
  score_date
  monopoly_score
  pricing_power_score
  durability_score
  quality_compounder_score
  macro_stability_score
  industry_ceiling_score
  earnings_growth_certainty_score
  prosperity_growth_score
  valuation_score
  risk_score
  total_score
  rating
  evidence_ids
  disconfirm_evidence_ids
  status
```

```text
FundamentalTurningPoint
  company_id
  symbol
  detected_at
  turning_point_type
  severity
  evidence
  affected_scores
  recommendation_scope
```

## 验收标准

1. 每家公司能生成 Alpha Score。
2. 每个分数都有证据。
3. 每次评级变化都有原因。
4. 基本面拐点必须显式提示。
5. 系统能区分“业绩兑现”和“题材预期”。
6. 系统能区分“高估值但仍兑现”和“高估值未兑现”。
7. 系统能区分长期垄断复利型和景气成长型。
8. Agent 只能解释评分，不能直接建议买卖。

---

# 16. V16.13 Industry Chain Tracking & Catalyst Monitor

## 目标

建立产业链跟踪和催化剂监控系统，持续追踪五大战略方向的关键事件、数据更新和拐点。

## 跟踪内容

```text
财报发布
业绩预告
订单公告
产业政策
出口管制
产品发布
客户验证
产能扩张
价格变化
技术路线变化
同行业绩
云厂商资本开支
AI 模型发布
AI 应用商业化数据
专利和论文
机构调研
减持和监管风险
```

## Catalyst 类型

```text
业绩催化
订单催化
政策催化
技术催化
客户催化
价格催化
资本开支催化
行业周期催化
风险催化
证伪催化
```

## 输出

```text
Daily Alpha Monitor
Weekly Strategic Alpha Report
Monthly Industry Chain Review
Earnings Season Alpha Review
Turning Point Alert
Catalyst Calendar
```

## 验收标准

1. 每个战略方向都有催化剂日历。
2. 每个催化剂都关联公司、产业节点和证据。
3. 风险催化和证伪催化必须显著提示。
4. 能生成中文周报。
5. 能生成基本面拐点提醒。
6. 不生成真实买卖指令。
7. 数据源不可用时必须标记 unavailable。

---

# 17. V16.14 Fundamental Alpha Portfolio & Watchlist

## 目标

建立长期 Alpha 股票池和观察列表，把基本面研究结果接入交易系统上游。

## 股票池分层

```text
S级：时代 Alpha 核心标的
A级：高景气行业核心公司
B级：主题弹性标的
C级：短线交易观察
D级：基本面降级观察
BAN：禁止池
```

## 与交易系统关系

```text
S级：
  允许中线持有；
  回撤容忍度略高；
  仓位上限较高，但仍受风控约束。

A级：
  允许波段参与；
  需结合技术面和风险状态。

B级：
  只做主题弹性；
  严格止损；
  不允许长期死扛。

C级：
  只观察或极小仓位；
  必须等待信号确认。

D级：
  不新增仓；
  已持仓需触发复核。

BAN：
  不交易。
```

## 核心交付

```text
Alpha Watchlist
Company Rating Dashboard
Theme Exposure View
Fundamental Risk Alert
Alpha Thesis Review
与 Evidence Engine 关联
与 Position Sizing Engine 关联
与 Risk Sentinel 关联
Agent 中文跟踪报告
股票池版本管理
```

## 验收标准

1. 每只股票都有所属战略方向和评级。
2. 每个评级都有证据。
3. 每次股票池变更都有版本记录。
4. 交易信号必须读取股票池等级。
5. BAN 股票不得生成买入信号。
6. D 级股票不得新增仓。
7. S/A/B/C 级仓位上限不同。
8. Agent 只能建议“进入跟踪/降级观察/移出股票池”，不能下单。
9. 股票池版本必须进入回测和信号快照。

---

# 18. V17.0 Paper Trading & Human Confirmation

## 目标

建立模拟交易和人工确认闭环，为仓位模型和策略验证提供执行层数据。

## 核心模型

```text
paper_account
paper_position
paper_order
paper_fill
manual_confirmation
risk_veto
reconciliation_result
```

## API

```text
POST /product/paper-trading/orders/preview
POST /product/paper-trading/orders/confirm
GET  /product/paper-trading/orders/{order_id}
GET  /product/paper-trading/account
GET  /product/paper-trading/positions
```

## 验收标准

1. 信号能生成模拟订单。
2. 模拟订单必须经过风控。
3. 每笔订单必须人工确认。
4. 支持成交、部分成交、撤单、拒单。
5. 能从信号追溯到订单、成交、持仓、账户。
6. 不接入真实交易。
7. Paper trading 结果进入 Strategy Validation Engine。

---

# 19. V17.1 Broker Readonly Shadow

## 目标

接入 miniQMT 或券商只读能力，读取真实账户、持仓、委托、成交和资金状态，建立 shadow 交易证据。

## 数据范围

```text
真实资产
真实现金
真实持仓
可用资金
可卖数量
委托状态
成交记录
资金流水
shadow_order
shadow_pnl
reconciliation_diff
```

## 验收标准

1. 只读接入，不发起任何真实委托。
2. 系统持仓与券商持仓可对账。
3. shadow order 不下单，只记录本来会下什么。
4. shadow 结果进入 Strategy Validation Engine。
5. 权限不足或连接异常时不得降级成模拟真实账户。
6. Broker 数据异常时阻断交易相关功能。

---

# 20. V17.2 Small Size Human-Confirmed Trading

## 目标

在长期 shadow 证据充分后，允许小额、白名单、人工确认的真实交易。

## 限制

```text
小额资金
白名单股票
白名单策略
限价单
人工确认
单票限额
单日限额
板块限额
熔断
对账
告警
Kill Switch
```

## 验收标准

1. 每笔真实订单必须人工确认。
2. 每笔真实订单必须可追溯到信号、证据、仓位、风控和确认记录。
3. 只允许白名单策略和白名单标的。
4. 必须支持撤单、拒单、异常回报处理。
5. 每日亏损、连续失败、对账不一致时自动熔断。
6. LLM 不得直接提交订单。

---

# 21. V17.3 LEVEL_3_AUTO Evaluation

## 目标

只有在长期 shadow 和小额真实交易证据充分后，才评估 LEVEL_3_AUTO。

## 必须具备

```text
长期 shadow 证据
小额真实交易证据
幂等订单
重复下单防护
双重熔断
对账机制
告警机制
人工 Kill Switch
风控一票否决
策略降级机制
审计日志
异常回滚机制
```

## 原则

1. LEVEL_3_AUTO 默认关闭。
2. 自动交易不是默认目标。
3. LLM 始终不得直接决定买卖或提交订单。
4. 任何自动交易能力必须有明确资金上限、标的白名单、策略白名单和熔断条件。
5. 人工 Kill Switch 必须始终优先。
6. 长期证据不足时不得开放。

---

# 22. Agent 落地强约束

## 22.1 PM Agent 必须覆盖

每个需求文档不得只写前端界面。必须同时覆盖：

```text
用户目标
业务流程
数据需求
数据来源
数据质量
后端模块
API 契约
前端展示
Artifact 输出
Agent 解读
安全边界
可观测性
测试验收
是否触碰 restricted modules
是否需要人工合并
```

## 22.2 Architect Agent 必须覆盖

每个架构文档必须同时覆盖：

```text
数据流
模块边界
数据模型
API 设计
存储方案
任务调度
缓存和 fallback
数据质量门禁
Agent 权限边界
前端技术路线
测试策略
安全审查
失败处理
可观测性
后续扩展
```

## 22.3 Developer Agent 必须遵守

```text
不得绕过产品 API；
不得绕过 Provider；
不得绕过 Tool Registry；
不得使用 mock 冒充 live；
不得直接修改交易执行模块；
不得把 LLM 输出写入最终交易字段；
不得隐藏异常；
不得只写报告不改实现；
```

## 22.4 Tester Agent 必须覆盖

```text
正常路径
异常路径
空数据
stale 数据
mock 数据
fallback 数据
权限拒绝
API schema
UI smoke
数据质量门禁
安全边界
回归测试
```

## 22.5 Reviewer / Acceptance Agent 必须检查

```text
是否符合 /product/** 前缀
是否只读
是否触碰 restricted modules
是否有数据质量状态
是否有测试
是否有中文报告
是否有 Agent 权限边界
是否有失败降级
是否误用 mock/stale
是否自动合并 main
```

---

# 23. 旧 Roadmap 冲突处理规则

如果旧文档与本文档冲突，按以下优先级处理。

## 23.1 Streamlit 与 Frontend v2

统一口径：

```text
Streamlit 是当前有效行情产品入口。
V16.1 可新增 React，也可沿用 Streamlit。
是否新增 React 由架构门禁决定。
```

## 23.2 API 前缀

统一口径：

```text
产品 API 使用 /product/**。
```

## 23.3 V16.1 范围

统一口径：

```text
V16.1 只做 AgentOps Control Tower Foundation。
System Health、Market Data Health、BugFix Center 后移。
```

## 23.4 Risk Sentinel 顺序

统一口径：

```text
Risk Sentinel 是 P1 业务验证场景，但排在 Market Data Relay、Provider、Tool Registry、Evidence Engine 之后。
```

## 23.5 LLM 权限

统一口径：

```text
LLM 只能解释、摘要、排序。
确定性规则、风控和人工确认决定信号与执行。
```

## 23.6 fallback

统一口径：

```text
fallback 可用于展示，不默认用于信号。
stale/mock/fallback 数据不得伪装为 live。
```

## 23.7 自动交易

统一口径：

```text
必须先 Paper Trading，再 Broker Readonly Shadow，再 Small Size Human Confirmed Trading，最后才评估 LEVEL_3_AUTO。
```

---

# 24. 旧 Roadmap 处理规则

本文件合并后，旧的分散 roadmap 文档应按以下方式处理：

1. 如果旧文档只是版本路线草案，删除或移动到 `docs/roadmap/archive/`。
2. 如果旧文档包含仍有价值的细节，将细节合并到对应版本章节后再删除旧文档。
3. 如果旧文档是正式需求、架构或验收文档，不删除，保留在 `docs/requirements/`、`docs/design/`、`docs/acceptance/` 等对应目录。
4. 不得删除 #75 相关的 requirements、architecture、team plan、dev report、test report、review、acceptance 文档。
5. 删除旧 roadmap 前必须确认其内容已被本文覆盖或已迁移到 archive。

---

# 25. 后续 Issue 建议

```text
[V16.2] Market Data Relay & Provider Contract
[V16.3] Provider Test Suite & Fallback Governance
[V16.4] Quant Tool Registry
[V16.5] Model Gateway & Research Agent Layer
[V16.6] Decision Snapshot & Evidence Engine
[V16.7] Position Sizing Engine
[V16.8] Strategy Validation Engine & Backtest Tearsheet
[V16.9] Risk Sentinel MVP
[V16.10] Strategic Alpha Map & Industry Ontology
[V16.11] Fundamental Data Relay & Filing Intelligence
[V16.12] Alpha Evidence Engine & Company Scoring
[V16.13] Industry Chain Tracking & Catalyst Monitor
[V16.14] Fundamental Alpha Portfolio & Watchlist
[V17.0] Paper Trading & Human Confirmation
[V17.1] Broker Readonly Shadow
[V17.2] Small Size Human-Confirmed Trading
[V17.3] LEVEL_3_AUTO Evaluation
```

每个 Issue 必须带：

```text
目标
非目标
数据需求
API 契约
后端模块
前端要求
Agent 权限边界
测试要求
验收标准
安全边界
```
