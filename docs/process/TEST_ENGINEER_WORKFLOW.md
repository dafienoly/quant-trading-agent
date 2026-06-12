# Test Engineer Workflow

This document defines the required workflow for Test Engineer Agents. It is a
standing process rule, not a feature-specific guide.

## Core Rule

Testing must be isolated from development work.

For every test cycle, the Test Engineer Agent must:

1. Start from the current development branch.
2. Create a local temporary test branch from that exact commit.
3. Run tests, probes, temporary diagnostics, and optional local-only experiments on the temporary test branch.
4. Write the final test report on the original development branch.
5. Delete the temporary test branch after testing.

The Test Engineer Agent must not modify business code on the original
development branch. Only the test report may be committed on the original
development branch.

## Why This Rule Exists

- Developer and tester work can proceed in parallel without stepping on each
  other.
- Test-only probes, temporary instrumentation, generated screenshots, or debug
  files cannot accidentally leak into development code.
- The original development branch remains reviewable: code changes come from the
  Developer Agent; testing evidence comes from the Test Engineer Agent.
- Architect Reviewer can distinguish implementation changes from test evidence.

## Branch Procedure

### 1. Record Starting State

Run:

```bash
git status --short --branch
git branch --show-current
git rev-parse --short HEAD
git diff --stat
```

If the working tree has uncommitted code changes before testing starts, stop and
report the problem. Do not test on an ambiguous mixed workspace.

Untracked or modified test reports from a previous tester must be resolved before
starting a new test cycle.

### 2. Create Temporary Test Branch

Use this naming pattern:

```bash
test/<feature-slug>-<YYYYMMDD-HHMM>
```

Example:

```bash
BASE_BRANCH="$(git branch --show-current)"
BASE_SHA="$(git rev-parse --short HEAD)"
TEST_BRANCH="test/product-startup-services-$(date +%Y%m%d-%H%M)"
git switch -c "$TEST_BRANCH"
```

Record `BASE_BRANCH`, `BASE_SHA`, and `TEST_BRANCH` in the test report.

### 3. Run Tests On Temporary Branch

On the temporary test branch, the tester may:

- run pytest, ruff, shell syntax checks, API smoke tests, browser smoke tests,
  and CLI smoke tests;
- create local diagnostic files under `runtime/`, `logs/`, or temporary
  directories;
- apply temporary local instrumentation only if it is reverted before leaving
  the temporary branch.

The tester must not commit implementation code changes.

Recommended baseline:

```bash
./.venv/bin/python -m pytest <developer-claimed-tests> -q --basetemp=runtime/pytest-tmp-test-<feature>
./.venv/bin/python -m pytest <tester-extra-tests> -q --basetemp=runtime/pytest-tmp-test-extra-<feature>
./.venv/bin/python -m ruff check <test-related-or-touched-python-files>
git diff --check
```

For WSL/Linux, default Python is:

```bash
./.venv/bin/python
```

If that path does not exist, run and record:

```bash
which python
python -V
ls .venv/bin/python
```

### 4. Preserve Evidence Without Polluting Code

If runtime defects generate feedback bugs, record paths such as:

```text
feedback/bugs/open/BUG_*.md
feedback/bugs/open/BUG_*.json
```

If tests generate local-only artifacts, either:

- keep them untracked and mention them in the report, or
- delete them before returning to the original branch.

Do not commit generated runtime files unless the test architecture explicitly
requires them as fixtures.

### 5. Return To Original Branch

Before leaving the temporary test branch:

```bash
git status --short
```

If temporary code changes exist, discard or manually revert them on the test
branch only. Do not carry them back.

Then return:

```bash
git switch "$BASE_BRANCH"
```

### 6. Write Test Report On Original Development Branch

Create or update:

```text
docs/test_reports/YYYY-MM-DD-<feature>-test-report.md
```

The report must include:

- base branch name;
- base commit SHA tested;
- temporary test branch name;
- test environment;
- requirement-to-test coverage matrix;
- commands executed and exact results;
- skipped, xfail, warnings, external dependency failures;
- defects and severity;
- feedback bug paths when generated;
- residual risk;
- final result: `PASS`, `PASS_WITH_NOTES`, or `REJECTED`.

Commit only the test report on the original development branch unless the user
explicitly asks otherwise.

### 7. Delete Temporary Test Branch

After the report is written on the original branch:

```bash
git branch -D "$TEST_BRANCH"
```

Confirm:

```bash
git branch --list "$TEST_BRANCH"
git status --short --branch
```

The temporary branch should no longer exist. The working tree should contain only
the intended test report changes.

## Tester Prohibitions

Test Engineer Agents must not:

- modify implementation code on the original development branch;
- commit code fixes while acting as Test Engineer Agent;
- weaken tests to make the feature pass;
- delete failing tests;
- treat mock/demo/paper trading as real live trading capability;
- ignore skipped tests, warnings, xfail, dependency failures, or external-service
  outages;
- approve orally without a reproducible test report;
- keep the temporary test branch after the test cycle completes.

## Agent Prompt Template

Use this prompt when assigning a feature to a Test Engineer Agent.

```text
你现在作为本项目的 Test Engineer Agent 参与验证。请先读取并遵守根目录 AGENTS.md；然后按顺序读取：

1. docs/process/AGENT_DEVELOPMENT_PIPELINE.md
2. docs/process/TEST_ENGINEER_WORKFLOW.md
3. docs/policy/SELF_TEST_CHECKLIST.md
4. 本次需求文档：docs/requirements/<YYYY-MM-DD-feature>-requirements.md
5. 本次架构文档：docs/design/<YYYY-MM-DD-feature>-architecture.md
6. 如存在，本次开发指导：docs/design/<YYYY-MM-DD-feature>-development-guide.md
7. 开发报告：docs/dev_reports/<YYYY-MM-DD-feature>-dev-report.md

你在 WSL/Linux 环境工作，必须使用项目虚拟环境执行 Python、pytest、ruff 等命令。默认虚拟环境路径为 ./.venv/bin/python。如果该路径不存在，先用 which python、python -V、ls .venv/bin/python 确认实际解释器路径，并在测试报告中记录。

重要分支纪律：
- 开始前在当前开发分支执行 git status --short --branch、git branch --show-current、git rev-parse --short HEAD、git diff --stat。
- 如果原开发分支存在未解释的未提交代码变更，停止并报告，不要继续测试。
- 从当前开发分支当前 commit 新建本地临时测试分支，命名为 test/<feature-slug>-<YYYYMMDD-HHMM>。
- 所有测试、探测、临时诊断、临时 instrumentation 都只能在临时测试分支上进行。
- 测试完成后回到原开发分支，只在原开发分支写入并提交 docs/test_reports/<YYYY-MM-DD-feature>-test-report.md。
- 删除临时测试分支。
- 你不允许在原开发分支修改业务代码，也不允许作为测试工程师提交代码修复。

你的任务不是证明开发通过，而是从用户、交易安全、数据契约和产品验收角度判断 <feature> 是否真的可交付。

测试要求：
- 对照需求文档建立功能点测试矩阵。
- 对照架构文档检查模块边界、失败路径和安全约束。
- 复跑开发报告中的自测命令，确认结果是否可复现。
- 补充正常路径、非法参数、异常路径、fail-closed、API/UI/数据源/风控相关测试。
- 不得只测 happy path。
- 不得把 mock/demo/paper trading 当作真实实盘能力验收。
- 涉及运行时缺陷时，检查是否生成 feedback/bugs/open/BUG_*.md 和 .json。
- 所有 skipped、xfail、warning、外部服务失败和未覆盖风险都必须写入报告。

至少运行并记录：

git status --short --branch
git branch --show-current
git rev-parse --short HEAD
git diff --stat

./.venv/bin/python -m pytest <开发报告声明的测试文件> -q --basetemp=runtime/pytest-tmp-test-<feature>
./.venv/bin/python -m pytest <你补充的相关测试文件> -q --basetemp=runtime/pytest-tmp-test-extra-<feature>
./.venv/bin/python -m ruff check <测试相关或本次触碰的 Python 文件>
git diff --check

测试报告必须输出到：
docs/test_reports/<YYYY-MM-DD-feature>-test-report.md

测试报告必须包含：
- base branch
- base commit
- temporary test branch
- 测试环境
- 测试范围和未覆盖范围
- 需求覆盖矩阵
- 命令和结果
- API/UI/CLI/数据源/风控 smoke 证据
- 缺陷列表和严重等级
- feedback bug 文件路径
- 剩余风险
- 最终结论：PASS、PASS_WITH_NOTES 或 REJECTED
```

