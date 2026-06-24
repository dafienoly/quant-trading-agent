# GitHub Pipeline OpenCode 团队路由功能说明

需求文档：`docs/requirements/2026-06-24-pipeline-opencode-team-routing-requirements.md`

架构文档：`docs/design/2026-06-24-pipeline-opencode-team-routing-architecture.md`

## 变更范围

1. 新增 `scripts/run-pipeline-team-agent.sh`，统一执行 Team stages：
   - Team Leader 固定使用 OpenCode `opencode-go/glm-5.2`。
   - Test Engineer 固定使用 OpenCode
     `opencode-go/deepseek-v4-pro --variant max`。
   - Developer/BugFix 固定使用 Claude Code
     `--model ultracode-xhigh --effort xhigh`。
2. 新增 `scripts/run-team-stage.ps1`，供 Windows self-hosted GitHub runner
   将当前 checkout 安全映射到 WSL。
3. Team runner 在正式执行前检查：
   - OpenCode 指定模型存在；
   - OpenCode 可发现 `using-superpowers`；
   - Claude Code 已启用 `superpowers` 与 `feature-dev`；
   - handoff、state 和当前 stage 合法。
4. Claude Developer 强制：
   - `/feature-dev` workflow；
   - `superpowers:using-superpowers`；
   - `test-driven-development`；
   - `verification-before-completion`；
   - `dontAsk` + 显式工具白名单，不使用危险权限跳过。
5. OpenCode Tester 强制：
   - `variant=max`；
   - `verification-before-completion`；
   - 失败时 `systematic-debugging`；
   - 临时测试分支纪律；
   - 原开发分支业务代码修改阻断。
6. `.github/workflows/agent-stage-runner.yml` 与
   `.github/workflows/agent-issue-bootstrap.yml` 改为直接调用仓库内 runner，
   不再允许 `CLAUDE_LEAD_AGENT_COMMAND` 或
   `CLAUDE_TESTER_AGENT_COMMAND` 替换实际执行者。
7. 保留 `claude_*` stage ID 和 labels 作为兼容协议，更新新建 state、
   handoff、流程文档和用户指南中的实际角色。
8. 修复 `sync_state_from_gates()` 中现存的重复不可达代码和未定义变量，
   恢复触碰模块 Ruff 通过。
9. 扩展严格回归，新增固定模型、effort、workflow、superpowers 和 Windows
   WSL bridge 检查。

本次未修改任何交易、行情、策略、风控、订单、账户、Broker 或真实执行模块。

## 功能映射

| 需求 | 实现 |
|---|---|
| R-001 仓库内统一 Team runner | `scripts/run-pipeline-team-agent.sh`、`scripts/run-team-stage.ps1` |
| R-002 OpenCode Team Leader | 固定 `opencode-go/glm-5.2` 与 superpowers 预检 |
| R-003 Claude Developer | 固定 `ultracode-xhigh`、`effort=xhigh`、feature-dev、superpowers |
| R-004 OpenCode Test Engineer | 固定 `deepseek-v4-pro`、`variant=max`、测试分支和验证技能 |
| R-005 角色状态与文档 | `agent_pipeline_automation.py`、Pipeline/process/user docs |
| R-006 可诊断性 | `.agent/tmp/<stage>.*` stdout/stderr/metadata |

## 测试命令

```bash
./.venv/bin/python -m pytest \
  tests/test_agent_pipeline_automation.py \
  tests/test_agent_pipeline_regression.py \
  -q --basetemp=runtime/pytest-tmp-pipeline-opencode-final-focused

./.venv/bin/python scripts/agent_pipeline_regression.py --strict

./.venv/bin/python -m pytest tests -q --tb=short \
  --basetemp=runtime/pytest-tmp-pipeline-opencode-full

./.venv/bin/python -m ruff check \
  src/product_app/agent_pipeline_automation.py \
  scripts/agent_pipeline_regression.py \
  tests/test_agent_pipeline_automation.py \
  tests/test_agent_pipeline_regression.py

./.venv/bin/python -m py_compile \
  src/product_app/agent_pipeline_automation.py \
  scripts/agent_pipeline.py \
  scripts/agent_pipeline_regression.py

bash -n scripts/run-pipeline-team-agent.sh
git diff --check
```

模型与插件预检：

```bash
opencode debug skill
opencode models
claude plugin list
```

## 测试结果

- Pipeline 聚焦测试：`79 passed in 3.15s`。
- Pipeline 严格回归：`PASS`，严重失败 `0`，警告 `0`。
- 全量测试：`888 passed, 6 skipped, 2 warnings in 60.25s`。
- Ruff：`All checks passed!`。
- `py_compile`：通过。
- GitHub workflow YAML 解析：通过。
- Bash 语法：通过。
- OpenCode skill 预检：发现 `using-superpowers`。
- OpenCode model 预检：发现 `opencode-go/glm-5.2` 和
  `opencode-go/deepseek-v4-pro`。
- Claude plugin 预检：发现 `feature-dev` 和 `superpowers`。
- 两项 warning 来自第三方依赖的弃用提示，不是本次变更失败。

未在当前开发工作区直接运行正式 Team stage，因为真实 stage 会调用模型并
修改当前分支。实际 Windows self-hosted runner 到 WSL 的端到端调用应由 PR
GitHub Actions 验证。

## 安全确认

- 未触碰任何 restricted trading module。
- 未启用真实交易、自动下单或 `LEVEL_3_AUTO`。
- 未绕过风控、股票池过滤或人工确认。
- 未新增 main 自动合并；现有 main merge gate 继续要求人工审阅和手动合并。
- 未提交凭据、Token、Cookie 或模型密钥。
- 未使用 `--dangerously-skip-permissions`。
- `.agent/tmp/**` 和 `.agent/reports/**` 仍为临时文件，不纳入提交。
- Tester 在原开发分支修改业务代码时 runner fail closed。

## 剩余风险

1. Windows PowerShell 到 WSL 的桥接只完成静态解析和本地脚本验证，仍需在
   self-hosted GitHub runner 上执行一次真实 stage。
2. `ultracode-xhigh` 是当前 Claude Code 代理环境使用的模型别名；代理侧若
   删除该别名，runner 会失败而不会自动回退。
3. OpenCode/Claude 插件升级可能改变 skill 名称；预检会 fail closed，需要
   运维同步 runner 与插件版本。

## 最终结论

开发实现完成，本地代码、严格回归和全量测试通过。结论：
`PASS_WITH_NOTES`。可进入 PR 上的 self-hosted runner 实际调用验收，不应
自动合并 main。
