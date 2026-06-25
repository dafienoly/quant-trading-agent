# Pipeline 报告修订版与重试熔断功能说明

## 变更范围

- 修复 Phase 报告选择算法，按 `-rN` 数字修订号选择每个 Phase 的最新证据。
- 在 Phase Test 推进前恢复 Team Plan 总阶段数，缺失阶段标题时停止自动推进。
- 将 delivery gate 与 `current_phase` 绑定，阻止旧 gate 跨阶段复用。
- 增加 Phase Test 三次失败熔断和 `register-stage-failure` 命令。
- Stage Runner 推送后显式触发 PR validation，并精确持久化测试报告引用的 Feedback bug 文件。
- PR validation 支持传入 PR 编号的 `workflow_dispatch`。

## 测试命令

```bash
python -m pytest tests/test_agent_pipeline_automation.py tests/test_agent_pipeline_regression.py -q
python scripts/agent_pipeline_regression.py --strict
python -m ruff check src/product_app/agent_pipeline_automation.py scripts/agent_pipeline.py scripts/agent_pipeline_regression.py tests/test_agent_pipeline_automation.py
git diff --check
```

## 测试结果

- 聚焦测试：`95 passed`。
- 全量测试：`1004 passed, 6 skipped`。
- 严格 Pipeline 回归：`PASS`。
- Ruff：`All checks passed`。
- YAML 解析：两个修改的 workflow 均通过。
- PR #77 最新提交的隔离演练：门禁选择 `-r3` 的 `PASS`，恢复 `total_phases=5`，并确定性推进到 `current_phase=2`、`next_stage=claude_developer`。

## 安全确认

- 未修改交易敏感模块。
- 未新增自动合并 main。
- 未跟踪 `.agent/tmp/**` 或 `.agent/reports/**`。
- 阶段元数据无法恢复、重试次数耗尽或交付证据失配时均 fail closed。

## 最终结论

实现完成，本地、PR #77 隔离迁移演练和 Draft PR #79 远端轻量验证均通过，可进入人工审阅。
