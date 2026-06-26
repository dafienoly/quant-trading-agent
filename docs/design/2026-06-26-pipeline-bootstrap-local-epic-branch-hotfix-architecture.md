# Pipeline Bootstrap 本地 Epic 分支残留 Hotfix Architecture

## 概述

本 hotfix 只修复 bootstrap workflow 的本地分支幂等性问题，不修改业务代码和 pipeline 状态机。

## 影响范围

- `.github/workflows/agent-issue-bootstrap.yml`
- `tests/test_agent_pipeline_automation.py`
- `scripts/agent_pipeline_regression.py`

## 设计思路

### 1. 保留现有 PR state 策略

以下逻辑保持不变：

- open PR：复用远端 branch
- merged PR：fail closed
- closed PR：生成 restart 分支

### 2. 新增本地分支残留检测

在 PR state 判断之后，增加：

```text
git show-ref --verify --quiet "refs/heads/$branch"
```

用来识别 self-hosted runner 工作目录残留的本地 branch ref。

### 3. 新分支路径改为 reset 语义

当不存在可复用远端 open PR 时：

- 若本地分支不存在：`git switch -C $branch` 等价于创建新分支。
- 若本地分支存在：`git switch -C $branch` 会把该分支 reset 到当前 HEAD。

这样 bootstrap 可以在 runner 有残留 branch ref 的情况下幂等执行。

### 4. 风险控制

该 reset 仅发生在：

1. 没有可复用 open PR；
2. 当前工作树已经被 `actions/checkout` 的 `clean` 和 `reset --hard` 清理；
3. bootstrap 即将重新生成 `.agent` 状态和 handoff。

因此不会放宽 PR 复用边界，也不会把 closed / merged PR 混回当前 issue。

## 测试策略

1. 文本级 workflow contract test：
   - 检查 `git show-ref --verify --quiet "refs/heads/$branch"`
   - 检查 reset 提示文案
   - 检查 `git switch -C $branch`
   - 检查不再存在 `git switch -c $branch`
2. `scripts/agent_pipeline_regression.py --strict`
3. 报告门禁校验

## 安全影响

1. 不新增真实交易能力。
2. 不改变 main 手动合并边界。
3. 不触碰交易敏感模块。
