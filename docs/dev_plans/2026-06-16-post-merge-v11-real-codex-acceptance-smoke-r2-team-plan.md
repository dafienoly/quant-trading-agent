# Team Plan: Post-merge V11 real Codex Acceptance R2

## Objective

对 V11 real Codex Acceptance 流水线进行 post-merge 冒烟验证（第二轮），确认自动化工件生成、阶段门禁流转、文档交付物完整性达到可重复执行状态。本轮聚焦“仅文档”变更，不涉及交易模块代码修改。

## Inputs Reviewed

| 文档 | 状态 |
|---|---|
| `docs/requirements/20260616-post-merge-v11-real-codex-acceptance-smoke-r2-requirements.md` | ✅ 已由 PM (Codex A) 产出 |
| `docs/design/20260616-post-merge-v11-real-codex-acceptance-smoke-r2-architecture.md` | ✅ 已由架构师 (Codex B) 产出 |
| `AGENTS.md` — 硬安全不变量与角色边界 | ✅ 已评审 |
| `docs/process/AGENT_DEVELOPMENT_PIPELINE.md` — 阶段门禁与标准流 | ✅ 已评审 |
| `docs/process/BRANCH_WORKFLOW.md` — 分支策略 | ✅ 已评审 |
| `docs/pipeline/AGENT_AUTOMATION_ARCHITECTURE.md` — 问题驱动自动化 | ✅ 已评审 |
| `docs/pipeline/TEAM_PIPELINE_V2.md` — Claude-first 团队流水线 | ✅ 已评审 |
| `docs/pipeline/AUTO_MERGE_POLICY.md` — 自动合并策略 | ✅ 已评审 |
| `docs/pipeline/AGENT_HANDOFF_CONTRACT.md` — Agent 交接契约 | ✅ 已评审 |
| `.agent/handoff/claude_lead_plan.md` — 当前交接内容 | ✅ 已评审 |

## Scope

1. 基于现有需求和架构文档，拆分为可执行的开发/测试阶段。
2. 每阶段由 Claude Code B（开发）和 Claude Code C（测试）依次执行。
3. 所有交付物仅限文档（`.md`），不修改 `.py`、`.ts`、`.go`、`.json`、`.yaml` 等代码或配置。
4. 完整走通：开发 → 测试 → Claude Lead Review → Codex Review → PM Acceptance → 合并。
5. 本轮产出包含失败回顾文档（postmortem），记录第一轮冒烟失败教训。

## Non-Goals

- 不修改任何 Broker、Execution、Order、Account、Risk、miniQMT 模块。
- 不修改交易策略或信号生成逻辑。
- 不修改 CI/CD 门禁规则或自动合并策略。
- 不引入新的安全凭证或密钥。
- 不修改实际交易环境配置。
- 不修改 `LEVEL_3_AUTO` 或任何交易权限级别。
- 不修改 `docs/policy/` 下的风控或执行策略。

## Safety Constraints

1. 当前任务为 **docs-only / pipeline-only**，任何超出文档变更范围的操作必须退回。
2. **不得修改交易敏感模块**：broker、execution、order、account、risk、miniQMT、live trading、real order submission。
3. **不得削弱 Merge Gate** 或绕过人工审批。
4. **不得将 API 密钥、令牌或机密写入仓库**。
5. **不得自动合并到 main** — 所有合并需经 Codex Review + PM Acceptance。
6. **不得修改策略执行或风控**。
7. 任一阶段门禁失败时，必须退回上游修复，不允许跳过门禁进入下一阶段。
8. 每阶段测试环境必须使用隔离的临时分支（`test/<feature>/<scope>-<tester>-<timestamp>`），不得直接在 `feat/` 分支上验证。

## Proposed Phases

### Phase 1: 基础文档验证与团队计划定稿

| 属性 | 值 |
|---|---|
| **Scope** | 确认需求和架构文档完整性，产出团队计划（本文档）并提交。 |
| **Owner** | Claude Code A (Lead Planning Agent) |
| **Branch** | 直接提交到 `epic/20260616-post-merge-v11-real-codex-acceptance-smoke-r2` |
| **Dev Command** | 无（计划文档，无代码） |
| **Self-Test** | 确认 team plan 各章节完整，与需求和架构文档无矛盾 |
| **Tester** | 无需独立测试，由 Claude Lead Review 纳入检查 |
| **Release Criteria** | `docs/dev_plans/20260616-post-merge-v11-real-codex-acceptance-smoke-r2-team-plan.md` 已提交并通过格式校验 |

---

### Phase 2: 开发阶段 — 用户指南 + 验收报告

| 属性 | 值 |
|---|---|
| **Scope** | 产出两份核心交付物：① 面向用户的冒烟测试操作指南；② 对照需求的正式验收报告。 |
| **Owner** | Claude Code B (Developer) |
| **Branch** | `feat/v11-smoke/user-guide-acceptance` |
| **Dev Command** | `Get-ChildItem -Path docs/user_guides/ -Filter "*v11*"`（确认文件存在） |
| **Self-Test Checklist** | □ 用户指南覆盖操作步骤和预期结果<br>□ 验收报告逐条对照需求文档<br>□ 无代码文件被修改<br>□ 路径命名符合标准格式 |
| **Tester** | Claude Code C (Test Engineer) |
| **Tester Checks** | ① 指南中的每步操作可被读者独立重现<br>② 验收报告覆盖全部需求点（逐条映射）<br>③ 文档格式与项目现有风格一致 |
| **Tester Branch** | `test/v11-smoke/guide-acceptance-<tester>-<timestamp>` |
| **Release Criteria** | 两份文档提交到 `docs/user_guides/` 和 `docs/acceptance/`，测试报告确认无阻断缺陷 |

---

### Phase 3: 开发阶段 — Postmortem（R3 失败回顾）

| 属性 | 值 |
|---|---|
| **Scope** | 分析第一轮冒烟（R1/R3）失败根因，产出正式的 postmortem 文档，纳入改进项。 |
| **Owner** | Claude Code B (Developer) |
| **Branch** | `feat/v11-smoke/postmortem` |
| **Dev Command** | 查阅历史第一轮冒烟的 `docs/postmortems/` 记录（如存在） |
| **Self-Test Checklist** | □ 根因分析完整（5 Whys 或等效方法）<br>□ 改进项可执行且分配责任人<br>□ 无归咎个人的表述，聚焦流程改进 |
| **Tester** | Claude Code C (Test Engineer) |
| **Tester Checks** | ① 改进项是否具备可衡量完成标准<br>② 是否遗漏已知的第一轮失败线索<br>③ 文档结构是否符合项目 postmortem 模板 |
| **Tester Branch** | `test/v11-smoke/postmortem-<tester>-<timestamp>` |
| **Release Criteria** | `docs/postmortems/20260616-post-merge-v11-real-codex-acceptance-smoke-r2-r3-failure.md` 已提交，测试通过。 |

---

### Phase 4: Review 阶段 — Claude Lead Review + Codex Review

| 属性 | 值 |
|---|---|
| **Scope** | Claude Code A 做 Lead Review，然后 Codex B 做独立 Architect Review。 |
| **Owner** | Claude Code A → Codex B |
| **Branch** | `review/v11-smoke/claude-lead` → `review/v11-smoke/codex-r1` |
| **Dev Command** | 无 |
| **Self-Test** | Claude Lead Review 检查所有阶段交付物是否对齐需求和架构 |
| **Tester** | Codex B (Architect Reviewer) |
| **Tester Checks** | ① 代码/文档变更是否违反硬安全不变量<br>② 是否引入对交易模块的意外修改<br>③ 流水线流转是否完整可达 |
| **Release Criteria** | 两份 Review 文档均记录 "Approved"，无阻断项。若 Codex Review 失败，最多重试 3 次（参照 `max_codex_review_attempts: 3`）。3 次失败则触发人工审批。 |

---

### Phase 5: 最终门禁 — PM Acceptance + 合并

| 属性 | 值 |
|---|---|
| **Scope** | Codex A (PM) 做最终全量验收，签字确认后合并到 `main`。 |
| **Owner** | Codex A (PM Acceptance Agent) |
| **Branch** | 基于 epic 分支，合并前确认无未关闭阻断项 |
| **Dev Command** | 无 |
| **Self-Test** | Codex A 逐条对照需求文档验收 |
| **Tester** | 无（验收即最终门禁） |
| **Tester Checks** | — |
| **Release Criteria** | `docs/acceptance/` 验收报告标记 PASS，合并到 `main`。自动合并策略适用时按 `AUTO_MERGE_POLICY.md` 执行，但 **不得跳过人工审批门禁**。 |

---

## Agent Assignments

| 阶段 | Agent | 角色 | 职责 |
|---|---|---|---|
| Phase 1 | **Claude Code A** | Lead Planning | 产出 team plan，确认需求/架构就绪 |
| Phase 2 Dev | **Claude Code B** | Developer | 产出用户指南 + 验收报告 |
| Phase 2 Test | **Claude Code C** | Test Engineer | 验证用户指南和验收报告完整性 |
| Phase 3 Dev | **Claude Code B** | Developer | 产出 Postmortem 失败回顾 |
| Phase 3 Test | **Claude Code C** | Test Engineer | 验证 Postmortem 根因分析质量 |
| Phase 4 | **Claude Code A** | Lead Reviewer | Claude Lead Review |
| Phase 4 | **Codex B** | Architect Reviewer | Codex Review（最多 3 次重试） |
| Phase 5 | **Codex A** | PM Acceptance | 最终全量验收，签字确认 |

## Validation Plan

| 检查项 | 方法 | 触发时机 |
|---|---|---|
| 管道文档完整性 | 确认每个必选工件存在于 `docs/` 下 | 每个阶段提交后 |
| 阶段门禁合规 | 检查 `stage_status` 标记是否按序推进 | 每个阶段开始前 |
| 文档内容对齐 | 对比需求 → 设计 → 实现 → 测试 → 验收链 | Phase 4 Review |
| 无代码文件变更 | `git diff --name-only -- '*.py' '*.ts' '*.go'` 应为空 | 每个阶段提交后 |
| 硬安全不变量 | 按 `AGENTS.md` Section 2 逐条审计 | Phase 4 Codex Review |
| 分支命名合规 | 检查分支名是否匹配 `BRANCH_WORKFLOW.md` 约定 | 每个阶段分支创建时 |
| 合并门禁 | 确认 `manual_approval_required_for` 列表中的操作未绕过 | 合并前 |

## Exit Criteria

1. ✅ 全部 5 个阶段完成并通过各自门禁。
2. ✅ 所有 required_docs 工件均已提交到对应的 `docs/` 子目录：
   - `docs/requirements/*.md`
   - `docs/design/*.md`
   - `docs/dev_plans/*.md`
   - `docs/dev_reports/*.md`
   - `docs/test_reports/*.md`
   - `docs/review/*.md`
   - `docs/acceptance/*.md`
   - `docs/user_guides/*.md`
   - `docs/postmortems/*.md`
3. ✅ Claude Lead Review + Codex Review 均标记 "Approved"。
4. ✅ PM Acceptance 签字确认。
5. ✅ `stage_status` 中所有阶段标记为 `completed`。
6. ✅ 分支合并到 `main`。
7. ❌ 不得有任何交易模块代码变更混入本次合并。
