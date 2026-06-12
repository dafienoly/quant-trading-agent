# Product Startup Services Development Guide

Date: 2026-06-12
Owner role: Architect Agent
Target readers: Developer Agent, Test Engineer Agent

## Goal

Make `scripts/start.sh` provide a product-ready one-command startup path that clearly starts the required services for live-data product use, including AkTools by default, while correctly documenting which Agents are background services and which are API-internal modules.

## Architecture

Keep `scripts/start.sh` as the WSL/Linux entrypoint and `scripts/start_product.py` as the process orchestrator. Default startup should run FastAPI, Streamlit Dashboard, and AkTools compatibility service.

BugFixAgent should remain explicit via `--with-bugfix` or a new `--full` mode because it requires `DEEPSEEK_API_KEY` and performs automated bug analysis. AkShare is not a daemon; it remains a Python library invoked by data providers inside FastAPI.

## Current Behavior

- `scripts/start.sh` calls `scripts/start_product.py "$@"`.
- Default `bash scripts/start.sh` starts only FastAPI and Streamlit Dashboard.
- `--with-aktools` is required to start AkTools compatibility service.
- `--with-bugfix` is required to start BugFixAgent watchdog job.
- AkShare is not a separate service and should not be started as a process.
- FactorDiscoveryAgent, RecommendationAgent, SignalExplanationAgent, LiveSignalOrchestrator, Risk Agent, factor engine, and backtest logic are API-internal modules invoked on demand.

## Required Product Behavior

- `bash scripts/start.sh` starts AkTools compatibility service, FastAPI, and Streamlit Dashboard by default.
- `bash scripts/start.sh --no-aktools` starts only FastAPI and Streamlit Dashboard.
- `bash scripts/start.sh --with-bugfix` starts BugFixAgent after API is healthy and only when `DEEPSEEK_API_KEY` exists.
- `bash scripts/start.sh --full` starts AkTools, FastAPI, Streamlit Dashboard, and BugFixAgent.
- `bash scripts/start.sh --dry-run` accurately lists every service that would be started.
- `runtime/product.pid.json` accurately records started service PIDs and flags.
- User-facing docs state that AkShare is an in-process Python provider, not a service.

## Files To Modify

- `scripts/start.sh`
- `scripts/start_product.py`
- `scripts/restart.sh`
- `scripts/stop_product.py`
- `tests/test_product_process_manager.py`
- `docs/user_guides/2026-06-11-a-share-live-data-closed-loop-user-manual.md`
- `docs/design/2026-06-11-wsl-product-runtime-ai-agent-architecture.md`
- `docs/dev_reports/YYYY-MM-DD-product-startup-services-dev-report.md`
- `docs/test_reports/YYYY-MM-DD-product-startup-services-test-report.md`

## Implementation Tasks

### Task 1: Add Startup Mode Tests

Modify `tests/test_product_process_manager.py`.

Add tests for:

1. Default startup includes `AkTools`, `FastAPI`, and `Streamlit`.
2. `--no-aktools` skips AkTools.
3. `--full` implies AkTools and BugFixAgent.
4. `--dry-run` lists the planned services accurately.
5. PID metadata records AkTools only when it starts.

The tests should monkeypatch process startup instead of launching real services.

Expected command:

```bash
./.venv/bin/python -m pytest tests/test_product_process_manager.py -q
```

Before implementation, the new tests should fail because default startup does not start AkTools and `--no-aktools` / `--full` are not implemented.

### Task 2: Implement Startup Modes

Modify `scripts/start_product.py`.

Add flags:

```python
parser.add_argument("--no-aktools", action="store_true", help="Do not start the AkTools compatibility service")
parser.add_argument("--with-aktools", action="store_true", help=argparse.SUPPRESS)
parser.add_argument("--with-bugfix", action="store_true", help="Start BugFix Agent job")
parser.add_argument("--full", action="store_true", help="Start AkTools and BugFix Agent in addition to API and Dashboard")
```

Compute service mode once:

```python
start_aktools = not args.no_aktools or args.with_aktools or args.full
start_bugfix = args.with_bugfix or args.full
```

Use `start_aktools` and `start_bugfix` for:

- port conflict checks
- service startup
- dry-run output
- PID metadata
- BugFixAgent startup

Partial startup cleanup must terminate AkTools if it was already started and another required service fails.

### Task 3: Update Shell Entrypoints

Modify `scripts/start.sh` and `scripts/restart.sh`.

Usage text should state:

```bash
# 用法: bash scripts/start.sh [--api-port 8000] [--aktools-port 8080] [--streamlit-port 8771] [--no-aktools] [--with-bugfix] [--full] [--force]
# 默认启动: AkTools + FastAPI + Streamlit
# --full 额外启动 BugFixAgent; AkShare 是 Python 包, 不是独立服务
```

Run:

```bash
bash -n scripts/start.sh
bash -n scripts/restart.sh
```

Expected: no output and exit code `0`.

### Task 4: Update Documentation

Modify `docs/design/2026-06-11-wsl-product-runtime-ai-agent-architecture.md`.

Add:

```markdown
Default `bash scripts/start.sh` starts AkTools compatibility service, FastAPI, and Streamlit Dashboard. AkShare is not a daemon; it is imported by in-process data providers inside FastAPI. BugFixAgent is a persistent watchdog job and starts only when `--with-bugfix` or `--full` is passed and `DEEPSEEK_API_KEY` exists. FactorDiscoveryAgent, RecommendationAgent, SignalExplanationAgent, LiveSignalOrchestrator, Risk Agent, and factor/backtest services are API-internal modules invoked on demand, not independent OS processes.
```

Modify `docs/user_guides/2026-06-11-a-share-live-data-closed-loop-user-manual.md`.

The quick start should show:

```bash
bash scripts/start.sh
```

Full startup:

```bash
export DEEPSEEK_API_KEY="your_key"
bash scripts/start.sh --full
```

API/UI-only debug startup:

```bash
bash scripts/start.sh --no-aktools
```

Manual AkTools startup should move to troubleshooting only:

```bash
./.venv/bin/python -m uvicorn src.integrations.aktools_compat_app:app --host 127.0.0.1 --port 8080
```

### Task 5: Verification

Run:

```bash
./.venv/bin/python -m ruff check scripts/start_product.py tests/test_product_process_manager.py
bash -n scripts/start.sh
bash -n scripts/restart.sh
./.venv/bin/python -m pytest tests/test_product_process_manager.py tests/test_aktools_compat_app.py -q --basetemp=runtime/pytest-tmp-startup-services
```

Run dry-run smoke:

```bash
bash scripts/start.sh --dry-run
bash scripts/start.sh --dry-run --no-aktools
bash scripts/start.sh --dry-run --full
```

Expected:

- default dry-run lists AkTools, FastAPI, Streamlit
- `--no-aktools` dry-run lists FastAPI and Streamlit only
- `--full` dry-run lists AkTools, FastAPI, Streamlit, BugFixAgent

Optional WSL real startup smoke:

```bash
bash scripts/start.sh --force
curl http://127.0.0.1:8000/product/health
curl http://127.0.0.1:8080/version
curl http://127.0.0.1:8000/product/runtime/services
bash scripts/stop.sh --force
```

Only run this if ports are free and the environment allows starting services.

## Handoff Reports

Developer Agent must create:

```text
docs/dev_reports/YYYY-MM-DD-product-startup-services-dev-report.md
```

Test Engineer Agent must create:

```text
docs/test_reports/YYYY-MM-DD-product-startup-services-test-report.md
```

Both reports must include exact commands and outputs.

## Acceptance Gate

Architecture review can pass only if:

- `bash scripts/start.sh --dry-run` lists AkTools, FastAPI, Streamlit.
- `bash scripts/start.sh --dry-run --full` lists BugFixAgent as requested.
- `bash scripts/start.sh --dry-run --no-aktools` skips AkTools.
- Tests prove default startup includes AkTools.
- Docs clearly state AkShare is not a standalone service.
- Docs clearly state which Agents are background jobs and which are API-internal modules.
- No change enables real automatic trading.

## Developer Constraints

- Do not create a fake AkShare service.
- Do not turn FactorDiscoveryAgent, RecommendationAgent, SignalExplanationAgent, LiveSignalOrchestrator, Risk Agent, factor engine, or backtest engine into daemon processes.
- Do not make BugFixAgent start silently when `DEEPSEEK_API_KEY` is missing.
- Do not enable `LEVEL_3_AUTO`.
- Do not change execution or risk behavior as part of this startup task.
- Keep backward compatibility for `--with-aktools`.
