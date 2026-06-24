# GitHub Pipeline OpenCode 团队路由改造需求

## 背景

现有 GitHub Issue/PR Agent Pipeline 使用 `Claude Code A/B/C` 表示团队
Leader、开发工程师和测试工程师，并通过可配置命令选择实际执行器。该方式
无法确定 GitHub workflow 最终使用了哪个模型、推理强度或技能插件，也可能
在配置缺失时回退到不符合当前团队分工的执行器。

本次改造将团队执行器固定为：

- Team Leader：OpenCode，模型 `opencode-go/glm-5.2`。
- Developer：Claude Code，模型 `ultracode-xhigh`，effort 为 `xhigh`。
- Test Engineer：OpenCode，模型 `opencode-go/deepseek-v4-pro`，variant 为
  `max`。

## 目标

1. GitHub workflow 使用仓库内受版本控制的 runner 启动团队 Agent。
2. Team Leader 固定由 OpenCode GLM 5.2 执行。
3. Test Engineer 固定由 OpenCode DeepSeek V4 Pro 执行，并强制
   `max` 推理等级。
4. Developer 和 BugFix Developer 固定由 Claude Code 执行，并强制
   `ultracode-xhigh`、`xhigh` effort、`feature-dev` workflow 和
   `superpowers`。
5. OpenCode Team Leader 和 Test Engineer 必须加载 `superpowers`；缺失时
   fail closed。
6. 保留现有 `claude_lead_plan`、`claude_developer`、`claude_tester`、
   `claude_lead_review` stage ID 与 GitHub label，避免破坏正在运行或历史
   Pipeline 的状态兼容性。
7. 所有执行器缺失、模型不可用、插件缺失、命令失败或阶段报告缺失时返回非
   0，不允许生成 mock、smoke 或 fallback 正式产物。

## 功能需求

### R-001 仓库内统一 Team runner

新增 Linux/WSL Team runner 和 Windows 到 WSL 的桥接 runner。GitHub
workflow 必须直接调用仓库内 runner，不再通过
`CLAUDE_LEAD_AGENT_COMMAND`、`CLAUDE_TESTER_AGENT_COMMAND` 等可替换命令
决定团队角色。

### R-002 OpenCode Team Leader

`claude_lead_plan`、`claude_lead_review` 和 `postmortem` 兼容 stage 必须：

- 使用 `opencode run`；
- 使用模型 `opencode-go/glm-5.2`；
- 使用 `build` agent；
- 在执行前确认 `superpowers` 的 `using-superpowers` skill 可发现；
- 在 handoff 中明确角色是 OpenCode Team Leader。

### R-003 Claude Code Developer

`claude_developer` 和 `bugfix` stage 必须：

- 使用 `claude --print`；
- 固定 `--model ultracode-xhigh`；
- 固定 `--effort xhigh`；
- 检查 `superpowers` 和 `feature-dev` 插件已启用；
- 在 prompt 中强制先使用 `superpowers:using-superpowers`；
- 通过 `/feature-dev` 启动开发 workflow；
- 不允许自动 commit、push、merge 或绕过 main 人工审阅。

### R-004 OpenCode Test Engineer

`claude_tester` 兼容 stage 必须：

- 使用 `opencode run`；
- 固定模型 `opencode-go/deepseek-v4-pro`；
- 固定 `--variant max`；
- 在执行前确认 `using-superpowers` skill 可发现；
- 强制使用 `verification-before-completion`，失败排查时使用
  `systematic-debugging`；
- 遵循临时测试分支纪律，不在原开发分支修改业务代码。

### R-005 角色状态与文档

新建 Pipeline state 的 `agent_roles` 必须表达：

- `opencode_lead`；
- `claude_developer`；
- `opencode_tester`。

流程文档、本地运行文档、命令示例和 handoff 必须同步更新。旧 stage ID
仅作为兼容标识，不再代表实际执行器。

### R-006 可诊断性

runner 必须在 `.agent/tmp/` 写入本地执行输出和执行元数据，至少记录：

- stage；
- provider；
- model；
- effort 或 variant；
- workflow；
- superpowers 是否为强制要求。

`.agent/tmp/**` 只能是临时运行文件，不得提交。

## 非目标

- 不修改 Codex PM、Codex Architect、Codex Reviewer、Codex Acceptance 的
  角色分工。
- 不修改交易、行情、策略、风控、订单或执行逻辑。
- 不引入 main 自动合并。
- 不在仓库保存 OpenCode、Claude Code 或模型服务凭据。
- 不重命名现有 stage labels 和 gate JSON key。

## 验收标准

1. 自动化测试能从 workflow 和 runner 静态验证三个角色的固定执行器。
2. Test Engineer runner 同时包含
   `opencode-go/deepseek-v4-pro`、`--variant max` 和 superpowers 预检。
3. Team Leader runner 包含 `opencode-go/glm-5.2` 和 superpowers 预检。
4. Developer runner 包含
   `--model ultracode-xhigh`、`--effort xhigh`、`/feature-dev`、
   `superpowers:using-superpowers`。
5. GitHub workflows 不再使用 Claude 作为 Team Leader 或 Test Engineer。
6. Handoff 和新建 state 正确展示 OpenCode Lead、Claude Developer、
   OpenCode Tester。
7. Pipeline 严格回归通过。
8. restricted module check 无命中。
9. `.agent/tmp/**`、`.agent/reports/**` 无 tracked file。
10. PR 保持人工审阅和手动合并。

## 安全约束

- 不允许任何 Agent 直接下单或修改交易安全边界。
- 不允许在 runner 使用 mock/fallback 冒充正式模型执行。
- 不允许为了无人值守而启用不受约束的 main 自动合并。
- Agent CLI 或所需插件不可用时必须 fail closed。
- 所有用户可见输出和新增文档默认使用中文。
