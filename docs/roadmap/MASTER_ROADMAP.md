# Quant Trading Agent MASTER_ROADMAP

> Canonical path: `docs/roadmap/MASTER_ROADMAP.md`  
> Compatibility source: `docs/roadmap/MASTER_ROADMAP_AGENT_EXECUTABLE.md`  
> Version: R0.1 Roadmap Canonicalization  
> Scope: roadmap entrypoint and conflict-resolution rules only.

---

## 0. Canonical status

This file is the canonical entrypoint for all future roadmap reads.

All PM Agent, Architect Agent, Developer Agent, Tester Agent, Reviewer Agent and Acceptance Agent workflows must start from this path:

```text
docs/roadmap/MASTER_ROADMAP.md
```

The detailed agent-executable roadmap content is currently preserved in:

```text
docs/roadmap/MASTER_ROADMAP_AGENT_EXECUTABLE.md
```

For R0.1, this canonical file establishes the official entrypoint and the conflict-resolution rules. The compatibility file remains in place so existing links and historical Agent handoffs do not break. Future roadmap edits must update this canonical path first; compatibility aliases must not become a second source of truth.

---

## 1. One-line system positioning

Quant Trading Agent is not an LLM stock-picking toy. It is an engineered research and trading-assistance system for A-share technology growth investing.

The long-term product chain is:

```text
AgentOps observability
  -> trusted data
  -> Provider standardization
  -> auditable Tool Registry
  -> governed Model Gateway
  -> reproducible evidence
  -> bounded position sizing
  -> strategy validation
  -> explainable backtests
  -> risk sentinel
  -> strategic Alpha tracking
  -> paper trading
  -> broker readonly shadow
  -> small-size human-confirmed execution
```

The system's strategic research focus remains:

```text
semiconductor subsectors
optical interconnect
optical computing
compute-in-memory / near-memory computing
large-model applications
```

These are research hypotheses, not conclusions. The system must convert them into testable, falsifiable, replayable and trackable Alpha hypotheses.

---

## 2. Non-negotiable project facts

### 2.1 Streamlit is still the active product entrypoint

The current Streamlit Dashboard remains a valid product entrypoint. Agent-generated changes must not mark Streamlit as:

```text
legacy
deprecated
to be deleted
```

unless a future approved architecture document explicitly changes the frontend baseline.

### 2.2 Product API prefix

All product-level APIs must use:

```text
/product/**
```

Future product namespaces must stay under this family, including:

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

Do not introduce a parallel business API prefix such as `/api/**` unless an Architect review explicitly approves it.

### 2.3 Frontend route

The repository does not yet have a stable React/TypeScript frontend baseline. The first implementation choice for AgentOps, market data, backtests and Risk Sentinel should usually be Streamlit unless a specific architecture gate approves a React/Vite/TypeScript baseline.

### 2.4 Pipeline fact

A full Issue Pipeline is not a single workflow run. It is a pipeline instance composed of GitHub Actions runs, stages, PR validation, gates, artifacts and reports.

AgentOps must be pipeline-instance-centric, not merely a list of recent workflow runs.

### 2.5 Safety stage

The current default stage is:

```text
LEVEL_1_SIGNAL_ONLY
```

V16 is a platform-foundation stage. V17 introduces simulated and readonly-shadow layers before any small-size human-confirmed execution can be evaluated. `LEVEL_3_AUTO` is evaluation-only and must not be exposed as a normal product option.

---

## 3. Unified version route

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

## 4. R0 platform-first rule

Before expanding quant business functionality, the repository must first stabilize the engineering system that builds the product:

```text
R0.1 Roadmap Canonicalization
R0.2 AgentOps Control Tower completion
R0.3 Agent Runtime Abstraction
R0.4 Bug Auto-Fix System productization
R0.5 Logging, audit and operational visibility baseline
```

Business modules such as watchlist monitoring, factor mining, backtesting and execution workflows should be built on top of these platform foundations rather than bypassing them.

---

## 5. Old-roadmap conflict handling

If another roadmap or historical planning document conflicts with this canonical entrypoint and the detailed compatibility roadmap, use this priority order:

1. `docs/roadmap/MASTER_ROADMAP.md`
2. `docs/roadmap/MASTER_ROADMAP_AGENT_EXECUTABLE.md`
3. Approved feature requirements under `docs/requirements/`
4. Approved architecture under `docs/design/`
5. Historical notes, chat summaries and archived roadmap drafts

Conflict rules:

```text
Streamlit is the current effective product entrypoint.
Product APIs use /product/**.
V16.1 is AgentOps Control Tower Foundation only.
Risk Sentinel is after Market Data Relay, Provider governance, Tool Registry and Evidence Engine.
LLM may explain, summarize and rank, but must not override deterministic controls.
fallback may be visible, but stale/mock/fallback must not impersonate live signal data.
Paper Trading precedes Broker Readonly Shadow; both precede Small Size Human-Confirmed execution; LEVEL_3_AUTO is last-stage evaluation only.
```

---

## 6. Agent execution requirements

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

PM, Architect, Developer, Tester, Reviewer and Acceptance agents must treat this file as the first roadmap entrypoint.

---

## 7. Detailed roadmap source

The detailed 25-section agent-executable roadmap remains preserved in:

```text
docs/roadmap/MASTER_ROADMAP_AGENT_EXECUTABLE.md
```

This R0.1 PR intentionally avoids deleting that compatibility file. Deletion or archival should only happen after a follow-up PR can prove that all historical references, Agent handoff paths and roadmap tests are safely migrated.
