# WSL Product Runtime & AI Agent Architecture Review

Date: 2026-06-12
Role: Architect Agent
Scope:
- Requirements: `docs/requirements/2026-06-11-wsl-product-runtime-ai-agent-requirements.md`
- Architecture: `docs/design/2026-06-11-wsl-product-runtime-ai-agent-architecture.md`
- Dev report: `docs/dev_reports/2026-06-11-wsl-product-runtime-ai-agent-dev-report.md`
- Test report: `docs/test_reports/2026-06-11-wsl-product-runtime-ai-agent-test-report.md`

## Verdict

CHANGES_REQUESTED.

The implementation has made meaningful progress on AkTools compatibility, WSL one-command runtime scripts, feedback bug backlog visibility, and DeepSeek model configuration. However, the AI Agent feature set is not ready for architectural approval because several safety and product-correctness boundaries are enforced only by prompts or are not wired into the actual UI/runtime flow.

## Blocking Findings

### S2: LLM safety boundary is prompt-only

Evidence:
- `src/agent_orchestrator/factor_discovery_agent.py:23`
- `src/agent_orchestrator/recommendation_agent.py:23`
- `src/agent_orchestrator/signal_explanation_agent.py:31`
- `src/api/product_routes.py:757`
- `src/api/product_routes.py:778`
- `src/api/product_routes.py:801`

The agents instruct the model not to output buy/sell decisions, but the returned JSON is passed through without schema validation, prohibited-field filtering, or hostile-output tests. This does not satisfy the system invariant that LLM cannot directly decide buy/sell, and it does not satisfy the architecture requirement that AI output must remain advisory.

Required fix:
- Add a deterministic AI output guard shared by factor discovery, recommendation research, and signal explanation.
- Reject or sanitize outputs containing direct trade decisions such as `BUY`, `SELL`, order instructions, target position sizing, executable prices, or order payloads.
- Add tests using hostile fake router responses to prove unsafe output is blocked before reaching API responses.

### S2: Signal explanation endpoint fabricates a `hold` signal

Evidence:
- `src/api/product_routes.py:784`
- `src/api/product_routes.py:798`

`/product/ai/signals/{signal_id}/explain` currently constructs `{"signal_id": signal_id, "signal_type": "hold"}` instead of loading an existing signal. This allows the product to explain a non-existent signal and silently changes the effective signal type to `hold`.

This violates the architecture rule that the AI signal explanation agent may only explain existing signals and must not create or alter signal decisions.

Required fix:
- Load the real signal draft/status from the signal service or closed-loop orchestration state.
- Return `404` or an explicit unavailable response when the signal does not exist.
- Pass the real immutable signal fields to the explanation agent.
- Add tests for existing signal, missing signal, and preservation of original signal type.

### S2: Missing `openai` package breaks local verification and optional LLM degradation

Evidence:
- `src/llm/model_router.py:8`
- `src/product_app/bug_fix_agent.py:60`

Local verification failed during test collection because `model_router.py` imports `OpenAI` at module import time:

```text
ModuleNotFoundError: No module named 'openai'
```

This also breaks BugFixAgent tests because `BugFixAgent.__init__` imports `ModelRouter`. The project declares `openai>=1.0` in `pyproject.toml`, so a clean environment may install it, but the runtime design says LLM features should fail gracefully when unavailable. A top-level missing dependency exception prevents that graceful path.

Required fix:
- Lazy import `OpenAI` inside the provider call path, or catch missing dependency and return `{"status": "unavailable", ...}` consistently.
- Ensure the WSL bootstrap/install documentation installs the declared optional/runtime dependency set.
- Add a test proving `/product/llm/status` and BugFixAgent construction do not crash when the OpenAI SDK is missing.

## Non-Blocking Findings

### S3: Runtime service status is incomplete

Evidence:
- `src/api/product_routes.py:632`
- `src/ui_report/product_dashboard.py`

`/product/runtime/services` currently reports API and BugFixAgent health, but does not expose AkTools, Dashboard, or LLM provider status as required by the architecture's runtime visibility goal. The dashboard source also does not appear to call `/product/llm/status`, `/product/runtime/services`, or the AI research endpoints directly; related labels exist mainly in i18n resources.

Required fix:
- Extend runtime service status to include AkTools, Dashboard, API, BugFixAgent, and LLM.
- Render the status and AI entry points in the product dashboard, not only in backend routes or translation strings.

### S3: Stop script zombie cleanup misses AkTools default port

Evidence:
- `scripts/stop_product.py:29`

`KNOWN_PORTS` includes `8000`, `8001`, `8002`, `8501`, `8502`, and `8771`, but does not include the default AkTools port `8080`. If the PID file is stale or missing, AkTools may remain running and keep the port occupied.

Required fix:
- Include `8080` or dynamically read `aktools_port` from the PID file before fallback cleanup.

### S3: WSL-facing guidance still contains Windows-style path examples

Evidence:
- `.env.example:21`
- `scripts/summarize_feedback_bugs.py:5`

The user explicitly requested WSL-friendly path guidance. `.env.example` still documents `.\.venv\Scripts\python.exe`, and the feedback summary script usage uses backslash line continuations.

Required fix:
- Use `/` path style in user-facing WSL setup docs and examples.
- Prefer `./.venv/bin/python` for WSL examples.

## Positive Observations

- AkTools FastAPI homepage compatibility fix is implemented in `src/integrations/aktools_compat_app.py` using the newer `TemplateResponse(request=request, name=..., context=...)` call style.
- One-command runtime scripts now cover API, Streamlit dashboard, optional AkTools, and optional BugFixAgent startup.
- `DEEPSEEK_MODEL` defaults to `deepseek-v4-flash`.
- BugFix proposal validation has added restricted path checks for core trading modules.
- Targeted ruff check for the reviewed touched files passed.

## Verification Performed

Passed:

```bash
./.venv/Scripts/python.exe -m ruff check src/integrations/aktools_compat_app.py scripts/start_product.py scripts/stop_product.py src/llm/model_router.py src/agent_orchestrator/factor_discovery_agent.py src/agent_orchestrator/recommendation_agent.py src/agent_orchestrator/signal_explanation_agent.py src/api/product_routes.py src/product_app/bug_fix_agent.py src/product_app/bug_fix_workflow.py tests/test_aktools_compat_app.py tests/test_product_process_manager.py tests/test_model_router.py tests/test_ai_research_agents.py tests/test_bug_auto_fix.py tests/test_feedback_bug_summary.py
```

Failed:

```bash
./.venv/Scripts/python.exe -m pytest tests/test_aktools_compat_app.py tests/test_product_process_manager.py tests/test_model_router.py tests/test_ai_research_agents.py tests/test_bug_auto_fix.py tests/test_feedback_bug_summary.py -q --basetemp=runtime/pytest-tmp
```

Reason:

```text
ModuleNotFoundError: No module named 'openai'
```

Partial rerun excluding direct model-router tests still failed in BugFixAgent tests for the same import-time dependency issue.

## Required Re-Review Gate

Before this review can pass, the development engineer and test engineer should provide:

1. Fix report covering all S2 findings.
2. Tests proving LLM unsafe outputs are blocked.
3. Tests proving signal explanation only works for existing signals and preserves the original signal type.
4. Tests proving missing OpenAI SDK or missing DeepSeek key degrades gracefully.
5. Updated test report with WSL commands and outputs.

After those are complete, the architecture review can be repeated. Current status remains CHANGES_REQUESTED.
