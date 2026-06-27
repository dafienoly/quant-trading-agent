# R0.1 Roadmap Canonicalization 需求

## 背景

主干中 `AGENTS.md` 要求 Agent 优先读取 `docs/roadmap/MASTER_ROADMAP.md`，但该文件缺失；同时历史详细路线保存在 `docs/roadmap/MASTER_ROADMAP_AGENT_EXECUTABLE.md`。这会导致后续 Agent 在执行 V16/V17 任务时继续读取不同入口，增加版本漂移风险。

## 用户目标

用户希望在继续开发看盘、因子、回测等业务功能前，先把大型软件的工程底座收敛：

1. GitHub pipeline；
2. Agent 抽象层；
3. Bug 自动修复；
4. 日志与审计；
5. 成熟架构；
6. 每次功能开发后的完整文档与用户说明。

## 目标

1. 新增 canonical roadmap 入口：`docs/roadmap/MASTER_ROADMAP.md`。
2. 保留历史详细路线文件，避免破坏已有引用。
3. 新增 `docs/roadmap/README.md` 说明优先级与旧路线冲突处理规则。
4. 明确 R0 平台优先规则。
5. 增加静态测试，确保 canonical 入口和核心约束存在。

## 非目标

1. 不实现 V16.3 / V16.4 业务功能。
2. 不重构 Market Data Relay 代码。
3. 不修改业务执行、账户、风控、券商接入等 restricted modules。
4. 不改变主干人工合并策略。

## 数据需求

本任务只读取和改写仓库文档，不读取外部行情或账户数据。

## 后端模块

无后端运行时代码变更。

## API 契约

无 API 变更。

## 前端要求

无前端运行时代码变更。Roadmap 仍明确 Streamlit 是当前有效产品入口。

## Artifact 输出

新增或更新以下文档：

```text
docs/roadmap/MASTER_ROADMAP.md
docs/roadmap/README.md
docs/requirements/2026-06-27-r0-1-roadmap-canonicalization-requirements.md
docs/design/2026-06-27-r0-1-roadmap-canonicalization-architecture.md
docs/dev_reports/2026-06-27-r0-1-roadmap-canonicalization-dev-report.md
docs/test_reports/2026-06-27-r0-1-roadmap-canonicalization-test-report.md
docs/acceptance/2026-06-27-r0-1-roadmap-canonicalization-acceptance.md
```

新增静态测试：

```text
tests/test_roadmap_canonicalization.py
```

## Agent 权限边界

Agent 只能改 Roadmap、报告和静态测试，不能扩展执行能力，不能绕过 pipeline，不能把历史 roadmap 当成第二主线。

## 测试要求

1. 验证 canonical 文件存在。
2. 验证 compatibility 文件存在。
3. 验证 Roadmap README 存在并说明优先级。
4. 验证 canonical 文件包含 Streamlit、`/product/**`、V16/V17、R0、旧路线冲突处理等核心规则。
5. 验证变更未触碰 restricted modules。

## 验收标准

1. `docs/roadmap/MASTER_ROADMAP.md` 可被 Agent 作为第一入口读取。
2. `docs/roadmap/README.md` 明确 Roadmap 优先级。
3. 历史详细 roadmap 未被删除。
4. 中文 requirements / design / dev report / test report / acceptance 齐备。
5. 静态测试覆盖核心约束。
6. PR 不自动合并 main。

## 安全边界

本任务仅限文档和静态测试，不允许引入任何运行时交易或执行能力。