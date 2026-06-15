# Team Plan: Smoke Test Real Claude Developer V7

## Objective

验证 Real Claude Developer V7 模式的完整开发流水线能否正确运行。本 feature 是 pipeline/infrastructure 级别的 smoke test，目标是通过端到端的多 Agent 协作流程（architect → developer → tester → review → acceptance），确认 Claude Code 作为 Developer Agent 和 Test Engineer Agent 在 TEAM_PIPELINE_V2 框架下可以正确产出代码、自测、接受测试反馈并完成修复。

## Inputs Reviewed

| 输入 | 路径 | 来源 |
|---|---|---|
| 需求文档 | `docs/requirements/2026-06-14-smoke-test-real-claude-developer-v7-requirements.md` | Codex A (PM) |
| 架构设计 | `docs/design/2026-06-14-smoke-test-real-claude-developer-v7-architecture.md` | Codex B (Architect) |
| 流水线状态 | `.agent/state.json` | Pipeline Runtime |
| Agent 角色定义 | `AGENTS.md` | Repository |
| 开发流水线流程 | `docs/process/AGENT_DEVELOPMENT_PIPELINE.md` | Repository |
| 分支策略 | `docs/process/BRANCH_WORKFLOW.md` | Repository |
| 团队流水线 V2 | `docs/pipeline/TEAM_PIPELINE_V2.md` | Repository |
| Agent 交接契约 | `docs/pipeline/AGENT_HANDOFF_CONTRACT.md` | Repository |

## Scope

- 在已有 `epic/20260614-smoke-test-real-claude-developer-v7` 分支上，规划从开发到验收的完整阶段
- 每个阶段包含：scope、owner、branch、自测命令、tester 检查项、发布标准
- 阶段之间通过 handoff 文档串接，Claude Code B (Developer) 和 Claude Code C (Tester) 交替工作
- 所有产出物写入 `docs/dev_reports/`、`docs/test_reports/`、`docs/review/`、`docs/acceptance/`

## Non-Goals

- ❌ 不修改 trading-sensitive 模块（broker, execution, order, account, risk, miniQMT, live trading）
- ❌ 不削弱 merge gate 或绕过 manual approval
- ❌ 不修改风控策略或执行策略
- ❌ 不连接真实行情或交易数据源
- ❌ 不部署到生产环境
- ❌ 不引入新的产品功能或用户流程

## Safety Constraints

1. **当前任务为 docs-only / pipeline-only 性质**。不触及交易逻辑、风控、执行策略。
2. **不得修改受限模块**：broker, execution, order, account, risk, miniQMT, live trading, real order submission。
3. **不得削弱 Merge Gate**：不得跳过 manual approval，不得修改 auto-merge-policy。
4. **不得写入密钥**：不提交任何 `.env`、API keys、tokens、credentials。
5. **不得自动合并到 main**：最终合并必须通过人工确认。
6. **不得修改风控或执行策略**：`docs/policy/RISK_POLICY.md` 和 `docs/policy/EXECUTION_POLICY.md` 保持只读。
7. **每阶段必须输出开发报告和测试报告**，通过后才能进入下一阶段。
8. **所有实盘相关代码必须保持模拟/演示模式**，不得绕过 `LEVEL_3_AUTO` 保护。

## Proposed Phases

### Phase 1: Developer Mode Wrapper Validation

| 属性 | 值 |
|---|---|
| **Scope** | 验证 `stage_runner_wrapper` 在 real Claude developer 模式下的正确配置和基础执行能力 |
| **Owner** | Claude Code B (Developer) |
| **Branch** | `feat/smoke-test-real-claude-dev-v7/wrapper-validation` |
| **自测命令** | `python -m pytest tests/agent/test_stage_runner_wrapper.py -x -v` |
| **Tester 检查项** | ① wrapper 是否正确加载 developer 配置 ② 环境变量注入是否正确 ③ handoff 文件格式是否符合契约 ④ 错误路径（配置缺失、阶段不存在）是否优雅降级 |
| **Release Criteria** | Tester 确认所有检查项通过，输出 Phase 1 测试报告 |

**详细任务：**

1.1 读取架构设计中的 wrapper 配置要求，确认 developer 模式的入口参数和开关
1.2 编写/更新 `stage_runner_wrapper` 对 developer 模式的单元测试
1.3 验证 wrapper 在 developer 模式下能正确读取 `.agent/handoff/` 中的交接文档
1.4 验证 wrapper 在 developer 模式下能正确输出开发报告到 `docs/dev_reports/`
1.5 验证错误场景：配置缺失时抛出可理解错误，不会产生脏数据
1.6 输出开发报告到 `docs/dev_reports/2026-06-14-smoke-test-real-claude-developer-v7-phase-1-dev-report.md`

---

### Phase 2: Single-Phase Dev Cycle Smoke Test

| 属性 | 值 |
|---|---|
| **Scope** | 执行一次完整的单阶段开发循环：developer 实现一个最小功能 → tester 验证 → 修复 → 通过 |
| **Owner** | Claude Code B (Developer) → Claude Code C (Tester) → Claude Code B (BugFix) |
| **Branch** | `feat/smoke-test-real-claude-dev-v7/single-phase-cycle` |
| **自测命令** | Developer: `python -m pytest tests/agent/test_dev_cycle.py -x -v` |
| **Tester 命令** | `python -m pytest tests/agent/test_dev_cycle.py -x -v --tester-mode` |
| **Tester 检查项** | ① developer 产出物是否符合 architecture 规范 ② 自测覆盖率是否达标（≥80%） ③ handoff 到 tester 阶段是否成功 ④ tester 能否独立运行测试并输出报告 ⑤ bug 修复后回归测试是否全部通过 |
| **Release Criteria** | 完成「开发→测试→修复→回归通过」的完整闭环，输出 Phase 2 测试报告 |

**详细任务：**

2.1 Developer 按架构设计实现一个最小验证功能（如 agent 辅助工具函数），包含完整测试
2.2 Developer 运行自测，确保全部通过
2.3 Developer 输出 Phase 2 开发报告
2.4 通过 handoff 文档将控制权转给 Tester (Claude Code C)
2.5 Tester 运行独立测试，输出测试报告和 bug 清单
2.6 通过 handoff 文档将 bug 清单转回 Developer
2.7 Developer 修复 bug 并补充回归测试
2.8 Tester 确认修复有效，输出 Phase 2 测试报告

---

### Phase 3: Multi-Phase Orchestration Smoke Test

| 属性 | 值 |
|---|---|
| **Scope** | 测试两阶段串联：Phase A 开发 → Phase A 测试通过 → Phase B 开发 → Phase B 测试通过，验证多阶段 handoff 和状态传递正确 |
| **Owner** | Claude Code B (Developer) / Claude Code C (Tester) 交替 |
| **Branch** | `feat/smoke-test-real-claude-dev-v7/multi-phase-orch` |
| **自测命令** | Developer (Phase A): `python -m pytest tests/agent/test_phase_a.py -x -v`; Developer (Phase B): `python -m pytest tests/agent/test_phase_b.py -x -v` |
| **Tester 命令** | `python -m pytest tests/agent/ -x -v --tester-mode` |
| **Tester 检查项** | ① Phase A 产出物完整且通过测试 ② handoff 到 Phase B 时状态文件正确更新 ③ Phase B 能正确读取 Phase A 的产出 ④ 最终所有测试通过 ⑤ 中间件记录完整 |
| **Release Criteria** | 两阶段串联通过，输出 Phase 3 测试报告 |

**详细任务：**

3.1 Developer 实现 Phase A 功能模块和相关测试
3.2 Developer 自测通过后输出开发报告，handoff 给 Tester
3.3 Tester 验证 Phase A，输出测试报告
3.4 通过 handoff 通知 Developer 开始 Phase B
3.5 Developer 实现 Phase B 功能（依赖 Phase A），自测通过
3.6 Developer 输出开发报告，handoff 给 Tester
3.7 Tester 验证 Phase B + 回归 Phase A，输出 Phase 3 测试报告

---

### Phase 4: Edge Cases & Failure Recovery

| 属性 | 值 |
|---|---|
| **Scope** | 测试流水线在异常场景下的行为：测试失败、配置错误、handoff 中断、部分完成后的恢复 |
| **Owner** | Claude Code B (Developer) / Claude Code C (Tester) |
| **Branch** | `feat/smoke-test-real-claude-dev-v7/edge-cases` |
| **自测命令** | `python -m pytest tests/agent/test_edge_cases.py -x -v` |
| **Tester 命令** | `python -m pytest tests/agent/test_edge_cases.py -x -v --tester-mode --edge-cases` |
| **Tester 检查项** | ① 测试失败时 bug 修复流程正确 ② 配置错误时错误信息可理解 ③ handoff 中断后可重新接续 ④ 部分完成阶段可回退 ⑤ 无脏数据残留 |
| **Release Criteria** | 所有 edge case 场景通过，输出 Phase 4 测试报告 |

**详细任务：**

4.1 场景 A — 测试失败：Developer 故意引入一个微小缺陷，验证 Tester 能捕获、Developer 能修复
4.2 场景 B — 配置错误：验证 pipeline 在缺少必要配置时给出明确错误并安全退出
4.3 场景 C — Handoff 中断：模拟 handoff 文件损坏/缺失，验证恢复机制
4.4 场景 D — 部分回退：验证阶段回退不留下不一致状态
4.5 输出开发报告和测试报告

---

### Phase 5: Code Review & Acceptance

| 属性 | 值 |
|---|---|
| **Scope** | Claude Lead (Claude A) 做最终 Lead Review，Codex B 做架构 Code Review，Codex A 做 PM 验收 |
| **Owner** | Claude A (Lead Review) → Codex B (Code Review) → Codex A (Acceptance) |
| **Branch** | 在 epic 分支上直接 review |
| **Reviewer 检查项** | ① 所有架构约束是否被遵守 ② 测试覆盖率是否满足标准 ③ pipeline 日志是否完整可追溯 ④ 安全不变量是否被保持 ⑤ 是否存在未关闭的缺陷 |
| **Acceptance 检查项** | ① 是否满足需求文档中的所有验收标准 ② 端到端流程是否可复现 ③ 用户文档是否完整 |
| **Release Criteria** | Code Review 通过 + PM Acceptance 通过 + 用户/owner 确认合并 |

**详细任务：**

5.1 Claude A 汇总所有阶段测试报告，做 Lead Review
5.2 输出 Lead Review 到 `docs/review/2026-06-14-smoke-test-real-claude-developer-v7-claude-lead-review.md`
5.3 Codex B 做架构 Code Review，输出到 `docs/review/2026-06-14-smoke-test-real-claude-developer-v7-codex-review-r1.md`
5.4 如有 Review 问题，退回 Developer 修复（最多 3 轮）
5.5 Codex A 做 PM 验收，输出到 `docs/acceptance/2026-06-14-smoke-test-real-claude-developer-v7-acceptance.md`
5.6 用户/owner 确认后合并到 main

## Agent Assignments

| Agent | 角色 | 负责阶段 | 产出物 |
|---|---|---|---|
| Claude Code A (当前) | Lead Planning & Lead Review | Phase 5 (Lead Review) | Team Plan, Lead Review |
| Claude Code B | Developer & BugFix | Phase 1, 2, 3, 4 | Dev Reports |
| Claude Code C | Test Engineer | Phase 2, 3, 4 | Test Reports |
| Codex A | PM & Acceptance | Phase 5 (Acceptance) | Acceptance Report |
| Codex B | Architect & Code Review | Phase 5 (Code Review) | Code Review Report |

## Validation Plan

### 阶段间验证流程

```
Phase N Developer (Claude B)
    ↓ 开发报告 + handoff
Phase N Tester (Claude C)
    ↓ 测试报告（通过/不通过）
[不通过] → Developer 修复 → 重新测试
[通过] → 进入 Phase N+1
```

### 全局验证标准

| 维度 | 标准 | 验证方式 |
|---|---|---|
| 功能正确 | 所有测试通过 | `pytest -x -v` |
| 架构一致 | 代码符合架构设计 | Code Review |
| 安全不变量 | 未触及受限模块 | 文件变更审计 |
| 可追溯 | 所有阶段有报告 | 文档完整性检查 |
| 无退化 | 回归测试全部通过 | `pytest tests/ -x -v` |

### 门禁清单（Each Gate）

- **Phase Gate**: Tester 报告必须明确标注「通过」或「不通过」，不得有歧义
- **Review Gate**: 必须检查架构一致性、安全边界、测试覆盖率
- **Acceptance Gate**: 必须逐条对照需求文档的验收标准
- **Merge Gate**: 需要用户/owner 手动确认

## Exit Criteria

本 feature 的完整退出条件：

1. ✅ Phase 1-4 全部完成，每阶段有对应的 `dev_report` 和 `test_report`
2. ✅ Claude Lead Review 通过，`docs/review/` 中有 review 文档
3. ✅ Codex Code Review 通过（≤3 轮），有 review 文档
4. ✅ PM Acceptance 通过，`docs/acceptance/` 中有 acceptance 文档
5. ✅ 所有测试在 epic 分支上通过
6. ✅ 无未关闭的安全或风控问题
7. ✅ 用户/owner 手动确认合并到 main

---

*Plan generated by Claude Code A (Lead Planning Agent) on 2026-06-14.*
