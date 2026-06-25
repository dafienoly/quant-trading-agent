# Pipeline 事务控制器 Hotfix 功能说明

## 变更范围

- Stage Runner 改为仅支持显式 `workflow_dispatch`，移除 label 自动触发。
- 同一 PR 使用统一并发键串行执行，并在 Agent 启动前校验阶段租约。
- 新增组合 transition gate，Developer 报告门禁与真实交付门禁必须同时通过。
- 新增 transition commit，显式更新 PM、架构、Team Plan、开发、评审和验收状态。
- Bootstrap 为 PR 创建前的三个阶段提交确定性状态迁移。
- Tester 驳回按预算返回 Developer，Developer 自身交付失败停止自动自循环。
- `feedback/index.json` 改为不跟踪的运行时索引，Tester 校验前防御性清理。
- PR 报告治理区分 Pipeline 中间阶段与最终验收阶段。
- 支持 team plan 明确声明的纯文档回归阶段。

## 测试命令

```bash
../../../.venv/bin/python -m pytest tests/test_agent_pipeline_automation.py tests/test_validate_pr_reports.py tests/test_agent_pipeline_regression.py -q --basetemp=runtime/pytest-tmp-pipeline-controller-all
../../../.venv/bin/python scripts/agent_pipeline_regression.py --strict
../../../.venv/bin/python -m ruff check src/product_app/agent_pipeline_automation.py scripts/agent_pipeline.py scripts/validate_pr_reports.py scripts/agent_pipeline_regression.py tests/test_agent_pipeline_automation.py tests/test_agent_pipeline_regression.py tests/test_validate_pr_reports.py
git diff --check
```

## 测试结果

聚焦测试 `126 passed`；全量测试 `1016 passed, 6 skipped`；严格 Pipeline 回归状态为通过，严重失败与警告均为 0；Ruff、Python 编译、YAML 解析与 diff 检查均通过。使用新报告治理脚本验证 PR #77 当前真实分支，5 份阶段开发报告通过且无 issue。

## 安全确认

本次只修改 GitHub Agent Pipeline、报告治理、测试与运行时反馈索引。不修改交易、风控、执行、行情、策略、股票池或 Broker 模块；不启用真实交易；不自动合并 main。

## 最终结论

PASS。修复已从单次 Action 补丁提升为可验证的事务化控制面，待远端 Draft PR CI 与 PR #77 真实恢复演练确认。
