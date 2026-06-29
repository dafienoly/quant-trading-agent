# bug-auto-fix-system-governance Architecture

## Architecture Summary

本功能为 Issue-driven Bug Auto-Fix 流程增加治理层，目标是在自动修复真正修改代码、进入 review 或成为 auto-merge candidate 前，先执行确定性的风险分类、受限模块阻断、审计证据校验和自动合并门禁检查。

架构定位：

- 路线图归属：`V16.4 Quant Tool Registry` 相关治理能力。
- Feature ID：`bug-auto-fix-system-governance`。
- Issue：`#122`。
- 当前阶段：Architecture，仅输出设计，不写生产代码。
- 运行入口：流水线或本地 automation 脚本调用，不新增用户前端。
- 默认行为：fail closed。风险未知、证据缺失、路径无法分类、测试未运行、artifact 过期或策略冲突时，阻断自动修复或自动合并。

治理层不负责生成补丁，不负责决定业务修复方案，也不负责放宽任何安全策略。它只回答两个问题：

1. 这个 bug fix candidate 是否允许由自动修复 Agent 处理？
2. 这个修复结果是否具备进入自动合并候选的最低证据？

核心输出是结构化治理决策：

```json
{
  "feature_id": "bug-auto-fix-system-governance",
  "issue_number": 122,
  "run_id": "28371421444",
  "candidate_files": [],
  "change_summary": "",
  "risk_level": "unknown",
  "allowed_by_whitelist": false,
  "restricted_module_touched": false,
  "manual_approval_required": true,
  "auto_fix_decision": "BLOCK_INSUFFICIENT_EVIDENCE",
  "decision_reason": "",
  "required_tests": [],
  "audit_artifact_path": ""
}
```

`auto_fix_decision` 只能是：

- `ALLOW_AUTO_FIX`
- `BLOCK_RESTRICTED_MODULE`
- `BLOCK_NOT_WHITELISTED`
- `BLOCK_INSUFFICIENT_EVIDENCE`
- `REQUIRE_MANUAL_APPROVAL`

高层数据流：

```text
Issue metadata / pipeline state / candidate diff / policy source / test evidence / review evidence
  -> BugAutoFixGovernanceEvaluator
  -> whitelist classifier
  -> restricted module detector
  -> evidence validator
  -> secret-like scanner
  -> auto-merge gate evaluator
  -> governance decision JSON
  -> audit artifact + pipeline summary
  -> downstream OpenCode Lead / Developer / Tester / Reviewer / Acceptance
```

本功能不新增真实交易能力，不修改 Risk Engine、Execution Engine、Provider Hub、Model Gateway、Tool Registry、Stock Pool、Backtest、Strategy 或产品 API 行为。

## Module Plan

### 1. 建议新增模块边界

建议将治理实现放在流水线自动化边界内，避免进入交易产品运行时模块。

建议位置：

```text
scripts/pipeline/bug_auto_fix_governance.py
tests/pipeline/test_bug_auto_fix_governance.py
docs/pipeline/bug_auto_fix_governance_policy.yaml
docs/features/bug-auto-fix-system-governance/phase-1-dev-report.md
docs/features/bug-auto-fix-system-governance/phase-1-test-report.md
```

说明：

- `scripts/pipeline/bug_auto_fix_governance.py`：确定性治理检查器，可由 GitHub Actions、本地 runner 或 OpenCode pipeline 调用。
- `docs/pipeline/bug_auto_fix_governance_policy.yaml`：白名单、受限路径、人工审批触发条件、必要证据字段的机器可读 policy。
- `tests/pipeline/test_bug_auto_fix_governance.py`：使用 fixture/mock 输入验证 normal 和 negative paths。
- `docs/features/bug-auto-fix-system-governance/`：阶段报告、review、acceptance、user guide 的 canonical feature 目录。

不得将治理逻辑放入以下路径：

```text
src/risk_engine/
src/execution_engine/
src/data_gateway/
src/backtest_engine/
src/factor_engine/
src/strategy_engine/
src/product_app/tools/
src/product_app/model_gateway/
src/product_app/market_data/
src/api/
src/ui_report/
config/
```

原因：

- 这些模块是受限模块或产品运行时边界。
- 本功能是 pipeline governance，不应改变产品交易、数据、模型、工具或 UI 行为。
- `config/` 也被需求列为敏感区域，治理 policy 不应放入该目录。

### 2. Policy 模型

建议 policy 使用 YAML 或 JSON，开发阶段优先 YAML，便于 reviewer 直接阅读。

示例结构：

```yaml
version: 1
feature_id: bug-auto-fix-system-governance

allowed_fix_types:
  documentation_low_risk:
    path_patterns:
      - "docs/**/*.md"
      - "*.md"
    allowed_change_kinds:
      - typo
      - formatting
      - link_fix
      - heading_fix
    required_tests:
      - "git diff --check"

  test_fixture_low_risk:
    path_patterns:
      - "tests/**/fixtures/**"
      - "tests/**/*fixture*"
      - "tests/**/*.py"
    allowed_change_kinds:
      - fixture_update
      - assertion_correction
      - temp_dir_isolation
    forbidden_if_touches_restricted_module: true
    required_tests:
      - "related pytest scope"
      - "git diff --check"

  non_behavioral_lint:
    path_patterns:
      - "**/*.py"
    allowed_change_kinds:
      - import_sort
      - typing_only
      - unused_import
      - dead_code_non_runtime
    forbidden_paths:
      - "src/**"
    required_tests:
      - "ruff check touched files"
      - "py_compile touched src files when applicable"
      - "git diff --check"

restricted_paths:
  - "src/risk_engine/**"
  - "src/execution_engine/**"
  - "src/data_gateway/**"
  - "src/backtest_engine/**"
  - "src/factor_engine/**"
  - "src/strategy_engine/**"
  - "src/product_app/agentops/**"
  - "src/product_app/market_data/**"
  - "src/product_app/tools/**"
  - "src/product_app/model_gateway/**"
  - "src/product_app/decisions/**"
  - "src/product_app/position_sizing/**"
  - "src/product_app/backtests/**"
  - "src/product_app/risk_sentinel/**"
  - "src/product_app/fundamental/**"
  - "src/product_app/alpha/**"
  - "src/product_app/paper_trading/**"
  - "src/product_app/broker_shadow/**"
  - "src/api/**"
  - "src/ui_report/**"
  - "config/**"
  - ".github/workflows/**"
  - "scripts/deploy/**"
  - "**/.env"
  - "**/.env.*"

manual_approval_required_for:
  - restricted-module
  - live-trading
  - risk-policy-change
  - execution-policy-change
  - main-merge-when-auto-merge-gate-fails
  - codex-review-fails-three-times
  - secret-like-content
  - insufficient-evidence

required_evidence_fields:
  - feature_id
  - issue_number
  - run_id
  - branch
  - base_branch
  - stage
  - candidate_files
  - change_summary
  - touched_files
  - test_commands
  - test_results
  - review_status
  - audit_artifact_path
```

Policy 变更本身必须视为高风险治理变更：

- 必须经过 Review 和 Acceptance。
- 不得由 LLM 自动放宽。
- 不得在 bug fix attempt 中临时覆盖。

### 3. 数据模型

建议使用 dataclass 或 Pydantic。若仓库已对 pipeline scripts 使用标准库 dataclass，则优先复用标准库，降低依赖和运行风险。

核心模型：

```python
class BugAutoFixCandidate:
    feature_id: str
    issue_number: int
    issue_url: str | None
    run_id: str
    branch: str
    base_branch: str
    stage: str
    candidate_files: list[str]
    touched_files: list[str]
    change_summary: str
    change_kind: str | None
    diff_stats: dict[str, int]
    test_evidence: list[TestEvidence]
    review_evidence: ReviewEvidence | None
    artifact_branch: str | None
    artifact_run_id: str | None

class TestEvidence:
    command: str
    exit_code: int
    summary: str
    started_at: str | None
    completed_at: str | None

class GovernanceDecision:
    feature_id: str
    issue_number: int
    run_id: str
    candidate_files: list[str]
    change_summary: str
    risk_level: str
    allowed_by_whitelist: bool
    restricted_module_touched: bool
    restricted_paths: list[str]
    manual_approval_required: bool
    manual_approval_reasons: list[str]
    auto_fix_decision: str
    decision_reason: str
    required_tests: list[str]
    audit_artifact_path: str
    evidence_status: str
    test_status: str
    secret_scan_status: str
    auto_merge_eligible: bool
```

### 4. 决策流程

决策顺序必须固定，避免后续条件覆盖更高优先级的安全阻断。

优先级：

1. 输入或 policy 不可读取：`BLOCK_INSUFFICIENT_EVIDENCE`
2. 缺少必要证据字段：`BLOCK_INSUFFICIENT_EVIDENCE`
3. artifact 非当前 branch 或非当前 run：`BLOCK_INSUFFICIENT_EVIDENCE`
4. 疑似 secret：`REQUIRE_MANUAL_APPROVAL`
5. 触碰受限模块：`BLOCK_RESTRICTED_MODULE`
6. 触发 live trading、risk policy、execution policy、human confirmation、LEVEL_3_AUTO 相关关键字：`REQUIRE_MANUAL_APPROVAL`
7. 不匹配白名单：`BLOCK_NOT_WHITELISTED`
8. 测试未运行或失败：`BLOCK_INSUFFICIENT_EVIDENCE`
9. review/acceptance/auto-merge policy 未满足：`REQUIRE_MANUAL_APPROVAL`
10. 全部满足：`ALLOW_AUTO_FIX`

伪代码：

```python
def evaluate_candidate(candidate, policy) -> GovernanceDecision:
    if not policy.loaded:
        return block_insufficient("policy unavailable")

    missing = validate_required_evidence(candidate, policy.required_evidence_fields)
    if missing:
        return block_insufficient(f"missing evidence fields: {missing}")

    if is_stale_or_cross_branch_artifact(candidate):
        return block_insufficient("artifact does not belong to current branch/run")

    secret_hits = scan_secret_like_content(candidate)
    if secret_hits:
        return require_manual("secret-like content detected", secret_hits)

    restricted_hits = match_paths(candidate.touched_files, policy.restricted_paths)
    if restricted_hits:
        return block_restricted("restricted module touched", restricted_hits)

    approval_hits = detect_manual_approval_triggers(candidate, policy)
    if approval_hits:
        return require_manual("manual approval policy matched", approval_hits)

    whitelist_match = match_whitelist(candidate, policy.allowed_fix_types)
    if not whitelist_match:
        return block_not_whitelisted("candidate does not match safe auto-fix whitelist")

    test_status = validate_tests(candidate.test_evidence, whitelist_match.required_tests)
    if not test_status.passed:
        return block_insufficient(f"required tests missing or failed: {test_status.reason}")

    merge_gate = validate_auto_merge_gate(candidate)
    if not merge_gate.passed:
        return require_manual(f"auto-merge gate failed: {merge_gate.reason}")

    return allow_auto_fix(
        reason="candidate matched whitelist, touched no restricted modules, evidence complete, tests passed"
    )
```

### 5. 审计 artifact

每次判断必须生成结构化审计 artifact。建议 runtime 路径：

```text
runtime/agent_audit/bug-auto-fix-system-governance/<run_id>/governance-decision.json
runtime/agent_audit/bug-auto-fix-system-governance/<run_id>/governance-summary.md
```

流水线中应上传为 artifact。不得只输出在控制台。

JSON 内容必须包含：

- 原始 bug 或失败输入来源。
- Agent 身份和阶段。
- candidate files。
- touched files。
- 允许或阻断依据。
- 白名单匹配结果。
- 受限路径命中结果。
- secret-like scan 结果。
- 测试命令、退出码和摘要。
- review/acceptance gate 状态。
- 是否影响真实交易能力。
- 是否需要人工审批。
- 最终门禁结论。

Markdown summary 用于人读，JSON 用于下游 gate 读取。

### 6. Pipeline 集成点

建议在三个位置集成：

```text
bug candidate detected
  -> pre-fix governance check

developer produced diff
  -> post-fix governance check

before auto-merge candidate
  -> final auto-merge governance gate
```

#### Pre-fix check

目的：判断是否允许自动修复 Agent 开始处理。

输入：

- Issue metadata。
- 初步失败摘要。
- 预估 candidate files。
- pipeline state。

输出：

- `ALLOW_AUTO_FIX`：允许进入自动修复。
- 其他决策：不启动自动修复，转人工处理。

#### Post-fix check

目的：Developer 生成 diff 后重新读取当前分支真实 touched files，防止修复过程越界。

输入：

- 当前 `git diff --name-only`。
- 当前 `git diff --stat`。
- Developer 声明测试结果。
- policy。

输出：

- 若触碰受限模块或超出白名单，阻断后续自动合并。
- 若证据不足，要求补充测试或人工审批。

#### Final auto-merge gate

目的：在 auto-merge 前做最后 fail-closed 判断。

必须重新校验：

- 当前 branch。
- 当前 run_id。
- 当前 diff。
- 测试结果 freshness。
- `git diff --check`。
- secret-like scan。
- Review/Acceptance 状态。
- manual approval 状态。
- Codex review attempt count。

## Technical Decisions

### 1. 不新增产品 API

本阶段不新增 API。治理结果优先通过 pipeline log、JSON artifact、Markdown summary 和 feature 报告呈现。

如果未来需要产品内查询能力，必须使用：

```text
/product/**
```

不得新增平行业务前缀 `/api/**`。

### 2. 不新增 React 前端

本功能不需要新 UI。状态展示优先使用：

- GitHub Actions log。
- pipeline artifact。
- feature report。
- 现有 Streamlit Dashboard 的既有入口。

不得将 Streamlit 标记为 legacy、deprecated 或待删除。

### 3. 使用确定性规则，不依赖 LLM 作为最终裁决

LLM 可用于解释和报告，但最终门禁必须由确定性代码基于 policy、diff、测试证据和 pipeline state 得出。

LLM 不得：

- 放宽白名单。
- 解除受限模块阻断。
- 批准真实交易、风控、执行、风险策略或自动合并豁免。
- 隐藏测试失败。
- 将 mock/stale/fallback 证据描述为 live 能力。

### 4. 路径匹配使用显式 glob policy

路径判断必须使用规范化路径：

```text
Windows backslash -> POSIX slash
去除 leading ./
禁止路径穿越
大小写按仓库实际文件系统处理
```

多文件 candidate 中只要任一文件命中受限路径，整体阻断。

### 5. Secret-like scan 是阻断或人工审批条件

最低检测规则：

```text
.env
.env.*
token=
api_key=
secret=
password=
AKIA[0-9A-Z]{16}
-----BEGIN PRIVATE KEY-----
broker credential keywords
cookie/session credential keywords
```

命中疑似 secret 时，不应在 artifact 中回显完整 secret，只记录文件、行号或摘要 hash。

### 6. 测试证据必须 fresh

测试证据必须满足：

- 属于当前 branch。
- 属于当前 run_id 或当前本地验证上下文。
- 时间晚于当前 candidate diff 生成时间，或由当前 post-fix gate 同步采集。
- 命令、退出码、摘要完整。
- 失败或未运行均不允许自动合并。

跨 branch artifact、旧 run artifact、手写不可验证测试摘要不得作为 auto-merge 证据。

### 7. 风险等级建议

`risk_level` 可使用：

```text
low
medium
high
unknown
```

映射规则：

- `low`：白名单内、非受限路径、证据完整、测试通过。
- `medium`：白名单边界不清、测试覆盖不足、但未触碰 restricted modules。
- `high`：触碰受限模块、secret-like、manual approval trigger、auto-merge gate failure。
- `unknown`：输入不足、policy 不可读、diff 不可读、artifact 不新鲜。

只有 `low` 且所有 gate 通过时，才可返回 `ALLOW_AUTO_FIX`。

### 8. Auto-merge eligibility 与 auto-fix decision 分离

`ALLOW_AUTO_FIX` 只表示允许自动修复流程处理候选；是否进入自动合并候选还必须满足 final auto-merge gate。

建议输出中同时包含：

```json
{
  "auto_fix_decision": "ALLOW_AUTO_FIX",
  "auto_merge_eligible": true
}
```

若测试失败或 review 未通过：

```json
{
  "auto_fix_decision": "ALLOW_AUTO_FIX",
  "auto_merge_eligible": false,
  "manual_approval_required": true
}
```

### 9. 错误处理

治理工具自身异常不得静默通过。

规则：

- policy parse 失败：`BLOCK_INSUFFICIENT_EVIDENCE`
- diff 读取失败：`BLOCK_INSUFFICIENT_EVIDENCE`
- test evidence 不可读：`BLOCK_INSUFFICIENT_EVIDENCE`
- artifact 写入失败：阻断 auto-merge
- 未识别 decision enum：阻断 auto-merge
- 未识别 risk_level：按 `unknown` 处理

## Safety Impact

本功能是安全增强，不应扩大任何交易能力。

必须保持以下不变量：

- 不新增真实订单路径。
- 不修改 broker execution。
- 不修改 human confirmation。
- 不修改 Risk Agent、Risk Engine、risk veto、kill switch。
- 不修改 stock pool filtering。
- 不修改 Provider contract、fallback、data quality gate。
- 不修改 Model Gateway 或 Tool Registry 权限边界。
- 不暴露 `LEVEL_3_AUTO` 为普通用户选项。
- 不把 mock、fixture、paper trading、cache、fallback、stale、shadow 数据描述为 live 能力。
- 不绕过 PM、Architecture、Development、Test、Review、Acceptance 阶段门禁。

受限模块命中时，默认结果：

```text
BLOCK_RESTRICTED_MODULE
```

需要人工审批但不一定是路径命中的情况：

```text
REQUIRE_MANUAL_APPROVAL
```

必须人工审批的触发项：

- `restricted-module`
- `live-trading`
- `risk-policy-change`
- `execution-policy-change`
- `main-merge-when-auto-merge-gate-fails`
- `codex-review-fails-three-times`
- secret-like content
- insufficient or stale evidence

安全审查清单：

```text
是否符合 docs/roadmap/MASTER_ROADMAP.md？
是否未新增真实交易能力？
是否未触碰 restricted modules，或已阻断并要求人工审批？
是否保留 /product/** API 边界？
是否保留 Streamlit 当前有效入口？
是否使用确定性 policy，而不是 LLM 最终裁决？
是否 fail closed？
是否生成结构化 audit artifact？
是否阻断 stale/cross-branch artifact？
是否阻断 secret-like 内容？
是否保留 manual merge 和 human confirmation 边界？
```

## Development Guidance

### Phase Slice

本功能建议单阶段实现，Phase 1 覆盖治理核心闭环。

#### Phase 1：Bug Auto-Fix Governance Core

范围：

- 新增 policy 文件。
- 新增 governance evaluator。
- 新增 CLI 或 pipeline-callable 函数。
- 新增 JSON/Markdown audit artifact 输出。
- 新增 deterministic tests。
- 新增中文开发报告和测试报告。

不包含：

- 不接入真实交易。
- 不新增产品 API。
- 不新增 React UI。
- 不修改受限模块。
- 不改 auto-merge policy 的核心语义，只在流水线中新增调用 gate。
- 不依赖真实 GitHub 网络、真实 Provider、真实券商或外部 LLM。

### OpenCode Lead Handoff

OpenCode Lead 需要产出 `docs/features/bug-auto-fix-system-governance/team-plan.md`，计划中必须明确：

- 只有 1 个 phase。
- Developer 不得触碰受限模块。
- Tester 必须覆盖 normal 和 negative paths。
- 若实现过程中发现必须修改 workflow、merge policy、权限、runner 或 deployment 配置，应停止并转人工审批。
- 若 policy 需要放宽，应退回 Architecture/PM，不得由 Developer 自行修改目标。
- 若 Codex review 连续三次失败，必须进入人工审批，不得继续自动重试绕过。

### OpenCode Developer Handoff

Developer 实现时必须先检查：

```bash
git status --short --branch
git diff --stat
```

建议 touched files：

```text
scripts/pipeline/bug_auto_fix_governance.py
docs/pipeline/bug_auto_fix_governance_policy.yaml
tests/pipeline/test_bug_auto_fix_governance.py
docs/features/bug-auto-fix-system-governance/phase-1-dev-report.md
```

Developer 不得修改：

```text
src/risk_engine/
src/execution_engine/
src/data_gateway/
src/backtest_engine/
src/factor_engine/
src/strategy_engine/
src/product_app/
src/api/
src/ui_report/
config/
```

最低实现能力：

- 读取 candidate metadata JSON。
- 读取 policy YAML/JSON。
- 规范化 candidate/touched file paths。
- 匹配白名单。
- 匹配受限模块。
- 检查 manual approval triggers。
- 检查必要 evidence 字段。
- 检查 test evidence exit code。
- 检查 stale/cross-branch artifact。
- 扫描 secret-like 内容并脱敏输出。
- 输出 governance decision JSON。
- 输出 human-readable Markdown summary。
- 非 0 exit code 用于阻断自动流程。

建议 CLI：

```bash
./.venv/bin/python scripts/pipeline/bug_auto_fix_governance.py \
  --candidate runtime/agent_audit/input/bug-fix-candidate.json \
  --policy docs/pipeline/bug_auto_fix_governance_policy.yaml \
  --out runtime/agent_audit/bug-auto-fix-system-governance/<run_id>/governance-decision.json \
  --summary runtime/agent_audit/bug-auto-fix-system-governance/<run_id>/governance-summary.md
```

建议 exit code：

```text
0 = ALLOW_AUTO_FIX and gate passed for requested mode
2 = blocked or manual approval required
3 = invalid input or insufficient evidence
4 = internal evaluator error, treated as fail closed
```

开发报告必须写入：

```text
docs/features/bug-auto-fix-system-governance/phase-1-dev-report.md
```

报告必须包含：

- Requirement document path。
- Architecture document path。
- Roadmap section reference。
- Changed files。
- Feature-to-code mapping。
- Added or updated tests。
- Exact commands and results。
- Data source and data-quality handling。
- API contract impact。
- UI impact。
- Agent / LLM boundary impact。
- Skipped or not-run items with reasons。
- Remaining risks。
- Whether real trading capability is affected。
- 是否确认未绕过 risk、stock-pool filtering、human confirmation、provider contracts、Tool Registry、fail-closed behavior。

### OpenCode Tester Handoff

Tester 必须创建临时测试分支，测试结束后回到原开发分支并删除临时分支。

必须覆盖测试场景：

1. 白名单文档修复允许。
2. 白名单测试 fixture 修复允许。
3. 非白名单业务逻辑修复阻断。
4. 受限模块路径阻断。
5. 多文件变更中任一受限路径触发整体阻断。
6. 缺失 `candidate_files` 阻断。
7. 缺失 `decision_reason` 或无法生成 audit artifact 阻断。
8. 缺失 `required_tests` 或 test evidence 阻断。
9. 测试失败阻断。
10. secret-like 内容阻断或要求人工审批。
11. manual approval policy 命中时阻断自动合并。
12. stale artifact 不可作为当前证据。
13. cross-branch artifact 不可作为当前证据。
14. Codex review 三次失败时要求人工审批。
15. workflow/merge policy/runner/deployment 文件命中时阻断或要求人工审批。

建议测试命令：

```bash
./.venv/bin/python -m pytest tests/pipeline/test_bug_auto_fix_governance.py -q --basetemp=runtime/pytest-tmp-bug-auto-fix-system-governance
./.venv/bin/python -m ruff check scripts/pipeline/bug_auto_fix_governance.py tests/pipeline/test_bug_auto_fix_governance.py
./.venv/bin/python -m py_compile scripts/pipeline/bug_auto_fix_governance.py
git diff --check
```

若实现触碰共享 pipeline 行为，增加更广泛回归：

```bash
./.venv/bin/python -m pytest tests -q --tb=short --basetemp=runtime/pytest-tmp-bug-auto-fix-system-governance-full
```

测试报告必须写入：

```text
docs/features/bug-auto-fix-system-governance/phase-1-test-report.md
```

最终结果只能是：

```text
PASS
PASS_WITH_NOTES
REJECTED
```

### Reviewer Handoff

Reviewer 必须重点检查：

- 是否没有修改受限模块。
- 白名单是否足够窄。
- restricted paths 是否覆盖需求完整列表。
- unknown/missing/stale/cross-branch evidence 是否 fail closed。
- secret-like 内容是否不会完整回显。
- LLM 是否不是最终裁决者。
- auto-fix decision enum 是否严格限制。
- auto-merge gate 是否检查测试、review、acceptance、manual approval。
- 是否没有新增 `/api/**` 产品业务前缀。
- 是否没有新增真实交易能力或暴露 `LEVEL_3_AUTO`。
- 测试是否覆盖 normal 和 negative paths。
- 中文 dev/test report 是否齐备。

发现 S0/S1/S2 缺陷必须 request changes。

### Acceptance Handoff

Acceptance Agent 只能在以下条件全部满足时通过：

- `requirements.md`、`architecture.md`、dev report、test report、review、acceptance 文档齐备。
- 自动修复治理规则覆盖白名单、受限模块、审计证据和自动合并门禁。
- normal 和 negative paths 测试通过。
- 未新增真实交易能力。
- 未触碰或绕过 Risk Engine、Execution Engine、Provider、Tool Registry、Model Gateway、Stock Pool、human confirmation。
- 未暴露 `LEVEL_3_AUTO` 为普通用户选项。
- manual approval 和 manual merge 边界保留。
- 用户能从 artifact 或流水线输出看清允许、拒绝或人工审批原因。