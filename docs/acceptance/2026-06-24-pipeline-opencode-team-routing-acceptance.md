# GitHub Pipeline OpenCode 团队路由验收报告

## 变更范围

本次将原 Claude A/B/C 团队执行拓扑改为：

- OpenCode GLM 5.2 Team Leader；
- Claude Code ultracode-xhigh Developer/BugFix；
- OpenCode DeepSeek V4 Pro max Test Engineer。

旧 `claude_*` stage ID 和 labels 继续兼容，但不再决定实际执行者。模型、
effort/variant、workflow 和 superpowers 由仓库内 runner 固定。

## 测试命令

```bash
./.venv/bin/python -m pytest \
  tests/test_agent_pipeline_automation.py \
  tests/test_agent_pipeline_regression.py \
  -q --basetemp=runtime/pytest-tmp-pipeline-opencode-final-focused

./.venv/bin/python scripts/agent_pipeline_regression.py --strict

./.venv/bin/python -m pytest tests -q --tb=short \
  --basetemp=runtime/pytest-tmp-pipeline-opencode-full
```

## 测试结果

- 聚焦测试：`79 passed in 3.15s`。
- Pipeline 严格回归：`PASS`。
- 全量测试：`888 passed, 6 skipped, 2 warnings in 60.25s`。
- 指定 OpenCode 模型均能从本机 catalog 发现。
- OpenCode `using-superpowers`、Claude `feature-dev` 和
  `superpowers` 均能发现。
- 未运行真实 GitHub self-hosted Team stage，端到端运行证据留待 PR CI。

## 安全确认

- 不触碰交易敏感模块。
- 不增加真实交易或自动下单能力。
- 不允许 LLM 绕过确定性交易安全边界。
- 不使用 mock/fallback 冒充正式 stage。
- CLI、模型或插件缺失时 fail closed。
- main 不自动合并，PR 必须人工审阅。
- `.agent/tmp/**` 与 `.agent/reports/**` 不提交。
- 用户已有的 `feedback/index.json` 修改未纳入本次功能范围。

## 验收说明

| 验收项 | 结果 |
|---|---|
| OpenCode GLM 5.2 担任 Team Leader | 通过 |
| Claude Code ultracode-xhigh 担任 Developer | 通过 |
| Developer 强制 xhigh、feature-dev、superpowers | 通过 |
| OpenCode DeepSeek V4 Pro 担任 Test Engineer | 通过 |
| Tester 强制 max 和 superpowers | 通过 |
| 旧 stage/label 兼容 | 通过 |
| 模型/插件缺失 fail closed | 通过 |
| 不自动合并 main | 通过 |
| Windows self-hosted 实际 stage | 待 PR 运行验证 |

## 最终结论

`ACCEPTED_WITH_NOTES`。功能实现和本地验收通过，可以创建 Draft PR 并运行
self-hosted GitHub Actions。取得真实 Team stage 成功证据并完成人工审阅前，
不得合并 main。
