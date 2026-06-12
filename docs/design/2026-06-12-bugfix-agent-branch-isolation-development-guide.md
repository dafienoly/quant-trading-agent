# BugFix Agent Branch Isolation Development Guide

Date: 2026-06-12
Owner role: Architect Agent
Target reader: Developer Agent

## Required Reading

Read in this order:

1. `AGENTS.md`
2. `docs/process/AGENT_DEVELOPMENT_PIPELINE.md`
3. `docs/policy/SELF_TEST_CHECKLIST.md`
4. `docs/design/2026-06-12-bugfix-agent-branch-isolation-architecture.md`
5. Current feedback bugs under `feedback/bugs/open/`

## Goal

Implement branch-isolated BugFixAgent execution so automated fixes never modify the active development workspace. The system must create an isolated bugfix worktree/branch from `main` or configured base branch, apply the approved fix there, run tests there, commit there, and expose a user-approved merge flow through API/Dashboard.

## Non-Goals

- Do not enable unattended merge to `main` by default.
- Do not allow BugFixAgent to modify `risk_engine`, `execution_engine`, trading logs, policy files, or other restricted modules without explicit human process outside the auto-fix path.
- Do not solve unrelated feedback bugs in this task.
- Do not convert BugFixAgent into a general coding agent that edits arbitrary files.
- Do not bypass current proposal validation.

## Files To Create

- `src/product_app/bug_fix_branch_manager.py`
- `tests/test_bug_fix_branch_manager.py`
- `docs/dev_reports/YYYY-MM-DD-bugfix-agent-branch-isolation-dev-report.md`

## Files To Modify

- `src/product_app/bug_fix_agent.py`
- `src/product_app/bug_fix_workflow.py`
- `src/product_app/service_manager.py` only if lifecycle/status fields need extension
- `src/api/product_routes.py`
- `src/ui_report/product_dashboard.py`
- `tests/test_bug_auto_fix.py`
- `tests/test_product_routes.py`
- `.gitignore`
- `docs/user_guides/2026-06-11-a-share-live-data-closed-loop-user-manual.md`
- `docs/design/2026-06-11-wsl-product-runtime-ai-agent-architecture.md`
- `docs/policy/SELF_TEST_CHECKLIST.md`

## Implementation Rules

1. Use TDD. Write failing tests before implementation.
2. BugFixAgent must not edit the active development branch.
3. Isolated worktrees must live under `runtime/bugfix_worktrees/`.
4. `runtime/bugfix_worktrees/` must be ignored by Git.
5. Default base branch is `main`, configurable via `BUGFIX_BASE_BRANCH`.
6. Default auto merge is disabled: `BUGFIX_AUTO_MERGE=false`.
7. Merge requires explicit user approval through API/Dashboard.
8. Every fix must record base branch, base SHA, worktree path, fix branch, fix commit, tests, and merge status.
9. Failed tests must not produce a `fixed` status.
10. Commit failure must not produce a `fixed` status.

## Task 1: Add Branch Manager Tests

Create `tests/test_bug_fix_branch_manager.py`.

Required tests:

- creates a branch name with `bugfix/` prefix;
- creates worktree path under configured root;
- rejects path traversal in worktree cleanup;
- records base branch and base SHA;
- commits only proposal files;
- refuses merge when auto merge is disabled;
- cleanup only deletes known worktree paths.

Run:

```bash
./.venv/bin/python -m pytest tests/test_bug_fix_branch_manager.py -q --basetemp=runtime/pytest-tmp-bugfix-branch-manager
```

Expected before implementation: tests fail because the module does not exist.

## Task 2: Implement `BugFixBranchManager`

Create `src/product_app/bug_fix_branch_manager.py`.

Required public API:

```python
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class BugFixWorktree:
    bug_id: str
    base_branch: str
    branch_name: str
    path: Path
    base_sha: str

class BugFixBranchManager:
    def __init__(
        self,
        project_root: Path,
        worktree_root: Path | None = None,
        base_branch: str = "main",
    ) -> None:
        ...

    def prepare_worktree(self, bug_id: str) -> BugFixWorktree:
        ...

    def commit_fix(self, worktree: BugFixWorktree, files: list[str], message: str) -> str:
        ...

    def merge_fix(self, worktree: BugFixWorktree) -> dict:
        ...

    def cleanup_worktree(self, worktree: BugFixWorktree, *, keep_on_failure: bool) -> None:
        ...
```

Implementation requirements:

- Use non-interactive Git commands.
- Use `git fetch origin <base_branch>` when remote exists; if unavailable, use local base branch and record that fallback.
- Use `git worktree add -b <branch> <path> <base_ref>`.
- Validate all resolved paths stay under configured worktree root before deletion.
- Do not delete untracked user paths outside `runtime/bugfix_worktrees/`.
- Return structured errors; do not silently swallow Git failures.

## Task 3: Add Execution Context

Modify `src/product_app/bug_fix_agent.py`.

Add:

```python
from dataclasses import dataclass
from pathlib import Path

@dataclass
class BugFixExecutionContext:
    bug_id: str
    project_root: Path
    base_branch: str
    branch_name: str
    worktree_path: Path
```

Change:

```python
def execute_fix(self, bug_report: dict, proposal: dict) -> dict:
```

to:

```python
def execute_fix(
    self,
    bug_report: dict,
    proposal: dict,
    context: BugFixExecutionContext | None = None,
) -> dict:
```

When context is present, all file reads/writes and test commands must run inside `context.project_root`. Preserve backward compatibility for tests that call without context.

## Task 4: Refactor Workflow To Use Isolated Worktree

Modify `src/product_app/bug_fix_workflow.py`.

Required changes:

- Inject or lazily create `BugFixBranchManager`.
- In `_execute_and_verify`, validate proposal first.
- Create worktree before applying code changes.
- Check dirty state inside the isolated worktree, not active `_PROJECT_ROOT`.
- Execute fix with `BugFixExecutionContext`.
- Commit only proposal files inside the worktree.
- Update bug report with:
  - `base_branch`
  - `base_sha`
  - `fix_branch`
  - `fix_commit`
  - `fix_worktree_path`
  - `merge_status`
- Do not mark as `fixed` merely because branch commit succeeded. Use `verified` or `merge_pending`.

Required state distinction:

```text
verified = fix branch exists and tests passed
merged = fix was merged into base branch after explicit approval
```

## Task 5: Add Merge And Cleanup APIs

Modify `src/api/product_routes.py`.

Add or normalize:

```text
GET  /product/bug-fix/bugs
GET  /product/bug-fix/{bug_id}/status
POST /product/bug-fix/{bug_id}/analyze
POST /product/bug-fix/{bug_id}/approve
POST /product/bug-fix/{bug_id}/reject
POST /product/bug-fix/{bug_id}/verify
POST /product/bug-fix/{bug_id}/merge
POST /product/bug-fix/{bug_id}/cleanup-worktree
```

Merge endpoint must reject when:

- tests failed;
- no fix branch exists;
- bug is not `verified` / `merge_pending`;
- restricted files are touched;
- worktree is dirty;
- human confirmation text is missing;
- `BUGFIX_AUTO_MERGE=false` and no explicit merge request is made.

## Task 6: Implement Dashboard Button Flow

Modify `src/ui_report/product_dashboard.py`.

Add Feedback / BugFix section with:

- bug list;
- selected bug detail;
- analysis/proposal panel;
- branch/test result panel;
- buttons:
  - `Analyze`
  - `Approve Fix`
  - `Reject Fix`
  - `Re-run Verification`
  - `Approve Merge`
  - `Cleanup Worktree`

Button enablement must follow the architecture document. `Approve Merge` must require explicit confirmation and must display base branch, fix branch, fix commit, touched files, and test result.

## Task 7: Tests

Extend `tests/test_bug_auto_fix.py`.

Required tests:

- dirty active workspace does not block isolated fix;
- dirty isolated worktree blocks fix;
- fix writes to worktree path, not active project root;
- fix result records branch metadata;
- restricted modules are blocked before branch creation;
- failed tests keep worktree when configured;
- merge endpoint rejects without explicit confirmation;
- cleanup endpoint refuses path traversal.

Extend `tests/test_product_routes.py`.

Required API tests:

- status returns branch metadata;
- approve returns fix branch after execution;
- merge rejects failed tests;
- merge rejects restricted modules;
- cleanup returns ok only for known worktree.

Add source-level UI tests if browser smoke is unavailable:

- required button labels exist;
- required API endpoint strings exist;
- merge confirmation text exists;
- disabled-state logic exists for failed tests and restricted proposals.

## Task 8: Documentation

Update:

- `docs/user_guides/2026-06-11-a-share-live-data-closed-loop-user-manual.md`
- `docs/design/2026-06-11-wsl-product-runtime-ai-agent-architecture.md`
- `docs/policy/SELF_TEST_CHECKLIST.md`

Must explain:

- BugFixAgent works in isolated branch/worktree;
- users approve fix and merge separately;
- merge to main is not automatic by default;
- command-line Git is not required for the happy path;
- restricted modules still require manual developer workflow.

## Verification Commands

Run:

```bash
./.venv/bin/python -m ruff check src/product_app/bug_fix_agent.py src/product_app/bug_fix_workflow.py src/product_app/bug_fix_branch_manager.py src/api/product_routes.py tests/test_bug_auto_fix.py tests/test_bug_fix_branch_manager.py tests/test_product_routes.py
./.venv/bin/python -m pytest tests/test_bug_fix_branch_manager.py tests/test_bug_auto_fix.py -q --basetemp=runtime/pytest-tmp-bugfix-branch
./.venv/bin/python -m pytest tests/test_product_routes.py -q --basetemp=runtime/pytest-tmp-bugfix-api
git diff --check
```

If UI changed:

```bash
./.venv/bin/python -m pytest tests/test_product_dashboard_source.py -q --basetemp=runtime/pytest-tmp-bugfix-ui
```

## Development Report

Create:

```text
docs/dev_reports/YYYY-MM-DD-bugfix-agent-branch-isolation-dev-report.md
```

Report must include:

- changed files;
- branch isolation design summary;
- API changes;
- Dashboard changes;
- test commands and exact results;
- remaining risks;
- safety confirmation:
  - no live trading enabled;
  - restricted modules blocked;
  - no secrets committed;
  - merge requires explicit user approval.

## Handoff Criteria

Do not hand off to Test Engineer until:

- targeted tests pass;
- ruff passes for touched files;
- `git diff --check` passes;
- development report is written;
- no unrelated files are changed.
