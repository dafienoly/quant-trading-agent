# Pipeline 交付证据与失败路由 Hotfix 架构

## 架构摘要

保留现有 GitHub label 和 `claude_*` 兼容 stage ID，在确定性 Python gate、
Stage Runner 路由和 OpenCode runtime 三层修复。Agent 的自然语言声明不再直接产生
阶段通过；通过必须由仓库 diff、报告结论、feature identity 和 phase metadata 共同证明。

## 模块方案

1. `src/product_app/agent_pipeline_automation.py`
   - 解析正式报告最终结论。
   - 验证 Developer 实际 diff 与报告声称路径。
   - 校验 gate `feature_id`。
   - 从 Team Plan 解析 `total_phases`，记录 `completed_phases`。
2. `scripts/agent_pipeline.py`
   - 新增 `validate-stage-delivery` 和 `advance-phase` 命令。
   - `check-gates` 写入 `decision` 与 `route_back_to`。
3. `.github/workflows/agent-stage-runner.yml`
   - gate 失败时仍提交诊断证据和 feedback。
   - 依据 gate 结果退回阶段，禁止无条件升级。
   - 中间 phase 通过后确定性推进下一 phase。
4. `scripts/run-pipeline-team-agent.sh`
   - Developer 改为 OpenCode DeepSeek V4 Flash `max`。
   - Lead、Developer、Tester 都通过 OpenCode build Agent 执行正式阶段。

## 技术决策

- Developer 交付证据使用本阶段未提交 `git status`，因为 Stage Runner 在 Agent 返回后、
  提交前执行 gate，可准确区分本次 Agent 产出和已有分支历史。
- `phase_dev_delivery_gate.json` 独立于报告 gate，后续阶段仍可复核开发证据。
- 报告结论仅从“最终结论/Final Result/Decision”等明确区块提取，避免正文中提及
  `REJECTED` 导致误判。
- 同一 phase 保留多轮报告时只验证最新一轮，历史拒绝报告继续保留审计价值。
- 失败路由完成后工作流返回非零，区分“编排成功地发现失败”和“业务阶段通过”。

## 安全影响

本 Hotfix 只修改开发流水线、报告 gate 和文档，不接触任何交易敏感模块。OpenCode
build Agent 权限与现有 Tester 一致，但 prompt 和 workflow 继续禁止提交、推送、合并、
读取凭据、真实交易及绕过安全边界。

## 开发指导

- 保留 `claude_developer` 等兼容 stage ID，避免同时迁移 Issue、label 和历史状态。
- 所有新判断必须有失败路径测试。
- Stage Runner 必须先提交报告和 gate，再路由回退。
- 不允许通过删除历史拒绝报告制造通过；应使用同 phase 最新报告覆盖结论。
- 合并前执行 OpenCode Developer runtime preflight，并保留 artifact 作为远端证据。
