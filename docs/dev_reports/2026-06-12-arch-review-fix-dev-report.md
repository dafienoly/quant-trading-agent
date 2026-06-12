# Architecture Review Fixes — Development Report

Date: 2026-06-12
Developer Role: Developer Agent
Branch: feature/quant-factor-v1

## Scope

- **Review Document:** `docs/review/2026-06-12-wsl-product-runtime-ai-agent-architecture-review.md`
- **Requirements:** `docs/requirements/2026-06-11-wsl-product-runtime-ai-agent-requirements.md`
- **Architecture:** `docs/design/2026-06-11-wsl-product-runtime-ai-agent-architecture.md`
- **Python:** `.venv/bin/python` → Python 3.13.5

## Changed Files

| File | Action | Purpose |
|------|--------|---------|
| `src/agent_orchestrator/output_guard.py` | **NEW** | Deterministic AI output sanitizer — shared guard |
| `src/agent_orchestrator/factor_discovery_agent.py` | Modified | Wired output guard into `discover()` |
| `src/agent_orchestrator/recommendation_agent.py` | Modified | Wired output guard into `recommend()` |
| `src/agent_orchestrator/signal_explanation_agent.py` | Modified | Wired output guard into `explain()` |
| `src/llm/model_router.py` | Modified | Lazy import OpenAI; graceful degradation when missing |
| `src/api/product_routes.py` | Modified | Fix signal explain (load real signal); API-level guard; extend runtime services |
| `scripts/stop_product.py` | Modified | Add port 8080 to KNOWN_PORTS |
| `.env.example` | Modified | Fix WSL path (backslash → forward slash) |
| `scripts/summarize_feedback_bugs.py` | Modified | Fix WSL usage example |
| `tests/test_output_guard.py` | **NEW** | 23 tests for output guard (safe, hostile, nested) |
| `tests/test_product_routes.py` | **NEW** | Runtime services, signal explain 404, LLM status |
| `tests/test_model_router.py` | Modified | Added missing-openai, get_config-no-openai tests |
| `tests/test_bug_auto_fix.py` | Modified | Added BugFixAgent construction without openai test |
| `tests/test_ai_research_agents.py` | (unchanged) | — |

## Review Finding → Code Mapping

| Review Finding | Fix | Files |
|---|---|---|
| S2: LLM safety boundary is prompt-only | Deterministic `sanitize_llm_output()` + API-level guard | `output_guard.py`, all 3 agents, `product_routes.py` |
| S2: Signal explanation fabricates `hold` | Load real signal from orchestrator; return 404 | `product_routes.py:ai_signal_explain()` |
| S2: Missing `openai` breaks local verification | Lazy import; catch ModuleNotFoundError | `model_router.py:chat_json()` |
| S3: Runtime services incomplete | Add akTools, dashboard, LLM fields | `product_routes.py:get_runtime_services()` |
| S3: Stop script misses port 8080 | Add 8080 to KNOWN_PORTS | `stop_product.py:29` |
| S3: WSL paths use `\` | Use `/` in examples | `.env.example`, `summarize_feedback_bugs.py` |

## Self-Test Commands and Results

### Static Checks

```bash
.venv/bin/python -m ruff check \
  src/agent_orchestrator/output_guard.py \
  src/agent_orchestrator/factor_discovery_agent.py \
  src/agent_orchestrator/recommendation_agent.py \
  src/agent_orchestrator/signal_explanation_agent.py \
  src/llm/model_router.py \
  src/api/product_routes.py \
  tests/test_output_guard.py \
  tests/test_model_router.py \
  tests/test_ai_research_agents.py \
  tests/test_product_routes.py \
  tests/test_bug_auto_fix.py
```

**Result:** All checks passed.

```bash
.venv/bin/python -m py_compile \
  src/agent_orchestrator/output_guard.py \
  src/agent_orchestrator/factor_discovery_agent.py \
  src/agent_orchestrator/recommendation_agent.py \
  src/agent_orchestrator/signal_explanation_agent.py \
  src/llm/model_router.py \
  src/api/product_routes.py
```

**Result:** No errors.

```bash
.venv/bin/python -m py_compile scripts/stop_product.py scripts/summarize_feedback_bugs.py
```

**Result:** No errors.

### Tests

```bash
.venv/bin/python -m pytest \
  tests/test_output_guard.py \
  tests/test_model_router.py \
  tests/test_ai_research_agents.py \
  tests/test_product_routes.py \
  tests/test_bug_auto_fix.py \
  tests/test_live_signal.py \
  -q --basetemp=runtime/pytest-tmp-arch-fix
```

**Result:** 88 passed, 1 warning (pre-existing StarletteDeprecationWarning).

### Git Diff

```bash
git status --short --branch
git diff --stat
git diff --check
```

**Result:** Clean. Branch `feature/quant-factor-v1`. 10 modified + 3 new files. No trailing whitespace or conflict markers.

## Not Run

- **API smoke (uvicorn + curl):** The touched API changes (signal explain, runtime services, LLM status) are covered by pytest with TestClient. Live WSL smoke requires external services (AkTools on :8080, Streamlit on :8771) which are not available in this session. The user can run `scripts/start.sh` manually.
- **Streamlit smoke:** Dashboard changes are limited to the backend (`/runtime/services` endpoint). No UI rendering was modified.

## Remaining Risk

| Risk | Mitigation |
|------|-----------|
| `sanitize_llm_output` may have false positives (block valid research output mentioning "sell" in a non-trade context) | Blocked outputs return `blocked_by_guard` status with `block_reasons` for debugging; agent-level and API-level guards can be tuned independently |
| `sanitize_llm_output` may have false negatives (miss novel phrasing of trade instructions) | Regex-based guard is deterministic and auditable; additional patterns can be added without code changes |
| WSL paths in historical doc files not updated | Only `docs/` files created in this iteration (dev report) use `/`; historical docs unchanged per scope |

## Safety Confirmations

- [x] Default live trading remains disabled (`ENABLE_LIVE_TRADING=false`).
- [x] Risk Agent veto was not bypassed (no changes to risk_engine/).
- [x] No secrets committed (OpenAI/DeepSeek keys from env only).
- [x] No batch buy confirmation introduced.
- [x] LLM cannot directly decide buy/sell — output guard blocks at agent and API layers.
- [x] Signal explanation only works for existing signals (404 for missing).
- [x] Missing openai package degrades gracefully (unavailable status).
- [x] Stock pool filter not bypassed (no changes to stock_pool/).
- [x] Data fail-closed not bypassed (no changes to data_gateway/).
- [x] No real trading capability enabled.

## Deliverables

1. Code changes implementing all S2 (blocking) and S3 (non-blocking) fixes.
2. 33 new tests across 3 test files + updates to 2 existing test files.
3. Static checks pass (ruff, py_compile).
4. 88 related tests pass.
5. This development report.

Signed-off for: **Test Engineer Agent** verification.
