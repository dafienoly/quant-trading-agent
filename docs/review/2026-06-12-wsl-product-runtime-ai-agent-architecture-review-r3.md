# WSL Product Runtime & AI Agent Architecture Review R3

Date: 2026-06-12
Role: Architect Reviewer
Verdict: CHANGES_REQUESTED

## Review Inputs

- Requirements: `docs/requirements/2026-06-11-wsl-product-runtime-ai-agent-requirements.md`
- Architecture: `docs/design/2026-06-11-wsl-product-runtime-ai-agent-architecture.md`
- R2 review: `docs/review/2026-06-12-wsl-product-runtime-ai-agent-architecture-review-r2.md`
- R2 fix report: `docs/dev_reports/2026-06-12-arch-review-r2-fix-dev-report.md`
- R2 test report: `docs/test_reports/2026-06-12-wsl-product-runtime-ai-agent-test-report-r2.md`
- Repository rule: `AGENTS.md`

## Conclusion

R2 fixed the exact English lower-case false negatives from the previous review. The output guard now blocks `buy`, `sell`, mixed-case variants, and generic fields such as `action`, `decision`, `recommendation`, `judgment`, and `suggestion` when they contain English direct trading decisions.

However, the review still cannot pass because direct Chinese trading decisions are not blocked. This project is Chinese-first at the product layer and uses a Chinese-capable LLM, so `买入` and `卖出` are realistic LLM outputs, not theoretical edge cases. `AGENTS.md:54` requires that LLMs must not directly decide buy or sell.

## Blocking Findings

### S2: Output guard still allows Chinese direct buy/sell decisions

Evidence:
- `AGENTS.md:54`
- `docs/requirements/2026-06-11-wsl-product-runtime-ai-agent-requirements.md:67`
- `docs/requirements/2026-06-11-wsl-product-runtime-ai-agent-requirements.md:189`
- `src/agent_orchestrator/output_guard.py:52`
- `src/agent_orchestrator/output_guard.py:56`
- `src/agent_orchestrator/output_guard.py:57`
- `src/agent_orchestrator/output_guard.py:209`

Manual verification:

```python
sanitize_llm_output({"status": "ok", "reason": "建议buy该股票"})["blocked"]
# False

sanitize_llm_output({"status": "ok", "reason": "建议sell该股票"})["blocked"]
# False

sanitize_llm_output({"status": "ok", "reason": "建议买入该股票"})["blocked"]
# False

sanitize_llm_output({"status": "ok", "reason": "建议卖出该股票"})["blocked"]
# False

sanitize_llm_output({"status": "ok", "action": "买入"})["blocked"]
# False

sanitize_llm_output({"status": "ok", "decision": "卖出"})["blocked"]
# False
```

This remains a safety boundary failure. The guard currently focuses on English `BUY/SELL` tokens and English order phrases. Because the product default language is Chinese and the AI provider is expected to generate Chinese text, Chinese direct trading instructions must be blocked before API responses leave the AI layer.

Required fix:
- Add Chinese direct decision patterns: `买入`, `买进`, `买`, `卖出`, `卖掉`, `卖`, and common phrases such as `建议买入`, `建议卖出`, `可以买`, `应卖出`.
- Add CJK-adjacent English token handling for `建议buy该股票` and `建议sell该股票`.
- Extend generic decision/action field checks to block Chinese direct decision values.
- Add committed tests for Chinese direct decision values, CJK-adjacent English `buy/sell`, nested fields, list items, and generic decision keys.
- Preserve false-positive safety for research terms where possible, but default to blocking ambiguous direct trading verbs in AI outputs.

## Resolved Since R2

### English lower-case direct decisions

Status: Fixed.

Evidence:
- `src/agent_orchestrator/output_guard.py:56`
- `src/agent_orchestrator/output_guard.py:57`
- `tests/test_output_guard.py:254`
- `tests/test_output_guard.py:260`

Verified:

```text
you should buy this stock => blocked=True
you should sell this stock => blocked=True
```

### Generic English decision fields

Status: Fixed.

Evidence:
- `src/agent_orchestrator/output_guard.py:43`
- `src/agent_orchestrator/output_guard.py:209`
- `tests/test_output_guard.py:266`
- `tests/test_output_guard.py:272`

Verified:

```text
{"action": "buy"} => blocked=True
{"decision": "sell"} => blocked=True
```

### Missing edge-case test file claim

Status: Fixed.

Evidence:
- `tests/test_output_guard.py:248`

The edge-case tests are now committed directly into `tests/test_output_guard.py` as `TestOutputGuardEdgeCases`. The R2 test report no longer relies on the previously missing `tests/test_output_guard_edge_cases.py`.

## Verification Performed

Passed:

```bash
.\.venv\Scripts\python.exe -m ruff check src/agent_orchestrator/output_guard.py src/api/product_routes.py tests/test_output_guard.py tests/test_product_routes.py
```

Result:

```text
All checks passed!
```

Passed:

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_output_guard.py tests/test_model_router.py tests/test_ai_research_agents.py tests/test_product_routes.py tests/test_bug_auto_fix.py tests/test_live_signal.py -q --basetemp=runtime/pytest-tmp-arch-r3
```

Result:

```text
105 passed, 2 warnings
```

Failed manual safety probe:

```text
建议buy该股票 => blocked=False
建议sell该股票 => blocked=False
建议买入该股票 => blocked=False
建议卖出该股票 => blocked=False
{"action": "买入"} => blocked=False
{"decision": "卖出"} => blocked=False
```

## Required Re-Review Gate

Before R4 review, the development and test engineers must provide:

1. Output guard fixes for Chinese direct trade decisions and CJK-adjacent English `buy/sell`.
2. Committed tests covering all false-negative examples listed in this report.
3. Updated test report with rerunnable commands and outputs.
4. Targeted AI safety tests passing in the submitted worktree.

Current status remains CHANGES_REQUESTED.
