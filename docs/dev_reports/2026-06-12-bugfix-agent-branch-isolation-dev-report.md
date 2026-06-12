# BugFix Branch Isolation — Development Report
# BugFix 分支隔离 — 开发报告

Date: 2026-06-12
Developer Role: Developer Agent
Branch: feature/quant-factor-v1

---

## 1. Scope / 范围

- **Architecture / 架构:** `docs/design/2026-06-12-bugfix-agent-branch-isolation-architecture.md`
- **Development Guide / 开发指南:** `docs/design/2026-06-12-bugfix-agent-branch-isolation-development-guide.md`
- **Python:** `.venv/bin/python` → Python 3.13.5

## 2. Design Summary / 设计概述

Before this change, BugFixAgent executed fixes in the active development workspace using `git add` and `git commit` on the project root. This meant automated fixes could modify the user's current branch, and dirty workspace state would block all fix execution.

The new design creates an **isolated Git worktree** for each fix:

```text
active branch (e.g. feature/quant-factor-v1)
  → BugFixBranchManager creates worktree at runtime/bugfix_worktrees/<bug_id>/
  → BugFixAgent applies fix inside worktree
  → Tests run inside worktree
  → Commit happens on bugfix/<bug_id> branch (NOT active branch)
  → Merge back to main only after explicit human approval
```

## 3. Changed Files / 修改文件

| File / 文件 | Action / 操作 | Purpose / 目的 |
|---|---|---|
| `src/product_app/bug_fix_branch_manager.py` | **NEW** | Git worktree management for isolated execution |
| `tests/test_bug_fix_branch_manager.py` | **NEW** | 12 tests for branch manager |
| `src/product_app/bug_fix_agent.py` | Modified | Add `BugFixExecutionContext`; `execute_fix()` accepts optional context |
| `src/product_app/bug_fix_workflow.py` | Modified | Use isolated worktree; add `merge_fix()`; add `merge_pending` state |
| `src/api/product_routes.py` | Modified | Add `POST /merge` and `POST /cleanup-worktree` endpoints |
| `tests/test_bug_auto_fix.py` | Modified | Updated 3 tests for verified state; mock branch manager |
| `tests/test_product_routes.py` | Modified | Added 3 API tests for merge/cleanup |
| `tests/test_product_dashboard_source.py` | Modified | Added source-level checks for bugfix UI strings |

## 4. Key Implementation Details / 关键实现

### BugFixBranchManager

- **`_make_worktree_info(bug_id)`** — computes branch name (`bugfix/<bug_id>-<timestamp>`) and worktree path without git
- **`prepare_worktree(bug_id)`** — runs `git fetch origin`, `git rev-parse`, `git worktree add -b`
- **`commit_fix(worktree, files, message)`** — stages and commits only proposal files
- **`merge_fix(worktree, force)`** — `--no-ff` merge; blocked by default unless `BUGFIX_AUTO_MERGE=true` or `force=True`
- **`cleanup_worktree(worktree, keep_on_failure)`** — validates path is under configured root before deletion

### BugFixExecutionContext

```python
@dataclass
class BugFixExecutionContext:
    bug_id: str
    project_root: Path      # worktree path (NOT active project root)
    base_branch: str
    branch_name: str
    worktree_path: Path
```

When `context` is passed to `execute_fix()`, all file operations use `context.project_root` and tests run in `context.worktree_path`.

### State Flow

```text
open → analyzing → proposed → approved → fixing
  → verified (fix branch committed, tests passed)
  → merge_pending (waiting for human merge approval)
  → fixed (merged into base branch)
```

### API Endpoints Added

| Endpoint | Method | Purpose |
|---|---|---|
| `/product/feedback/{bug_id}/merge` | POST | Merge verified fix into base branch (requires `force=true`) |
| `/product/feedback/{bug_id}/cleanup-worktree` | POST | Remove isolated worktree after merge |

## 5. Verification / 验证

### Commands & Results

```bash
# Ruff
.venv/bin/python -m ruff check \
  src/product_app/bug_fix_branch_manager.py src/product_app/bug_fix_agent.py \
  src/product_app/bug_fix_workflow.py src/api/product_routes.py \
  tests/test_bug_fix_branch_manager.py tests/test_bug_auto_fix.py \
  tests/test_product_routes.py tests/test_product_dashboard_source.py
```
Result: **All checks passed!**

```bash
# Py_compile
.venv/bin/python -m py_compile src/product_app/bug_fix_branch_manager.py \
  src/product_app/bug_fix_agent.py src/product_app/bug_fix_workflow.py \
  src/api/product_routes.py
```
Result: **No errors.**

```bash
# Tests
.venv/bin/python -m pytest tests/test_bug_fix_branch_manager.py -q
# 12 passed

.venv/bin/python -m pytest tests/test_bug_auto_fix.py -q
# 30 passed

.venv/bin/python -m pytest tests/test_product_routes.py -q
# 9 passed (6 original + 3 new merge/cleanup)

.venv/bin/python -m pytest tests/test_product_dashboard_source.py -q
# 3 passed
```
**Total: 54 tests passed.**

```bash
git diff --check
```
Result: **No trailing whitespace or conflict markers.**

## 6. Not Run / 未运行项

- **WSL real startup smoke:** Requires ports 8000/8080 free. Not run due to existing FastAPI process on port 8000.
- **Dashboard Streamlit browser smoke:** No browser tooling available in this environment. Source-level tests verify required strings exist.
- **Full worktree integration test with actual git:** The `BugFixBranchManager.prepare_worktree()` method runs real git commands and requires a real git repository. Unit tests mock `subprocess.run` or use `_make_worktree_info()` to verify path construction without real git.

## 7. Safety Confirmation / 安全确认

- [x] **BugFixAgent 不修改活跃开发分支** — 所有操作在隔离 worktree 中执行
- [x] **活跃工作区脏状态不阻断修复** — 不再检查 `_get_dirty_files()`，改为检查 worktree
- [x] **脏 worktree 仍阻断执行** — `BugFixBranchManager` 通过 git 命令确保状态干净
- [x] **受限模块仍被阻断** — `execute_fix()` 在创建 worktree 前检查 `_is_blocked_module()`
- [x] **合并默认不自动** — `BUGFIX_AUTO_MERGE=false`，需要用户 `force=true` 才合并
- [x] **合并需要显式 API 调用** — `POST /feedback/{id}/merge` 端点
- [x] **未启用真实自动交易** — 未修改 `ENABLE_LIVE_TRADING`、风控、执行模块
- [x] **未提交密钥** — 所有密钥来自环境变量

## 8. Remaining Risks / 剩余风险

| Risk / 风险 | Mitigation / 缓解 |
|---|---|
| `BugFixBranchManager.prepare_worktree()` requires real git repo and network (for fetch) | Falls back to local branch if fetch fails |
| Dashboard UI not fully implemented (button labels exist in source checks only) | Backend routes work; UI can be iterated separately |
| Cleanup endpoint assumes `workflow.branch_manager` exists | Falls back with error message if not initialized |

## 9. Deliverables / 交付物

1. `src/product_app/bug_fix_branch_manager.py` — isolated worktree management.
2. `src/product_app/bug_fix_agent.py` — `BugFixExecutionContext` + context-aware `execute_fix()`.
3. `src/product_app/bug_fix_workflow.py` — isolated execution, `merge_fix()`, `merge_pending` state.
4. `src/api/product_routes.py` — merge + cleanup-worktree API endpoints.
5. 54 tests across 4 test files — all pass.
6. Static checks pass (ruff, py_compile).
7. This development report in Chinese + English.

Signed-off for / 移交: **Test Engineer Agent** verification.
