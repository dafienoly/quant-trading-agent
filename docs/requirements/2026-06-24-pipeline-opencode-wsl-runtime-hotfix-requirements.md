# Pipeline OpenCode WSL Runtime Hotfix 需求

## 背景

PR #73 合并前的真实 GitHub Actions 运行显示：

```text
claude_developer: success
claude_tester: failure
Required command is unavailable: opencode
```

Windows self-hosted runner 使用 `wsl.exe -- bash -c` 启动非登录 shell，
没有加载用户 CLI PATH，导致安装在 `~/.opencode/bin` 的 OpenCode 不可见。
同时，合并后的 OpenCode runner 使用了无效的
`--permission-mode allow` 和高风险的 `--dangerously-skip-permissions`。
Issue 模板仍描述旧 Claude A/B/C 角色及已废止的自动合并行为。

## 目标

1. Windows 到 WSL 的桥接使用登录 shell，并显式补齐受支持的用户 CLI
   目录。
2. Team runner 在调用 OpenCode/Claude 前输出可诊断但不泄露凭据的运行时
   信息。
3. OpenCode Lead/Tester 不使用无效参数或危险权限跳过。
4. 新增 Runtime Preflight，真实验证三个模型、认证、effort/variant 和插件
   可用性，不修改仓库；在新 workflow 合并到默认分支前，现有 Stage Runner
   必须提供兼容入口以验证 PR 分支。
5. Issue 模板使用当前 OpenCode Lead、Claude Developer、OpenCode Tester
   角色，并明确 main 只允许人工合并。
6. 缺少 CLI、模型、插件、认证或预期探针输出时 fail closed。

## 功能需求

### R-001 WSL 登录环境

`scripts/run-team-stage.ps1` 必须：

- 使用 `bash -lc`；
- 在 WSL 命令中显式加入 `$HOME/.opencode/bin` 和 `$HOME/.local/bin`；
- 支持现有 `AGENT_WSL_DISTRO`；
- 保持相对仓库 runner 调用；
- 正确透传非零退出码。

### R-002 安全的 OpenCode 调用

`scripts/run-pipeline-team-agent.sh` 必须：

- 移除 `--permission-mode allow`；
- 移除 `--dangerously-skip-permissions`；
- 依赖 OpenCode 已解析的 `build` agent 权限策略；
- 保留模型、variant 和 superpowers 固定契约。

### R-003 Runtime Preflight

新增 preflight 模式和 GitHub workflow：

- Lead：真实调用 `opencode-go/glm-5.2`；
- Tester：真实调用 `opencode-go/deepseek-v4-pro --variant max`；
- Developer：真实调用 Claude `ultracode-xhigh --effort xhigh`；
- 探针禁止工具调用和仓库写入；
- 响应必须包含 `PIPELINE_RUNTIME_OK`；
- stdout、stderr 和 metadata 仅保存到 `.agent/tmp/**` 并上传 artifact；
- 任一角色失败则 workflow 失败。
- 现有 `agent-stage-runner.yml` 必须支持隔离的 `runtime_preflight` stage，
  且不得执行 handoff、gate、commit、label 或后续 stage dispatch。

### R-004 Issue 模板

Issue 模板必须：

- 使用当前三个 Team 角色名称；
- 不再声称 Claude A/B/C；
- 不再提供或声明 main 自动合并；
- 明确所有 gate 通过后仍需人工审阅和手动合并。

### R-005 回归门禁

自动化测试和 strict regression 必须检查：

- `bash -lc` 和显式 OpenCode PATH；
- 不存在危险权限跳过；
- Runtime Preflight workflow 存在且覆盖三个角色；
- Stage Runner 的兼容 preflight 不推进正式 Pipeline；
- Issue 模板角色与手动合并文案正确。

## 非目标

- 不修改 Codex PM/Architect/Review/Acceptance 的执行方式。
- 不修改 Pipeline stage ID、labels 或 gate key。
- 不修改交易、行情、策略、风控、执行、订单和账户模块。
- 不自动创建或合并 main PR。
- 不在仓库中保存模型服务凭据。

## 验收标准

1. 聚焦 Pipeline 测试通过。
2. strict regression 为 PASS。
3. 全量测试无失败。
4. Runtime Preflight 在 self-hosted runner 上三个角色全部成功。
5. Issue 模板创建的新 Issue 能自动带上
   `agent:pipeline`、`stage:pm-pending`。
6. restricted module check 无命中。
7. `.agent/tmp/**`、`.agent/reports/**` 无 tracked file。
8. PR 保持 Draft，不自动合并 main。

## 安全约束

- 不允许 mock、fallback 或 smoke 文档冒充正式阶段产物。
- Runtime Preflight 只能验证运行时，不得修改仓库或推进 stage。
- 不允许使用危险权限跳过。
- 不允许 LLM 直接执行交易或提交真实订单。
