# Branch Workflow for Parallel Agent Development

This document is a standing repository rule. All Developer Agents, Test Engineer
Agents, BugFix Agents, Architect Reviewers, and PM Acceptance Agents must follow
it unless the user explicitly overrides it for a specific task.

## 1. Goals

The branch workflow exists to let multiple developers and testers work in
parallel without corrupting the stable product line or each other's working
state.

It must ensure:

1. `main` only contains reviewed and accepted work.
2. A large feature has one integration branch.
3. Each developer works on an isolated feature branch.
4. Each tester verifies from a temporary local test branch.
5. Review fixes are isolated and traceable.
6. BugFix automation never modifies the user's active working branch directly.

## 2. Branch Types

| Branch | Purpose | Owner |
|---|---|---|
| `main` | Stable product line; only reviewed and accepted work | Owner / release lead |
| `epic/<date-feature>` | Integration branch for one stage or large feature | Architect / lead agent |
| `feat/<feature>/<module>` | Developer branch for one module or task slice | Developer Agent |
| `fix/<feature>/<issue>` | Review, test, or acceptance fix branch | Developer or BugFix Agent |
| `test/<feature>/<scope>-<tester>-<timestamp>` | Local temporary verification branch | Test Engineer Agent |
| `bugfix/<bug-id>-<timestamp>` | Isolated BugFixAgent branch/worktree | BugFix Agent |

## 3. Standard Flow

### 3.1 Start a New Stage

The lead agent starts from current `main`:

```bash
git switch main
git pull --ff-only origin main
git switch -c epic/<date-feature>
git push -u origin epic/<date-feature>
```

Requirements and architecture documents may be committed directly to the epic
branch or merged from a docs branch. They must be present before development
starts.

### 3.2 Developer Work

Each Developer Agent starts from the epic branch:

```bash
git switch epic/<date-feature>
git pull --ff-only origin epic/<date-feature>
git switch -c feat/<feature>/<module>
```

Developer branches must contain:

- code changes;
- focused tests;
- a development report in `docs/features/<feature-id>/`;
- exact self-test commands and results.

Developer branches merge back into the epic branch, not directly into `main`.

### 3.3 Test Work

Each Test Engineer Agent creates a local temporary test branch from the branch
under test:

```bash
git status --short --branch
git switch <branch-under-test>
git switch -c test/<feature>/<scope>-<tester>-$(date +%Y%m%d-%H%M)
```

Rules:

- Test branches are local verification branches.
- Testers may add temporary probes or tests on the test branch.
- Testers must not modify business code on the original development branch.
- After testing, testers return to the original branch, delete the temporary
  test branch, and commit only the test report to the original branch or to a
  dedicated report branch if requested.

Cleanup:

```bash
git switch <branch-under-test>
git branch -D test/<feature>/<scope>-<tester>-<timestamp>
```

### 3.4 Review Fixes

Architect Review or PM Acceptance failures use a fix branch:

```bash
git switch epic/<date-feature>
git pull --ff-only origin epic/<date-feature>
git switch -c fix/<feature>/review-r1
```

The fix branch must include:

- the fix;
- regression tests;
- an updated development report or fix report;
- updated test report after tester verification.

### 3.5 Merge to Main

Only after development, testing, architecture review, PM acceptance, and log
updates pass:

```bash
git switch main
git pull --ff-only origin main
git merge --no-ff epic/<date-feature>
git push origin main
```

After successful merge and push, delete completed local and remote feature
branches when they are no longer needed:

```bash
git branch -d epic/<date-feature>
git push origin --delete epic/<date-feature>
```

## 4. BugFixAgent Branch Rules

BugFixAgent must work in an isolated branch/worktree:

```text
bugfix/<bug-id>-<timestamp>
runtime/bugfix_worktrees/<bug-id>-<timestamp>/
```

BugFixAgent must not:

- modify the active user branch directly;
- merge to `main` without human approval;
- touch restricted trading, risk, execution, broker, or order modules without a
  separate architecture decision;
- mark a bug fixed if tests or git commit fail.

## 5. Pull and Rebase Discipline

Developer Agents should sync with the epic branch before starting a work block
and before opening a merge request:

```bash
git fetch origin
git switch feat/<feature>/<module>
git merge origin/epic/<date-feature>
```

Use merge by default for agent work because it is easier to audit. Rebase is
allowed only when the branch owner understands the history rewrite and the
branch has not been shared.

## 6. Required Reports

| Stage | Required report |
|---|---|
| Developer branch ready | `docs/features/<feature-id>/phase-<n>-dev-report.md` |
| Test branch verification complete | `docs/features/<feature-id>/phase-<n>-test-report.md` |
| Review complete | `docs/features/<feature-id>/codex-review-r1.md` |
| Acceptance complete | `docs/features/<feature-id>/acceptance.md` |

Reports are part of the branch deliverable. A branch is not ready just because
tests pass.

## 7. Automatic Adherence

To make agents follow this workflow automatically:

1. `AGENTS.md` lists this file in the required read order.
2. Task prompts for developers and testers must mention the target branch type.
3. Architecture documents should include a "Branch Plan" section for large work.
4. Test prompts must require temporary local `test/...` branches.
5. Reviewers must reject work that used the wrong branch type when it creates
   traceability or safety risk.

If an Agent receives a task with no branch instructions, it must ask whether to
work from the current epic branch or create a new one, unless the task is a
small documentation-only fix.
