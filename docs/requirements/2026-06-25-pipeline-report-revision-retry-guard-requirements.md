# Pipeline 报告修订版与重试熔断修复需求

## 用户目标

修复 PR #77 中测试报告已改为 `PASS` 但门禁仍读取旧 `REJECTED` 报告、阶段数丢失后错误进入 Team Lead Review、以及测试失败后 Developer 与 Tester 无限循环的问题。

## 功能需求

1. 同一 Phase 存在基础报告和 `-rN` 修订报告时，门禁必须按数字修订号选择最新报告。
2. Phase Test 通过前必须从 Team Plan 恢复总阶段数；无法解析阶段标题时必须 fail closed。
3. 旧版 delivery gate 不得跨 Phase 复用；当前 Phase 已被测试拒绝时必须要求新的实质性交付证据。
4. Phase Test 连续失败达到三次后停止自动回流，转入人工审批。
5. Stage Runner 推送后必须显式触发 PR 轻量验证，避免机器人推送只产生 `action_required` 空运行。
6. 测试报告引用的 `feedback/bugs/open/BUG_*.md/.json` 必须精确持久化，不得笼统提交整个 `feedback/`。

## 验收标准

- 基础报告为 `REJECTED`、`-r2` 为 `REJECTED`、`-r3` 为 `PASS` 时 Phase Test gate 通过。
- 旧状态缺少 `total_phases` 时，可从五阶段 Team Plan 恢复并进入 Phase 2。
- Team Plan 无阶段标题时，不得进入 Lead Review。
- 第三次 Phase Test 失败后不再自动调度 Developer。
- `workflow_dispatch` 可按 PR 编号运行轻量验证并更新对应 PR 的 Dashboard 说明。
- 严格 Pipeline 回归、聚焦测试、Ruff 和 `git diff --check` 全部通过。

## 安全约束

- 不触碰交易敏感模块。
- 不自动合并 main。
- 不提交 `.agent/tmp/**` 或 `.agent/reports/**`。
- 所有门禁异常默认阻断，不允许 fallback 伪装为正式成功。
