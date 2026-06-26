# Pipeline Bootstrap 本地 Epic 分支残留 Hotfix Requirements

## 用户目标

修复 Issue-driven bootstrap 在 self-hosted runner 上重复触发同一 issue 时，因残留同名本地 epic 分支而直接失败的问题，确保 V16.3 及后续 issue 可以稳定重跑。

## 背景

在 `PR #92` 合并后，重新触发 V16.3 issue `#91` 的 bootstrap run `28216886529`，已经越过 Team Lead team-plan 超时问题，但失败在：

```text
Create or switch epic branch
fatal: a branch named 'epic/20260626-provider-test-suite-fallback-governance-issue-91' already exists
```

根因是 self-hosted runner 工作目录残留了同名本地分支，而 workflow 仍使用：

```text
git switch -c $branch
```

该命令在本地分支已存在时会直接失败。

## 目标

1. Bootstrap 识别 self-hosted runner 上已存在的同名本地 epic 分支。
2. 当不存在可复用远端 open PR 时，允许将该本地分支安全 reset 到当前 HEAD 并继续流程。
3. 保持已有 open PR 复用、closed PR restart 分支、merged PR fail closed 逻辑不变。
4. 补充自动化测试与严格 regression 标记，避免同类问题回归。

## 非目标

1. 不修改 Team Lead / Developer / Tester 的模型路由。
2. 不修改交易、风控、券商、行情业务逻辑。
3. 不绕过 PR state 检查。
4. 不改变 main 手动合并边界。

## 功能要求

### F-001 本地分支残留检测

在 bootstrap 的 `Create or switch epic branch` 步骤中，必须检查：

```text
refs/heads/$branch
```

是否已存在。

### F-002 安全 reset

若不存在可复用远端 open PR，且本地分支已存在，则允许：

```text
git switch -C $branch
```

将本地分支 reset 到当前 HEAD 后继续。

### F-003 远端复用逻辑保持

当存在 open PR 时，仍必须：

```text
git fetch origin $branch
git switch -C $branch --track origin/$branch
```

### F-004 回归守护

自动化测试和 `scripts/agent_pipeline_regression.py --strict` 必须覆盖：

1. 本地分支残留检测标记。
2. reset 提示文案。
3. `git switch -C $branch` 的存在。
4. 不再保留 `git switch -c $branch`。

## 验收标准

1. 同一 issue 在 self-hosted runner 上重复触发时，不再因残留同名本地 epic 分支直接失败。
2. open PR 远端复用逻辑保持不变。
3. merged / closed PR 保护逻辑保持不变。
4. 自动化测试通过。
5. `scripts/agent_pipeline_regression.py --strict` 通过。

## 安全约束

1. 不自动合并 `main`。
2. 不提交 `.agent/tmp/**`、`.agent/reports/**`、`runtime/**`、`feedback/index.json`。
3. 不触碰交易敏感模块。
