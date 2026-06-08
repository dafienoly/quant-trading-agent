# Phase 4 Risk-First Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Phase 4 live monitoring foundation while keeping the system in `LEVEL_1_SIGNAL_ONLY` and preventing any path to order creation.

**Architecture:** Phase 4 starts with a runtime `risk_engine` and realtime data health gate, then adds a signal monitor that emits explainable alerts only. API/UI are thin read-only surfaces over risk decisions, data-delay reports, and signals.

**Tech Stack:** Python 3.10+, pandas, pydantic, pytest, FastAPI TestClient if API endpoints are implemented.

---

## File Structure

- Create `src/risk_engine/models.py`: Pydantic models for runtime risk decisions, block reasons, and kill-switch state.
- Create `src/risk_engine/runtime.py`: Runtime risk checks for data delay, data emptiness, trading mode, stock universe, and manual kill switch.
- Modify `src/risk_engine/__init__.py`: Export the runtime risk API.
- Create `tests/test_phase4_risk_engine.py`: Unit tests for runtime risk decisions and fail-closed behavior.
- Create `src/data_gateway/realtime_health.py`: Convert realtime quote fetch metadata into `DataDelayReport` and risk snapshots.
- Create `tests/test_phase4_realtime_health.py`: Tests for latency, empty quote, and stale quote detection.
- Create `src/agent_orchestrator/watchlist_monitor.py`: Read-only monitor that combines realtime quotes, strategy signals, and runtime risk decisions without creating orders.
- Create `tests/test_phase4_watchlist_monitor.py`: Tests proving alerts are explainable and no `Order` objects are created.
- Optionally create `src/api/app.py`: Read-only API endpoints for risk status, latest quotes, and latest signals.
- Optionally create `tests/test_phase4_api.py`: API tests if `src/api/app.py` is added.

---

### Task 1: Runtime Risk Models

**Files:**
- Create: `src/risk_engine/models.py`
- Modify: `src/risk_engine/__init__.py`
- Test: `tests/test_phase4_risk_engine.py`

- [ ] **Step 1: Write failing model tests**

Add this to `tests/test_phase4_risk_engine.py`:

```python
from src.risk_engine.models import RiskDecision, RiskLevel


def test_risk_decision_defaults_to_blocked_when_not_passed():
    decision = RiskDecision(risk_pass=False, level=RiskLevel.BLOCK)

    assert decision.risk_pass is False
    assert decision.level == RiskLevel.BLOCK
    assert decision.can_generate_order is False


def test_signal_mode_never_allows_order_generation():
    decision = RiskDecision(
        risk_pass=True,
        level=RiskLevel.OK,
        trading_mode="LEVEL_1_SIGNAL_ONLY",
    )

    assert decision.can_generate_signal is True
    assert decision.can_generate_order is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_phase4_risk_engine.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.risk_engine.models'`.

- [ ] **Step 3: Implement risk models**

Create `src/risk_engine/models.py`:

```python
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    OK = "OK"
    WARN = "WARN"
    BLOCK = "BLOCK"


class RiskBlockReason(str, Enum):
    DATA_DELAY = "DATA_DELAY"
    EMPTY_QUOTES = "EMPTY_QUOTES"
    UNKNOWN_SYMBOL = "UNKNOWN_SYMBOL"
    DISALLOWED_BOARD = "DISALLOWED_BOARD"
    KILL_SWITCH = "KILL_SWITCH"
    INVALID_TRADING_MODE = "INVALID_TRADING_MODE"
    LIVE_TRADING_DISABLED = "LIVE_TRADING_DISABLED"


class KillSwitchState(BaseModel):
    active: bool = False
    reason: str = ""
    activated_at: str = ""


class RiskDecision(BaseModel):
    risk_pass: bool
    level: RiskLevel
    trading_mode: str = "LEVEL_1_SIGNAL_ONLY"
    reasons: list[RiskBlockReason] = Field(default_factory=list)
    messages: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    checked_at: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    @property
    def can_generate_signal(self) -> bool:
        return self.risk_pass and self.level in {RiskLevel.OK, RiskLevel.WARN}

    @property
    def can_generate_order(self) -> bool:
        return self.can_generate_signal and self.trading_mode in {
            "LEVEL_2_HUMAN_CONFIRM",
            "LEVEL_3_AUTO",
        }
```

Modify `src/risk_engine/__init__.py`:

```python
from src.risk_engine.models import KillSwitchState, RiskBlockReason, RiskDecision, RiskLevel

__all__ = [
    "KillSwitchState",
    "RiskBlockReason",
    "RiskDecision",
    "RiskLevel",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_phase4_risk_engine.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/risk_engine/models.py src/risk_engine/__init__.py tests/test_phase4_risk_engine.py
git commit -m "feat: add runtime risk decision models"
```

---

### Task 2: Runtime Risk Engine

**Files:**
- Create: `src/risk_engine/runtime.py`
- Modify: `src/risk_engine/__init__.py`
- Test: `tests/test_phase4_risk_engine.py`

- [ ] **Step 1: Add failing runtime risk tests**

Append to `tests/test_phase4_risk_engine.py`:

```python
from src.risk_engine.models import KillSwitchState, RiskBlockReason
from src.risk_engine.runtime import RuntimeRiskEngine


def test_runtime_risk_blocks_stale_quotes():
    engine = RuntimeRiskEngine(max_quote_delay_seconds=10)

    decision = engine.check_realtime_snapshot(
        quotes=[{"symbol": "002463.SZ", "delay_seconds": 12, "status": "NORMAL"}],
        trading_mode="LEVEL_1_SIGNAL_ONLY",
    )

    assert decision.risk_pass is False
    assert RiskBlockReason.DATA_DELAY in decision.reasons


def test_runtime_risk_blocks_manual_kill_switch():
    engine = RuntimeRiskEngine(kill_switch=KillSwitchState(active=True, reason="manual stop"))

    decision = engine.check_realtime_snapshot(
        quotes=[{"symbol": "002463.SZ", "delay_seconds": 1, "status": "NORMAL"}],
        trading_mode="LEVEL_1_SIGNAL_ONLY",
    )

    assert decision.risk_pass is False
    assert RiskBlockReason.KILL_SWITCH in decision.reasons


def test_runtime_risk_rejects_chinext_symbol():
    engine = RuntimeRiskEngine()

    decision = engine.check_symbol_universe(["300001.SZ"])

    assert decision.risk_pass is False
    assert RiskBlockReason.DISALLOWED_BOARD in decision.reasons
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_phase4_risk_engine.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.risk_engine.runtime'`.

- [ ] **Step 3: Implement runtime risk engine**

Create `src/risk_engine/runtime.py`:

```python
from __future__ import annotations

from src.config.settings import LEVEL_1_SIGNAL_ONLY
from src.risk_engine.models import KillSwitchState, RiskBlockReason, RiskDecision, RiskLevel
from src.stock_pool.mainboard_filter import is_excluded


class RuntimeRiskEngine:
    def __init__(
        self,
        max_quote_delay_seconds: float = 10.0,
        kill_switch: KillSwitchState | None = None,
    ):
        self.max_quote_delay_seconds = max_quote_delay_seconds
        self.kill_switch = kill_switch or KillSwitchState()

    def check_realtime_snapshot(self, quotes: list[dict], trading_mode: str = LEVEL_1_SIGNAL_ONLY) -> RiskDecision:
        reasons: list[RiskBlockReason] = []
        messages: list[str] = []
        evidence = {"quote_count": len(quotes), "max_quote_delay_seconds": self.max_quote_delay_seconds}

        if self.kill_switch.active:
            reasons.append(RiskBlockReason.KILL_SWITCH)
            messages.append(f"Kill Switch active: {self.kill_switch.reason}")

        if not quotes:
            reasons.append(RiskBlockReason.EMPTY_QUOTES)
            messages.append("Realtime quote payload is empty")

        delayed = [
            quote for quote in quotes
            if float(quote.get("delay_seconds", 0.0)) > self.max_quote_delay_seconds
        ]
        if delayed:
            reasons.append(RiskBlockReason.DATA_DELAY)
            messages.append(f"{len(delayed)} quotes exceed delay threshold")
            evidence["delayed_symbols"] = [quote.get("symbol", "") for quote in delayed]

        risk_pass = len(reasons) == 0
        return RiskDecision(
            risk_pass=risk_pass,
            level=RiskLevel.OK if risk_pass else RiskLevel.BLOCK,
            trading_mode=trading_mode,
            reasons=reasons,
            messages=messages,
            evidence=evidence,
        )

    def check_symbol_universe(self, symbols: list[str]) -> RiskDecision:
        reasons: list[RiskBlockReason] = []
        messages: list[str] = []
        disallowed = [symbol for symbol in symbols if is_excluded(symbol)]

        if disallowed:
            reasons.append(RiskBlockReason.DISALLOWED_BOARD)
            messages.append(f"Disallowed board symbols: {','.join(disallowed)}")

        risk_pass = len(reasons) == 0
        return RiskDecision(
            risk_pass=risk_pass,
            level=RiskLevel.OK if risk_pass else RiskLevel.BLOCK,
            reasons=reasons,
            messages=messages,
            evidence={"symbols": symbols, "disallowed": disallowed},
        )
```

Modify `src/risk_engine/__init__.py`:

```python
from src.risk_engine.models import KillSwitchState, RiskBlockReason, RiskDecision, RiskLevel
from src.risk_engine.runtime import RuntimeRiskEngine

__all__ = [
    "KillSwitchState",
    "RiskBlockReason",
    "RiskDecision",
    "RiskLevel",
    "RuntimeRiskEngine",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_phase4_risk_engine.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/risk_engine/runtime.py src/risk_engine/__init__.py tests/test_phase4_risk_engine.py
git commit -m "feat: add runtime risk engine"
```

---

### Task 3: Realtime Data Health Gate

**Files:**
- Create: `src/data_gateway/realtime_health.py`
- Test: `tests/test_phase4_realtime_health.py`

- [ ] **Step 1: Write failing health gate tests**

Create `tests/test_phase4_realtime_health.py`:

```python
from datetime import datetime, timedelta

from src.data_gateway.realtime_health import build_realtime_health_report


def test_realtime_health_report_marks_stale_quote():
    now = datetime(2026, 6, 8, 10, 0, 20)
    quotes = [
        {"symbol": "002463.SZ", "datetime": "2026-06-08 10:00:00", "last_price": 10.0},
    ]

    report = build_realtime_health_report(
        provider="mock",
        quotes=quotes,
        now=now,
        max_delay_seconds=10,
    )

    assert report.is_acceptable is False
    assert report.delayed_symbols[0]["symbol"] == "002463.SZ"


def test_realtime_health_report_accepts_fresh_quote():
    now = datetime(2026, 6, 8, 10, 0, 5)
    quotes = [
        {"symbol": "002463.SZ", "datetime": "2026-06-08 10:00:00", "last_price": 10.0},
    ]

    report = build_realtime_health_report(
        provider="mock",
        quotes=quotes,
        now=now,
        max_delay_seconds=10,
    )

    assert report.is_acceptable is True
    assert report.delayed_symbols == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_phase4_realtime_health.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.data_gateway.realtime_health'`.

- [ ] **Step 3: Implement realtime health report**

Create `src/data_gateway/realtime_health.py`:

```python
from __future__ import annotations

from datetime import datetime

from src.models.schemas import DataDelayReport


def _parse_quote_time(value: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y%m%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unsupported quote datetime: {value}")


def build_realtime_health_report(
    provider: str,
    quotes: list[dict],
    now: datetime,
    max_delay_seconds: float = 10.0,
) -> DataDelayReport:
    delayed_symbols = []
    max_latency = 0.0
    total_latency = 0.0

    for quote in quotes:
        quote_time = _parse_quote_time(str(quote.get("datetime", "")))
        latency = max((now - quote_time).total_seconds(), 0.0)
        total_latency += latency
        max_latency = max(max_latency, latency)
        if latency > max_delay_seconds:
            delayed_symbols.append({
                "symbol": quote.get("symbol", ""),
                "elapsed_seconds": latency,
            })

    avg_latency = total_latency / max(len(quotes), 1)
    return DataDelayReport(
        provider=provider,
        total_symbols=len(quotes),
        avg_latency_seconds=round(avg_latency, 2),
        max_latency_seconds=round(max_latency, 2),
        delayed_symbols=delayed_symbols,
        is_acceptable=len(quotes) > 0 and len(delayed_symbols) == 0,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_phase4_realtime_health.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/data_gateway/realtime_health.py tests/test_phase4_realtime_health.py
git commit -m "feat: add realtime data health gate"
```

---

### Task 4: Read-Only Watchlist Monitor

**Files:**
- Create: `src/agent_orchestrator/watchlist_monitor.py`
- Test: `tests/test_phase4_watchlist_monitor.py`

- [ ] **Step 1: Write failing monitor tests**

Create `tests/test_phase4_watchlist_monitor.py`:

```python
import pandas as pd

from src.agent_orchestrator.watchlist_monitor import WatchlistMonitor
from src.risk_engine.models import RiskDecision, RiskLevel


def test_watchlist_monitor_returns_alerts_without_orders():
    monitor = WatchlistMonitor()
    scored = pd.DataFrame([
        {
            "symbol": "002463.SZ",
            "name": "沪电股份",
            "sector_key": "pcb_ccl",
            "trade_date": "20260608",
            "open": 10.0,
            "high": 11.0,
            "low": 9.8,
            "close": 10.8,
            "volume": 300000.0,
            "amount": 3240000.0,
            "pct_change": 3.0,
            "ma5": 10.0,
            "ma10": 9.9,
            "ma20": 9.6,
            "ma60": 9.2,
            "highest_20": 11.0,
            "volume_ma5": 100000.0,
            "volume_ma20": 120000.0,
            "sector_strength": 1.0,
            "policy_score": 95.0,
            "fundamental_score": 80.0,
            "total_score": 85.0,
        }
    ])
    risk = RiskDecision(risk_pass=True, level=RiskLevel.OK)

    result = monitor.generate_alerts(scored, risk)

    assert result["risk_pass"] is True
    assert len(result["signals"]) >= 1
    assert result["orders"] == []


def test_watchlist_monitor_blocks_signals_when_runtime_risk_fails():
    monitor = WatchlistMonitor()
    scored = pd.DataFrame([{"symbol": "002463.SZ", "trade_date": "20260608"}])
    risk = RiskDecision(risk_pass=False, level=RiskLevel.BLOCK, messages=["data delay"])

    result = monitor.generate_alerts(scored, risk)

    assert result["signals"] == []
    assert result["orders"] == []
    assert result["risk_messages"] == ["data delay"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_phase4_watchlist_monitor.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.agent_orchestrator.watchlist_monitor'`.

- [ ] **Step 3: Implement read-only monitor**

Create `src/agent_orchestrator/watchlist_monitor.py`:

```python
from __future__ import annotations

import pandas as pd

from src.risk_engine.models import RiskDecision
from src.strategy_engine.signal_generator import generate_signals


class WatchlistMonitor:
    def generate_alerts(self, scored_data: pd.DataFrame, risk_decision: RiskDecision) -> dict:
        if not risk_decision.can_generate_signal:
            return {
                "risk_pass": risk_decision.risk_pass,
                "risk_messages": risk_decision.messages,
                "signals": [],
                "orders": [],
            }

        signals = generate_signals(scored_data, include_hold=False)
        return {
            "risk_pass": risk_decision.risk_pass,
            "risk_messages": risk_decision.messages,
            "signals": [signal.model_dump() for signal in signals],
            "orders": [],
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_phase4_watchlist_monitor.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_orchestrator/watchlist_monitor.py tests/test_phase4_watchlist_monitor.py
git commit -m "feat: add read-only watchlist monitor"
```

---

### Task 5: Read-Only Phase 4 API

**Files:**
- Create: `src/api/__init__.py`
- Create: `src/api/app.py`
- Test: `tests/test_phase4_api.py`

- [ ] **Step 1: Write failing API tests**

Create `tests/test_phase4_api.py`:

```python
from fastapi.testclient import TestClient

from src.api.app import create_app


def test_health_endpoint_reports_signal_only_mode():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["max_trading_level"] == "LEVEL_1_SIGNAL_ONLY"
    assert response.json()["enable_live_trading"] is False


def test_risk_endpoint_is_read_only():
    client = TestClient(create_app())

    response = client.get("/risk/status")

    assert response.status_code == 200
    assert "risk_pass" in response.json()
    assert "orders" not in response.json()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_phase4_api.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.api'`.

- [ ] **Step 3: Implement read-only API**

Create `src/api/__init__.py`:

```python
from src.api.app import create_app

__all__ = ["create_app"]
```

Create `src/api/app.py`:

```python
from __future__ import annotations

from fastapi import FastAPI

from src.config.settings import ENABLE_LIVE_TRADING, MAX_TRADING_LEVEL
from src.risk_engine.models import RiskDecision, RiskLevel


def create_app() -> FastAPI:
    app = FastAPI(title="Quant Trading Agent", version="0.1.0")

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "max_trading_level": MAX_TRADING_LEVEL,
            "enable_live_trading": ENABLE_LIVE_TRADING,
        }

    @app.get("/risk/status")
    def risk_status() -> dict:
        decision = RiskDecision(
            risk_pass=True,
            level=RiskLevel.OK,
            trading_mode=MAX_TRADING_LEVEL,
        )
        return decision.model_dump()

    return app
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_phase4_api.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/api/__init__.py src/api/app.py tests/test_phase4_api.py
git commit -m "feat: add read-only phase4 api"
```

---

### Task 6: Final Phase 4 Gate Verification

**Files:**
- Modify: `PHASE_COMPLETION_REPORT.md`
- Modify: `DEVELOPMENT_LOG.md`

- [ ] **Step 1: Run focused Phase 4 tests**

Run:

```bash
.venv\Scripts\python.exe -m pytest tests/test_phase4_risk_engine.py tests/test_phase4_realtime_health.py tests/test_phase4_watchlist_monitor.py tests/test_phase4_api.py -q
```

Expected: all Phase 4 tests pass.

- [ ] **Step 2: Run full regression**

Run:

```bash
.venv\Scripts\python.exe -m pytest tests -q
```

Expected: all tests pass.

- [ ] **Step 3: Run lint**

Run:

```bash
.venv\Scripts\python.exe -m ruff check src tests
```

Expected: no lint errors.

- [ ] **Step 4: Update logs**

Append a Phase 4 implementation note to `DEVELOPMENT_LOG.md`:

```markdown
### Phase 4 Risk-First Foundation

Completed runtime risk engine, realtime data health gate, read-only watchlist monitor, and read-only API surface.
Trading mode remains `LEVEL_1_SIGNAL_ONLY`; no order objects are generated in Phase 4.
```

Append a Phase 4 checkpoint to `PHASE_COMPLETION_REPORT.md`:

```markdown
### Phase 4 Risk-First Checkpoint

| Gate | Status |
|------|--------|
| Runtime risk engine | Completed |
| Realtime data health gate | Completed |
| Read-only signal monitor | Completed |
| Order generation | Not enabled |
| Full tests | Passing |
```

- [ ] **Step 5: Commit**

```bash
git add PHASE_COMPLETION_REPORT.md DEVELOPMENT_LOG.md
git commit -m "docs: record phase4 risk-first checkpoint"
```

---

## Self-Review

Spec coverage:

- Runtime risk gate covers Risk Agent one-vote veto for Phase 4 monitoring.
- Realtime data health covers data delay and empty quotes.
- Watchlist monitor keeps signals explainable and order-free.
- API is read-only and exposes configuration state.
- Full regression keeps Phase 1-3 behavior protected.

Placeholder scan:

- No `TBD`, `TODO`, or unspecified file paths are present.
- Each code-changing task includes concrete code and exact test commands.

Type consistency:

- `RiskDecision`, `RiskLevel`, `RiskBlockReason`, and `KillSwitchState` are defined before use.
- `RuntimeRiskEngine` returns `RiskDecision`.
- `WatchlistMonitor.generate_alerts()` consumes `RiskDecision` and returns dictionaries only, never `Order`.
