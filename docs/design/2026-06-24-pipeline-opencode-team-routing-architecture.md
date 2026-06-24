# GitHub Pipeline OpenCode 团队路由改造架构

## 架构摘要

本次使用“GitHub workflow -> Windows 桥接 runner -> WSL 统一 Team runner”
的固定调用链替代可任意替换的 Team Agent command。模型、effort/variant、
workflow 和 superpowers 要求写在受版本控制的 runner 中，并由自动化测试
验证，配置缺失时 fail closed。

现有 stage ID、label 和 gate key 保持不变。`claude_lead_plan` 等名称仅作为
兼容协议标识，实际角色由统一 Team runner 决定。

## 模块计划

| 模块 | 变更 |
|---|---|
| `scripts/run-pipeline-team-agent.sh` | 新增统一 Team Agent 路由、固定模型、插件预检、执行元数据 |
| `scripts/run-team-stage.ps1` | 新增 Windows self-hosted runner 到 WSL 的桥接 |
| `.github/workflows/agent-stage-runner.yml` | Team stages 直接调用仓库内 runner |
| `.github/workflows/agent-issue-bootstrap.yml` | bootstrap team plan 改由 OpenCode Lead 执行 |
| `src/product_app/agent_pipeline_automation.py` | 新 state 角色和 handoff 文案改造 |
| `tests/test_agent_pipeline_automation.py` | 固定路由、参数和兼容性测试 |
| Pipeline/process 文档 | 更新角色拓扑和本地运行说明 |

## 技术决策

### 1. 保留 stage ID，替换实际角色

保留：

```text
claude_lead_plan
claude_developer
claude_tester
claude_lead_review
```

映射为：

```text
claude_lead_plan   -> OpenCode GLM 5.2 Team Leader
claude_developer  -> Claude Code ultracode-xhigh Developer
claude_tester     -> OpenCode DeepSeek V4 Pro max Test Engineer
claude_lead_review-> OpenCode GLM 5.2 Team Leader
```

这样不会使历史 state、handoff 路径、GitHub labels 和 gate 文件失效。

### 2. 固定参数而不是环境变量默认值

统一 runner 内使用只读常量：

```text
Lead model:       opencode-go/glm-5.2
Tester model:     opencode-go/deepseek-v4-pro
Tester variant:   max
Developer model:  ultracode-xhigh
Developer effort: xhigh
```

不提供环境变量覆盖这些值，避免 GitHub repository variable 将角色悄悄改回
其他模型。

### 3. superpowers fail-closed 预检

OpenCode 执行前运行 `opencode debug skill`，必须发现
`using-superpowers`。Claude Code 执行前运行 `claude plugin list`，必须发现
已启用的 `superpowers` 与 `feature-dev` 插件。

预检失败直接退出 2，不调用模型，不生成正式报告。

### 4. Developer workflow 约束

Claude Developer prompt 以 `/feature-dev` 开始，并追加系统约束：

- 首先加载 `superpowers:using-superpowers`；
- 行为变化遵循 `test-driven-development`；
- 完成声明前使用 `verification-before-completion`；
- 不自动 commit、push、merge；
- 不修改未获架构授权的受限模块。

Claude CLI 同时固定 `--model ultracode-xhigh --effort xhigh`。

### 5. Test Engineer 约束

OpenCode Tester prompt 要求：

- 使用 `using-superpowers`；
- 使用 `verification-before-completion`；
- 失败排查使用 `systematic-debugging`；
- 从被测 commit 创建临时测试分支；
- 回到原分支后只写测试报告；
- 不修改原分支业务代码。

CLI 固定 `--variant max`。

### 6. 执行证据

runner 将 stdout/stderr 和元数据写入 `.agent/tmp/`。元数据只用于 Actions
诊断，不作为 gate 的唯一真相；阶段报告和现有 deterministic gate 仍是放行
依据。

## 数据流

```text
GitHub label / workflow_dispatch
  -> agent-stage-runner.yml
  -> scripts/run-team-stage.ps1
  -> WSL scripts/run-pipeline-team-agent.sh
  -> role preflight
  -> fixed CLI/model/effort/skill execution
  -> stage report + .agent/tmp execution evidence
  -> existing check-gates
  -> existing state sync and next-label routing
```

## 失败处理

以下任一条件返回非 0：

- stage 不属于支持列表；
- handoff 或 state 缺失；
- `opencode` 或 `claude` 命令缺失；
- 固定模型不在 OpenCode model catalog；
- superpowers/feature-dev 不可发现；
- Agent CLI 返回失败；
- 阶段 gate 未通过。

不允许自动换用低规格模型，不允许换回 Claude Tester，不允许用模板或 smoke
报告继续推进。

## 安全影响

本次只修改 Agent Pipeline、runner、测试和文档，不触碰交易敏感模块。Main
merge gate 仍保持人工审阅和手动合并。Team Agent 没有获得任何交易账户、
Broker 或真实订单能力。

## 测试策略

1. 静态验证 GitHub workflows 直接调用 `scripts/run-team-stage.ps1`。
2. 静态验证统一 runner 的固定模型、effort、variant、workflow 和 skill
   预检。
3. 验证 state 新角色映射。
4. 验证 handoff 明确新的实际角色和强制能力。
5. 解析 workflow YAML。
6. 运行 Pipeline automation、regression 和 strict regression。
7. 运行 shell syntax、Ruff、py_compile、`git diff --check`、restricted 和
   tracked runtime file 检查。

## 开发指导

1. 先增加失败测试，确认旧实现仍使用 Claude Lead/Tester。
2. 新增两个 runner，不修改历史临时产物。
3. 改造两个 GitHub workflows。
4. 更新 state/handoff 生成器。
5. 更新稳定流程文档和本地配置示例。
6. 运行聚焦回归后生成中文开发报告和验收报告。
