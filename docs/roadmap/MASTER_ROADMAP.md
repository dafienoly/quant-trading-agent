# Quant Trading Agent MASTER_ROADMAP

> Canonical path: `docs/roadmap/MASTER_ROADMAP.md`  
> Compatibility source: `docs/roadmap/MASTER_ROADMAP_AGENT_EXECUTABLE.md`  
> Version: R1.0 Platform Rescue + OSS-Reuse Roadmap  
> Status: Canonical. All future roadmap reads and Agent handoffs must start here.  
> Updated intent: stop feature sprawl, rebuild the engineering foundation, enforce real-data governance, then grow quant research/backtest/trading capabilities.

---

## 0. Canonical status and conflict rules

This file is the canonical entrypoint for all future roadmap reads:

```text
docs/roadmap/MASTER_ROADMAP.md
```

If another roadmap, historical handoff, old planning document, feature spec or Agent-generated document conflicts with this file, use this priority order:

1. `docs/roadmap/MASTER_ROADMAP.md`
2. Approved ADRs under `docs/adr/`
3. Approved feature requirements under `docs/requirements/`
4. Approved architecture docs under `docs/design/`
5. `docs/roadmap/MASTER_ROADMAP_AGENT_EXECUTABLE.md`
6. Historical notes, chat summaries and archived roadmap drafts

The compatibility file may remain for historical references, but it must not become a second source of truth. New roadmap changes must update this canonical file first.

---

## 1. One-line system positioning

Quant Trading Agent is not an LLM stock-picking toy. It is an engineered research, monitoring, backtesting and trading-assistance system for A-share technology-growth investing.

The long-term product chain is:

```text
AgentOps governance
  -> trusted market/fundamental data
  -> Provider Contract and no-silent-fallback governance
  -> auditable Tool Registry
  -> governed Model Gateway and Research Agent Layer
  -> reproducible Decision Snapshot and Evidence Engine
  -> bounded Position Sizing and deterministic Risk Sentinel
  -> factor research, validation and explainable backtests
  -> modern watchlist / QMT decision dashboard
  -> paper trading and human confirmation
  -> broker readonly shadow
  -> small-size human-confirmed execution
  -> LEVEL_3_AUTO evaluation only
```

The system's strategic research focus remains:

```text
A-share technology-growth investing
semiconductor subsectors
PCB / CCL / optical interconnect
storage / HBM / memory chain
semiconductor equipment and materials
AI server and infrastructure chain
large-model applications
```

These are research hypotheses, not conclusions. The system must convert them into testable, falsifiable, replayable and trackable Alpha hypotheses.

---

## 2. Non-negotiable project facts

### 2.1 Safety stage

The current default stage is:

```text
LEVEL_1_SIGNAL_ONLY
```

V16 is a platform-foundation stage. V17 introduces research, factor and backtest systems. V18 introduces paper trading and human confirmation. V19 introduces broker readonly and small-size human-confirmed trading. `LEVEL_3_AUTO` is evaluation-only and must not be exposed as a normal product option.

LLM may explain, summarize, rank and draft evidence. LLM must never directly submit orders, modify broker state, bypass provider checks, override risk controls, change kill-switch rules, or silently convert failed live data into demo data.

### 2.2 Streamlit and frontend migration

Current Streamlit Dashboard remains an effective product entrypoint until a new frontend baseline passes architecture, CI and E2E gates.

However, future complex product surfaces should follow a strangler migration strategy:

```text
Phase A: keep Streamlit working; forbid breaking existing product entrypoint.
Phase B: create a React + Vite + TypeScript Product Web Shell behind an architecture gate.
Phase C: new complex pages such as Data Health Center, AgentOps Control Tower, Watchlist Board, Factor Lab and Backtest Tearsheet may move to the new shell after CI/E2E exists.
Phase D: Streamlit can be marked legacy only after an approved ADR proves route parity and user acceptance.
```

Until the React baseline exists, frontend Issues must explicitly choose:

```text
Option A: Streamlit quick product entrypoint
Option B: React + Vite + TypeScript long-term product console
```

### 2.3 Product API prefix

All product-level APIs must stay under:

```text
/product/**
```

Future namespaces must stay under this family:

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
/product/trading-journal/**
```

Do not introduce a parallel business API prefix such as `/api/**` unless an Architect review explicitly approves it.

### 2.4 Issue Pipeline fact

A full Issue Pipeline is not a single workflow run. It is a pipeline instance composed of GitHub Actions runs, stages, PR validation, gates, artifacts and reports.

AgentOps must be pipeline-instance-centric, not merely a list of recent workflow runs.

### 2.5 Real-data rule

The most important product rule is:

```text
Live mode: failed live data must fail visibly.
Live mode: mock/demo/fallback data must never impersonate live data.
Demo mode: demo data is allowed only when explicitly enabled and globally marked.
Backtest mode: historical data must include provider, version, timestamp and coverage metadata.
```

No module may return a trading signal, buy candidate, position sizing output or risk decision without a `data_status` and evidence references.

---

## 3. OSS reuse strategy

The project should aggressively learn from existing AI trading-agent open-source projects, but must not become a multi-repository code dump.

Reference index:

```text
https://github.com/LLMQuant/awesome-trading-agents/blob/master/README.zh-CN.md
```

Reuse rule:

```text
Borrow architecture patterns, role definitions, API ideas, tool schemas, skill contracts, UI flows and evaluation methods.
Do not blindly copy incompatible source code into the core runtime.
All imported ideas must pass Provider Contract, Tool Registry, Evidence Engine, Risk Sentinel and licensing review.
```

### 3.1 QuantGPT-inspired factor research

Reference:

```text
https://github.com/Miasyster/QuantGPT
```

Borrow:

```text
factor expression engine
operator registry
batch factor generation
factor scoring
rolling validation
anti-overfit checks
research memory / knowledge base
factor report generation
```

Do not directly import early-stage cloud-specific, contest-specific or non-A-share assumptions without an adapter.

Target internal module:

```text
src/quantos/research/factors/
```

### 3.2 TradingAgents-inspired research roles

Borrow the multi-role research process:

```text
Market Analyst
Sector Analyst
Technical Analyst
Fundamental Analyst
Catalyst Analyst
Bull Researcher
Bear Researcher
Risk Officer
PM Agent
```

The role layer must output evidence-backed recommendations only. It must not place orders.

Target internal module:

```text
src/agentos/research_agents/
```

### 3.3 AI-Trader-inspired skill/API discipline

Borrow the idea of explicit `SKILL.md`, API specs and Agent integration guides.

Target structure:

```text
.agent/skills/
  pm/SKILL.md
  architect/SKILL.md
  developer/SKILL.md
  tester/SKILL.md
  reviewer/SKILL.md
  acceptance/SKILL.md
  market-data/SKILL.md
  quant-researcher/SKILL.md
  risk-officer/SKILL.md
  trading-operator/SKILL.md
```

Each skill must declare:

```yaml
role: string
allowed_paths: string[]
forbidden_paths: string[]
required_inputs: string[]
required_outputs: string[]
must_generate_docs: boolean
must_generate_tests: boolean
risk_level: LEVEL_1_SIGNAL_ONLY | LEVEL_2_HUMAN_CONFIRM | LEVEL_3_AUTO_EVAL
human_approval_required: boolean
```

### 3.4 MCP/tool ecosystem bridge

MCP market data, backtest, portfolio and trading-memory projects may be used as optional bridges. They must never be the only trusted data layer.

All external tools must be wrapped by:

```text
Provider Contract
Tool Registry
Evidence Engine
Audit Log
Rate-limit / retry policy
```

---

## 4. Target architecture: AgentOS + QuantOS

The system is divided into two controlled planes.

### 4.1 AgentOS: build, govern and observe the software/Agent system

```text
src/agentos/
  runtime/              Agent runtime abstraction
  skills/               Skill loading and validation
  pipeline/             Issue -> stage -> PR pipeline model
  gates/                merge, evidence and safety gates
  bugfix/               restricted auto-fix system
  model_gateway/        LLM provider routing and policy
  observability/        run_id, trace_id, audit log, event log
  evidence/             PR evidence packs and decision evidence
  docs/                 generated user guide / dev guide helpers
```

AgentOS owns:

```text
GitHub Issue Pipeline
Agent abstraction layer
Bug auto-fix system
Evidence Pack generation
CI/CD gates
logs, traces and auditability
Agent behavior constraints
```

### 4.2 QuantOS: market, research, risk and trading assistance

```text
src/quantos/
  market_data/          live and historical data relay
  fundamentals/         filings, announcements and financial data
  research/             factor, sector, catalyst and company research
  backtest/             strategy validation and tearsheets
  decision/             decision snapshot and evidence engine
  portfolio/            position sizing and exposure model
  risk/                 deterministic risk sentinel
  paper_trading/        simulated orders and portfolio
  broker_shadow/        readonly broker state
  execution/            human-confirmed execution adapters only
  journal/              trading journal and replay
```

QuantOS owns:

```text
行情可信性
因子挖掘
研究证据
回测验证
风控规则
纸面交易
只读券商影子
小额人工确认交易
```

### 4.3 Product surfaces

```text
apps/
  streamlit-dashboard/      current product entrypoint
  product-web/             future React + Vite + TypeScript console
  api-server/              FastAPI product backend if/when separated
```

Core product pages:

```text
AgentOps Control Tower
Data Health Center
Market Board
QMT Decision Dashboard
Watchlist
Short-term Hunter
Position Risk Board
Factor Lab
Backtest Tearsheet
Research Knowledge Base
Risk Sentinel
Paper Trading
Broker Shadow
Trading Journal
```

---

## 5. Provider Contract and no-silent-fallback design

Every market/fundamental provider must implement a shared contract.

### 5.1 Data status enum

```text
LIVE_OK        Real provider returned fresh valid data.
LIVE_PARTIAL   Real provider returned partial valid data.
LIVE_STALE     Real provider returned data, but it is stale.
LIVE_FAILED    Real provider failed; do not synthesize signal data.
DEMO_EXPLICIT  Demo data is intentionally enabled and globally visible.
BACKTEST       Historical/backtest data with versioned coverage.
UNKNOWN        Invalid state; should fail tests.
```

### 5.2 Provider response fields

Every provider response must include:

```json
{
  "data_status": "LIVE_OK | LIVE_PARTIAL | LIVE_STALE | LIVE_FAILED | DEMO_EXPLICIT | BACKTEST | UNKNOWN",
  "provider": "akshare | tencent | eastmoney | sina | tushare | miniqmt | mock",
  "symbol": "string",
  "as_of": "timestamp",
  "latency_ms": 0,
  "source_trace_id": "string",
  "errors": [],
  "warnings": [],
  "is_tradeable_signal_safe": false
}
```

### 5.3 Fallback governance

Forbidden:

```text
catch exception -> return demo quote
missing provider -> return fake market board
failed live data -> generate buy recommendation
stale data -> display as real-time data
mock provider -> appear in live mode
```

Required:

```text
failure reason displayed in UI
trace_id displayed or linkable in UI
provider diagnostics endpoint available
tests prove demo cannot impersonate live
Agent PRs modifying provider paths require manual review
```

---

## 6. Decision Snapshot and Evidence Engine

Every signal, recommendation, risk warning or position-sizing result must be represented as a snapshot:

```json
{
  "decision_id": "uuid",
  "created_at": "timestamp",
  "symbol": "string",
  "action": "WATCH | BUY_CANDIDATE | REDUCE | SELL | AVOID | NO_ACTION",
  "confidence": 0.0,
  "data_status": "LIVE_OK",
  "market_regime": "string",
  "evidence_ids": [],
  "risk_ids": [],
  "invalid_if": [],
  "human_required": true,
  "llm_explanation": "string",
  "deterministic_controls_passed": false
}
```

No Decision Snapshot may be created without evidence. No Decision Snapshot may bypass deterministic risk controls.

---

## 7. Agent execution requirements

Every future Issue must include:

```text
goal
non-goals
data requirements
data sources
data quality requirements
backend modules
API contract
frontend requirements
artifacts
Agent interpretation boundaries
safety boundary
observability
test requirements
acceptance criteria
restricted-module impact
manual merge requirement
```

Every PR must produce or update:

```text
requirements.md
design.md
implementation_report.md
test_report.md
user_guide.md
risk_report.md
evidence_pack.json
```

Merge is forbidden if:

```text
No tests for changed business logic.
No user-facing documentation for a user-visible feature.
No evidence_pack for Agent-generated work.
Provider paths changed without Provider Contract tests.
Trading/risk paths changed without manual approval.
Demo/fallback data can impersonate live data.
```

---

## 8. Unified version route

### V16: Platform rescue, real-data governance and modern product shell

V16 goal: make the system trustworthy and observable before adding more quant business logic.

```text
V16.1   Repo Rescue & Architecture Freeze
V16.2   AgentOps Control Tower Foundation
V16.3   Agent Runtime Abstraction & Skill Contract
V16.4   Bug Auto-Fix System Governance
V16.5   Logging, Audit and Observability Baseline
V16.6   No Silent Fallback Contract
V16.7   Market Data Relay v1
V16.8   Provider Test Suite & Fallback Governance
V16.9   Data Health Center
V16.10  Product Web Shell Gate: React/Vite/TypeScript or Streamlit Extension Decision
V16.11  Watchlist & Market Board v1
V16.12  QMT Decision Dashboard IA and Visual System
V16.13  GitHub Pipeline v2 Evidence Pack Gate
V16.14  Documentation System and User-Facing Release Notes
V16.15  Legacy Isolation / Strangler Migration Plan
```

V16 acceptance:

```text
Live data failures are visible, not hidden.
Demo data cannot impersonate live data.
Every market-data API returns data_status.
Users can see why live data is unavailable.
Agent PRs are constrained by Skill Contract and Evidence Pack gates.
The product has a credible dashboard IA for market, data health, watchlist and AgentOps.
No real trading is enabled.
```

### V17: Research, factors, validation and backtesting

V17 goal: build reproducible research and backtest capabilities on top of trusted data.

```text
V17.1   Quant Tool Registry
V17.2   Factor Operator Registry
V17.3   Factor Expression Parser and Validator
V17.4   A-share Daily Bar Data Coverage Contract
V17.5   Factor Lab UI v1
V17.6   Single-Factor Backtest Engine
V17.7   Batch Factor Mining v1
V17.8   Factor Scoring: IC/IR/Return/Drawdown/Turnover/Stability
V17.9   Anti-Overfit Suite
V17.10  Rolling Out-of-Sample Validation
V17.11  Backtest Engine v1: Rebalance, Fees, Slippage, Limit-up/down, Suspension
V17.12  Backtest Tearsheet v1
V17.13  Research Knowledge Base
V17.14  Sector & Catalyst Monitor
V17.15  Decision Snapshot & Evidence Engine v1
```

V17 acceptance:

```text
A user can input a factor expression and run a reproducible report.
Backtest results include data provider, coverage, assumptions and version.
Factor candidates are scored and can be rejected by anti-overfit checks.
Research Agents must check prior failed research directions before proposing repeats.
No recommendation may be generated without a Decision Snapshot and evidence.
```

### V18: Productized monitoring, portfolio assistance and paper trading

V18 goal: turn research outputs into a usable monitoring and simulated-trading product.

```text
V18.1   QMT Decision Dashboard v1
V18.2   Short-Term Hunter Board
V18.3   Position Risk Board
V18.4   Announcement and Event Risk Scanner
V18.5   Position Sizing Engine v1
V18.6   Risk Sentinel MVP
V18.7   Paper Trading Engine
V18.8   Human Confirmation Workflow
V18.9   Trading Journal and Replay
V18.10  Strategy Validation Engine v2
V18.11  Portfolio Watchlist and Alpha Map
V18.12  User Guide and Operational Runbook v1
```

V18 acceptance:

```text
The UI resembles a modern decision dashboard, not a raw demo page.
All cards show data source and data_status.
All actions are signal-only or paper-trading unless explicitly human-confirmed.
Risk Sentinel is deterministic and not controlled by LLM.
Paper trading produces a replayable journal.
```

### V19: Broker shadow, small-size human-confirmed execution and production hardening

V19 goal: connect to real broker state safely, then evaluate tiny human-confirmed execution.

```text
V19.1   Broker Readonly Shadow: Account, Position, Orders, Trades
V19.2   Broker Data Reconciliation
V19.3   Broker Shadow Risk Board
V19.4   Execution Policy Engine
V19.5   MiniQMT Write Adapter Behind Kill Switch
V19.6   Small-Size Human-Confirmed Trading v1
V19.7   Real Trade Evidence Pack
V19.8   Execution Replay and Post-Trade Audit
V19.9   Production Kill Switch and Incident Runbook
V19.10  LEVEL_3_AUTO Evaluation Harness
```

V19 acceptance:

```text
Readonly broker shadow works before any write adapter.
Write adapter is disabled by default.
Only one-hand, whitelist, main-board, human-confirmed execution is evaluated.
Every real trade has evidence, confirmation, order response and replay record.
LEVEL_3_AUTO remains evaluation-only.
```

### V20: Scaling, governance and research productivity

V20 goal: make the platform sustainable for long-term Agent-assisted research and product development.

```text
V20.1   Multi-Provider Data Quality Scorecard
V20.2   Fundamental Data Relay and Filing Intelligence
V20.3   Industry Chain Ontology and Alpha Evidence Graph
V20.4   Model Gateway Cost/Latency/Quality Governance
V20.5   Agent Evaluation Benchmark and Regression Suite
V20.6   Scenario Stress Testing and Market Regime Library
V20.7   Multi-User Product Configuration and Secrets Governance
V20.8   Release Train, Changelog and Migration Automation
```

V20 acceptance:

```text
The system can continuously evaluate data quality, agent quality and research quality.
The product has release governance instead of ad-hoc feature piling.
Fundamental and industry-chain research are connected to evidence graphs.
Agents can improve productivity without bypassing safety gates.
```

---

## 9. V16 detailed implementation plan

### V16.1 Repo Rescue & Architecture Freeze

Objective: stop expanding the old structure before defining module boundaries.

Deliverables:

```text
docs/adr/ADR-0001-platform-rescue-and-strangler-migration.md
docs/adr/ADR-0002-no-silent-fallback.md
docs/adr/ADR-0003-agent-skill-contract.md
docs/adr/ADR-0004-product-web-shell-gate.md
```

Acceptance:

```text
New feature Issues must reference the relevant ADR.
No new major module may be added without module boundary declaration.
Old dashboard remains usable but no longer becomes a dumping ground for unrelated concerns.
```

### V16.2 AgentOps Control Tower Foundation

Objective: make pipeline instances visible.

Deliverables:

```text
/product/agentops/pipelines
/product/agentops/pipelines/{feature_id}
/product/agentops/runs
/product/agentops/gates
```

Acceptance:

```text
AgentOps groups Issue, branch, PR, stage runs, artifacts and gates by feature_id.
It does not confuse one workflow run with the full pipeline.
```

### V16.3 Agent Runtime Abstraction & Skill Contract

Objective: make Codex, Claude, DeepSeek or other agents interchangeable behind a constrained interface.

Deliverables:

```text
src/agentos/runtime/
.agent/skills/*/SKILL.md
.agent/contracts/agent_stage.schema.json
.agent/contracts/agent_output.schema.json
```

Acceptance:

```text
Agent output is schema-validated.
Agents cannot modify forbidden paths without explicit review.
Data, risk and trading modules require manual approval.
```

### V16.4 Bug Auto-Fix System Governance

Objective: allow automation to fix safe failures only.

Allowed auto-fix:

```text
test failures
format/lint failures
documentation omissions
non-trading UI regressions
non-risk API schema mismatches
```

Forbidden auto-fix:

```text
trading execution
risk thresholds
broker adapters
position sizing formulas
provider fallback policy
secrets or credentials
```

### V16.5 Logging, Audit and Observability Baseline

Objective: every meaningful action has traceability.

Deliverables:

```text
src/agentos/observability/trace_context.py
src/agentos/observability/audit_log.py
src/agentos/observability/event_log.py
src/agentos/evidence/evidence_store.py
```

Acceptance:

```text
Every provider request has trace_id.
Every agent run has run_id.
Every decision has decision_id.
Every failure can be linked to an audit event.
```

### V16.6 No Silent Fallback Contract

Objective: end the current demo-data ambiguity.

Deliverables:

```text
src/quantos/contracts/data_status.py
src/quantos/contracts/provider_contract.py
src/quantos/contracts/provider_error.py
```

Acceptance:

```text
Live failures return LIVE_FAILED.
Demo requires DEMO_EXPLICIT.
UI must show failure reason.
Tests prove fake/demo data cannot satisfy live-signal checks.
```

### V16.7 Market Data Relay v1

Objective: create a trusted market data relay.

Deliverables:

```text
src/quantos/market_data/relay.py
src/quantos/market_data/provider_registry.py
src/quantos/market_data/providers/akshare_provider.py
src/quantos/market_data/providers/tencent_provider.py
src/quantos/market_data/providers/eastmoney_provider.py
src/quantos/market_data/providers/mock_provider.py
src/quantos/market_data/diagnostics.py
```

Acceptance:

```text
At least 10 A-share main-board symbols can return LIVE_OK, LIVE_PARTIAL, LIVE_STALE or LIVE_FAILED.
Failure includes provider, error code, latency, last_success_at and trace_id.
Mock provider is disabled unless DEMO_MODE=true.
```

### V16.8 Provider Test Suite & Fallback Governance

Objective: make provider behavior testable.

Acceptance:

```text
Provider contract unit tests exist.
Live-disabled and live-failed paths are tested.
Provider timeout, parse failure and stale data are tested.
No provider test allows silent fallback.
```

### V16.9 Data Health Center

Objective: tell the user exactly why live data is unavailable.

Required UI fields:

```text
current provider
provider status
last successful fetch
current failure reason
latency
coverage
rate-limit status
stale status
fallback allowed or forbidden
repair suggestion
trace link
```

### V16.10 Product Web Shell Gate

Objective: decide and prepare the long-term frontend baseline.

Acceptance:

```text
Architect must approve React/Vite/TypeScript before building complex new product pages there.
If approved, CI, typecheck and E2E smoke test must exist before migration.
If not approved, Streamlit extension must still satisfy Data Health and no-fallback requirements.
```

### V16.11 Watchlist & Market Board v1

Objective: provide a usable watchlist and market board.

Required cards:

```text
market regime
suggested exposure range
sector direction
watchlist
must-handle risks
data health
```

Acceptance:

```text
No live data -> no buy recommendation.
Every card shows data source and data_status.
Every recommendation has evidence or is downgraded to WATCH/NO_ACTION.
```

### V16.12 QMT Decision Dashboard IA and Visual System

Objective: design the dashboard shown in the target screenshot style.

Required layout:

```text
Top: date, refresh state, data mode, provider status.
Left: market conclusion, exposure range, risk level, today's strategy.
Right: market score, radar chart, breadth/trend card.
Middle: sector strategy, operating instructions, current state.
Bottom: position risk, announcement risk, must-handle list.
Side: short-term hunter candidate cards.
```

### V16.13 GitHub Pipeline v2 Evidence Pack Gate

Objective: make every Agent PR auditable.

Acceptance:

```text
PR without evidence_pack.json cannot pass.
PR without user_guide for user-visible change cannot pass.
Provider/risk/trading path changes require manual gate.
```

### V16.14 Documentation System and User-Facing Release Notes

Objective: every feature ships with user-facing explanation.

Required docs:

```text
what changed
how to use
what data source is used
failure modes
known limitations
risk notes
rollback notes
```

### V16.15 Legacy Isolation / Strangler Migration Plan

Objective: isolate old code without breaking it.

Acceptance:

```text
Current dashboard continues working.
New modules live under AgentOS/QuantOS boundaries.
Old routes call new services instead of duplicating logic where possible.
Streamlit is not marked legacy until the Product Web Shell gate passes.
```

---

## 10. One-month Codex Pro x20 realistic scope

The realistic one-month target is a credible platform MVP, not a complete automatic trading system.

Must finish:

```text
V16.1 Repo Rescue & Architecture Freeze
V16.2 AgentOps Control Tower Foundation
V16.3 Agent Runtime Abstraction & Skill Contract
V16.5 Logging, Audit and Observability Baseline
V16.6 No Silent Fallback Contract
V16.7 Market Data Relay v1
V16.8 Provider Test Suite & Fallback Governance
V16.9 Data Health Center
V16.11 Watchlist & Market Board v1
V16.13 GitHub Pipeline v2 Evidence Pack Gate
```

Stretch goals:

```text
V16.10 Product Web Shell Gate
V16.12 QMT Decision Dashboard IA and Visual System
V17.1 Quant Tool Registry
V17.2 Factor Operator Registry skeleton
V17.3 Factor Expression Parser skeleton
```

Out of scope for one month:

```text
real broker write trading
LEVEL_3_AUTO
fully automated factor evolution
complex minute-level backtest engine
production-grade multi-user SaaS
```

---

## 11. Seed Epic and Issue plan

Create a new Epic:

```text
Epic: V16 Platform Rescue — No Silent Fallback + AgentOS + QuantOS + Product Dashboard Foundation
```

Initial Issues:

```text
#1 ADR: Platform Rescue and Strangler Migration
#2 DataStatus and ProviderContract
#3 Remove Silent Demo Fallback from Live Path
#4 Market Data Relay v1
#5 Provider Contract Test Suite
#6 Data Health Center
#7 Agent SKILL.md Contract
#8 Pipeline Evidence Pack Gate
#9 AgentOps Control Tower Pipeline Instance Model
#10 Observability Trace/Audit/Event Baseline
#11 Watchlist & Market Board v1
#12 QMT Decision Dashboard IA
#13 Documentation and User Release Notes Gate
#14 Legacy Isolation Plan
#15 Quant Tool Registry Skeleton
```

Labels:

```text
agent:pipeline
stage:pm-pending
epic:v16-platform-rescue
risk:platform
risk:data-provider
manual-approval-required
```

---

## 12. Final governing sentence

All new features must first prove:

```text
data is real or explicitly marked non-live;
failure is visible and traceable;
Agent behavior is constrained and auditable;
user-facing behavior is documented;
risk and trading controls remain deterministic.
```

If a feature cannot satisfy these conditions, it must not merge.
