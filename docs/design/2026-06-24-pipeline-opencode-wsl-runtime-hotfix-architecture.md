# Pipeline OpenCode WSL Runtime Hotfix 架构

## 架构摘要

修复采用三层防护：

1. PowerShell bridge 使用 WSL 登录 shell，并显式设置用户 CLI PATH。
2. Team runner 移除危险权限参数，增加只读 Runtime Preflight 模式。
3. 独立 GitHub workflow 在 PR 分支上真实探测三个模型和插件，不触发 stage
   状态迁移。

## 模块计划

| 文件 | 变更 |
|---|---|
| `scripts/run-team-stage.ps1` | `bash -lc`、显式 PATH、`-PreflightOnly` |
| `scripts/run-pipeline-team-agent.sh` | 安全权限、preflight 探针、metadata |
| `.github/workflows/agent-runtime-preflight.yml` | 三角色真实运行时探针与 artifact |
| `.github/ISSUE_TEMPLATE/agent_feature_request.yml` | 当前角色与人工合并文案 |
| `tests/test_agent_pipeline_automation.py` | runner、workflow、模板契约测试 |
| `scripts/agent_pipeline_regression.py` | strict runtime/模板检查 |
| Pipeline 文档 | 运维命令、preflight 和故障诊断 |

## 技术决策

### 1. 登录 shell 加显式 PATH

PowerShell 使用：

```text
wsl.exe ... bash -lc '<command>'
```

命令前置：

```bash
export PATH="$HOME/.opencode/bin:$HOME/.local/bin:$PATH"
```

登录 shell 负责加载用户配置，显式 PATH 为 OpenCode 默认安装目录提供确定性
保障。二者并用，避免 runner 服务进程与交互终端环境不同。

### 2. 不使用危险权限跳过

OpenCode 保留 `--agent build`，使用已解析的项目/用户 permission policy。
删除 CLI 不支持的 `--permission-mode allow` 和
`--dangerously-skip-permissions`。所需 superpowers 外部目录由 OpenCode
配置预检确认。

### 3. 真实但只读的探针

`--preflight-only` 不读取 handoff/state，不运行 gate，不修改 git 状态。

OpenCode 探针：

```text
opencode run --model <fixed> --variant <fixed> --agent build \
  "不要使用工具，只输出 PIPELINE_RUNTIME_OK"
```

Claude 探针：

```text
claude --print --model ultracode-xhigh --effort xhigh \
  --tools "" --no-session-persistence \
  "不要使用工具，只输出 PIPELINE_RUNTIME_OK"
```

探针输出不包含预期标记时返回 2。

### 4. 独立 Preflight workflow

该 workflow 仅支持 `workflow_dispatch`，可以选择 `all` 或单个角色。它：

- checkout 被指定的 ref；
- 调用仓库 PowerShell bridge；
- 上传 `.agent/tmp/runtime-preflight-*`；
- 不写 stage report、不提交、不打 label、不创建 PR。

### 5. 回归规则

strict regression 对运行时修复做静态 fail-closed 检查，真实模型/认证由
Runtime Preflight Actions 形成动态证据。两者缺一不可。

## 数据流

```text
workflow_dispatch
  -> agent-runtime-preflight.yml
  -> scripts/run-team-stage.ps1 -PreflightOnly
  -> wsl.exe bash -lc + explicit PATH
  -> run-pipeline-team-agent.sh <stage> --preflight-only
  -> CLI/plugin/model precheck
  -> no-tool model probe
  -> PIPELINE_RUNTIME_OK
  -> .agent/tmp metadata/log artifact
```

正式 Issue Pipeline 沿用同一 bridge 和 Team runner，因此 preflight 与正式
stage 共享 PATH、CLI 和模型解析逻辑。

## 失败处理

- OpenCode/Claude 命令不可见：fail closed。
- model catalog 不包含固定模型：fail closed。
- superpowers/feature-dev 不可见：fail closed。
- API 认证、额度、代理或模型调用失败：fail closed。
- 探针未返回 `PIPELINE_RUNTIME_OK`：fail closed。
- Preflight 不允许自动 fallback 到其他模型。

## 安全影响

本次仅修改 Pipeline runner、workflow、Issue 模板、测试和文档。Preflight
禁用 Claude 工具，并明确要求 OpenCode 不调用工具；不读取交易账户，不连接
Broker，不提交订单。Main merge 仍保持人工审阅和手动合并。

## 测试策略

1. 先写失败测试复现 `bash -c`、危险权限参数和旧 Issue 文案。
2. 运行聚焦测试确认失败。
3. 修复 bridge、runner、workflow 和模板。
4. 运行 Bash、PowerShell parser、YAML、Ruff、py_compile。
5. 运行 Pipeline 聚焦测试、strict regression、全量测试。
6. 发布 Draft PR 后在 PR 分支运行 Runtime Preflight，记录 Actions URL。
