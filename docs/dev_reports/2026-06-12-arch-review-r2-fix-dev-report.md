# R2 Architecture Review Fix — Development Report
# R2 架构评审修复 — 开发报告

Date: 2026-06-12
Developer Role: Developer Agent
Branch: feature/quant-factor-v1

---

## 1. Scope / 范围

- **Review Document / 评审文档:** `docs/review/2026-06-12-wsl-product-runtime-ai-agent-architecture-review-r2.md`
- **Previous fix report / 上次修复报告:** `docs/dev_reports/2026-06-12-arch-review-fix-dev-report.md`
- **Python:** `.venv/bin/python` → Python 3.13.5

This round addresses two remaining S2 blocking findings from R2:

本轮修复 R2 评审中两个 S2 阻断项：

1. **S2: Output guard allows lowercase buy/sell** — case-insensitivity fix + generic key check.
2. **S2: Missing edge-case test file** — false-negative tests from the review are now committed.

---

## 2. Changes / 修改

### 2.1 Changed Files / 修改文件

| File / 文件 | Action / 操作 | Purpose / 目的 |
|---|---|---|
| `src/agent_orchestrator/output_guard.py` | Modified | Add `re.IGNORECASE` to BUY/SELL patterns; add `exempt_keys` param; add generic decision field check |
| `src/api/product_routes.py` | Modified | Pass `exempt_keys` to API-level guard for signal explain metadata |
| `tests/test_output_guard.py` | Modified | Add 17 edge-case tests for lowercase, mixed-case, generic-key, Chinese-adjacent, and false-positive avoidance |

### 2.2 Finding → Code Map / 评审发现 → 代码映射

| R2 Finding / 发现 | Fix / 修复 | Key lines / 关键代码 |
|---|---|---|
| BUY/SELL regex is case-sensitive | Add `re.IGNORECASE` to both patterns | `output_guard.py:48-49` |
| `action: "buy"` / `decision: "sell"` not caught | Add `_find_generic_decision_values()` check | `output_guard.py:171-192` |
| System metadata fields (signal_id, original_signal_type) cause false positives | Add `exempt_keys` param to `sanitize_llm_output()` | `output_guard.py:58`, `product_routes.py:907` |
| Missing committed edge-case tests | Add 17 tests covering all R2 false-negative examples | `test_output_guard.py:249-397` |

### 2.3 Key Design Decisions / 关键设计决策

**Case-insensitive regex / 大小写不敏感正则:**

```python
# Before: only uppercase BUY/SELL
re.compile(r'(?:\b|_)BUY(?:\b|_)')

# After: case-insensitive
re.compile(r'(?:\b|_)BUY(?:\b|_)', re.IGNORECASE)
```

**Generic decision field check / 通用决策字段检查:**

```python
_GENERIC_DECISION_KEYS = {"action", "decision", "recommendation", "judgment", "suggestion"}
```

These catch `{"action": "buy"}` or `{"judgment": "sell"}` while allowing research-safe terms like `buyback` and `seller concentration`.

**Exempt keys / 豁免键:**

System metadata fields (`signal_id`, `original_signal_type`, `decision_source`, `llm_model`, `llm_provider`) are exempted from API-level sanitization to avoid false positives when the LLM's explanation output contains a reference to an existing buy/sell signal.

---

## 3. Verification / 验证

### Static checks / 静态检查

```bash
.venv/bin/python -m ruff check src/agent_orchestrator/output_guard.py src/api/product_routes.py tests/test_output_guard.py tests/test_product_routes.py
```

Result: All checks passed.

```bash
.venv/bin/python -m py_compile src/agent_orchestrator/output_guard.py src/api/product_routes.py
```

Result: No errors.

### Tests / 测试

```bash
.venv/bin/python -m pytest tests/test_output_guard.py tests/test_model_router.py tests/test_ai_research_agents.py tests/test_product_routes.py tests/test_bug_auto_fix.py tests/test_live_signal.py -q --basetemp=runtime/pytest-tmp-arch-r2
```

**Result: 105 passed, 1 warning** (pre-existing StarletteDeprecationWarning).

Breakdown / 明细:

| Test file / 测试文件 | Count / 数量 |
|---|---|
| `test_output_guard.py` | 40 (23 original + 17 new edge case) |
| `test_model_router.py` | 7 |
| `test_ai_research_agents.py` | 2 |
| `test_product_routes.py` | 8 |
| `test_bug_auto_fix.py` | 27 |
| `test_live_signal.py` | 21 |

### R2 False-Negative Probe / R2 假阴性验证

The exact cases from the review are now tested and pass:

| Input / 输入 | R2 expected / 期望 | Actual / 实际 |
|---|---|---|
| `"you should buy this stock"` | blocked=True | blocked=True |
| `"you should sell this stock"` | blocked=True | blocked=True |
| `{"action": "buy"}` | blocked=True | blocked=True |
| `{"decision": "sell"}` | blocked=True | blocked=True |
| `{"recommendation": "buy 600000.SH"}` | blocked=True | blocked=True |
| `{"suggestion": "sell signal detected"}` | blocked=True | blocked=True |
| `{"reason": "Buy this stock now"}` (mixed case) | blocked=True | blocked=True |
| `{"analysis": {"verdict": "buy"}}` (nested) | blocked=True | blocked=True |

Safe terms preserved / 安全术语未误判:

| Input / 输入 | blocked |
|---|---|
| `"Company announced a buyback program"` | False |
| `"seller concentration is high"` | False |
| `{"hypotheses": [{"name": "buyback_yield_factor"}]}` | False |

### Git / Git 检查

```bash
git status --short --branch
git diff --stat
git diff --check
```

Result: Clean. 3 files modified. No trailing whitespace or conflict markers.

---

## 4. Safety Confirmation / 安全确认

- [x] **LLM 不能直接决定买卖:** BUY/SELL 守卫现在大小写不敏感，覆盖 `action: "buy"`、`decision: "sell"` 等通用字段
- [x] **Risk Agent 一票否决未被绕过:** 未修改 `risk_engine/`
- [x] **默认不启用真实自动交易:** `ENABLE_LIVE_TRADING=false`
- [x] **未提交密钥:** 所有密钥来自环境变量
- [x] **Research-safe 术语未误判:** `buyback`, `seller concentration` 放行

---

## 5. Not Run / 未运行项

- **WSL API smoke:** 需要 AkTools(:8080) + Streamlit(:8771) 外部服务。
- **Full project regression (tests/):** 受影响的模块已全部通过定向测试（105 项），全量回归约 380+ 测试，存在少量非本次变更引入的历史失败 —— 已在 R1 报告中记录。

---

## 6. Deliverables / 交付物

1. Output guard fixed for case-insensitive buy/sell detection.
2. 17 new edge-case tests covering all R2 review false-negative examples.
3. Generic decision field check (`action`/`decision`/`recommendation`/`judgment`/`suggestion`).
4. `exempt_keys` mechanism to avoid false-positives on system metadata.
5. Static checks pass (ruff, py_compile).
6. 105 related tests pass.
7. This development report in Chinese + English.

Signed-off for / 移交: **Test Engineer Agent** verification.
