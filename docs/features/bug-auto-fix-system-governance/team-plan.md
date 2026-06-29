# Team Plan: Bug Auto-Fix System Governance — 安全修复白名单、受限模块阻断与审计门禁

> **给执行 Agent：** 本计划由 OpenCode Team Leader（`claude_lead_plan` 阶段，运行时 `opencode-go/deepseek-v4-pro`，`variant=max`，superpowers）产出。架构已明确本功能仅含 1 个交付阶段，实现一个确定性治理评估器。Developer（`opencode-go/deepseek-v4-flash`，`variant=max`，superpowers）实现并自测，Tester（同运行时，superpowers）在临时 `test/...` 分支验证。若测试通过，路由至 OpenCode Lead Review；若测试被拒，路由回 Developer 修复。阶段不得跳跃。Developer 和 Tester 均不得执行 `git commit/push/merge`（由 GitHub Stage Runner 管理）。

**Goal:** 为 Issue-driven Bug Auto-Fix 流程建立确定性治理层：安全修复白名单分类、受限模块路径阻断、审计证据校验、自动合并门禁检查。

**Architecture:** `docs/design/2026-06-29-bug-auto-fix-system-governance-architecture.md`（历史兼容路径）——内容以架构文档为准；本计划对照该文档拆分阶段。

**Tech Stack:** 后端 Python 3.10+（标准库 dataclass / Pydantic）；Policy YAML；审计 artifact JSON/Markdown；测试 pytest；静态检查 ruff + py_compile。

## Inputs Reviewed

| Document | Path |
|---|---|
| Requirements | `docs/requirements/2026-06-29-bug-auto-fix-system-governance-requirements.md` |
| Architecture | `docs/design/2026-06-29-bug-auto-fix-system-governance-architecture.md` |
| MASTER_ROADMAP | `docs/roadmap/MASTER_ROADMAP.md`（V16.4 Bug Auto-Fix System Governance） |
| Agent Pipeline | `docs/process/AGENT_DEVELOPMENT_PIPELINE.md` |
| Branch Workflow | `docs/process/BRANCH_WORKFLOW.md` |
| Automation Architecture | `docs/pipeline/AGENT_AUTOMATION_ARCHITECTURE.md` |
| Auto Merge Policy | `docs/pipeline/AUTO_MERGE_POLICY.md` |
| Self-test Checklist | `docs/policy/SELF_TEST_CHECKLIST.md` |
| Current task state | `.agent/current_task.yaml` |

## Repo Findings by Team Leader

Leader 在拆分前已确认仓库现状，以下结论影响阶段划分：

1. **单体阶段实现**：架构文档明确建议本功能单阶段实现（Phase 1: Bug Auto-Fix Governance Core），`current_task.yaml` 中 `total_phases: 1` 与此一致。本计划不拆分多阶段；单阶段必须覆盖从 policy 到 audit artifact 的完整闭环。

2. **脚本级定位**：架构将治理逻辑定位为 pipeline 脚本（`scripts/pipeline/bug_auto_fix_governance.py`），不进入交易产品运行时模块。仓库中 `scripts/` 目录使用扁平布局，无需深嵌套子包。测试采用仓库约定的扁平测试路径（`tests/pipeline/test_*.py`）。

3. **不新增 API / UI**：架构明确不新增产品 API、不新增 React 前端、不新增 Streamlit 页面。治理结果仅通过 pipeline log、JSON artifact、Markdown summary 和 feature 报告呈现。此决策无需前端栈门禁。

4. **Policy 为安全屏障**：Policy YAML 中 `restricted_paths` 和 `manual_approval_required_for` 是治理决策的数据源头。Policy 变更本身属高风险治理变更，必须经过 Review 和 Acceptance；不得在 bug fix attempt 中临时覆盖。

5. **日期命名兼容**：现存文档使用 `2026-06-29`（带分隔符）位于 `docs/design/` 和 `docs/requirements/`。本 feature 的 canonical report 路径使用 `docs/features/bug-auto-fix-system-governance/` 下的 `phase-<n>-dev-report.md` 和 `phase-<n>-test-report.md`。gate 以 glob 模式匹配，对两种命名均兼容。

6. **当前分支状态**：epic 分支 `epic/20260629-bug-auto-fix-system-governance-issue-122` 已创建，PM 和 Architecture 阶段已通过。当前工作区仅有 pipeline 元数据文件（`.agent/`、`.github/workflows/`、历史报告），无本功能业务实现代码。Developer 必须从 epic 分支创建 `feat/` 分支。

## Scope

1. 新增 `docs/pipeline/bug_auto_fix_governance_policy.yaml`：机器可读的治理 policy（白名单、受限路径、手动审批触发条件、必要证据字段）。
2. 新增 `scripts/pipeline/bug_auto_fix_governance.py`：确定性治理评估器，接收 candidate JSON 与 policy YAML，执行优先级固定决策流程。
3. 新增 `tests/pipeline/test_bug_auto_fix_governance.py`：覆盖 normal（白名单允许）和 negative（受限阻断、非白名单、证据缺失、secret-like、stale/cross-branch artifact）路径。
4. 审计 artifact 输出：JSON（`governance-decision.json`）+ Markdown summary（`governance-summary.md`），含完整决策链路。
5. CLI 接口：支持 `--candidate`、`--policy`、`--out`、`--summary` 参数；exit code 区分允许/阻断/无效输入/内部错误。
6. 产出中文开发报告和测试报告。

## Non-Goals

- 不新增真实交易能力、不修改 broker execution、不暴露 `LEVEL_3_AUTO`。
- 不修改 `src/risk_engine/`、`src/execution_engine/`、`src/data_gateway/`、`src/backtest_engine/`、`src/factor_engine/`、`src/strategy_engine/`、`src/stock_pool/` 及 `src/product_app/` 下所有子包。
- 不修改 `src/api/`、`src/ui_report/`、`config/`、`.github/workflows/`、`scripts/deploy/`。
- 不新增产品 API（`/product/**` 或 `/api/**`）。
- 不新增 React UI 或新 Streamlit 页面。
- 不改 auto-merge policy 的核心语义，仅在流水线中新增调用 gate。
- 不依赖真实 GitHub 网络、真实 Provider、真实券商或外部 LLM 作为决策者。
- 不执行 `git commit/push/merge` 或 GitHub API mutation。

## Safety Constraints（全阶段适用）

1. **Fail-closed 硬约束**：risk_level `unknown`、证据缺失、policy 不可读、diff 不可读、artifact 不新鲜时，默认返回 `BLOCK_INSUFFICIENT_EVIDENCE`。治理工具自身异常不得静默通过。
2. **受限模块阻断**：任一 `touched_file` 命中 `restricted_paths` 时整体阻断，返回 `BLOCK_RESTRICTED_MODULE`。
3. **Secret-like scan**：最低检测规则（`.env`、token/key/secret 关键字、`-----BEGIN PRIVATE KEY-----`、AWS Key ID、broker credential 关键字）。命中疑似 secret 时不回显完整 secret，只记录文件、行号或摘要 hash。
4. **LLM 不是最终裁决者**：治理决策由确定性代码基于 policy、diff、测试证据和 pipeline state 得出。LLM 仅可辅助生成解释和报告。
5. **不伪造 live 能力**：mock/fixture/paper trading/cache/fallback/stale/shadow 数据不得被描述为 live trading 或真实执行证据。
6. **不自动合并 main**，不执行 `git commit/push/merge`（GitHub Stage Runner 管理提交）。
7. 所有核心行为变更必须有测试证据；不得删除、弱化或跳过失败测试来制造通过。

## Global Constraints

- Python 3.10+；静态检查 `ruff`（配置 `pyproject.toml`）与 `py_compile`。
- 测试 `pytest`；外部依赖必须 mock；不依赖真实 GitHub 网络、Provider、券商、LLM。
- 代码标识、JSON key、环境变量、第三方术语保留英文；用户可见输出与新增文档默认中文。
- 测试隔离：统一传 `--basetemp=runtime/pytest-tmp-bug-auto-fix-system-governance`。
- 开发报告必须记录准确运行命令和结果；tester 必须覆盖 normal + negative paths。

---

## Proposed Phases

本功能为单体阶段交付，Phase 1 覆盖治理核心闭环。

### Phase 1 — Bug Auto-Fix Governance Core（完整治理闭环）

| Field | Value |
|---|---|
| **Phase ID** | 1 |
| **Scope** | 新增 Policy YAML、治理评估器、审计 artifact（JSON + Markdown）、CLI 接口。实现优先级固定决策流程（policy 可读 → 证据完整 → stale/cross-branch 检测 → secret scan → 受限模块检测 → manual approval trigger → 白名单匹配 → 测试验证 → auto-merge gate → ALLOW_AUTO_FIX）。输出结构化 GovernanceDecision JSON 与 human-readable summary。 |
| **Non-Goals** | 不新增产品 API；不新增 UI；不修改受限模块；不接入真实 GitHub mutation；不依赖外部 LLM 做最终裁决；不修改 auto-merge policy 核心语义。 |
| **Owner** | OpenCode Developer（`claude_developer`，`opencode-go/deepseek-v4-flash`，`variant=max`，superpowers） |
| **Branch** | `feat/bug-auto-fix-system-governance/core`（自 `epic/20260629-bug-auto-fix-system-governance-issue-122` 分支） |
| **Restricted modules** | 不触碰任何受限模块；新增代码仅限于 `scripts/pipeline/`、`docs/pipeline/`、`tests/pipeline/`、`docs/features/bug-auto-fix-system-governance/`。 |
| **Dev report** | `docs/features/bug-auto-fix-system-governance/phase-1-dev-report.md` |
| **Test report** | `docs/features/bug-auto-fix-system-governance/phase-1-test-report.md` |

**Files:**

- Create: `docs/pipeline/bug_auto_fix_governance_policy.yaml`
- Create: `scripts/pipeline/bug_auto_fix_governance.py`
- Create: `tests/pipeline/test_bug_auto_fix_governance.py`
- Create: `docs/features/bug-auto-fix-system-governance/phase-1-dev-report.md`
- Create: `docs/features/bug-auto-fix-system-governance/phase-1-test-report.md`

None of these files are in restricted modules. No existing production code is modified.

**Policy YAML (`docs/pipeline/bug_auto_fix_governance_policy.yaml`):**

必须包含且仅包含以下顶层 section（字段含义与架构文档和需求文档一致）：

```yaml
version: 1
feature_id: bug-auto-fix-system-governance

allowed_fix_types:
  documentation_low_risk:  # docs/**/*.md, *.md; typo/formatting/link_fix/heading_fix
  test_fixture_low_risk:   # tests/**/fixtures/**, tests/**/*fixture*, tests/**/*.py; fixture_update/assertion_correction/temp_dir_isolation
  non_behavioral_lint:     # **/*.py; import_sort/typing_only/unused_import/dead_code_non_runtime (forbidden_paths: src/**)

restricted_paths:     # 完整路径列表，与需求文档 F-002 一致
manual_approval_required_for:  # restricted-module, live-trading, risk-policy-change, execution-policy-change, main-merge-when-auto-merge-gate-fails, codex-review-fails-three-times, secret-like-content, insufficient-evidence
required_evidence_fields:      # feature_id, issue_number, run_id, branch, base_branch, stage, candidate_files, change_summary, touched_files, test_commands, test_results, review_status, audit_artifact_path
```

**治理评估器 (`scripts/pipeline/bug_auto_fix_governance.py`):**

核心能力：

- 读取 candidate metadata JSON（`BugAutoFixCandidate` 字段集）。
- 读取 policy YAML/JSON。
- 规范化 candidate/touched file paths（Windows backslash → POSIX slash；去除 leading `./`；禁止路径穿越）。
- 按固定优先级执行 10 步决策流程（步骤顺序、逻辑和返回与架构文档伪代码一致）。
- 匹配白名单 path_pattern + change_kind + forbidden_paths（若命中 `forbidden_paths` 则跳过该 fix_type）。
- 匹配受限模块路径（glob 匹配，支持 `**`）。
- 检查 manual approval triggers（关键字检测 + policy 命中）。
- 检查必要 evidence 字段完整性。
- 检查 test evidence：exit code 非 0 或 commands 为空则测试失败；stale/cross-branch artifact 判断（branch 不匹配 或 run_id 不匹配则不可用）。
- 扫描 secret-like 内容（`.env`、`token=`、`api_key=`、`secret=`、`password=`、`AKIA[0-9A-Z]{16}`、`-----BEGIN PRIVATE KEY-----`、broker credential keywords、cookie/session credential keywords），命中时脱敏输出。
- 输出 `GovernanceDecision` JSON 到 `--out`，输出 Markdown summary 到 `--summary`。
- Exit code 映射：`0` = ALLOW_AUTO_FIX and gate passed；`2` = blocked or manual approval required；`3` = invalid input or insufficient evidence；`4` = internal evaluator error（fail closed）。

数据模型使用标准库 `dataclass` 或 Pydantic；优先 `dataclass` 以降低脚本级运行依赖。

**测试文件 (`tests/pipeline/test_bug_auto_fix_governance.py`):**

必须覆盖以下 16 个场景（对应需求验收标准）：

| # | 场景 | 预期决策 | 类型 |
|---|---|---|---|
| 1 | 白名单文档修复（仅修改 `docs/README.md` typo，证据完整） | `ALLOW_AUTO_FIX` | normal |
| 2 | 白名单测试 fixture 修复（仅修改 `tests/fixtures/input.csv`） | `ALLOW_AUTO_FIX` | normal |
| 3 | 白名单测试断言修正（仅修改 `tests/test_foo.py` 断言，不触碰受限模块） | `ALLOW_AUTO_FIX` | normal |
| 4 | 非白名单业务逻辑修复（修改 `src/product_app/feedback_service.py`，不在任何白名单） | `BLOCK_NOT_WHITELISTED` | negative |
| 5 | 受限模块路径阻断（修改 `src/risk_engine/risk_evaluator.py`） | `BLOCK_RESTRICTED_MODULE` | negative |
| 6 | 受限模块路径阻断（修改 `src/execution_engine/broker.py`） | `BLOCK_RESTRICTED_MODULE` | negative |
| 7 | 受限模块路径阻断（修改 `src/data_gateway/provider.py`） | `BLOCK_RESTRICTED_MODULE` | negative |
| 8 | 受限模块路径阻断（修改 `src/product_app/tools/tool.py`） | `BLOCK_RESTRICTED_MODULE` | negative |
| 9 | 多文件变更中任一受限路径触发整体阻断（修改 `docs/README.md` + `src/risk_engine/eval.py`） | `BLOCK_RESTRICTED_MODULE` | negative |
| 10 | 缺失 `candidate_files` 证据 | `BLOCK_INSUFFICIENT_EVIDENCE` | negative |
| 11 | 缺失 `decision_reason` 或无法生成 audit artifact | `BLOCK_INSUFFICIENT_EVIDENCE` | negative |
| 12 | 缺失 `required_tests` 或 test evidence 为空 | `BLOCK_INSUFFICIENT_EVIDENCE` | negative |
| 13 | 测试失败（test evidence exit_code != 0） | `BLOCK_INSUFFICIENT_EVIDENCE` | negative |
| 14 | secret-like 内容检测（diff 中包含 `password=123456`） | `REQUIRE_MANUAL_APPROVAL` | negative |
| 15 | manual approval policy 命中（candidate 涉及 `live-trading` 关键字） | `REQUIRE_MANUAL_APPROVAL` | negative |
| 16 | stale / cross-branch artifact（artifact branch != current branch） | `BLOCK_INSUFFICIENT_EVIDENCE` | negative |

额外边界测试（建议实现，不强制，但计入 tester 覆盖率要求）：

| # | 场景 | 预期决策 | 类型 |
|---|---|---|---|
| 17 | policy 文件不可读或解析失败 | `BLOCK_INSUFFICIENT_EVIDENCE` | negative |
| 18 | candidate 输入 JSON 无效（无法解析） | `BLOCK_INSUFFICIENT_EVIDENCE` | negative |
| 19 | Codex review 三次失败标记（`codex_review_attempts >= 3`） | `REQUIRE_MANUAL_APPROVAL` | negative |
| 20 | workflow/merge policy/runner/deployment 文件命中 | `REQUIRE_MANUAL_APPROVAL` | negative |

**Self-Test Commands（Developer 必须运行并记录结果）:**

```bash
git status --short --branch
git diff --stat
./.venv/bin/python -m pytest tests/pipeline/test_bug_auto_fix_governance.py -q --basetemp=runtime/pytest-tmp-bug-auto-fix-system-governance
./.venv/bin/python -m ruff check scripts/pipeline/bug_auto_fix_governance.py tests/pipeline/test_bug_auto_fix_governance.py
./.venv/bin/python -m py_compile scripts/pipeline/bug_auto_fix_governance.py
git diff --check
```

若实现过程中参考了其他 pipeline 测试文件或共享模块：

```bash
./.venv/bin/python -m pytest tests/pipeline/ -q --tb=short --basetemp=runtime/pytest-tmp-bug-auto-fix-system-governance-full
```

**Tester Verification Commands（Tester 必须运行并记录结果）:**

```bash
git status --short --branch
git switch feat/bug-auto-fix-system-governance/core
git switch -c test/bug-auto-fix-system-governance/core-tester-$(date +%Y%m%d-%H%M)
# --- 在此临时分支上运行测试 ---
./.venv/bin/python -m pytest tests/pipeline/test_bug_auto_fix_governance.py -v --tb=long --basetemp=runtime/pytest-tmp-bug-auto-fix-system-governance-test
./.venv/bin/python -m ruff check scripts/pipeline/bug_auto_fix_governance.py tests/pipeline/test_bug_auto_fix_governance.py
./.venv/bin/python -m py_compile scripts/pipeline/bug_auto_fix_governance.py
git diff --check
# --- 验证 CLI exit code ---
./.venv/bin/python scripts/pipeline/bug_auto_fix_governance.py --help
# --- 结束：回到开发分支并删除临时分支 ---
git switch feat/bug-auto-fix-system-governance/core
git branch -D test/bug-auto-fix-system-governance/core-tester-$(date +%Y%m%d-%H%M)
```

**Release Criteria（Phase 1 通过条件）:**

- [ ] `docs/pipeline/bug_auto_fix_governance_policy.yaml` 存在且包含所有 required sections。
- [ ] `scripts/pipeline/bug_auto_fix_governance.py` 实现完整 10 步决策流程且 exit code 正确。
- [ ] `tests/pipeline/test_bug_auto_fix_governance.py` 覆盖至少 16 个 mandatory 场景，全部 PASS。
- [ ] ruff check 通过（零 warning/error 在 touched Python 文件中）。
- [ ] py_compile 通过。
- [ ] `git diff --check` 通过（无 whitespace 错误）。
- [ ] 开发报告 `phase-1-dev-report.md` 包含：requirement/architecture path、changed files、feature-to-code mapping、exact test commands and results、restricted module non-touch confirmation、real trading capability non-affectation confirmation。
- [ ] 测试报告 `phase-1-test-report.md` 包含：test environment、scope、requirement coverage matrix、test results、data-quality and fail-closed evidence、defect list、final result（`PASS` / `PASS_WITH_NOTES` / `REJECTED`）。
- [ ] 未触及任何受限模块路径（`src/risk_engine/`、`src/execution_engine/`、`src/data_gateway/`、`src/backtest_engine/`、`src/factor_engine/`、`src/strategy_engine/`、`src/product_app/` 子包、`src/api/`、`src/ui_report/`、`config/`、`.github/workflows/`、`scripts/deploy/`）。
- [ ] 审计 artifact（`governance-decision.json` + `governance-summary.md`）可在测试 fixture 下成功生成且内容完整。

**Pass/Fail Routing:**

| Phase 1 测试结果 | 路由 |
|---|---|
| `PASS` | 路由至 OpenCode Lead Review（`claude_lead_review` 阶段） |
| `PASS_WITH_NOTES` | 路由至 OpenCode Lead Review，同时记录 notes 供 reviewer 裁决 |
| `REJECTED` | 路由回 OpenCode Developer 修复；修复后重新进入 Test 循环 |
| 测试循环超过 3 次 | 转为人工审批，生成 `r3-failure.md` 记录原因 |

---

## Phase Summary

| Phase | Scope | Branch | Owner | Test Result → Next |
|---|---|---|---|---|
| Phase 1 | Policy + Evaluator + Audit + CLI + Tests | `feat/bug-auto-fix-system-governance/core` | OpenCode Developer | PASS → Lead Review; REJECTED → Fix; 3x rejection → Manual |

## Routing After All Phases Complete

单阶段完成后，Tester 产出 `phase-1-test-report.md`，若最终结果为 `PASS` 或 `PASS_WITH_NOTES`：

- **Next stage:** `claude_lead_review`（OpenCode Lead Review），由 OpenCode Team Leader（`opencode-go/deepseek-v4-pro`，`variant=max`，superpowers）执行。
- Lead Review 输出：`docs/features/bug-auto-fix-system-governance/opencode-lead-review.md`。
- Lead Review 通过后，路由至 Codex B Reviewer（`codex_review` 阶段）进行最终架构审查。
- Codex Review 输出：`docs/features/bug-auto-fix-system-governance/codex-review-r1.md`。
- Codex Review 通过后，路由至 Codex A Acceptance Agent（`acceptance` 阶段）进行 PM 验收。
- Acceptance 输出：`docs/features/bug-auto-fix-system-governance/acceptance.md`。
- Acceptance 通过后，由 merge gate 决定自动合并或人工审批后合并。

## Restricted Module Declaration

本功能所有新增文件均在以下非受限路径内：

```text
scripts/pipeline/bug_auto_fix_governance.py
docs/pipeline/bug_auto_fix_governance_policy.yaml
tests/pipeline/test_bug_auto_fix_governance.py
docs/features/bug-auto-fix-system-governance/
```

**无任何文件位于需求文档 F-002 所列受限模块路径中。** Developer 必须确认：若实现过程中发现必须触碰受限模块，立即停止并路由回 Architect 和 PM 审批。
