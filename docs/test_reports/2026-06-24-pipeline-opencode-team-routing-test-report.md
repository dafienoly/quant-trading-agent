# GitHub Pipeline OpenCode 团队路由测试报告

需求文档：`docs/requirements/2026-06-24-pipeline-opencode-team-routing-requirements.md`

架构文档：`docs/design/2026-06-24-pipeline-opencode-team-routing-architecture.md`

开发报告：`docs/dev_reports/2026-06-24-pipeline-opencode-team-routing-dev-report.md`

## 测试环境

- Linux/WSL workspace
- OpenCode `1.17.9`
- Claude Code `2.1.177`
- 项目虚拟环境 `./.venv/bin/python`

## 测试范围

- GitHub bootstrap 和 stage runner 路由。
- OpenCode Lead 模型与 superpowers 契约。
- Claude Developer 模型、effort、workflow、superpowers 和权限白名单。
- OpenCode Tester 模型、max variant、superpowers 和原分支修改阻断。
- Pipeline state 与 handoff 角色映射。
- 严格回归、全量测试、YAML/shell/Python 静态检查。
- restricted module、runtime artifact 和 main merge 安全边界。

不包含真实模型 stage 对仓库的写操作，也不包含 Windows self-hosted runner
上的实际 GitHub Actions 调度。

## 需求覆盖矩阵

| 需求 | 证据 | 结果 |
|---|---|---|
| R-001 仓库内 runner | workflow 静态断言、Windows bridge 静态断言 | PASS |
| R-002 GLM 5.2 Lead | model catalog + runner 常量 + handoff 测试 | PASS |
| R-003 Claude Developer | model/effort/workflow/plugin/权限测试 | PASS |
| R-004 DeepSeek V4 Pro max Tester | model catalog + variant + handoff/guard 测试 | PASS |
| R-005 state/handoff/docs | automation tests 与文档检查 | PASS |
| R-006 `.agent/tmp` 诊断 | runner 静态检查、strict regression | PASS |

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

## 测试结果

- 聚焦测试：`79 passed in 3.15s`。
- 严格回归：`PASS`。
- 全量测试：`888 passed, 6 skipped, 2 warnings in 60.25s`。
- Ruff、`py_compile`、Bash syntax、workflow YAML、diff check 全部通过。
- 6 个 skip 为项目既有可选 E2E/浏览器条件，不是本次新增 skip。
- 2 个 warning 为 Starlette/httpx 与 py_mini_racer 第三方弃用提示。

## 缺陷列表

本轮发现并修复一项既有 S2 代码质量缺陷：

- `sync_state_from_gates()` 尾部存在重复不可达代码，并引用未定义
  `expected_label`，导致触碰文件 Ruff 失败。已删除重复块，相关状态同步测试
  和全量测试通过。

未发现新的 S0、S1 或 S2 未关闭缺陷。

## 安全确认

- Restricted module check 无命中。
- Team runner 不使用危险权限跳过。
- Tester 原分支业务代码修改被确定性阻断。
- main merge 仍需人工审阅与手动合并。
- 无真实交易能力变更，无 LLM 直接下单能力。
- 无 tracked `.agent/tmp/**` 或 `.agent/reports/**`。

## 剩余风险

- 需要在 PR 上触发 self-hosted GitHub Actions，验证 Windows PowerShell、
  WSL、OpenCode、Claude Code 和凭据环境的真实组合。
- 未执行真实模型写操作，因此无法在本地报告模型服务的延迟、配额或代理端
  alias 可用性。

## 最终结论

`PASS_WITH_NOTES`。代码和本地门禁满足需求；PR 合并前必须取得一次真实
self-hosted Team stage 或等价的人工运行证据。
