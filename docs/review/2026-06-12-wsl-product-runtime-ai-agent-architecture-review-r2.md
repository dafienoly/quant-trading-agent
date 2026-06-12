# WSL Product Runtime & AI Agent Architecture Review R2

Date: 2026-06-12
Role: Architect Reviewer
Verdict: CHANGES_REQUESTED

## Review Inputs

- Requirements: `docs/requirements/2026-06-11-wsl-product-runtime-ai-agent-requirements.md`
- Architecture: `docs/design/2026-06-11-wsl-product-runtime-ai-agent-architecture.md`
- Previous review: `docs/review/2026-06-12-wsl-product-runtime-ai-agent-architecture-review.md`
- Developer fix report: `docs/dev_reports/2026-06-12-arch-review-fix-dev-report.md`
- Test report: `docs/test_reports/2026-06-12-wsl-product-runtime-ai-agent-test-report.md`
- Actual code at branch: `feature/quant-factor-v1`

## Conclusion

The implementation resolves several previous findings in the right direction: the OpenAI SDK import is now lazy, signal explanation now loads an existing signal, runtime service status includes more components, and the stop script includes port `8080`.

However, the architecture review still cannot pass because the deterministic AI output guard has reproducible false negatives for direct trading language. This leaves the project exposed to a violation of the system invariant: **LLM cannot directly decide buy/sell**.

## Blocking Findings

### S2: AI output guard still allows direct buy/sell recommendations

Evidence:
- `src/agent_orchestrator/output_guard.py:44`
- `src/agent_orchestrator/output_guard.py:46`
- `src/agent_orchestrator/output_guard.py:47`
- `src/agent_orchestrator/factor_discovery_agent.py:36`
- `src/agent_orchestrator/recommendation_agent.py:36`
- `src/agent_orchestrator/signal_explanation_agent.py:38`
- `src/api/product_routes.py:820`
- `src/api/product_routes.py:855`
- `src/api/product_routes.py:907`

The guard is now shared by all AI agents and API routes, but the BUY/SELL detection is case-sensitive and mostly catches uppercase tokens. Direct lower-case trading instructions still pass:

```python
sanitize_llm_output({"status": "ok", "reason": "you should buy this stock"})["blocked"]
# False

sanitize_llm_output({"status": "ok", "reason": "you should sell this stock"})["blocked"]
# False

sanitize_llm_output({"status": "ok", "action": "buy"})["blocked"]
# False

sanitize_llm_output({"status": "ok", "decision": "sell"})["blocked"]
# False
```

This is not just a theoretical issue. LLMs commonly emit lower-case natural-language recommendations, and product users may be Chinese while the model still emits English `buy`/`sell` words. Because the project invariant prohibits LLM buy/sell decisions in any form, this remains a blocking safety gap.

Required fix:
- Make direct trade decision detection case-insensitive.
- Add forbidden key patterns for generic decision/action fields when their values are direct buy/sell decisions.
- Add tests for lower-case, title-case, Chinese-adjacent, nested, list item, and generic-key cases.
- Keep research-safe terms such as `buyback`, `seller concentration`, or factor names from being over-blocked where possible.

### S2: Test report claims an edge-case test file that is absent from the repo

Evidence:
- `docs/test_reports/2026-06-12-wsl-product-runtime-ai-agent-test-report.md`
- Missing file: `tests/test_output_guard_edge_cases.py`

The test report states that `tests/test_output_guard_edge_cases.py` passed and references 24 additional edge-case tests, but the file is not present in the current worktree. The current test suite therefore does not contain the claimed additional coverage for output guard edge cases.

Required fix:
- Add the missing test file or remove the claim from the test report.
- The next test report must be generated from commands that can be rerun in the submitted worktree.
- Include the direct false-negative cases above in committed tests.

## Resolved Previous Findings

### Previous S2: Signal explanation fabricated `hold`

Status: Fixed enough for architecture review.

Evidence:
- `src/api/product_routes.py:891`
- `src/api/product_routes.py:892`
- `src/api/product_routes.py:893`
- `tests/test_product_routes.py:69`
- `tests/test_product_routes.py:91`

The endpoint now loads `get_signal_status(signal_id)`, returns `not_found` for missing signals, and passes the actual signal draft to the explanation agent.

### Previous S2: Missing OpenAI SDK crashed imports

Status: Fixed enough for architecture review.

Evidence:
- `src/llm/model_router.py:46`
- `src/llm/model_router.py:49`
- `src/llm/model_router.py:50`
- `tests/test_model_router.py:83`

`OpenAI` is imported lazily inside `chat_json()`, and missing SDK returns an `unavailable` response instead of crashing import-time paths.

### Previous S3: Runtime service status incomplete

Status: Mostly fixed for backend API review.

Evidence:
- `src/api/product_routes.py:696`
- `src/api/product_routes.py:699`
- `src/api/product_routes.py:700`
- `src/api/product_routes.py:701`
- `src/api/product_routes.py:702`
- `src/api/product_routes.py:708`

The backend now reports API, AkTools, Dashboard, BugFixAgent, and LLM status. Full UI rendering remains a PM acceptance concern.

### Previous S3: Stop script missed AkTools port

Status: Fixed.

Evidence:
- `scripts/stop_product.py:29`

`8080` is now included in `KNOWN_PORTS`.

### Previous S3: WSL path examples

Status: Mostly fixed for touched files.

Evidence:
- `.env.example`
- `scripts/summarize_feedback_bugs.py`

The explicit Windows-style AkTools command was removed from `.env.example`. `scripts/summarize_feedback_bugs.py` still uses shell line-continuation backslashes in its usage block, but those are not Windows path separators and are not a blocking issue.

## Verification Performed

Passed:

```bash
.\.venv\Scripts\python.exe -m ruff check src/agent_orchestrator/output_guard.py src/agent_orchestrator/factor_discovery_agent.py src/agent_orchestrator/recommendation_agent.py src/agent_orchestrator/signal_explanation_agent.py src/llm/model_router.py src/api/product_routes.py tests/test_output_guard.py tests/test_model_router.py tests/test_ai_research_agents.py tests/test_product_routes.py tests/test_bug_auto_fix.py
```

Result:

```text
All checks passed!
```

Passed:

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_output_guard.py tests/test_model_router.py tests/test_ai_research_agents.py tests/test_product_routes.py tests/test_bug_auto_fix.py tests/test_live_signal.py -q --basetemp=runtime/pytest-tmp-arch-rereview
```

Result:

```text
88 passed, 2 warnings
```

Manual guard probe:

```text
you should buy this stock => blocked=False
you should sell this stock => blocked=False
{"action": "buy"} => blocked=False
{"decision": "sell"} => blocked=False
```

## Required Re-Review Gate

Before R3 review, the development and test engineers must provide:

1. A fix that blocks lower-case and mixed-case direct buy/sell decisions.
2. Committed tests for the false-negative examples listed in this report.
3. A corrected test report that does not reference missing files.
4. A rerun of the targeted AI safety tests and product route tests.

Current status remains CHANGES_REQUESTED.
