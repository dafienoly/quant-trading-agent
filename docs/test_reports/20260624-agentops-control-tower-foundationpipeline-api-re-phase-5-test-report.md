# Phase 5 测试报告: AgentOps Control Tower Foundation — 文档、报告与回归

## 基本信息

| 字段 | 值 |
|------|-----|
| 测试阶段 | Phase 5 — 文档、报告与回归 |
| Feature ID | agentops-control-tower-foundationpipeline-api-re |
| Base 分支 | `epic/20260624-agentops-control-tower-foundationpipeline-api-re-issue-75` |
| Base Commit | `592a687` |
| 临时测试分支 | `test/agentops-control-tower-foundationpipeline-api-re/phase-5-tester-20260625-1700`（已删除） |
| 测试日期 | 2026-06-25 17:00 UTC |
| 测试角色 | OpenCode Test Engineer（opencode-go/deepseek-v4-pro + superpowers） |

## 参考文档

| 文档类型 | 路径 |
|------|------|
| 需求 | `docs/requirements/2026-06-24-agentops-control-tower-foundationpipeline-api-re-requirements.md` |
| 架构 | `docs/design/2026-06-24-agentops-control-tower-foundationpipeline-api-re-architecture.md` |
| 团队计划 | `docs/dev_plans/20260624-agentops-control-tower-foundationpipeline-api-re-team-plan.md` |
| Phase 5 开发报告 | `docs/dev_reports/20260624-agentops-control-tower-foundationpipeline-api-re-phase-5-dev-report.md` |
| Phase 1-4 开发报告 | `docs/dev_reports/20260624-agentops-control-tower-foundationpipeline-api-re-phase-{1,2,3,4}-dev-report.md` |
| Phase 1-4 测试报告 | `docs/test_reports/20260624-agentops-control-tower-foundationpipeline-api-re-phase-{1,2,3,4}-test-report.md` |
| 测试流程 | `docs/process/TEST_ENGINEER_WORKFLOW.md` |

## 测试环境

| 项目 | 值 |
|------|-----|
| OS | Linux（GitHub Actions runner） |
| Python | 3.14.4（`/usr/bin/python3`） |
| pytest | 9.1.1 |
| ruff | 0.15.19 |
| 虚拟环境 | 无 `.venv/bin/python`，使用系统 `python3` |

## 测试范围

### 覆盖范围

1. Phase 5 开发报告所有自测命令复跑验证
2. 后端 AgentOps 单元测试（Phase 1-2 实现）：契约/reader/aggregator/sanitizer/errors/routes
3. API 回归测试：现有 `/product` 路由
4. Streamlit 状态中心 + Control Tower 页面测试
5. Dashboard UI 回归测试
6. 全量 agentops + product 相关测试合并回归
7. 全项目扩展回归
8. 静态检查：ruff + py_compile + git diff --check
9. 安全审计：只读 API 保证、受限模块未触碰、敏感信息清洗
10. 文档完整性检查
11. fail-visible 行为验证
12. API 端点功能探针（正常/404 路径）

### 未覆盖范围

- 不运行 `scripts/agent_pipeline.py check-gates`（该脚本当前分支不可用）
- 不执行真实 GitHub API 调用（网络依赖不可控，单元测试已 mock）
- 不执行 Streamlit 浏览器渲染 smoke（无图形环境，已有 pytest 测试覆盖）

## 需求覆盖矩阵

| 需求条目 | 覆盖方式 | 结果 |
|----------|----------|------|
| FR1: Pipeline 观测契约（字段/枚举/未知状态） | `tests/test_agentops_pipeline_contracts.py`（98 tests 内） | ✅ PASS |
| FR2: 只读聚合 API（GET only, 结构化错误） | `tests/test_agentops_routes.py` + API 探针 | ✅ PASS |
| FR3: React/Streamlit 状态中心（loading/ready/empty/stale/error/blocked） | `tests/test_agentops_state.py`（46 tests） | ✅ PASS |
| FR4: Control Tower Foundation 页面（信息展示/缺失可见/无白屏） | `tests/test_agentops_control_tower_page.py` | ✅ PASS |
| FR5: 非目标（无控制动作/交易/风控变更） | 只读保证 + 受限模块审计 | ✅ PASS |
| NFR1: 可追踪性（状态来源明确） | 契约 source 字段 + API 探针 | ✅ PASS |
| NFR2: 稳定性（异常不崩溃/不白屏） | 404/异常路径测试 | ✅ PASS |
| NFR3: 安全性（无 secrets/tokens/.env） | sanitizer 测试 + API 探针 | ✅ PASS |
| NFR4: 兼容性（不破坏现有 /product 路由） | `tests/test_product_routes.py` 回归 | ✅ PASS |
| NFR5: 可测试性 | 17 个测试文件覆盖所有模块 | ✅ PASS |
| NFR6: 用户体验（状态区分明确） | 状态中心 + Control Tower 测试 | ✅ PASS |
| AC1: 契约验收（字段/枚举/状态完整） | 契约测试 | ✅ PASS |
| AC2: API 验收（只读/错误/敏感清洗） | routes 测试 + API 探针 | ✅ PASS |
| AC3: 状态中心验收（6 种状态/去重） | `test_agentops_state.py` | ✅ PASS |
| AC4: 页面验收（信息/缺失/fail-visible） | `test_agentops_control_tower_page.py` | ✅ PASS |
| AC5: 文档报告验收 | 文档完整性检查 | ✅ PASS |
| AC6: 测试命令验收 | ruff + py_compile + pytest | ✅ PASS |

## 命令与结果

### 1. 后端单元测试（Phase 1-2 agentops 实现）

```bash
python3 -m pytest \
  tests/test_agentops_pipeline_contracts.py \
  tests/test_agentops_pipeline_state_reader.py \
  tests/test_agentops_pipeline_aggregator.py \
  tests/test_agentops_pipeline_sanitizer.py \
  tests/test_agentops_pipeline_errors.py \
  tests/test_agentops_routes.py \
  -q --tb=short --basetemp=runtime/pytest-tmp-agentops-control-tower-full
```

结果: **98 passed in 3.52s**（与开发报告一致）

### 2. API 回归测试

```bash
python3 -m pytest \
  tests/test_product_routes.py \
  tests/test_v16_0b_watchlist_api.py \
  tests/test_v16_0b_signal_observation.py \
  -q --tb=short --basetemp=runtime/pytest-tmp-agentops-control-tower-full-regression
```

结果: **18 passed in 14.85s**（与开发报告一致）

### 3. Streamlit / UI 回归测试

```bash
python3 -m pytest \
  tests/test_agentops_state.py \
  tests/test_agentops_control_tower_page.py \
  -q --tb=short --basetemp=runtime/pytest-tmp-agentops-control-tower-page
```

结果: **46 passed in 1.02s**

```bash
python3 -m pytest \
  tests/test_product_dashboard_source.py \
  -q --tb=short --basetemp=runtime/pytest-tmp-agentops-control-tower-ui-regression
```

结果: **3 passed in 0.32s**

### 4. 静态检查

```bash
python3 -m ruff check \
  src/product_app/agentops \
  src/api/agentops_routes.py \
  src/api/app.py \
  tests/test_agentops_pipeline_contracts.py \
  tests/test_agentops_pipeline_state_reader.py \
  tests/test_agentops_pipeline_aggregator.py \
  tests/test_agentops_pipeline_sanitizer.py \
  tests/test_agentops_routes.py \
  tests/test_agentops_pipeline_errors.py \
  tests/test_agentops_state.py \
  tests/test_agentops_control_tower_page.py
```

结果: **All checks passed!**

```bash
python3 -m py_compile \
  src/product_app/agentops/__init__.py \
  src/product_app/agentops/pipeline_contracts.py \
  src/product_app/agentops/pipeline_state_reader.py \
  src/product_app/agentops/pipeline_aggregator.py \
  src/product_app/agentops/pipeline_errors.py \
  src/product_app/agentops/pipeline_sanitizer.py \
  src/api/agentops_routes.py \
  src/api/app.py \
  src/ui_report/agentops_state.py \
  src/ui_report/agentops_control_tower.py
```

结果: **(no output)** 编译通过

```bash
git diff --check
```

结果: 无空白问题

### 5. 全量 AgentOps + Product 合并回归

```bash
python3 -m pytest \
  tests/test_agentops_pipeline_*.py \
  tests/test_agentops_routes.py \
  tests/test_agentops_state.py \
  tests/test_agentops_control_tower_page.py \
  tests/test_product_routes.py \
  tests/test_v16_0b_*.py \
  tests/test_product_dashboard_source.py \
  -q --tb=line --basetemp=runtime/pytest-tmp-agentops-control-tower-all
```

结果: **165 passed in 15.97s**（98 + 18 + 46 + 3）

### 6. 全项目扩展回归

```bash
python3 -m pytest tests -q --tb=line --basetemp=runtime/pytest-tmp-agentops-full-project
```

结果: **1154 passed, 6 failed, 6 skipped in 113.21s**

失败的 6 个测试分布在以下无关文件：
- `tests/test_aktools_compat_app.py`（2 失败）
- `tests/test_eastmoney_provider.py`（2 失败）
- `tests/test_live_data_mapper.py`（1 失败）
- `tests/test_realtime_provider.py`（1 失败）

失败原因：运行环境缺少 `socksio` 包导致 `ImportError: Using SOCKS proxy, but the 'socksio' package is not installed`。这些是**预存在环境问题**，与 AgentOps 功能无关。

### 7. 受限模块审计

```bash
python3 -c "import ast; ..."
```

结果: **All OK** — agentops 代码（`src/product_app/agentops/`、`src/api/agentops_routes.py`、`src/ui_report/agentops_*.py`）未 import 任何 restricted module。

### 8. API 只读保证探针

| 方法 | 端点 | 状态码 | 验证 |
|------|------|--------|------|
| GET | `/product/agentops/pipelines/{feature_id}` | 200 | ✅ 返回 observation |
| GET | `/product/agentops/pipelines/by-issue/{issue_number}` | 200 | ✅ 返回 observation |
| GET | `/product/agentops/pipelines/nonexistent` | 404 | ✅ 返回 FEATURE_NOT_FOUND |
| GET | `/product/agentops/pipelines/by-issue/99999` | 404 | ✅ 返回错误 |
| POST | `/product/agentops/pipelines/test` | 405 | ✅ Method Not Allowed |
| PUT | `/product/agentops/pipelines/test` | 405 | ✅ Method Not Allowed |
| DELETE | `/product/agentops/pipelines/test` | 405 | ✅ Method Not Allowed |
| PATCH | `/product/agentops/pipelines/test` | 405 | ✅ Method Not Allowed |

### 9. 文档完整性检查

| 文档 | 路径 | 状态 |
|------|------|------|
| 需求文档 | `docs/requirements/2026-06-24-...` | ✅ 存在 |
| 架构设计 | `docs/design/2026-06-24-...` | ✅ 存在 |
| 团队计划 | `docs/dev_plans/20260624-...` | ✅ 存在 |
| Phase 1 开发报告 | `docs/dev_reports/20260624-...-phase-1-dev-report.md` | ✅ 存在 |
| Phase 2 开发报告 | `docs/dev_reports/20260624-...-phase-2-dev-report.md` | ✅ 存在 |
| Phase 3 开发报告 | `docs/dev_reports/20260624-...-phase-3-dev-report.md` | ✅ 存在 |
| Phase 4 开发报告 | `docs/dev_reports/20260624-...-phase-4-dev-report.md` | ✅ 存在 |
| Phase 5 开发报告 | `docs/dev_reports/20260624-...-phase-5-dev-report.md` | ✅ 存在 |
| Phase 1 测试报告 | `docs/test_reports/20260624-...-phase-1-test-report.md` | ✅ 存在 |
| Phase 2 测试报告 | `docs/test_reports/20260624-...-phase-2-test-report.md` | ✅ 存在 |
| Phase 3 测试报告 | `docs/test_reports/20260624-...-phase-3-test-report.md` | ✅ 存在 |
| Phase 4 测试报告 | `docs/test_reports/20260624-...-phase-4-test-report.md` | ✅ 存在 |

**12/12 必需文档完整**（Phase 1-4 测试报告结论：Phase 1 R1→REJECTED/R2→PASS/R3→PASS；Phase 2-4→PASS）

### 10. fail-visible 行为验证

API 探针对有效 feature 返回的 `AgentOpsPipelineObservation` 显示：
- `data_quality.status: incomplete`
- 8 个 `missing_sources`（包含命名约定不一致导致的路径不匹配）
- `safety.blockers` 包含 8 条缺失文档阻塞提示
- 无 `passed` 伪装

这是正确的 fail-visible 行为：缺少或被不同路径命名的文档均报告为 `missing`/`blocked`，不伪装为通过。

## 缺陷列表

| ID | 严重等级 | 描述 | 状态 |
|----|----------|------|------|
| — | — | 未发现 Phase 5 范围内的新缺陷 | — |

## 发现与备注

### FN-1: `required_docs` 路径命名约定不一致

`current_task.yaml` 中的 `required_docs` 使用 `20260624`（无分隔符）格式，而实际存入仓库的需求/架构文件使用 `2026-06-24`（带分隔符）。这导致 API 正确地将这些文档报告为 `missing`。

- **严重等级**: S4（建议，非阻塞）
- **影响**: API 的 fail-visible 行为正确，但对用户可能产生困惑
- **已记录**: 团队计划已知此命名约定差异
- **建议**: 后续统一命名约定或让 reader 同时尝试两种命名模式

### FN-2: 6 个预存在无关测试失败

运行全项目 `pytest tests` 时有 6 个无关文件测试失败，均由运行环境缺少 `socksio` 包导致。

- **严重等级**: S4（非阻塞，预存在环境问题）
- **影响**: 不涉及 AgentOps 功能
- **建议**: 安装 `pip install httpx[socks]` 解决

## 安全确认

| 检查项 | 结果 |
|--------|------|
| 默认不真实自动下单 | ✅ 全程只读，无交易入口 |
| Risk Agent 一票否决未被绕过 | ✅ 未修改 `src/risk_engine/` |
| 股票池/人工确认/fail-closed 未被绕过 | ✅ 未修改对应模块 |
| 不自动合并 main | ✅ GitHub Stage Runner 管理提交 |
| 未提交密钥/Token/Cookie/凭据 | ✅ git diff 确认无泄露 |
| LEVEL_3_AUTO 未暴露 | ✅ 未修改配置相关代码 |
| 只读 API 保证 | ✅ 仅注册 GET，POST/PUT/DELETE/PATCH 返回 405 |
| API 响应无绝对路径/敏感信息 | ✅ sanitizer 验证通过 |
| fail-visible 行为 | ✅ 缺失→missing/blocked，不伪装为 passed |
| 受限模块审计 | ✅ 未 import/修改任何 restricted module |
| 源代码与测试文件完整性 | ✅ 9 source + 8 test 文件全部存在 |

## 剩余风险

1. **命名约定不一致**: `current_task.yaml` 中的 `required_docs` 路径与实际文件使用不同日期格式。不影响功能正确性（fail-visible 行为正常），但后续应统一或让 reader 兼容两种格式。
2. **前端方案**: 采用方案 B（Streamlit）而非架构文档中原设计的方案 A（React）。团队计划已在"前端栈决策门禁"中记录此决策，测试均基于方案 B 执行并通过。
3. **未运行浏览器渲染 smoke**: 无图形环境限制，已有 pytest 测试覆盖 Streamlit 页面组件逻辑。

## 最终结论

**PASS**

全阶段回归测试可复现且全部通过：
- 后端单元测试 98/98（Phase 1-2 agentops 实现）
- API 回归 18/18（现有 product 路由无回归）
- Streamlit 状态中心 + Control Tower 46/46
- Dashboard UI 回归 3/3
- 全量合并 165/165 passed
- ruff + py_compile 静态检查通过
- 只读 API 保证验证通过（仅 GET，写方法返回 405）
- 受限模块审计通过
- sanitizer 功能验证通过
- fail-visible 行为正确（缺失→missing/blocked）
- 必需文档 12/12 完备
- 未引入 S0/S1/S2 阻断缺陷
- 安全确认全部通过
