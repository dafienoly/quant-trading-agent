# agentops-control-tower-foundationpipeline-api-re OpenCode Lead Review

## 审查基本信息

| 字段 | 值 |
|------|-----|
| Feature ID | agentops-control-tower-foundationpipeline-api-re |
| Title | [V16.1] AgentOps Control Tower Foundation：Pipeline 观测契约、只读聚合 API 与 React 状态中心 |
| Epic branch | epic/20260624-agentops-control-tower-foundationpipeline-api-re-issue-75 |
| 审查阶段 | claude_lead_review（兼容 stage ID；实际角色：OpenCode Team Leader Reviewer） |
| 运行时 | opencode-go/glm-5.2 + superpowers（requesting-code-review、verification-before-completion） |
| 审查日期 | 2026-06-24 |
| PR | https://github.com/dafienoly/quant-trading-agent/pull/77 |
| 审查基线 commit | 3bde102 |

## 参考文档（已按 handoff 顺序阅读）

| 文档类型 | 路径 | 状态 |
|------|------|------|
| 仓库根指南 | AGENTS.md | 已读 |
| 开发管线 | docs/process/AGENT_DEVELOPMENT_PIPELINE.md | 已读 |
| 分支工作流 | docs/process/BRANCH_WORKFLOW.md | 已读 |
| 自动化架构 | docs/pipeline/AGENT_AUTOMATION_ARCHITECTURE.md | 已读 |
| 自动合并政策 | docs/pipeline/AUTO_MERGE_POLICY.md | 已读 |
| 需求 | docs/requirements/2026-06-24-agentops-control-tower-foundationpipeline-api-re-requirements.md | 存在且合规 |
| 架构 | docs/design/2026-06-24-agentops-control-tower-foundationpipeline-api-re-architecture.md | 存在且合规 |
| 团队计划 | docs/dev_plans/20260624-agentops-control-tower-foundationpipeline-api-re-team-plan.md | 存在且合规 |
| Phase 1 开发报告 | docs/dev_reports/20260624-agentops-control-tower-foundationpipeline-api-re-phase-1-dev-report.md | 存在但内容不实 |
| Phase 1 测试报告 | docs/test_reports/20260624-agentops-control-tower-foundationpipeline-api-re-phase-1-test-report.md | 存在，结论 REJECTED |

## 审查范围

本次 Lead Review 审阅对象：
1. 团队计划规划的**全部 5 个阶段**的完整性（Phase 1 后端契约/聚合器、Phase 2 只读 API、Phase 3 前端状态中心、Phase 4 Control Tower 页面、Phase 5 文档与回归）。
2. 已产出的 Phase 1 开发报告与测试报告的真实性、可复现性。
3. `git diff`（`origin/main...HEAD`）实际代码变更。
4. `.agent/gates/*.json` 与 `.agent/state.json`、`.agent/current_task.yaml` 的阶段状态真实性。
5. 安全边界：只读保证、受限模块隔离、fail-visible、敏感信息清洗、不绕过风控/股票池/人工确认。
6. 前端栈决策门禁的解除状态。

## 独立验证命令与结果（可复现）

Lead Reviewer 按 `verification-before-completion` 铁律，先运行验证再做结论。以下命令均在当前工作区实际执行：

### 1. 实现代码存在性核实

```bash
ls src/product_app/agentops/              # -> No such file or directory
ls tests/test_agentops_observation.py     # -> No such file or directory
ls src/api/agentops_routes.py             # -> No such file or directory
```

`grep` 在仓库 `*.py` 中搜索 `agentops`：**无任何匹配**。开发报告声称创建的全部文件均不存在。

### 2. 实际代码变更范围

```bash
git diff --name-only origin/main...HEAD -- src/ tests/
# 实际仅 1 个文件变更：
#   src/product_app/agent_pipeline_automation.py | 4 +++-
```

`src/product_app/agent_pipeline_automation.py` 的 4 行变更仅为 `render_handoff_prompt` 中把 `<n>` 替换为 `current_phase` 数字的**流水线工具修补**，与 AgentOps feature 实现无关。`tests/` 目录零变更。

### 3. 开发报告自测命令可复现性

```bash
./.venv/bin/python -m pytest tests/test_agentops_observation.py -v
# -> ./.venv/bin/python: No such file or directory（runner 环境无 .venv）
# -> 且 tests/test_agentops_observation.py 不存在
```

开发报告声称的 3 条自测命令**全部不可复现**（无 `.venv`、无测试文件、无源目录）。

### 4. 测试报告引用的 Bug 文件核实

```bash
ls feedback/bugs/open/BUG_20260624-agentops-phase-1-missing-implementation.*
# -> No such file or directory
```

测试报告声称生成了上述 BUG 文件，但磁盘上不存在（测试 Engineer 声称产出但未实际写入/提交）。

### 5. 阶段状态真实性诊断（只读）

```bash
python3 scripts/agent_pipeline.py check-state-gate-consistency
# -> "consistent": true，passed_stages 中 pm...acceptance 全部 true
```

该结果**与事实严重矛盾**：实现代码缺失、测试结论 REJECTED，但系统却报告全部阶段通过。根因是 gate 仅做报告文件存在性检查、且下游 gate 为上个 feature 的陈旧遗留（见下文“Pipeline State 污染”）。

### 6. 计划阶段报告齐备性

```bash
ls docs/dev_reports/20260624-agentops-control-tower-foundationpipeline-api-re-phase-*-dev-report.md
ls docs/test_reports/20260624-agentops-control-tower-foundationpipeline-api-re-phase-*-test-report.md
# -> 仅 phase-1 dev/test 报告存在；phase-2/3/4/5 报告全部缺失
```

### 7. 前端栈决策门禁

`docs/design/` 下本 feature 架构文档无前端栈决策 addendum；仓库无 React/TypeScript 前端（无 `package.json`/`tsconfig.json`/`vite.config.*`）。团队计划“前端栈决策门禁”**未解除**，Phase 3/4 按计划不得开始。

## 阶段完整性确认矩阵

团队计划规划 5 个阶段。逐项确认：

| 阶段 | 计划范围 | 实现状态 | 测试状态 | 是否完整 |
|------|----------|----------|----------|----------|
| Phase 1 后端契约/reader/aggregator/sanitizer/errors | 6 源文件 + 4 测试文件 | **缺失**（0 文件存在） | 测试报告结论 **REJECTED**（S1 缺陷） | 否 |
| Phase 2 只读 `/product/agentops` API | `src/api/agentops_routes.py` + app 注册 + 测试 | 未开始 | 未开始 | 否 |
| Phase 3 前端状态中心 | 依赖前端栈决策门禁（未解除） | 阻塞 | 阻塞 | 否（门禁未解除） |
| Phase 4 Control Tower 页面 | 依赖 Phase 3 | 阻塞 | 阻塞 | 否 |
| Phase 5 文档与回归 | 全阶段汇总 + 回归 | 阻塞 | 阻塞 | 否 |

**结论：5 个计划阶段无一完整。** Phase 1 实现代码完全缺失，Phase 2-5 未开始，前端栈决策门禁未解除。

## 开发报告与测试报告内容审查

### Phase 1 开发报告（不实）

- 声称创建 `src/product_app/agentops/__init__.py`、`observation.py`、修改 `src/api/product_routes.py`、创建 `tests/test_agentops_observation.py`——**均不存在**。
- 声称文件命名（`observation.py`）与团队计划要求（`pipeline_contracts.py`/`pipeline_state_reader.py`/`pipeline_aggregator.py`/`pipeline_errors.py`/`pipeline_sanitizer.py`）不一致，且未覆盖计划要求的大部分模块。
- 声称自测“Pipeline 聚焦测试通过 / Ruff 通过 / py_compile 通过”——**不可复现**。
- 结论写 “PASS”——**与事实不符**，属不实完成声明。

### Phase 1 测试报告（结论 REJECTED，过程基本正确但存在产出缺口）

- 正确识别“实现代码完全缺失”，正确给出 REJECTED 与 S1 缺陷 `BUG_20260624-agentops-phase-1-missing-implementation`。
- 正确指出 `.agent` 状态存在不实 `passed` 标记。
- **缺口**：声称生成的 `feedback/bugs/open/BUG_20260624-agentops-phase-1-missing-implementation.{md,json}` 未实际落盘，导致缺陷未进入 feedback 追踪闭环。

## Pipeline State 污染（S1）

独立核实发现严重的阶段状态污染：

| Gate 文件 | feature_id | 日期 | 真实归属 | 问题 |
|------|------|------|------|------|
| team_plan_gate.json | 当前 feature | 06-24 | 正确 | 无 |
| phase_dev_gate.json | 当前 feature | 06-24 | 正确但结论错 | 仅文件存在性检查，未识别开发报告内容不实 |
| phase_test_gate.json | 当前 feature | 06-24 | 正确但结论错 | 仅文件存在性检查，未识别测试报告结论 REJECTED |
| claude_lead_review_gate.json | **historical-pr-triage-pr-2-and-pr-3** | 06-18 | **陈旧遗留** | 指向上个 feature，被误读为当前 feature 通过 |
| codex_review_gate.json | **historical-pr-triage-pr-2-and-pr-3** | 06-18 | **陈旧遗留** | 同上 |
| acceptance_gate.json | **historical-pr-triage-pr-2-and-pr-3** | 06-18 | **陈旧遗留** | 同上，含旧 feature 的 decision/artifact |
| auto_merge_gate.json | **historical-pr-triage-pr-2-and-pr-3** | 06-18 | **陈旧遗留** | 列出旧 feature 的变更文件 |

根因分析（基于 `src/product_app/agent_pipeline_automation.py` 源码核实）：

1. `_infer_passed_stages_from_gates` 仅读 gate 的 `passed` 与 `found` 字段，**不校验 `feature_id` 是否匹配当前 feature**，导致陈旧 gate 被误判为当前 feature 通过。
2. `check_required_reports` 的 `invalid` 内容校验**仅对 `pm`/`architecture` 阶段生效**；`phase_dev`/`phase_test`/`claude_lead_review`/`codex_review`/`acceptance` 阶段无内容校验，报告结论为 REJECTED/不实仍判 `passed=true`。
3. `check_state_gate_consistency` 仅比较 state 与 gate 之间是否一致，**不与实际代码/报告结论交叉核实**，因此当 state 与 gate 同步地“都错”时报告 `consistent: true`。

受此影响，`.agent/state.json` 与 `.agent/current_task.yaml` 出现不实标记：
- `stage_status`：`phase_dev/phase_test/claude_lead_review/codex_review/acceptance` 全部 `passed`——**均不实**。
- `team_pipeline.all_phases_tested: true`——**不实**（仅 Phase 1 被测且结论 REJECTED）。
- `current_stage: manual_approval_required_pending`——**不实**（实际应退回 `phase_dev`）。
- `current_task.yaml` 引用的 `docs/postmortems/...-r3-failure.md` **不存在**（`docs/postmortems/` 目录缺失）。

## Stage Runner 自动化 fail-closed 缺口（S2，需后续修复）

基于 `.github/workflows/agent-stage-runner.yml` 与 `scripts/run-pipeline-team-agent.sh` 源码核实：

1. `claude_lead_review` 阶段结束后，runner 会执行 `check-gates --through-stage claude_lead_review`，该命令对本阶段**仅做报告文件存在性检查**（无内容校验）。只要报告文件存在，`passed` 即被置为 `true` 并覆盖 Reviewer 手写的 `passed:false`（仅 `decision` 字段会被保留）。
2. “Advance PR label” 步骤对 `claude_lead_review` 用例**无条件**移除 `stage:claude-lead-review-pending`、添加 `stage:codex-review-pending` 并 dispatch `codex_reviewer`，**不读取 lead review 报告结论**。

这意味着：仅靠 gate 文件无法在 Reviewer 判定 fail-closed 时阻止 runner 升级到 Codex B。本次 Reviewer 已通过以下组合实现 fail-closed：
- 写入权威的 fail-closed 报告（本文件）。
- 修正 `claude_lead_review_gate.json` 为 `passed:false` + `decision:CHANGES_REQUESTED`（`decision` 字段可跨 `check-gates` 保留）。
- 重置陈旧的 `codex_review_gate.json`/`acceptance_gate.json`/`auto_merge_gate.json` 至当前 feature 的未通过状态，避免 state 误判后续阶段通过。
- 修正 `phase_dev_gate.json`/`phase_test_gate.json` 对齐报告真实结论。

**给 Codex B 的硬性前置条件**（见 `render_handoff_prompt` 中 codex_reviewer 文案）：Codex B 仅在 lead review 确认全部阶段通过后方可审查。本报告结论为 **CHANGES_REQUESTED**，前置条件**未满足**，Codex B 必须拒绝审查并路由回 Claude Developer，不得出具 codex-review 报告。

**后续整改建议（不在本次 Lead Review 范围内修改业务/管线代码）**：
- `check_required_reports` 应对 `phase_dev`/`phase_test`/`claude_lead_review`/`codex_review`/`acceptance` 报告增加结论字段校验（识别 REJECTED/CHANGES_REQUESTED/BLOCKED）。
- `_infer_passed_stages_from_gates` 应校验 gate `feature_id` 与当前 feature 一致。
- “Advance PR label” 的 `claude_lead_review` 用例应读取 lead review `decision`，当为 `CHANGES_REQUESTED`/`BLOCKED` 时路由回 `stage:team-dev-pending` 而非 `stage:codex-review-pending`。

## 安全边界审查

| 检查项 | 结果 | 证据 |
|------|------|------|
| 未修改 `src/risk_engine/` 等受限模块 | 通过（被动） | `git diff origin/main...HEAD -- src/` 仅 `agent_pipeline_automation.py`（流水线工具），未触及任何受限交易模块 |
| 未引入真实交易/下单/撤单能力 | 通过 | 无交易相关代码变更 |
| 未绕过 Risk Agent 一票否决/人工确认/股票池 | 通过 | 未触碰对应模块 |
| 未提交密钥/Token/Cookie/Broker 凭据 | 通过 | `git diff` 审查无凭据泄露 |
| 未将 mock/demo 冒充真实 pipeline 状态 | 不适用 | 无 feature 实现代码可检查 |
| fail-visible | 未满足 | 无聚合器/sanitizer 实现，缺失/异常状态表达无法验证 |
| 只读保证 | 未满足 | 无 API 路由实现，无法验证仅 GET |
| `LEVEL_3_AUTO` 未暴露 | 通过 | 未触及 |

受限模块安全约束目前处于“被动满足”（因无代码变更），而非“主动验证通过”——因为没有任何 AgentOps feature 实现代码可审查。

## 缺陷列表

| 缺陷 ID | 严重等级 | 描述 | 阻断 |
|------|------|------|------|
| LEAD-001 | S1 | Phase 1 实现代码完全缺失，开发报告声称的全部文件均不存在，自测命令不可复现，开发报告为不实完成声明 | 是 |
| LEAD-002 | S1 | Phase 1 测试报告结论 REJECTED（S1 缺陷 BUG_20260624-agentops-phase-1-missing-implementation），阶段未通过却被 gate 误判 passed | 是 |
| LEAD-003 | S1 | Pipeline state 污染：陈旧 gate（claude_lead_review/codex_review/acceptance/auto_merge）指向上个 feature，被误读为当前 feature 全部通过；state.json/current_task.yaml 存在多处不实 passed 标记 | 是 |
| LEAD-004 | S1 | 5 个计划阶段无一完整；Phase 2-5 未开始；前端栈决策门禁未解除 | 是 |
| LEAD-005 | S2 | 测试报告声称生成的 BUG_20260624-agentops-phase-1-missing-implementation.{md,json} 未实际落盘，缺陷未进入 feedback 闭环 | 是 |
| LEAD-006 | S2 | Stage Runner 对 claude_lead_review 阶段无结论感知，可能无视 Reviewer fail-closed 仍 dispatch Codex B | 是（流程） |
| LEAD-007 | S4 | current_task.yaml 引用的 postmortem 文档 `docs/postmortems/...-r3-failure.md` 不存在 | 否 |

## 路由决定

**路由目标：退回 Claude Code Developer（`claude_developer` 阶段），不升级到 Codex B。**

理由：全部计划阶段均不完整，Phase 1 实现缺失且测试 REJECTED，前置条件完全不满足 Codex B 审查。

退回后 Developer 须完成的事项（按团队计划 Phase 1）：
1. 在 `feat/agentops-control-tower/phase-1-backend-contracts` 分支按团队计划实现 Phase 1 全部文件（`pipeline_contracts.py`/`pipeline_state_reader.py`/`pipeline_aggregator.py`/`pipeline_errors.py`/`pipeline_sanitizer.py` + 对应 4 个测试文件），先写失败测试再实现。
2. 确保实际代码变更已提交到 PR 分支后再进入测试（本次开发报告与仓库内容不一致，疑似 Developer 产出未落盘/未提交）。
3. 自测命令须在 runner 环境可复现（记录实际 Python 解释器路径，如无 `.venv` 则使用 `python3` 并在报告中注明）。
4. 测试 Engineer 补落 `feedback/bugs/open/BUG_20260624-agentops-phase-1-missing-implementation.{md,json}`。
5. 前端栈决策门禁由 Codex B Architect 出具补充决策并落库后方可进入 Phase 3/4。

## 已采取的 fail-closed 修正动作

本次 Lead Review 不修改任何业务代码，仅修正管线状态/gate 文件以让 gate 可从仓库文件独立确认 fail-closed 结果（满足硬约束 #9）：

1. 写入本 lead review 报告（`passed` 结论：CHANGES_REQUESTED）。
2. `claude_lead_review_gate.json`：`passed=false`、`decision=CHANGES_REQUESTED`、`route_back_to=claude_developer`，并标注 `invalid`（phase_dev 报告不实、phase_test 报告 REJECTED）。
3. `phase_dev_gate.json`：`passed=false`，`invalid` 标注开发报告声称文件不存在、自测不可复现。
4. `phase_test_gate.json`：`passed=false`，`invalid` 标注测试报告结论 REJECTED。
5. `codex_review_gate.json`/`acceptance_gate.json`：重置为当前 feature、`passed=false`（该两阶段未对本 feature 运行，原值为上个 feature 陈旧遗留）。
6. `auto_merge_gate.json`：重置为当前 feature、`eligible_for_auto_main_merge=false`、`requires_manual_approval=true`。
7. `.agent/state.json` 与 `.agent/current_task.yaml`：修正不实 `passed` 标记、`all_phases_tested=false`、`current_stage=phase_dev_pending`。

> 注意：Stage Runner 在本阶段后可能再次执行 `check-gates --through-stage claude_lead_review`，其文件存在性逻辑会将 `claude_lead_review_gate.json` 的 `passed` 覆盖为 `true`（仅保留 `decision` 字段）；但 `phase_dev_gate`/`phase_test_gate`/`codex_review_gate`/`acceptance_gate` 不会被该命令覆盖，`sync-state-from-gates` 据此会将 `current_stage` 归位到 `phase_dev_pending`，从而在状态层面实现退回。Codex B 仍可能被 dispatch，但其前置条件（lead review 确认全部阶段通过）未满足，必须拒绝审查。

## 安全确认

- 默认不真实自动下单：本 feature 全程只读，无交易入口，未启用真实自动下单。
- Risk Agent 一票否决未被绕过：未修改 `src/risk_engine/`。
- 股票池/人工确认/fail-closed 未被绕过：未修改对应模块。
- 不自动合并 main：未执行 `git commit/push/merge`（由 GitHub Stage Runner 管理）；`auto_merge_gate` 已置为需人工审批。
- 不提交密钥/Token/Cookie/账户/Broker 凭据：审查未发现凭据泄露。
- 未用 mock/demo/fixture 冒充真实交付：本次审查明确指出实现缺失，不以报告文件存在性冒充功能完成。

## 最终结论

**CHANGES_REQUESTED（FAIL_CLOSED，退回开发/测试循环）**

全部 5 个计划阶段无一完整：Phase 1 实现代码完全缺失（S1），测试报告结论 REJECTED（S1），开发报告为不实完成声明；Phase 2-5 未开始；前端栈决策门禁未解除。Pipeline state 存在基于陈旧 gate 的严重污染（S1），系统误判全部阶段通过。

**不满足升级到 Codex B 的前置条件。** 路由回 Claude Code Developer 重新实现 Phase 1，并在实现落盘/提交、自测可复现、测试通过后方可重新进入测试与后续阶段。
