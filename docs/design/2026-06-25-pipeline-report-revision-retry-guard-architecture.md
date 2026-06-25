# Pipeline 报告修订版与重试熔断修复架构

## 架构摘要

修复保持现有文档驱动 Pipeline 边界：Python 状态机负责确定性决策，GitHub Actions 只负责执行、提交证据和调度下一阶段。任何无法确认的阶段元数据均停止自动推进。

## 模块计划

- `src/product_app/agent_pipeline_automation.py`：报告修订号解析、阶段元数据迁移、delivery gate Phase 绑定、失败重试计数。
- `scripts/agent_pipeline.py`：增加失败登记 CLI。
- `.github/workflows/agent-stage-runner.yml`：消费重试结果、精确提交缺陷证据、显式触发 PR validation。
- `.github/workflows/agent-pr-validation.yml`：支持带 PR 编号的手工调度。
- `scripts/agent_pipeline_regression.py` 与测试：固化新的工作流契约。

## 技术决策

1. 报告版本使用文件名末尾 `-rN.md` 的数字 `N` 排序；无后缀基础报告视为修订号 0。
2. 每次 Phase Test 通过前重新解析 Team Plan，兼容旧状态文件；无合法阶段标题时不采用默认值。
3. delivery gate 写入 `current_phase`；缺少该字段的旧 gate 仅允许在 Phase 1 兼容复用。
4. `phase_test_attempts` 按 Phase 计数，默认最多三次；达到上限后清空自动回流目标。
5. PR validation 使用显式 `workflow_dispatch`，并由 Stage Runner 传入 PR 编号和分支 ref。
6. Feedback 证据仅从本轮变更的测试报告中提取合法路径并 `git add -f`。

## 安全影响

本修复仅修改 Agent Pipeline、工作流和测试，不改变行情、策略、风控、订单或执行能力。新增逻辑均强化 fail-closed 和人工审批边界。

## 开发指导

- 必须覆盖 PR #77 的基础报告与 `-r3` 并存场景。
- 必须覆盖旧状态迁移、多阶段推进、无阶段标题阻断和第三次失败熔断。
- 不得通过删除旧测试报告解决版本选择问题。
- 不得恢复笼统的 `git add feedback`。
