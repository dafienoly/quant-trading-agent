# Team Plan: V12 Real Codex PM and Architect Smoke

## Objective

验证 V12 Agent 开发流水线中 Codex PM（ChatGPT，角色 Codex A）和 Codex Architect（ChatGPT，角色 Codex B）的真实协作流程，确保 PM 输出需求文档 → Architect 输出架构设计 → Claude Lead 输出团队计划 → Claude Developer 分阶段开发 → Claude Tester 测试 → Codex Review → PM Acceptance 的完整链路可执行、可追溯、可门禁控制。

## Inputs Reviewed

| 输入 | 来源 |
|---|---|
| AGENTS.md | 仓库根级 Agent 硬约束 |
| docs/process/AGENT_DEVELOPMENT_PIPELINE.md | 阶段门禁定义、角色职责、标准交付物 |
| docs/process/BRANCH_WORKFLOW.md | 分支类型与并行开发流程 |
| docs/pipeline/AGENT_AUTOMATION_ARCHITECTURE.md | Issue 驱动自动化架构 |
| docs/pipeline/TEAM_PIPELINE_V2.md | Claude-first 团队流水线模式 |
| docs/pipeline/AUTO_MERGE_POLICY.md | 自动合并策略 |
| docs/pipeline/AGENT_HANDOFF_CONTRACT.md | Agent 交接契约 |
| docs/design/20260616-v12-real-codex-pm-architect-smoke-architecture.md | 架构设计文档 |
| .agent/handoff/claude_lead_plan.md | 当前交接上下文 |
| Pipeline State (issue #50) | 阶段状态、角色绑定、门禁配置 |

## Scope

1. 实现并验证 Codex PM → Codex Architect → Claude Lead → Claude Dev → Claude Test → Codex Review → PM Acceptance 全流水线
2. 在 epic 分支上按阶段推进，每个阶段产出标准交付物
3. 每个阶段设置明确的自测命令、Tester 检查项和发布标准
4. 阶段间通过 `.agent/handoff/` 机制路由，失败时回退到上游修复
5. 对流水线关键门禁点（架构门禁、Review 门禁、验收门禁）进行实测

## Non-Goals

1. 不修改任何交易模块代码（broker、execution、order、account、risk、miniQMT）
2. 不修改策略逻辑、风控策略、执行策略
3. 不向仓库写入任何 API 密钥或凭据
4. 不自动合并到 `main` 分支
5. 不修改 `.github/workflows/` 中的 CI/CD 门禁逻辑
6. 不修改生产流水线配置或部署脚本
7. 不引入新的第三方依赖

## Safety Constraints

1. **当前任务为 docs-only / pipeline-only**：所有变更仅限 `docs/`、`.agent/`、`.github/`（仅 workflow 编排文件，不含门禁逻辑）范围
2. **不得修改交易敏感模块**：broker、execution、order、account、risk、miniQMT、实盘、真实订单提交
3. **不得削弱 Merge Gate 或绕过人工审批**：`manual_approval_required_for` 列表中的门禁不可移除
4. **不得将 API 密钥、Token、凭据写入仓库**：所有密钥必须来自环境变量
5. **不得自动合并到 main**：Auto-merge 仅限非 epic 的 hotfix 分支，且必须满足 AUTO_MERGE_POLICY.md
6. **不得修改风控策略或执行策略**：RISK_POLICY.md 和 EXECUTION_POLICY.md 不可变
7. **每个阶段必须通过门禁后才能进入下一阶段**：一旦失败，退回上游修复后再提交
8. **Codex Review 最多重试 3 次**：超过则触发人工审批

## Proposed Phases

### Phase 1：流水线基础设施搭建

**Scope**
- 创建所有需要的目录结构（如存在则跳过）
- 配置 Pipeline State 初始状态
- 验证 `.agent/handoff/` 交接机制可工作
- 验证当前 epic 分支已包含 PM 需求文档和 Architect 架构设计

**Owner**：Claude B（Developer Agent）

**Branch**：`feat/v12-real-codex-pm-architect-smoke/pipeline-setup`

**Self-Test Commands**
```bash
# 验证目录存在
test -d docs/requirements
test -d docs/design
test -d docs/dev_plans
test -d docs/dev_reports
test -d docs/test_reports
test -d docs/review
test -d docs/acceptance
test -d .agent/handoff

# 验证必要文件存在
test -f docs/requirements/20260616-v12-real-codex-pm-architect-smoke-requirements.md
test -f docs/design/20260616-v12-real-codex-pm-architect-smoke-architecture.md

# 验证 Pipeline State 结构完整性
grep -q "stage_status" .agent/current_task.yaml 2>/dev/null || echo "WARN: no current_task.yaml"
```

**Tester Checks**
1. 所有标准交付物目录已创建且非空
2. `.agent/handoff/` 目录包含当前交接文件
3. Pipeline State 中 `stage_status` 各字段不为空
4. 分支基于 `epic/20260616-v12-real-codex-pm-architect-smoke` 创建

**Release Criteria**
- 所有 self-test 命令返回 0
- Tester 检查项全部通过（测试报告标记为 PASS）
- Pipeline State 确认 Phase 1 完成

**Phase 1 完成后路由**：→ Claude Lead → 确认 Phase 1 通过 → Claude B 继续 Phase 2

---

### Phase 2：团队计划文档（当前阶段）

**Scope**
- 生成 `docs/dev_plans/20260616-v12-real-codex-pm-architect-smoke-team-plan.md`
- 包含所有 Phase 定义、角色分配、自测命令、Tester 检查项
- 设置 Pipeline State 中 `team_plan` 为完成状态

**Owner**：Claude A（Lead Planning Agent）

**Branch**：`feat/v12-real-codex-pm-architect-smoke/team-plan`（或直接在 epic 上提交）

**Self-Test Commands**
```bash
# 验证 team plan 文件存在
test -f docs/dev_plans/20260616-v12-real-codex-pm-architect-smoke-team-plan.md

# 验证包含所有必需章节
grep -q "## Objective" docs/dev_plans/20260616-v12-real-codex-pm-architect-smoke-team-plan.md
grep -q "## Proposed Phases" docs/dev_plans/20260616-v12-real-codex-pm-architect-smoke-team-plan.md
grep -q "## Exit Criteria" docs/dev_plans/20260616-v12-real-codex-pm-architect-smoke-team-plan.md

# 验证每个 Phase 包含 scope/owner/branch/self-test/tester-checks/release-criteria
grep -q "**Scope**" docs/dev_plans/20260616-v12-real-codex-pm-architect-smoke-team-plan.md
grep -q "**Owner**" docs/dev_plans/20260616-v12-real-codex-pm-architect-smoke-team-plan.md
grep -q "**Tester Checks**" docs/dev_plans/20260616-v12-real-codex-pm-architect-smoke-team-plan.md
```

**Tester Checks**
1. 文件包含 Objective/Inputs/Scope/Non-Goals/Safety/Phases/Assignments/Validation/Exit 全部章节
2. 每个 Phase 都明确定义了 owner 和 branch 名称
3. Safety Constraints 完整嵌入，未遗漏 6 条硬约束
4. Pipeline State 中 `current_phase` 与 plan 一致

**Release Criteria**
- 文件格式有效、章节完整
- Safety Constraints 全部列出且无遗漏
- 通过 Claude Lead 自审

**Phase 2 完成后路由**：→ Claude Lead → 确认 Phase 2 通过 → Claude B 继续 Phase 3

---

### Phase 3：Dev Report 流程验证

**Scope**
- 模拟 Developer Agent 工作：基于架构设计实现一个最小可验证的文档变更
- 生成 `docs/dev_reports/20260616-v12-real-codex-pm-architect-smoke-phase-3-dev-report.md`
- 开发报告中包含：实现说明、自测结果、风险说明
- 承诺遵守 AGENTS.md 中的 Hard Safety Invariants

**Owner**：Claude B（Developer Agent）

**Branch**：`feat/v12-real-codex-pm-architect-smoke/dev-phase-3`

**Self-Test Commands**
```bash
# 验证 dev report 文件存在
test -f docs/dev_reports/20260616-v12-real-codex-pm-architect-smoke-phase-3-dev-report.md

# 验证包含必须内容
grep -q "自测结果" docs/dev_reports/20260616-v12-real-codex-pm-architect-smoke-phase-3-dev-report.md
grep -q "风险说明" docs/dev_reports/20260616-v12-real-codex-pm-architect-smoke-phase-3-dev-report.md
grep -q "Hard Safety Invariants" docs/dev_reports/20260616-v12-real-codex-pm-architect-smoke-phase-3-dev-report.md

# 确认未修改受限模块
git diff --name-only epic/20260616-v12-real-codex-pm-architect-smoke..HEAD | grep -vE '^docs/|^.agent/' || echo "仅 docs/ 和 .agent/ 范围变更"
```

**Tester Checks**
1. Dev Report 包含完整的实现说明和自测记录
2. 变更范围仅限于 `docs/` 和 `.agent/`，未触及交易模块
3. 报告中声明了安全约束的遵守情况
4. 无真实交易相关变更

**Release Criteria**
- Self-test 全部通过
- 变更范围检查通过（无受限模块变更）
- Tester 验证通过

**Phase 3 完成后路由**：→ Claude Lead → 确认 Phase 3 通过 → Claude C 继续 Phase 4

---

### Phase 4：Test Report 流程验证

**Scope**
- 模拟 Test Engineer Agent 工作：对 Phase 3 的变更进行测试
- 生成 `docs/test_reports/20260616-v12-real-codex-pm-architect-smoke-phase-4-test-report.md`
- 测试报告包含：测试范围、用例清单、执行结果、Bug 清单（如适用）
- 验证 Tester 不会只测 happy path

**Owner**：Claude C（Test Engineer Agent）

**Branch**：`feat/v12-real-codex-pm-architect-smoke/test-phase-4`

**Self-Test Commands**
```bash
# 验证 test report 文件存在
test -f docs/test_reports/20260616-v12-real-codex-pm-architect-smoke-phase-4-test-report.md

# 验证包含关键节
grep -q "测试范围" docs/test_reports/20260616-v12-real-codex-pm-architect-smoke-phase-4-test-report.md
grep -q "测试用例" docs/test_reports/20260616-v12-real-codex-pm-architect-smoke-phase-4-test-report.md
grep -q "执行结果" docs/test_reports/20260616-v12-real-codex-pm-architect-smoke-phase-4-test-report.md

# 验证包含非 happy path 用例
grep -q "边界" docs/test_reports/20260616-v12-real-codex-pm-architect-smoke-phase-4-test-report.md || grep -q "异常" docs/test_reports/20260616-v12-real-codex-pm-architect-smoke-phase-4-test-report.md || grep -q "故障" docs/test_reports/20260616-v12-real-codex-pm-architect-smoke-phase-4-test-report.md
```

**Tester Checks**
1. 测试报告包含至少一个非 happy path 测试用例
2. Bug 清单格式正确（如无 Bug，需明确声明）
3. 测试范围覆盖了 Phase 3 的全部变更
4. 报告中包含 TDD 回执说明（测试先行验证）

**Release Criteria**
- Self-test 全部通过
- 测试范围完整
- 至少覆盖了 edge case / boundary case

**Phase 4 完成后路由**：→ Claude Lead → 确认 Phase 4 通过 → 进入 Codex Review 阶段

---

### Phase 5：Codex Review 流程验证

**Scope**
- 由 Codex B（Architect Reviewer）执行完整代码 Review
- 生成 `docs/review/20260616-v12-real-codex-pm-architect-smoke-codex-review-r1.md`
- Review 确认架构一致性和系统安全边界
- 验证 Review 门禁机制：通过/失败/退回修复

**Owner**：Codex B（ChatGPT，Architect Reviewer 角色）

**Branch**：在 epic 上创建 Review 标签/备注，如需修复则从 `fix/v12-real-codex-pm-architect-smoke/review-issues` 修复

**Self-Test Commands**
```bash
# 验证 review 文件存在
test -f docs/review/20260616-v12-real-codex-pm-architect-smoke-codex-review-r1.md

# 验证包含 Review 结论
grep -q "Review 结论" docs/review/20260616-v12-real-codex-pm-architect-smoke-codex-review-r1.md || grep -q "结论" docs/review/20260616-v12-real-codex-pm-architect-smoke-codex-review-r1.md

# 如结果为 FAIL，检查是否触发回退
grep -q "FAIL" docs/review/20260616-v12-real-codex-pm-architect-smoke-codex-review-r1.md && echo "需触发修复流程"
```

**Tester Checks**
1. Review 涵盖所有前一阶段交付物（dev report + test report）
2. Review 检查了安全约束遵守情况
3. Review 不只看测试通过就放行，包含架构一致性判断
4. 如果 Review 失败，必须有明确的退回路径说明

**Release Criteria**
- Codex Review 结论为 PASS，或
- Codex Review 失败但已触达修复流程且修复后再次 Review 通过
- 记录 Review 尝试次数（不超过 3 次上限）

**Phase 5 完成后路由**：→ Claude Lead → 确认 Phase 5 通过 → Codex A 继续 Phase 6

---

### Phase 6：PM Acceptance 流程验证

**Scope**
- 由 Codex A（PM Acceptance Agent）对照需求文档做功能性全量验收
- 生成 `docs/acceptance/20260616-v12-real-codex-pm-architect-smoke-acceptance.md`
- 验收不得用实现细节替代用户视角
- 确认所有需求点均已满足

**Owner**：Codex A（ChatGPT，PM Acceptance Agent 角色）

**Branch**：在 epic 上直接提交验收文档

**Self-Test Commands**
```bash
# 验证 acceptance 文件存在
test -f docs/acceptance/20260616-v12-real-codex-pm-architect-smoke-acceptance.md

# 验证对照需求文档
grep -q "需求" docs/acceptance/20260616-v12-real-codex-pm-architect-smoke-acceptance.md

# 验证验收结论
grep -q "验收结论" docs/acceptance/20260616-v12-real-codex-pm-architect-smoke-acceptance.md || grep -q "结果" docs/acceptance/20260616-v12-real-codex-pm-architect-smoke-acceptance.md
```

**Tester Checks**
1. 验收文档逐条对照需求文档，不遗漏任何功能点
2. 验收以用户视角评估，不引用内部实现细节
3. 如有未满足需求，明确标记为 blocker 并说明原因
4. 验收结论明确（PASS / FAIL / CONDITIONAL PASS）

**Release Criteria**
- 验收结论为 PASS
- 所有需求点均被覆盖
- 无 blocker 级别的未满足项

**Phase 6 完成后路由**：→ Claude Lead → 确认全流水线完成

---

### Phase 7：用户指南与流水线复盘

**Scope**
- 生成 `docs/user_guides/20260616-v12-real-codex-pm-architect-smoke-user-guide.md`
- 生成 `docs/postmortems/20260616-v12-real-codex-pm-architect-smoke-r3-failure.md`（如适用）
- 更新 `docs/log/` 中的开发日志
- 总结流水线执行情况、遇到的问题、优化建议
- 生成 `docs/review/20260616-v12-real-codex-pm-architect-smoke-claude-lead-review.md` 作为 Lead 总体评审

**Owner**：Claude A（Lead Planning Agent）

**Branch**：`feat/v12-real-codex-pm-architect-smoke/wrap-up`

**Self-Test Commands**
```bash
# 验证 user guide 存在
test -f docs/user_guides/20260616-v12-real-codex-pm-architect-smoke-user-guide.md

# 验证 claude lead review 存在
test -f docs/review/20260616-v12-real-codex-pm-architect-smoke-claude-lead-review.md

# 验证日志已更新
grep -q "v12-real-codex-pm-architect-smoke" docs/log/development-log.md 2>/dev/null || echo "WARN: 日志未更新"

# 确认最终状态
git status
```

**Tester Checks**
1. 用户指南对后续 Agent 具有可操作性
2. 复盘文档诚实记录失败和优化建议
3. Lead Review 从全局视角评估流水线效果
4. 所有交付物完整且可追溯

**Release Criteria**
- Self-test 全部通过
- 所有文档式交付物完整
- Claude Lead 确认流水线执行完毕

**Phase 7 完成后路由**：→ Claude Lead → 确认所有 Phase 完成 → 标记 `all_phases_tested = true`

---

## Agent Assignments

| Phase | 角色 | Agent | 分支 |
|---|---|---|---|
| Phase 1 | Pipeline Setup | Claude B | `feat/v12-real-codex-pm-architect-smoke/pipeline-setup` |
| Phase 2 | Team Plan | Claude A | `feat/v12-real-codex-pm-architect-smoke/team-plan` |
| Phase 3 | Developer | Claude B | `feat/v12-real-codex-pm-architect-smoke/dev-phase-3` |
| Phase 4 | Tester | Claude C | `feat/v12-real-codex-pm-architect-smoke/test-phase-4` |
| Phase 5 | Codex Review | Codex B (ChatGPT) | epic 分支 + fix 分支 |
| Phase 6 | PM Acceptance | Codex A (ChatGPT) | epic 分支 |
| Phase 7 | Wrap-up / Lead Review | Claude A | `feat/v12-real-codex-pm-architect-smoke/wrap-up` |

## Team Routing Flow

```
Phase 1 (Claude B) → Claude Lead Gate → Phase 2 (Claude A)
→ Claude Lead Gate → Phase 3 (Claude B)
→ Claude Lead Gate → Phase 4 (Claude C)
→ Claude Lead Gate → Phase 5 (Codex B)
→ Claude Lead Gate → Phase 6 (Codex A)
→ Claude Lead Gate → Phase 7 (Claude A)
→ Claude Lead → all_phases_tested = true
```

失败回退路径：
- Phase 3/4 失败 → 退回 Phase 3 修复 → 重新测试
- Phase 5 Codex Review 失败 → 退回 Phase 3 修复 → 重新进入 Phase 4 → 再次 Phase 5（最多 3 次）
- Phase 6 验收失败 → 退回 Phase 1/2 重新审视需求

## Validation Plan

| 验证维度 | 方法 | 通过标准 |
|---|---|---|
| 交付物完整性 | 每个阶段检查文件是否存在、格式正确 | 所有交付物存在且符合标准 |
| 门禁机制 | 每个阶段 Gate 确认后才推进 | 无跳过门禁情况 |
| 安全约束 | git diff 检查变更范围 | 仅 docs/ 和 .agent/ 变更 |
| 角色边界 | 确认无越界行为（Developer 不改需求、Tester 不写代码） | 角色职责严格执行 |
| 交接机制 | `.agent/handoff/` 文件可路由 | 每阶段完成后能正确路由到下一角色 |
| 失败回退 | 模拟一次非关键失败，验证退回路径 | 回退后可正常修复并重新提交 |
| 完整性追溯 | 从需求到验收可逐条追溯 | 每条需求都有对应的验收结论 |

## Exit Criteria

1. ✅ 所有 7 个 Phase 均已完成并通过门禁
2. ✅ 每条硬安全约束在整个过程中未被违反
3. ✅ 每个角色的标准交付物均已生成且格式正确
4. ✅ Pipeline State 中 `all_phases_tested = true`
5. ✅ Acceptance 报告结论为 PASS
6. ✅ Claude Lead Review 报告确认无遗留问题
7. ✅ 流水线中任何失败路径均被正确触发和处理
8. ✅ 所有交付物均已提交到 `epic/20260616-v12-real-codex-pm-architect-smoke` 分支
