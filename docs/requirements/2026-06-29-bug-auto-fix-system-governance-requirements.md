# bug-auto-fix-system-governance Requirements

## User Goal

用户希望为 Bug Auto-Fix 自动修复流程建立一套可审计、可阻断、可人工接管的治理机制，确保自动化 Agent 只能处理明确安全的低风险缺陷修复，不能擅自修改交易安全、风控、执行、数据 Provider、Model Gateway、Tool Registry、股票池、回测等受限模块，也不能在审计证据不足时自动合并。

本功能面向 Issue-driven automation 和团队流水线，Feature ID 为 `bug-auto-fix-system-governance`，对应议题为 Issue `#122`，路线图归属为 `V16.4 Quant Tool Registry` 相关治理能力。功能目标不是提升修复速度本身，而是为自动修复建立边界、证据和失败可见性。

用户成功标准：

- 自动修复系统只处理安全白名单内的修复类型。
- 涉及受限模块、真实交易、风控策略、执行策略或人工确认边界的修复会被自动阻断。
- 每次自动修复尝试都有结构化审计记录，能追溯输入、判断、变更范围、测试证据和最终门禁结果。
- 当门禁失败或风险未知时，系统不会自动合并，而是转入人工审批或人工修复。
- 用户可以从流水线日志、报告或 artifact 中明确知道为什么某个自动修复被允许、拒绝或要求人工确认。

非目标：

- 不实现新的真实交易能力。
- 不修改 Risk Agent、Execution Engine、Broker、Stock Pool、Provider Hub、Model Gateway 或核心交易策略逻辑。
- 不允许 LLM 自动决定是否下单、是否绕过风控、是否改变仓位或是否放宽数据质量门禁。
- 不在本阶段建设新的 React 前端基线。
- 不把自动修复能力扩展为通用代码重写系统。
- 不绕过既有 PM、Architecture、Development、Test、Review、Acceptance 阶段门禁。

## Functional Requirements

1. 安全修复白名单

系统必须定义 Bug Auto-Fix 允许自动处理的修复类型白名单。白名单至少应区分：

- 文档错别字、格式、链接、标题层级等低风险文档修复。
- 非生产路径测试 fixture、测试断言、测试隔离目录等低风险测试修复。
- 明确不影响业务行为的 lint、typing、import 排序或 dead code 清理。
- 自动化流水线元数据中不影响合并门禁、安全策略或执行策略的低风险修正。

任何不在白名单内的修复类型必须默认拒绝自动修复，进入人工处理。

2. 受限模块阻断

系统必须识别并阻断 Bug Auto-Fix 对以下区域的自动修改，除非后续架构和人工审批明确放行：

- `src/risk_engine/`
- `src/execution_engine/`
- `src/data_gateway/`
- `src/backtest_engine/`
- `src/factor_engine/`
- `src/strategy_engine/`
- `src/product_app/agentops/`
- `src/product_app/market_data/`
- `src/product_app/tools/`
- `src/product_app/model_gateway/`
- `src/product_app/decisions/`
- `src/product_app/position_sizing/`
- `src/product_app/backtests/`
- `src/product_app/risk_sentinel/`
- `src/product_app/fundamental/`
- `src/product_app/alpha/`
- `src/product_app/paper_trading/`
- `src/product_app/broker_shadow/`
- `src/api/`
- `src/ui_report/`
- `config/`
- workflow、merge policy、权限、secret、deployment、runner 配置相关文件

阻断结果必须说明触发的路径、规则和所需人工审批类型。

3. 风险分类与决策结果

每次 Bug Auto-Fix 尝试必须产出结构化风险判断，至少包含：

- `feature_id`
- `issue_number`
- `run_id`
- `candidate_files`
- `change_summary`
- `risk_level`
- `allowed_by_whitelist`
- `restricted_module_touched`
- `manual_approval_required`
- `auto_fix_decision`
- `decision_reason`
- `required_tests`
- `audit_artifact_path`

`auto_fix_decision` 只允许使用以下结果：

- `ALLOW_AUTO_FIX`
- `BLOCK_RESTRICTED_MODULE`
- `BLOCK_NOT_WHITELISTED`
- `BLOCK_INSUFFICIENT_EVIDENCE`
- `REQUIRE_MANUAL_APPROVAL`

4. 审计门禁

系统必须为每次自动修复生成审计证据。审计证据必须包含：

- 原始 bug 或失败输入来源。
- 自动修复 Agent 身份和阶段。
- 允许或阻断依据。
- 预期变更范围。
- 实际 touched files。
- 测试命令和结果。
- 是否触碰受限模块。
- 是否影响真实交易能力。
- 是否需要人工审批。
- 最终门禁结论。

缺少审计证据时，自动合并必须失败关闭。

5. 自动合并约束

Bug Auto-Fix 结果只有在同时满足以下条件时，才允许进入自动合并候选：

- 修复类型在白名单内。
- 未触碰受限模块。
- 未改变交易、风控、执行、Provider、Tool Registry、Model Gateway、股票池或数据质量门禁。
- 测试命令已运行并通过。
- `git diff --check` 通过。
- 没有 secret 泄露迹象。
- 审计 artifact 完整。
- Review 和 Acceptance 门禁未失败。

任何条件不满足时，必须阻断自动合并并保留人工处理指引。

6. Pipeline 集成要求

本功能必须与现有文档驱动流水线兼容：

- PM 阶段产出 requirements。
- Architecture 阶段定义治理模型、配置边界和 pipeline 集成点。
- Development 阶段实现最小必要自动化治理逻辑。
- Test 阶段验证 normal、blocked、restricted、missing-evidence、manual-approval 路径。
- Review 阶段检查安全边界和测试充分性。
- Acceptance 阶段确认不会绕过 manual merge 和 human confirmation。

系统不得跳过现有阶段门禁。

7. 数据需求与数据来源

系统需要读取或接收以下数据：

- Issue metadata：`feature_id`、`issue_number`、`issue_url`、`run_id`、branch、stage。
- Pipeline state：当前 stage、attempt count、manual approval policy、required docs。
- Candidate diff metadata：文件路径、变更类型、diff 统计、测试范围。
- Policy source：`AGENTS.md`、branch workflow、automation architecture、auto merge policy 中的安全规则。
- Test evidence：命令、退出码、摘要、失败原因。
- Review evidence：review 状态、失败次数、request changes 结果。

数据 freshness 要求：

- 风险判断必须基于当前分支当前 diff。
- 合并前必须重新读取最新 touched files 和测试结果。
- 过期的测试结果、旧 run artifact 或其他 branch 的证据不得用于当前自动合并判断。

8. API、CLI 与 UI 行为

如后续架构需要暴露产品内查询能力，必须使用 `/product/**` 命名空间，不得新增平行业务前缀 `/api/**`。

本阶段不要求新增用户前端。若需要展示状态，优先使用现有流水线日志、Markdown 报告、artifact 和 Streamlit Dashboard 的既有入口。不得将 Streamlit 标记为 legacy 或 deprecated。

9. Agent 权限边界

LLM Agent 只能进行以下操作：

- 分类 bug 修复风险。
- 解释阻断原因。
- 生成结构化审计摘要。
- 建议人工审批路径。
- 辅助生成报告。

LLM Agent 不得：

- 放宽白名单。
- 自行解除受限模块阻断。
- 自行批准真实交易、风控、执行或风险策略修改。
- 隐藏测试失败。
- 把 mock、stale、fallback 数据描述为 live 能力。
- 生成买入、卖出、下单、仓位或 risk override 结论。

## Non-functional Requirements

1. 安全性

系统必须 fail closed。风险未知、证据缺失、路径无法分类、测试未运行、策略冲突或门禁状态不明确时，默认阻断自动修复或自动合并。

2. 可审计性

所有允许、拒绝和人工审批决策都必须有可追溯记录。审计记录应适合 Reviewer 和 Acceptance Agent 复核，不得只存在于临时控制台输出中。

3. 可配置性

白名单和受限模块规则应由明确的 policy/config 来源管理。不得把临时 sprint 规则硬编码为长期不可见逻辑。规则变更本身应被视为高风险变更，需要 Review 和 Acceptance。

4. 可测试性

必须支持确定性测试，不依赖真实 GitHub 网络状态、真实 Provider、真实券商、真实交易账户或外部 LLM 输出。外部输入应可通过 fixture 或 mock 注入。

5. 可观测性

流水线应能记录以下事件：

- auto-fix candidate detected
- whitelist matched
- whitelist missed
- restricted module touched
- manual approval required
- evidence missing
- tests passed
- tests failed
- auto-merge blocked
- auto-merge candidate accepted

事件中不得包含 secret、token、cookie、账户凭据或券商凭据。

6. 兼容性

功能必须兼容当前分支策略：

- `main` 保持稳定。
- `epic/<date-feature>` 作为集成分支。
- 开发分支使用 `feat/<feature>/<module>`。
- 测试分支使用临时 `test/<feature>/<scope>-<tester>-<timestamp>`。
- review fix 使用 `fix/<feature>/<issue>`。

7. 性能与可靠性

治理检查应在流水线中快速完成，不应显著增加常规 bug fix 的等待时间。即便检查工具异常，也必须返回可解释的 fail-closed 结果，而不是静默通过。

8. 文档要求

后续阶段必须在 `docs/features/bug-auto-fix-system-governance/` 下产出：

- `architecture.md`
- `team-plan.md`
- `phase-<n>-dev-report.md`
- `phase-<n>-test-report.md`
- `opencode-lead-review.md`
- `codex-review-r1.md`
- `acceptance.md`

开发报告和测试报告必须使用中文，并包含变更范围、测试命令、测试结果、安全确认和最终结论。

## Acceptance Criteria

1. 白名单行为验收

给定一个仅修改低风险文档格式的 bug fix candidate，当候选变更符合白名单、未触碰受限模块且审计证据完整时，系统应返回 `ALLOW_AUTO_FIX`，并记录允许原因、文件范围和所需测试。

2. 非白名单行为验收

给定一个修改业务逻辑但不在白名单内的 bug fix candidate，系统必须返回 `BLOCK_NOT_WHITELISTED`，不得允许自动修复或自动合并。

3. 受限模块阻断验收

给定一个触碰 `src/risk_engine/`、`src/execution_engine/`、`src/data_gateway/`、`src/product_app/tools/`、`src/product_app/model_gateway/`、`src/api/` 或其他受限模块的 candidate，系统必须返回 `BLOCK_RESTRICTED_MODULE` 或 `REQUIRE_MANUAL_APPROVAL`，并明确列出触发路径。

4. 真实交易安全验收

任何可能新增、改变或间接放宽真实订单、broker execution、human confirmation、risk veto、stock pool filtering、LEVEL_3_AUTO 暴露的候选修复，必须被阻断并要求人工审批。

5. 审计证据验收

每次判断必须生成结构化审计结果。缺少 `candidate_files`、`decision_reason`、`required_tests`、测试结果或 touched files 证据时，系统必须返回 `BLOCK_INSUFFICIENT_EVIDENCE`。

6. 自动合并门禁验收

当测试失败、review failed、Codex review 三次失败、manual approval required 或 auto-merge policy 不满足时，系统不得自动合并，并必须说明阻断原因。

7. 测试覆盖验收

后续实现必须包含至少以下测试场景：

- 白名单文档修复允许。
- 白名单测试 fixture 修复允许。
- 非白名单业务逻辑修复阻断。
- 受限模块路径阻断。
- 多文件变更中任一受限路径触发整体阻断。
- 缺失审计证据阻断。
- 测试失败阻断。
- secret-like 内容阻断或标记高风险。
- manual approval policy 命中时阻断自动合并。
- stale 或跨 branch artifact 不可作为当前证据。

8. 报告验收

后续 Development 和 Test 阶段必须产出中文报告，报告中明确声明：

- 是否触碰 restricted modules。
- 是否影响真实交易能力。
- 是否改变 Risk Policy 或 Execution Policy。
- 是否绕过 Provider contract、Tool Registry、human confirmation、fail-closed 行为。
- 运行的准确命令和结果。
- 剩余风险和未执行项。

9. 用户可见验收

用户能够从流水线输出或 artifact 中清楚看到：

- 哪个 bug fix candidate 被检查。
- 为什么允许或拒绝。
- 哪些文件触发了风险。
- 需要谁进行人工审批。
- 下一步应由哪个 Agent 或人工角色处理。

10. 最终验收结论要求

Acceptance Agent 只能在以下条件全部满足时给出通过：

- requirements、architecture、dev report、test report、review、acceptance 文档齐备。
- 自动修复治理规则已覆盖白名单、受限模块、审计证据和自动合并门禁。
- normal 和 negative paths 测试通过。
- 未新增真实交易能力。
- 未暴露 `LEVEL_3_AUTO` 为普通用户选项。
- 未绕过 manual merge、human confirmation、risk veto 或 stock pool filtering。

## Safety Constraints

1. 默认禁止真实自动交易

本功能不得新增、修改或启用任何真实交易路径。任何与真实订单、券商执行、账户凭据、订单状态、成交回报相关的变更都必须阻断自动修复并进入人工审批。

2. Risk Agent 与 Risk Engine 一票否决

Bug Auto-Fix 不得修改、绕过、模拟覆盖或自动批准 Risk Agent、Risk Engine、risk veto、kill switch、position sizing risk constraint。

3. 受限模块默认人工审批

所有受限模块变更默认不得自动修复。即使修复看似简单，也必须进入人工审批和完整测试流程。

4. 数据源失败必须 fail closed

治理判断依赖的 diff、policy、test evidence、pipeline state 或 artifact 不可用时，系统不得假设安全，必须返回阻断结果。

5. 不得伪造 live 能力

mock、fixture、paper trading、cache、fallback、stale、shadow 数据不得被描述为 live trading、live provider 或真实执行证据。

6. LLM 权限限制

LLM 不得直接决定买入、卖出、最终仓位、risk override、真实订单、人工确认豁免或自动合并豁免。LLM 输出必须是可校验的结构化解释或分类建议。

7. Secret 保护

任何候选变更、日志、报告或审计 artifact 中不得包含 `.env`、token、key、cookie、账户凭据、券商凭据或其他 secret。发现疑似 secret 必须阻断自动修复并升级人工处理。

8. Product API 边界

如后续实现需要提供产品查询接口，必须位于 `/product/**`。不得新增未批准的 `/api/**` 平行业务前缀。

9. Streamlit 边界

当前 Streamlit Dashboard 仍是有效产品入口。不得在本功能中将其标记为 legacy、deprecated 或待删除。

10. Manual Approval 不可绕过

以下情况必须保留人工审批：

- restricted-module
- live-trading
- risk-policy-change
- execution-policy-change
- main-merge-when-auto-merge-gate-fails
- codex-review-fails-three-times

自动修复系统不得通过配置、重试、LLM 解释或报告覆盖来绕过这些审批要求。