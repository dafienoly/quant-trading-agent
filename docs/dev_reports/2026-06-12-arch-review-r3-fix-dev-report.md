# R3 Architecture Review Fix — Development Report
# R3 架构评审修复 — 开发报告

Date: 2026-06-12
Developer Role: Developer Agent
Branch: feature/quant-factor-v1

---

## 1. Scope / 范围

- **Review Document / 评审文档:** `docs/review/2026-06-12-wsl-product-runtime-ai-agent-architecture-review-r3.md`
- **Previous fix reports / 上次修复报告:**
  - `docs/dev_reports/2026-06-12-arch-review-fix-dev-report.md` (R1)
  - `docs/dev_reports/2026-06-12-arch-review-r2-fix-dev-report.md` (R2)
- **Python:** `.venv/bin/python` → Python 3.13.5

This round addresses one remaining S2 blocking finding from R3: **Chinese direct buy/sell decisions bypass the output guard.**

本轮修复 R3 评审中一个 S2 阻断项：**中文直接买卖决策绕过 output guard。**

---

## 2. Root Cause / 根因

Two separate problems:

1. **Python 3.13 将 CJK 字符视为 `\\w`**（Unicode 单词字符），因此 `\\b`（单词边界）在 CJK 和 ASCII 之间不匹配。`\\bbuy\\b` 无法匹配 `"建议buy该股票"` 中的 `buy`。

2. **中文交易术语未被检查:** `买入`、`卖出`、`买进`、`卖掉` 等标准中文股票交易指令未被列入黑名单。

**Verification / 验证:**

```python
# Python 3 welds CJK into \w — \b fails between CJK and ASCII
"议"  # 议 → re.match(r'\w', ...) = True
"b"       # → re.match(r'\w', ...) = True
# So \b matches nowhere between 议 and b
```

---

## 3. Changes / 修改

### Files / 修改文件

| File / 文件 | Action / 操作 | Purpose / 目的 |
|---|---|---|
| `src/agent_orchestrator/output_guard.py` | Modified | Fix BUY/SELL regex; add Chinese patterns |
| `tests/test_output_guard.py` | Modified | Add 18 tests for Chinese + CJK-adjacent |

### 3.1 Regex Fix: \\b → ASCII-aware boundaries

**Before (broken for CJK):**

```python
re.compile(r'(?:\b|_)BUY(?:\b|_)', re.IGNORECASE)
```

**After (works with CJK + ASCII mixed text):**

```python
re.compile(r'(?:^|[^a-zA-Z])BUY(?:[^a-zA-Z]|$)', re.IGNORECASE)
```

This correctly matches `buy` in:
- `建议buy该股票` ✓ (议 and 该 are `[^a-zA-Z]`)
- `buy` ✓ (`^` at start, `$` after)
- `_BUY_` ✓ (`_` is `[^a-zA-Z]`)

And does NOT match `buy` in `buyback`, `seller`, etc.

### 3.2 New Chinese Patterns / 新增中文模式

```python
re.compile(r'买入'),   # buy in — standard CSRC stock trading term
re.compile(r'买进'),   # buy into
re.compile(r'卖出'),   # sell out
re.compile(r'卖掉'),   # sell off
```

These are 2-character compounds specific to stock trading, safe from false positives on general Chinese terms like `购买` (purchase), `买卖` (business), `买家` (buyer), `买盘` (buy orders).

### 3.3 Generic Decision Field Check / 通用字段检查更新

`_find_generic_decision_values()` now also checks Chinese values:

```python
_CHINESE_DECISION_VALUES = frozenset({"买入", "买进", "卖出", "卖掉"})
```

This catches `{"action": "买入"}` and `{"decision": "卖出"}`.

### 3.4 Tests / 测试用例

18 new tests in `TestOutputGuardChineseCJK`:

| Category / 类别 | Tests / 数量 | Examples |
|---|---|---|
| Chinese direct terms / 中文直接术语 | 8 | `买入`, `卖出`, `买进`, `卖掉` in reason/action/decision |
| CJK-adjacent English / 中英混合 | 3 | `建议buy该股票`, `建议sell该股票` |
| Generic Chinese fields / 中文通用字段 | 2 | `recommendation: "买入"`, `suggestion: "卖出"` |
| Nested Chinese / 嵌套中文 | 1 | List item with `action: "买入"` |
| Research-safe Chinese / 安全中文术语 | 4 | `购买`, `买卖`, `买盘`, `买家` NOT blocked |

---

## 4. Verification / 验证

### R3 False-Negatives Before/After / R3 假阴性修复前后

| Input / 输入 | R3 blocked | Now blocked |
|---|---|---|
| `"建议buy该股票"` | False | **True** |
| `"建议sell该股票"` | False | **True** |
| `"建议买入该股票"` | False | **True** |
| `"建议卖出该股票"` | False | **True** |
| `{"action": "买入"}` | False | **True** |
| `{"decision": "卖出"}` | False | **True** |

### Static Checks / 静态检查

```bash
.venv/bin/python -m ruff check src/agent_orchestrator/output_guard.py tests/test_output_guard.py
```

**Result:** All checks passed.

```bash
.venv/bin/python -m py_compile src/agent_orchestrator/output_guard.py
```

**Result:** No errors.

### Test Results / 测试结果

```bash
.venv/bin/python -m pytest tests/test_output_guard.py \
  tests/test_model_router.py tests/test_ai_research_agents.py \
  tests/test_product_routes.py tests/test_bug_auto_fix.py \
  tests/test_live_signal.py -q --basetemp=runtime/pytest-tmp-arch-r3
```

**Result: 123 passed, 1 warning** (pre-existing StarletteDeprecationWarning).

Breakdown / 明细:

| Test file / 文件 | Count / 数量 |
|---|---|
| `test_output_guard.py` | 58 (40 original + 18 Chinese/CJK) |
| `test_model_router.py` | 7 |
| `test_ai_research_agents.py` | 2 |
| `test_product_routes.py` | 8 |
| `test_bug_auto_fix.py` | 27 |
| `test_live_signal.py` | 21 |

### Git / Git 检查

```bash
git status --short --branch
git diff --stat
git diff --check
```

**Result:** Clean. 2 files modified. No trailing whitespace or conflict markers.

---

## 5. Safety Confirmation / 安全确认

- [x] **中文直接买卖决策被阻断:** `买入`, `买进`, `卖出`, `卖掉` + CJK-adjacent `buy`/`sell`
- [x] **中文安全术语不误判:** `购买`, `买卖`, `买盘`, `买家` 放行
- [x] **LLM 不能直接决定买卖:** 输出守卫覆盖英文 + 中文
- [x] **Risk Agent 一票否决未被绕过:** 未修改 `risk_engine/`
- [x] **默认不启用真实自动交易:** `ENABLE_LIVE_TRADING=false`
- [x] **未提交密钥:** 所有密钥来自环境变量

---

## 6. Deliverables / 交付物

1. Output guard updated for Chinese direct trading decisions + CJK-adjacent English.
2. Root cause fixed: Python 3 `\w` includes CJK → replaced `\b` with explicit ASCII boundaries.
3. 18 new tests covering all R3 false-negative examples.
4. Research-safe Chinese terms (`购买`, `买卖`, `买盘`, `买家`) confirmed NOT blocked.
5. Static checks pass (ruff, py_compile).
6. 123 related tests pass.
7. This development report in Chinese + English.

Signed-off for / 移交: **Test Engineer Agent** verification.
