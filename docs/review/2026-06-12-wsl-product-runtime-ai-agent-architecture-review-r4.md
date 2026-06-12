# WSL Product Runtime & AI Agent Architecture Review R4

Date: 2026-06-12
Role: Architect Reviewer
Verdict: CHANGES_REQUESTED

## Review Inputs

- R3 review: `docs/review/2026-06-12-wsl-product-runtime-ai-agent-architecture-review-r3.md`
- R3 fix dev report: `docs/dev_reports/2026-06-12-arch-review-r3-fix-dev-report.md`
- R3 fix test report: `docs/test_reports/2026-06-12-arch-review-r3-fix-test-report.md`
- Repository rule: `AGENTS.md`
- Actual code: `src/agent_orchestrator/output_guard.py`

## Conclusion

The R3 fix closes the exact six false-negative samples from the previous review:

- CJK-adjacent English `buy` / `sell`
- Chinese `买入` / `买进`
- Chinese `卖出` / `卖掉`
- generic fields such as `action=买入` and `decision=卖出`

However, the review still cannot pass because common Chinese direct trading phrases with single-character `买` / `卖` remain unblocked. R3 explicitly required coverage for common phrases such as `可以买` and similar direct buy/sell language. These are realistic Chinese LLM outputs and still violate the invariant that LLMs must not directly decide buy or sell.

## Blocking Findings

### S2: Common Chinese direct buy/sell phrases still bypass the output guard

Evidence:

- `AGENTS.md:54`
- `docs/review/2026-06-12-wsl-product-runtime-ai-agent-architecture-review-r3.md`
- `src/agent_orchestrator/output_guard.py:58`
- `src/agent_orchestrator/output_guard.py:72`
- `src/agent_orchestrator/output_guard.py:75`
- `tests/test_output_guard.py:363`

The implementation added patterns for `买入`, `买进`, `卖出`, and `卖掉`, but does not block common direct decision phrases using single-character verbs.

Manual safety probe:

```text
建议买该股票 => blocked=False
可以买 => blocked=False
应买 => blocked=False
该卖了 => blocked=False
卖该股票 => blocked=False
```

These are direct trading decisions in Chinese. Because the product is Chinese-first and the LLM is expected to produce Chinese explanations, these phrases must not be allowed through the AI output boundary.

Required fix:

- Add phrase-level Chinese direct-decision patterns that block direct trading instructions without over-blocking neutral market terms.
- Minimum cases to block:
  - `建议买该股票`
  - `可以买`
  - `应买`
  - `该买`
  - `买该股票`
  - `建议卖该股票`
  - `可以卖`
  - `应卖`
  - `该卖`
  - `卖该股票`
- Keep existing safe terms unblocked where possible:
  - `购买意愿`
  - `买卖双方`
  - `买盘力量`
  - `买家观望`
  - `卖方压力`
  - `卖盘变化`
- Add committed tests for all required direct-decision phrases and safe terms.

## Resolved Since R3

### CJK-adjacent English `buy` / `sell`

Status: Fixed.

Verified:

```text
建议buy该股票 => blocked=True
建议sell该股票 => blocked=True
```

### Chinese compound direct terms

Status: Fixed for compound terms.

Verified:

```text
建议买入该股票 => blocked=True
建议卖出该股票 => blocked=True
{"action": "买入"} => blocked=True
{"decision": "卖出"} => blocked=True
```

## Verification Performed

Passed:

```bash
.\.venv\Scripts\python.exe -m ruff check src/agent_orchestrator/output_guard.py tests/test_output_guard.py
```

Result:

```text
All checks passed!
```

Passed:

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_output_guard.py tests/test_model_router.py tests/test_ai_research_agents.py tests/test_product_routes.py tests/test_bug_auto_fix.py tests/test_live_signal.py -q --basetemp=runtime/pytest-tmp-arch-r4
```

Result:

```text
123 passed, 2 warnings
```

Passed:

```bash
git diff --check
```

Failed manual safety probe:

```text
建议买该股票 => blocked=False
可以买 => blocked=False
应买 => blocked=False
该卖了 => blocked=False
卖该股票 => blocked=False
```

## Process Note

The R3 test report does not record the temporary test branch metadata required by `docs/process/TEST_ENGINEER_WORKFLOW.md`. This is a process issue and should be corrected in future test cycles, but the current blocking decision is based on the reproducible AI safety gap above.

## Required Re-Review Gate

Before the next review, the development and test engineers must provide:

1. Output guard changes covering common Chinese direct buy/sell phrases.
2. Tests for all phrase-level false negatives listed in this report.
3. Tests proving safe Chinese market/research terms remain allowed.
4. Updated test report with rerunnable commands and temporary-branch metadata.

Current status remains CHANGES_REQUESTED.
