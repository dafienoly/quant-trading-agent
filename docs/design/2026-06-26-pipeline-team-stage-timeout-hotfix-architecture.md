# Pipeline Team Stage Timeout Hotfix Architecture

## 概述

本 hotfix 只修复 Team stage runner 的执行边界，不修改 pipeline 状态机和业务模块。

核心思路：

1. 保留现有 `run_opencode_preflight()` 逻辑不变。
2. 为正式 `opencode run` 增加统一的 `run_stage_with_timeout()` 包装器。
3. 使用 stage role 对应的 timeout 环境变量。
4. 超时统一输出明确诊断信息并返回非零退出码，交给现有 workflow fail closed。

## 影响模块

- `scripts/run-pipeline-team-agent.sh`
- `tests/test_agent_pipeline_automation.py`
- `scripts/agent_pipeline_regression.py`

## 设计细节

### 1. 环境变量

新增：

- `AGENT_LEAD_STAGE_TIMEOUT_SECONDS`
- `AGENT_TESTER_STAGE_TIMEOUT_SECONDS`
- `AGENT_DEVELOPER_STAGE_TIMEOUT_SECONDS`

默认值：

- lead: `1200`
- tester: `1800`
- developer: `2400`

### 2. 参数校验

复用统一的正整数校验函数，而不是分别手写判断。

### 3. 执行包装器

新增 `run_stage_with_timeout()`：

- 使用 `timeout --signal=TERM --kill-after=10s "${timeout_seconds}s"`
- 保留 stdout/stderr 文件输出
- 若退出码为 `124` 或 `137`，输出明确超时消息
- 其余非零退出码保持现有失败语义

### 4. 兼容性

不改变：

- 模型固定配置
- `using-superpowers` 要求
- `--agent build`
- `--format json`
- WSL bridge
- preflight-only 路径
- tester branch restore / runtime cleanup 行为

## 风险评估

低风险，原因：

1. 仅影响 pipeline runner。
2. 不改变业务代码。
3. 保持原有命令结构，只增加外层 timeout。

潜在风险：

1. timeout 默认值过短会误杀真实长任务。
2. timeout 默认值过长则 fail closed 不够及时。

本次采用保守中间值，并允许通过环境变量覆盖。

## 测试策略

1. `bash -n scripts/run-pipeline-team-agent.sh`
2. `pytest tests/test_agent_pipeline_automation.py`
3. `scripts/agent_pipeline_regression.py --strict`
4. `ruff` / `py_compile` / `git diff --check`

