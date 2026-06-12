# BugFix Agent Branch Isolation Test Guide

Date: 2026-06-12
Owner role: Architect Agent
Target reader: Test Engineer Agent

## Required Reading

Read in this order:

1. `AGENTS.md`
2. `docs/process/AGENT_DEVELOPMENT_PIPELINE.md`
3. `docs/process/TEST_ENGINEER_WORKFLOW.md`
4. `docs/policy/SELF_TEST_CHECKLIST.md`
5. `docs/design/2026-06-12-bugfix-agent-branch-isolation-architecture.md`
6. `docs/design/2026-06-12-bugfix-agent-branch-isolation-development-guide.md`
7. Developer report: `docs/dev_reports/YYYY-MM-DD-bugfix-agent-branch-isolation-dev-report.md`

## Branch Isolation Requirement

You must test from a temporary local branch according to:

```text
docs/process/TEST_ENGINEER_WORKFLOW.md
```

Required start commands:

```bash
git status --short --branch
git branch --show-current
git rev-parse --short HEAD
git diff --stat
```

Create:

```bash
BASE_BRANCH="$(git branch --show-current)"
BASE_SHA="$(git rev-parse --short HEAD)"
TEST_BRANCH="test/bugfix-agent-branch-isolation-$(date +%Y%m%d-%H%M)"
git switch -c "$TEST_BRANCH"
```

At the end, switch back to `BASE_BRANCH`, write the test report there, and delete `TEST_BRANCH`.

## Test Mission

Do not try to prove the developer right. Verify whether BugFixAgent is safe enough to run in a multi-Agent workspace.

The feature passes only if:

- active development workspace is never modified by automated fix execution;
- fix execution happens in an isolated worktree;
- dirty active workspace does not block isolated execution;
- dirty isolated worktree still blocks execution;
- merge to main is not automatic by default;
- user can approve merge through Dashboard/API only after gates pass;
- restricted modules remain blocked.

## Mandatory Coverage Matrix

Your report must include this matrix:

| Requirement | Test Evidence | Status |
|---|---|---|
| Isolated worktree is created under `runtime/bugfix_worktrees/` | command/test path | PASS/FAIL |
| Bugfix branch uses `bugfix/` prefix | command/test path | PASS/FAIL |
| Dirty active workspace does not block fix | test name | PASS/FAIL |
| Dirty isolated worktree blocks fix | test name | PASS/FAIL |
| Fix writes inside worktree only | test name | PASS/FAIL |
| Branch metadata is recorded | API/test output | PASS/FAIL |
| Tests run inside worktree | test output | PASS/FAIL |
| Commit is created on bugfix branch | git/test output | PASS/FAIL |
| Merge is manual by default | API/test output | PASS/FAIL |
| Merge rejects failed tests | API/test output | PASS/FAIL |
| Merge rejects restricted modules | API/test output | PASS/FAIL |
| Dashboard exposes required buttons | source/browser evidence | PASS/FAIL |
| Approve Merge requires confirmation | source/browser evidence | PASS/FAIL |
| Cleanup cannot delete outside worktree root | test name | PASS/FAIL |

## Required Commands

Run developer-declared tests first:

```bash
./.venv/bin/python -m pytest tests/test_bug_fix_branch_manager.py tests/test_bug_auto_fix.py -q --basetemp=runtime/pytest-tmp-test-bugfix-branch
```

Run API tests:

```bash
./.venv/bin/python -m pytest tests/test_product_routes.py -q --basetemp=runtime/pytest-tmp-test-bugfix-api
```

Run UI/source tests:

```bash
./.venv/bin/python -m pytest tests/test_product_dashboard_source.py -q --basetemp=runtime/pytest-tmp-test-bugfix-ui
```

Run static checks:

```bash
./.venv/bin/python -m ruff check src/product_app/bug_fix_agent.py src/product_app/bug_fix_workflow.py src/product_app/bug_fix_branch_manager.py src/api/product_routes.py src/ui_report/product_dashboard.py tests/test_bug_auto_fix.py tests/test_bug_fix_branch_manager.py tests/test_product_routes.py tests/test_product_dashboard_source.py
git diff --check
```

If browser tooling is available, run a Streamlit smoke test for the Feedback / BugFix page. If not available, explicitly record the gap.

## Manual Safety Probes

### Probe 1: Dirty active workspace

On the temporary test branch, create an unrelated untracked file in the active workspace:

```bash
mkdir -p runtime/manual-probe
echo "probe" > runtime/manual-probe/active-workspace-dirty.txt
git status --short
```

Then run the isolated BugFixAgent test or API path. Expected:

```text
isolated fix execution is not blocked by this active workspace artifact
```

Clean the probe file before returning to base branch.

### Probe 2: Dirty isolated worktree

Use the test suite or a controlled fixture to create a dirty file inside the bugfix worktree before commit. Expected:

```text
workflow returns fix_failed or blocked; no commit; no fixed/merged state
```

### Probe 3: Merge gate

Attempt merge without confirmation. Expected:

```text
merge rejected
```

Attempt merge when tests failed. Expected:

```text
merge rejected
```

Attempt merge for restricted file proposal. Expected:

```text
merge rejected before branch creation or before merge
```

## Dashboard Validation

Verify the Dashboard contains:

- `Analyze`
- `Approve Fix`
- `Reject Fix`
- `Re-run Verification`
- `Approve Merge`
- `Cleanup Worktree`

Verify Dashboard displays:

- bug id
- status
- base branch
- base SHA
- fix branch
- fix commit
- worktree path
- test result
- touched files
- merge status
- blocked reason

`Approve Merge` must require explicit confirmation and must not be enabled when:

- tests failed;
- no fix branch exists;
- restricted files are touched;
- worktree is dirty;
- human confirmation is missing.

## Defect Severity Guidance

Use these severities:

- S0: auto merge can change trading/risk/execution behavior without approval; secrets leak; active workspace overwritten.
- S1: BugFixAgent modifies active development branch; merge happens automatically by default; restricted module is modified.
- S2: branch metadata missing; dirty isolated worktree not detected; Dashboard merge button enabled incorrectly; tests not run in worktree.
- S3: confusing UI labels, incomplete status text, non-blocking doc mismatch.
- S4: polish or future improvement.

S0/S1/S2 must block review.

## Test Report

Create on the original development branch after finishing temporary branch tests:

```text
docs/test_reports/YYYY-MM-DD-bugfix-agent-branch-isolation-test-report.md
```

Report must include:

- base branch;
- base commit;
- temporary test branch;
- whether temporary branch was deleted;
- test environment;
- coverage matrix;
- exact commands and outputs;
- manual probe results;
- API/UI evidence;
- defect list with severity;
- feedback bug paths if generated;
- residual risks;
- final result: `PASS`, `PASS_WITH_NOTES`, or `REJECTED`.

## Prompt Template For Test Agent

```text
你现在作为本项目的 Test Engineer Agent 验证 BugFix Agent 分支隔离能力。请先读取并遵守：

1. AGENTS.md
2. docs/process/AGENT_DEVELOPMENT_PIPELINE.md
3. docs/process/TEST_ENGINEER_WORKFLOW.md
4. docs/policy/SELF_TEST_CHECKLIST.md
5. docs/design/2026-06-12-bugfix-agent-branch-isolation-architecture.md
6. docs/design/2026-06-12-bugfix-agent-branch-isolation-development-guide.md
7. docs/dev_reports/YYYY-MM-DD-bugfix-agent-branch-isolation-dev-report.md

你必须从当前开发分支新建本地临时测试分支 test/bugfix-agent-branch-isolation-<YYYYMMDD-HHMM>，所有测试和探测都在该分支执行。测试结束后切回原开发分支，只提交 docs/test_reports/YYYY-MM-DD-bugfix-agent-branch-isolation-test-report.md，并删除临时测试分支。

重点验证：
- BugFixAgent 不修改当前开发分支；
- 自动修复在 runtime/bugfix_worktrees/ 下的独立 worktree 执行；
- dirty active workspace 不阻塞隔离修复；
- dirty isolated worktree 会阻断修复；
- merge 默认不自动执行；
- Approve Merge 必须有人为确认并通过安全门禁；
- restricted modules 仍然被阻断；
- Dashboard 按钮流完整可用。

至少运行：

./.venv/bin/python -m pytest tests/test_bug_fix_branch_manager.py tests/test_bug_auto_fix.py -q --basetemp=runtime/pytest-tmp-test-bugfix-branch
./.venv/bin/python -m pytest tests/test_product_routes.py -q --basetemp=runtime/pytest-tmp-test-bugfix-api
./.venv/bin/python -m pytest tests/test_product_dashboard_source.py -q --basetemp=runtime/pytest-tmp-test-bugfix-ui
./.venv/bin/python -m ruff check src/product_app/bug_fix_agent.py src/product_app/bug_fix_workflow.py src/product_app/bug_fix_branch_manager.py src/api/product_routes.py src/ui_report/product_dashboard.py tests/test_bug_auto_fix.py tests/test_bug_fix_branch_manager.py tests/test_product_routes.py tests/test_product_dashboard_source.py
git diff --check

测试报告必须包含 base branch、base commit、temporary test branch、覆盖矩阵、命令结果、手动安全探针、缺陷分级、剩余风险和最终结论。
```
