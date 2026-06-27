# R0.3 Agent Runtime Abstraction 需求

## 背景

R0.1 已完成 Roadmap canonical 入口收敛，R0.2 已完成 AgentOps Control Tower 第一阶段只读观测。R0.3 需要把 Agent 执行来源抽象为统一 runtime profile，让不同 stage 的执行模式能被审计，而不是散落在 workflow、PowerShell、Bash 和环境变量里。

当前项目存在多类执行来源：

```text
Codex stages
OpenCode team stages
mock / smoke 命令
dry-run workflow 输入
strict flags
legacy claude_* stage name
```

如果没有统一 runtime contract，后续 AgentOps 页面和 pipeline gate 很难回答：当前 stage 到底是 real、mock、dry-run、disabled 还是 unknown。

## 目标

1. 新增 `src/product_app/agent_runtime/` 只读 runtime abstraction 模块。
2. 定义 `AgentRuntimeProfile`、`RuntimeMode`、`RuntimeProvider` 等契约。
3. 新增 resolver：根据 stage、环境变量和 dry-run 输入解析 runtime profile。
4. profile 不暴露命令原文和 secret，只输出变量名、配置状态和 hash fingerprint。
5. 新增 CLI：`scripts/agent_runtime_profile.py`。
6. 新增测试覆盖 real、mock、dry-run、disabled、unknown、strict、fallback command 和 OpenCode team stage。

## 非目标

1. 不实际调用 Agent。
2. 不执行任何 runtime command。
3. 不改 GitHub Actions 编排。
4. 不新增产品写接口。
5. 不修改行情、策略、风控、执行、账户、券商接入等业务模块。

## API 契约

本次不新增 HTTP API。后续 AgentOps 可以读取 runtime resolver 输出再接入 `/product/agentops/**`。

## 后端模块

```text
src/product_app/agent_runtime/__init__.py
src/product_app/agent_runtime/contracts.py
src/product_app/agent_runtime/resolver.py
scripts/agent_runtime_profile.py
```

## 数据需求

输入只来自：

```text
stage id
environment variable names and configured / missing status
dry_run flag
```

不读取 secret 原值，不输出 command 原文。

## 测试要求

测试必须覆盖：

```text
real codex profile
disabled codex profile
strict blocking
mock command detection
dry-run override
fallback command variable
OpenCode team stage
unknown stage
CLI JSON output
```

## 验收标准

1. 轻量验证 CI 通过。
2. runtime profile 不泄露 command 原文或 secret。
3. resolver 不执行命令。
4. 中文 reports 齐备。
5. 不触碰 restricted runtime business modules。

## 安全边界

R0.3 只是 runtime contract 和 resolver，不是执行器。任何后续执行仍必须由现有 workflow / runner / stage gate 控制。