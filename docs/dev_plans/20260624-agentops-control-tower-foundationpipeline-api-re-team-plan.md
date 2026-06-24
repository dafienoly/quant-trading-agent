# Team Plan: AgentOps Control Tower Foundation — Pipeline 观测契约、只读聚合 API 与状态中心

> **给执行 Agent：** 本计划由 OpenCode Team Leader（`claude_lead_plan` 阶段，运行时 `opencode-go/glm-5.2` + superpowers）产出，按阶段串行执行。每个阶段由 Claude Code Developer（`ultracode-xhigh`，`effort=xhigh`，feature-dev + superpowers）实现并自测，再由 OpenCode Test Engineer（`deepseek-v4-pro`，`variant=max` + superpowers）在临时 `test/...` 分支验证。任一阶段测试通过后路由回 Claude Code Developer 执行下一阶段，直到全部阶段完成。阶段顺序不得跳跃。

**Goal:** 为 AgentOps Control Tower 建立只读、可观测、可追踪的基础层——稳定的 Pipeline 观测契约、只读聚合 API 与状态中心页面，不引入任何写操作或交易能力。

**Architecture:** `docs/design/2026-06-24-agentops-control-tower-foundationpipeline-api-re-architecture.md`

**Tech Stack:** 后端 Python 3.10+ / FastAPI / Pydantic；前端待架构决策（见下文“前端栈决策门禁”）。

## Inputs Reviewed

| Document | Path |
|---|---|
| Requirements | `docs/requirements/2026-06-24-agentops-control-tower-foundationpipeline-api-re-requirements.md` |
| Architecture | `docs/design/2026-06-24-agentops-control-tower-foundationpipeline-api-re-architecture.md` |
| Agent Pipeline | `docs/process/AGENT_DEVELOPMENT_PIPELINE.md` |
| Branch Workflow | `docs/process/BRANCH_WORKFLOW.md` |
| Automation Architecture | `docs/pipeline/AGENT_AUTOMATION_ARCHITECTURE.md` |
| Auto Merge Policy | `docs/pipeline/AUTO_MERGE_POLICY.md` |
| Self-test Checklist | `docs/policy/SELF_TEST_CHECKLIST.md` |
| Current task state | `.agent/current_task.yaml` |

## Repo Findings by Team Leader

Leader 在拆分前已确认仓库现状，以下结论影响阶段划分：

1. **后端结构确认**：`src/api/app.py` 的 `create_app()` 通过 `app.include_router(product_router, prefix="/product", tags=["product"])` 注册产品路由；`src/api/product_routes.py` 为单一 `APIRouter()`。AgentOps 路由将按同一模式以 `prefix="/product/agentops"` 注册。`src/product_app/` 为扁平模块布局，新增 `src/product_app/agentops/` 子包符合模块边界决策。
2. **测试约定确认**：仓库测试为扁平结构 `tests/test_*.py`（如 `tests/test_product_routes.py`、`tests/test_v16_0b_*.py`），不存在 `tests/api/` 或 `tests/product_app/` 子目录。本计划测试文件采用扁平命名以遵循既有约定，而非架构“建议 touched files”中的嵌套路径。
3. **前端栈缺失（重要）**：仓库**不存在** React/TypeScript 前端，无 `package.json`、`tsconfig.json`、`vite.config.*`。既有“只读监控 UI”由 Streamlit 承担（`src/ui_report/product_dashboard.py` + FastAPI `/product` 路由，参见前序 V16.0b `docs/design/2026-06-23-v16-0b-readonly-market-api-ui-architecture.md`）。架构文档假设的 React 状态中心与 Control Tower 页面无法在现有仓库直接落地。
4. **日期命名约定**：`docs/requirements`、`docs/design`、`docs/dev_plans` 实际文件使用 `2026-06-24`（带分隔符）；`docs/dev_reports`、`docs/test_reports`、`docs/review`、`docs/acceptance` 报告使用 `20260624`（无分隔符），与 `.agent/state.json` 的 `required_docs` 一致。gate 以 glob `docs/dev_plans/*-{feature_id}*team-plan.md` 等模式匹配，对两种命名均兼容。本计划团队计划文件按 handoff 指定为 `docs/dev_plans/20260624-agentops-control-tower-foundationpipeline-api-re-team-plan.md`。

## Scope

1. 后端定义稳定的 Pipeline 观测契约（Pydantic 模型、枚举、响应/错误模型）。
2. 后端实现只读 state reader、document status checker、aggregator、sanitizer、结构化错误。
3. 后端新增 `/product/agentops` 只读 router，支持按 `feature_id` 与 `issue_number` 查询。
4. 前端建立统一状态中心，消费只读 API，表达 `loading/ready/empty/stale/error/blocked` 状态。
5. 前端 Control Tower Foundation 页面展示 feature/issue/branch/阶段/文档/安全阻塞提示。
6. 每阶段产出中文 dev/test 报告，最终回归与文档齐备。

## Non-Goals

- 不实现任何流水线控制动作：approve、reject、rerun、merge、create branch/PR、comment、assign、label、trigger workflow、CI rerun。
- 不修改交易、风控、执行、行情、回测、因子、策略、股票池等 restricted modules。
- 不引入真实交易、模拟交易、纸面交易或任何下单/撤单/审批入口。
- 不接入实时 GitHub mutation；如后续接入 GitHub，只允许只读查询且失败必须可见。
- 不改变自动合并政策、分支工作流、Agent 角色职责、CI 策略或 GitHub workflow 行为。
- 不把 mock/demo/fixture 数据表现为真实 pipeline 状态。
- 前端阶段不得新增 approve/merge/rerun/trigger/trade 等按钮文案或动作。

## Safety Constraints（全阶段适用）

1. **只读硬约束**：API 仅注册 `GET`；聚合器/reader 不调用任何文件写入、GitHub mutation、workflow trigger、branch/PR mutation、交易执行、风控放行或 broker 模块。错误路径不写 bug 文件、不更新 `.agent` 状态、不生成报告文件。
2. **fail-visible**：数据缺失/不可解析/过期/必需文档缺失时必须返回 `unknown`/`missing`/`unavailable`/`stale`/`blocked`，不得默认为 `passed`/`complete`/`ready`。
3. **敏感信息清洗**：只返回仓库相对路径；不返回 `.env`、token、cookie、broker 凭据、CI 凭据、完整 traceback、本地绝对路径。sanitizer 处理绝对路径→相对、token-like 字符串→`<redacted>`、环境变量值不入响应。
4. **不触碰受限模块**：`src/risk_engine/`、`src/execution_engine/`、`src/data_gateway/`、`src/backtest_engine/`、`src/factor_engine/`、`src/strategy_engine/`、`src/stock_pool/` 一律不修改、不引入依赖。如实现中必须触碰，立即停止并升级为受限模块变更（人工审批 + 负向测试 + 架构复审）。
5. **不暴露 `LEVEL_3_AUTO`** 为普通用户可选项。
6. **不自动合并 main**，不执行 `git commit/push/merge`（GitHub Stage Runner 管理提交）。
7. 所有核心行为变更必须有测试证据；不得删除、弱化或跳过失败测试来制造通过。

## Global Constraints

- Python 3.10+；静态检查 `ruff`（配置 `pyproject.toml`）与 `py_compile`。
- 测试 `pytest`；外部依赖必须 mock，单元测试不依赖真实 GitHub 网络。
- API 测试用 `fastapi.testclient.TestClient`；触及共享 API/product route 时追加 `tests/api` 范围或 `tests/test_product_routes.py` 回归。
- 测试隔离：统一传 `--basetemp=runtime/pytest-tmp-agentops-control-tower`。
- 运行环境若无 `.venv/bin/python`，记录并以 `python3` 等效运行；报告中写明实际命令与结果。
- 代码标识、JSON key、环境变量、第三方术语保留英文；用户可见输出与新增文档默认中文。

## 前端栈决策门禁（Phase 3 前置，必须先解除）

**状态：未解除。** 架构文档要求 React 状态中心与 Control Tower 页面，但仓库无 React 前端，既有只读监控 UI 为 Streamlit。Leader 无权单方面改写架构边界。

**解除条件（二选一，由 Codex B Architect 出具架构补充决策并更新 `docs/design/` 下本 feature 架构文档或新增 addendum）：**

- **方案 A（遵循架构原意）**：引入 React + TypeScript 前端栈（新增 `package.json`、`vite`、`vitest`、`tsconfig`、前端根目录与构建脚本）。此方案扩大范围，触及新工具链与 UI entrypoint，按 `AUTO_MERGE_POLICY.md` 属“Always Manual”，且需补前端构建/测试 smoke。
- **方案 B（沿用仓库现状）**：将“状态中心 + Control Tower 页面”映射到既有 Streamlit（扩展 `src/ui_report/product_dashboard.py` 或新增 `src/ui_report/agentops_control_tower.py`），状态中心以 Streamlit `st.session_state` + 模块化 helper 实现，对应 `/product/agentops` API。

**在解除前**：Phase 1、Phase 2（纯后端，不依赖前端决策）可立即推进并独立通过 gate；Phase 3、Phase 4 不得开始实现，Claude Developer 到达 Phase 3 时必须停在该门禁并路由回 Architect。Phase 3/4 下文同时给出两种方案的精确路径与命令，**实现时严格按已选方案执行，不得混用**。

---

## Proposed Phases

### Phase 1 — 后端 Pipeline 观测契约与只读聚合器

| Field | Value |
|---|---|
| **Scope** | 新增 `src/product_app/agentops/` 子包：`pipeline_contracts.py`（Pydantic 契约/枚举/响应/错误模型）、`pipeline_state_reader.py`（只读读取 `.agent/current_task.yaml`、`.agent/state.json`、`.agent/handoff/*.md`、必需文档存在性）、`pipeline_aggregator.py`（聚合为 `AgentOpsPipelineObservation`，计算文档状态/阶段归一化/数据质量/安全提示）、`pipeline_errors.py`（参数错误、feature 不存在、数据源缺失、不可解析、内部异常）、`pipeline_sanitizer.py`（路径相对化、token-like→`<redacted>`、环境变量值不入响应）。先写失败测试再实现最小代码。 |
| **Non-Goals** | 不新增 API 路由（Phase 2）；不接 GitHub；不写文件；不创建目录；不修改 `.agent` 状态。 |
| **Owner** | Claude Code Developer（`claude_developer`，`ultracode-xhigh`，`effort=xhigh`） |
| **Branch** | `feat/agentops-control-tower/phase-1-backend-contracts`（自 epic 分支） |
| **Restricted modules** | 不触碰任何受限模块；新增模块仅限 `src/product_app/agentops/`。 |
| **Dev report** | `docs/dev_reports/20260624-agentops-control-tower-foundationpipeline-api-re-phase-1-dev-report.md` |
| **Test report** | `docs/test_reports/20260624-agentops-control-tower-foundationpipeline-api-re-phase-1-test-report.md` |

**Files:**
- Create: `src/product_app/agentops/__init__.py`
- Create: `src/product_app/agentops/pipeline_contracts.py`
- Create: `src/product_app/agentops/pipeline_state_reader.py`
- Create: `src/product_app/agentops/pipeline_aggregator.py`
- Create: `src/product_app/agentops/pipeline_errors.py`
- Create: `src/product_app/agentops/pipeline_sanitizer.py`
- Create: `tests/test_agentops_pipeline_contracts.py`
- Create: `tests/test_agentops_pipeline_state_reader.py`
- Create: `tests/test_agentops_pipeline_aggregator.py`
- Create: `tests/test_agentops_pipeline_sanitizer.py`

**Interfaces（契约形状，字段名严格对齐架构）:**
- `AgentOpsPipelineObservation`：`contract_version="agentops.pipeline_observation.v1"`、`generated_at`、`feature`、`issue`、`branch`、`stages[]`、`roles[]`、`required_docs[]`、`safety`、`data_quality`、`errors[]`。
- 枚举：`PipelineStageStatus`（pending/in_progress/passed/failed/blocked/skipped/unknown）、`DocumentStatus`（present/missing/stale/unreadable/unknown）、`DataQualityStatus`（complete/incomplete/unavailable/unparsable/stale/unknown）、`ControlTowerViewStatus`（ready/empty/stale/error/blocked）。
- `errors[]` 项：`code`、`message`、`source`、`safe_detail`。
- `source` 必须指向可追踪来源（如 `.agent/current_task.yaml`、`docs/requirements/...`、`pipeline_state.required_docs`）；`path` 使用仓库相对路径。

**Self-test commands:**
```bash
git status --short --branch
git diff --stat
./.venv/bin/python -m ruff check src/product_app/agentops tests/test_agentops_pipeline_contracts.py tests/test_agentops_pipeline_state_reader.py tests/test_agentops_pipeline_aggregator.py tests/test_agentops_pipeline_sanitizer.py
./.venv/bin/python -m py_compile src/product_app/agentops/*.py
./.venv/bin/python -m pytest tests/test_agentops_pipeline_contracts.py tests/test_agentops_pipeline_state_reader.py tests/test_agentops_pipeline_aggregator.py tests/test_agentops_pipeline_sanitizer.py -q --basetemp=runtime/pytest-tmp-agentops-control-tower
git diff --check
```

**Tester checks（OpenCode Test Engineer，临时 `test/agentops-control-tower/phase-1-<tester>-<timestamp>` 分支）:**
- 完整 pipeline state 返回 `complete`/`ready` 候选数据。
- 缺失 required doc 返回 `missing`，绝不返回 `passed`。
- 未知 stage status 归一化为 `unknown`。
- 不可解析 YAML 返回结构化错误或 partial observation，不抛裸异常。
- 绝对路径、token-like 字符串、`.env` 内容不出现在响应模型中。
- reader/aggregator 不执行写操作（monkeypatch 文件写入 API 断言未被调用）。
- 重跑 Developer 报告中的命令并比对结果；建立 requirement→test 覆盖矩阵。
- 验证未触碰 restricted modules（grep import）。

**Release criteria:**
- 上述 pytest 全绿；`ruff`、`py_compile` 通过。
- 契约字段/枚举与架构一致；`contract_version` 存在。
- fail-visible 行为有测试证据；无未解释的 skipped/xfail/mock 真实网络。
- 中文 dev report 含变更范围/测试命令/结果/安全确认/最终结论。
- 测试报告结论为 `PASS` 或 `PASS_WITH_NOTES` 且无 S0/S1/S2 阻断。

**Gate after phase:** 测试通过后路由回 Claude Code Developer 执行 Phase 2。

---

### Phase 2 — 只读 AgentOps API 路由

| Field | Value |
|---|---|
| **Scope** | 新增 `src/api/agentops_routes.py`，定义只读 `APIRouter()`；在 `src/api/app.py` 的 `create_app()` 内以 `app.include_router(agentops_router, prefix="/product/agentops", tags=["agentops"])` 注册。端点：`GET /product/agentops/pipelines/{feature_id}`、`GET /product/agentops/pipelines/by-issue/{issue_number}`。复用 Phase 1 聚合器与 sanitizer；错误映射为 400/422/404/503/500 与结构化 `error` 体。只注册 `GET`，无任何写方法。 |
| **Non-Goals** | 不实现前端；不接 GitHub mutation；不修改 `product_routes.py` 内部业务逻辑（仅在 app factory 增加一行 router 注册）；不新增交易/风控/执行端点。 |
| **Owner** | Claude Code Developer |
| **Branch** | `feat/agentops-control-tower/phase-2-readonly-api`（自 epic 分支） |
| **Restricted modules** | 仅改 `src/api/app.py`（router 注册）与新增 `src/api/agentops_routes.py`；不触碰受限模块。触及共享 API entrypoint，须跑更广回归。 |
| **Dev report** | `docs/dev_reports/20260624-agentops-control-tower-foundationpipeline-api-re-phase-2-dev-report.md` |
| **Test report** | `docs/test_reports/20260624-agentops-control-tower-foundationpipeline-api-re-phase-2-test-report.md` |

**Files:**
- Create: `src/api/agentops_routes.py`
- Modify: `src/api/app.py`（在 product router 注册后新增 agentops router 注册）
- Create: `tests/test_agentops_routes.py`

**Interfaces:**
- Consumes: `src.product_app.agentops.pipeline_aggregator.get_pipeline_observation(feature_id, issue_number)`、`pipeline_errors.*`、`pipeline_sanitizer.*`（来自 Phase 1）。
- Produces: HTTP `GET` 端点；200 返回 `AgentOpsPipelineObservation`，错误返回 `{"error": {"code","message","source","safe_detail"}}`。
- 路由聚合逻辑不得写入 `product_routes.py` 内部，避免路由文件臃肿（架构明确要求）。

**Self-test commands:**
```bash
git status --short --branch
git diff --stat
./.venv/bin/python -m ruff check src/api/agentops_routes.py src/api/app.py tests/test_agentops_routes.py
./.venv/bin/python -m py_compile src/api/agentops_routes.py src/api/app.py
./.venv/bin/python -m pytest tests/test_agentops_routes.py -q --basetemp=runtime/pytest-tmp-agentops-control-tower-api
# 触及共享 API entrypoint，追加更广回归：
./.venv/bin/python -m pytest tests/test_product_routes.py tests/test_v16_0b_watchlist_api.py tests/test_v16_0b_signal_observation.py -q --tb=short --basetemp=runtime/pytest-tmp-agentops-control-tower-api-regression
git diff --check
```

**Tester checks:**
- `GET /product/agentops/pipelines/{feature_id}` 成功返回 observation。
- `GET /product/agentops/pipelines/by-issue/{issue_number}` 成功返回 observation。
- 参数格式错误→`400`/`422`；feature 不存在→`404`；数据源缺失→`503` 或 partial 200；不可解析→`422`；内部异常→`500`。
- 500 错误体不含 traceback/secret/绝对路径。
- router 仅注册 `GET`（遍历 `app.routes` 断言无 POST/PUT/PATCH/DELETE 于 `/product/agentops`）。
- route mock aggregator，断言未调用任何写入函数、未发起 GitHub mutation、未触发交易/风控模块。
- 回归现有 `/product` 路由未被破坏（`tests/test_product_routes.py` 等）。

**Release criteria:**
- 上述 pytest 全绿；`ruff`、`py_compile` 通过。
- HTTP 状态映射与架构表一致；错误体经 sanitizer。
- 现有 product 路由回归无回归性失败（若有预存在无关失败，按 AGENTS.md 说明并缩窄重跑）。
- 中文 dev/test report 齐备；测试结论 `PASS`/`PASS_WITH_NOTES` 且无 S0/S1/S2 阻断。

**Gate after phase:** 测试通过后，**暂停**。若“前端栈决策门禁”已解除，路由回 Claude Code Developer 执行 Phase 3；若未解除，路由回 Codex B Architect 出具前端决策，决策落库后再进 Phase 3。

---

### Phase 3 — 前端状态中心（依赖前端栈决策门禁）

> **前置硬门禁：** “前端栈决策门禁”必须已由 Architect 解除并在 `docs/design/` 落库。未解除时 Claude Developer 不得开始本阶段，须停在此处并路由回 Architect。下文 A/B 两方案均给出精确路径，**按已选方案执行，不得混用**。

#### 方案 A — React 状态中心（架构原意）

| Field | Value |
|---|---|
| **Scope** | 新增 React + TypeScript 前端：`pipeline.ts`（镜像后端契约 TS 类型）、`pipelineClient.ts`（只读 GET 调用，HTTP 错误→统一错误结构）、`pipelineStore.ts`（loading/ready/empty/stale/error/blocked 状态转换，缓存同一 feature 避免重复并发请求）。状态中心对外暴露 `viewStatus/observation/error/lastLoadedAt/isRefreshing` 与 `loadByFeatureId/loadByIssueNumber/refresh/clear`。 |
| **Owner** | Claude Code Developer |
| **Branch** | `feat/agentops-control-tower/phase-3-react-state-center` |
| **Restricted modules** | 仅前端目录；不触碰后端受限模块。 |
| **Dev report** | `docs/dev_reports/20260624-agentops-control-tower-foundationpipeline-api-re-phase-3-dev-report.md` |
| **Test report** | `docs/test_reports/20260624-agentops-control-tower-foundationpipeline-api-re-phase-3-test-report.md` |

**Files (方案 A):**
- Create: `<react-root>/src/features/agentops/types/pipeline.ts`
- Create: `<react-root>/src/features/agentops/api/pipelineClient.ts`
- Create: `<react-root>/src/features/agentops/state/pipelineStore.ts`
- Create: `<react-root>/src/features/agentops/__tests__/pipelineStore.test.ts`
- Create（若仓库无前端骨架）: `package.json`、`tsconfig.json`、`vite.config.ts`、`vitest.config.ts` 等工具链文件（由 Architect 决策确定具体清单）

**Self-test commands (方案 A，以仓库实际脚本为准):**
```bash
npm run lint -- --quiet
npm test -- --run
npm run build
```

**Tester checks (方案 A):**
- 正常 200→`ready`；有 blockers→`blocked`；404→`empty`；500/网络错误→`error`；refresh 失败但有旧数据→`stale`。
- 状态中心缓存同一 feature，避免重复并发请求。
- 不存在写 API client 方法（grep 断言无 POST/PUT/PATCH/DELETE 调用）。
- TS 类型与后端契约枚举一致，不定义冲突状态。

#### 方案 B — Streamlit 状态中心（沿用仓库现状）

| Field | Value |
|---|---|
| **Scope** | 在 `src/ui_report/` 下新增 AgentOps 状态中心模块：`agentops_state.py`（封装对 `/product/agentops` 只读 GET 调用、错误归一化、`st.session_state` 缓存与状态转换 helper：loading/ready/empty/stale/error/blocked）。不新增 React/Node 工具链。状态中心 helper 对外暴露 `load_by_feature_id`/`load_by_issue_number`/`refresh`/`clear` 与 `view_status/observation/error/last_loaded_at/is_refreshing`。 |
| **Owner** | Claude Code Developer |
| **Branch** | `feat/agentops-control-tower/phase-3-streamlit-state-center` |
| **Restricted modules** | 仅 `src/ui_report/`；不触碰后端受限模块。 |
| **Dev report** | `docs/dev_reports/20260624-agentops-control-tower-foundationpipeline-api-re-phase-3-dev-report.md` |
| **Test report** | `docs/test_reports/20260624-agentops-control-tower-foundationpipeline-api-re-phase-3-test-report.md` |

**Files (方案 B):**
- Create: `src/ui_report/agentops_state.py`
- Create: `tests/test_agentops_state.py`
- Modify（可选，仅当需要 API base 配置）: `src/ui_report/product_dashboard.py` 的常量复用

**Self-test commands (方案 B):**
```bash
./.venv/bin/python -m ruff check src/ui_report/agentops_state.py tests/test_agentops_state.py
./.venv/bin/python -m py_compile src/ui_report/agentops_state.py
./.venv/bin/python -m pytest tests/test_agentops_state.py -q --basetemp=runtime/pytest-tmp-agentops-control-tower-state
```

**Tester checks (方案 B):**
- 正常 200→`ready`；有 blockers→`blocked`；404→`empty`；500/网络错误→`error`；refresh 失败但有旧数据→`stale`。
- `st.session_state` 缓存同一 feature，避免重复并发请求。
- helper 不调用写接口（mock requests 断言仅 GET）。
- 错误归一化不暴露 traceback/secret/绝对路径。

**Release criteria（两方案共用）:**
- 所选方案自测全绿；lint/build 通过。
- 状态转换规则与架构状态机一致；不重新实现后端核心聚合规则。
- 中文 dev/test report 齐备；测试结论 `PASS`/`PASS_WITH_NOTES` 且无 S0/S1/S2 阻断。
- 报告中注明实际采用方案 A 或 B 与对应命令。

**Gate after phase:** 测试通过后路由回 Claude Code Developer 执行 Phase 4。

---

### Phase 4 — Control Tower Foundation 页面集成

> **前置：** Phase 3 已完成且前端栈方案已确定。按 Phase 3 同一方案延续，不得切换。

#### 方案 A — React 页面

| Field | Value |
|---|---|
| **Scope** | 新增页面组件：`ControlTowerPage.tsx`（顶部 feature 摘要+当前阶段；中部阶段状态列表+必需文档清单；侧/下方安全阻塞+数据质量）、`PipelineSummary.tsx`、`StageStatusList.tsx`、`RequiredDocsList.tsx`、`SafetyBlockersPanel.tsx`。消费 Phase 3 状态中心，不重复请求/解析。 |
| **Owner** | Claude Code Developer |
| **Branch** | `feat/agentops-control-tower/phase-4-react-page` |
| **Restricted modules** | 仅前端目录。 |
| **Dev report** | `docs/dev_reports/20260624-agentops-control-tower-foundationpipeline-api-re-phase-4-dev-report.md` |
| **Test report** | `docs/test_reports/20260624-agentops-control-tower-foundationpipeline-api-re-phase-4-test-report.md` |

**Files (方案 A):**
- Create: `<react-root>/src/features/agentops/components/ControlTowerPage.tsx`
- Create: `<react-root>/src/features/agentops/components/PipelineSummary.tsx`
- Create: `<react-root>/src/features/agentops/components/StageStatusList.tsx`
- Create: `<react-root>/src/features/agentops/components/RequiredDocsList.tsx`
- Create: `<react-root>/src/features/agentops/components/SafetyBlockersPanel.tsx`
- Create: `<react-root>/src/features/agentops/__tests__/ControlTowerPage.test.tsx`

**Self-test commands (方案 A):**
```bash
npm run lint -- --quiet
npm test -- --run
npm run build
```

**Tester checks (方案 A):** 浏览器/组件渲染 smoke：正常 observation 展示 feature 基础信息；missing doc 显示未生成/missing；failed/blocked/unknown 可见；API 错误显示错误面板不白屏、不显示为通过；不存在 approve/merge/rerun/trigger/trade 按钮文案或 action；组件不重复实现后端阶段聚合规则。

#### 方案 B — Streamlit 页面

| Field | Value |
|---|---|
| **Scope** | 新增 `src/ui_report/agentops_control_tower.py`（Streamlit 页面：顶部 feature 摘要+当前阶段；中部阶段状态列表+必需文档清单；下方安全阻塞+数据质量）。消费 Phase 3 `agentops_state.py`。在 `product_dashboard.py` 或 `main.py dashboard` 入口按现有方式接入导航（不破坏现有 dashboard）。 |
| **Owner** | Claude Code Developer |
| **Branch** | `feat/agentops-control-tower/phase-4-streamlit-page` |
| **Restricted modules** | 仅 `src/ui_report/`。 |
| **Dev report** | `docs/dev_reports/20260624-agentops-control-tower-foundationpipeline-api-re-phase-4-dev-report.md` |
| **Test report** | `docs/test_reports/20260624-agentops-control-tower-foundationpipeline-api-re-phase-4-test-report.md` |

**Files (方案 B):**
- Create: `src/ui_report/agentops_control_tower.py`
- Create: `tests/test_agentops_control_tower_page.py`
- Modify（导航接入，按现有模式）: `src/ui_report/product_dashboard.py` 或 `main.py` dashboard 入口

**Self-test commands (方案 B):**
```bash
./.venv/bin/python -m ruff check src/ui_report/agentops_control_tower.py tests/test_agentops_control_tower_page.py
./.venv/bin/python -m py_compile src/ui_report/agentops_control_tower.py
./.venv/bin/python -m pytest tests/test_agentops_control_tower_page.py tests/test_agentops_state.py -q --basetemp=runtime/pytest-tmp-agentops-control-tower-page
# UI entrypoint 回归：
./.venv/bin/python -m pytest tests/test_product_dashboard_source.py -q --tb=short --basetemp=runtime/pytest-tmp-agentops-control-tower-ui-regression
```

**Tester checks (方案 B):** Streamlit 渲染 smoke（参照 `tests/test_v16_0b_readonly_market_dashboard.py`、`tests/test_product_dashboard_source.py` 模式）：正常 observation 展示 feature 基础信息；missing doc 显示未生成/missing；failed/blocked/unknown 可见；API 错误显示错误面板不白屏、不显示为通过；不存在 approve/merge/rerun/trigger/trade 按钮文案或动作；页面不重复实现后端聚合规则；现有 dashboard 导航未被破坏。

**Release criteria（两方案共用）:**
- 所选方案自测全绿；UI smoke 有渲染证据（不得用 mock 冒充真实渲染）。
- missing/unknown/failed/blocked 在页面可见，不伪装为通过。
- 无控制动作按钮或写接口暴露。
- 中文 dev/test report 齐备；测试结论 `PASS`/`PASS_WITH_NOTES` 且无 S0/S1/S2 阻断。

**Gate after phase:** 测试通过后路由回 Claude Code Developer 执行 Phase 5。

---

### Phase 5 — 文档、报告与回归

| Field | Value |
|---|---|
| **Scope** | 汇总本 feature 全阶段中文 dev/test 报告；按 touched scope 运行后端与前端（或 Streamlit）回归；确认必需文档齐备且 gate 可独立从仓库文件确认；更新 `docs/log/DEVELOPMENT_LOG.md` 与 `docs/log/PHASE_COMPLETION_REPORT.md`（仅当阶段/发布状态实际变化时）。准备验收所需的用户视角说明。 |
| **Non-Goals** | 不新增功能；不修复本阶段以外缺陷；不自动合并 main。 |
| **Owner** | Claude Code Developer（汇总）+ OpenCode Test Engineer（最终回归验证） |
| **Branch** | `feat/agentops-control-tower/phase-5-reports-regression`（自 epic 分支） |
| **Restricted modules** | 无代码变更；仅文档与回归。 |
| **Dev report** | 复用/更新 `docs/dev_reports/20260624-agentops-control-tower-foundationpipeline-api-re-phase-<n>-dev-report.md`，新增本阶段汇总说明。 |
| **Test report** | `docs/test_reports/20260624-agentops-control-tower-foundationpipeline-api-re-phase-5-test-report.md` |

**Self-test commands（后端，按实际 touched 范围调整）:**
```bash
git status --short --branch
git diff --stat
./.venv/bin/python -m ruff check src/product_app/agentops src/api/agentops_routes.py src/api/app.py tests/test_agentops_pipeline_*.py tests/test_agentops_routes.py
./.venv/bin/python -m py_compile src/product_app/agentops/*.py src/api/agentops_routes.py src/api/app.py
./.venv/bin/python -m pytest tests/test_agentops_pipeline_contracts.py tests/test_agentops_pipeline_state_reader.py tests/test_agentops_pipeline_aggregator.py tests/test_agentops_pipeline_sanitizer.py tests/test_agentops_routes.py -q --tb=short --basetemp=runtime/pytest-tmp-agentops-control-tower-full
# 共享 API entrypoint 回归：
./.venv/bin/python -m pytest tests/test_product_routes.py tests/test_v16_0b_watchlist_api.py tests/test_v16_0b_signal_observation.py -q --tb=short --basetemp=runtime/pytest-tmp-agentops-control-tower-full-regression
git diff --check
```

**前端/Streamlit 回归命令：** 按 Phase 3/4 已选方案对应命令执行（方案 A：`npm run lint && npm test -- --run && npm run build`；方案 B：相关 `tests/test_agentops_*.py` + `tests/test_product_dashboard_source.py`）。

**Tester checks:**
- 全阶段报告存在且中文齐备（dev/test/acceptance 候选）。
- 需求→测试覆盖矩阵完整；未运行项有原因与剩余风险。
- 安全回归：只读保证、敏感信息清洗、fail-visible、未触碰受限模块。
- gate 可从仓库文件独立确认（`python3 scripts/agent_pipeline.py check-gates --through-stage team_plan` 通过；后续阶段 gate 随报告落库逐步通过）。
- 无 S0/S1/S2 阻断缺陷未关闭。

**Release criteria:**
- 后端与前端/Streamlit 回归全绿（预存在无关失败按 AGENTS.md 说明并缩窄重跑）。
- 全阶段中文报告齐备；`all_phases_tested` 可置真。
- 安全确认：未启用真实自动下单、未提交密钥、未绕过风控/股票池/人工确认/fail-closed。
- 测试报告最终结论 `PASS`/`PASS_WITH_NOTES`。

**Gate after phase:** 路由至 OpenCode Lead Review（`claude_lead_review`），再至 Codex B Review、Codex A Acceptance。

---

## Agent Assignments

| Role | Agent | Phases |
|---|---|---|
| Lead Planning & Review | OpenCode Lead（`opencode-go/glm-5.2` + superpowers） | 本计划产出、阶段间路由、最终 Lead Review |
| Developer | Claude Code（`ultracode-xhigh`，`effort=xhigh`，feature-dev + superpowers） | Phase 1、2、3、4、5 实现 + 自测 + 中文 dev report |
| Test Engineer | OpenCode（`deepseek-v4-pro`，`variant=max` + superpowers） | 每阶段临时 `test/...` 分支验证 + 中文 test report |
| Architect Reviewer | Codex B | 前端栈决策门禁解除 + 最终 Codex Review |
| PM Acceptance | Codex A | 最终需求验收 |

## Validation Plan

| Check | When | How |
|---|---|---|
| 后端单测 | 每阶段 gate | `pytest tests/test_agentops_*.py` 全绿 |
| 静态检查 | 每阶段 gate | `ruff check` + `py_compile` 通过 |
| API HTTP 契约 | Phase 2 gate | `TestClient` 验证状态码与错误体 |
| 只读保证 | Phase 2/5 gate | 遍历 `app.routes` 断言无写方法；monkeypatch 断言无写调用 |
| 敏感信息清洗 | Phase 1/2 gate | 响应不含绝对路径/token/`.env`/traceback |
| fail-visible | Phase 1/2 gate | 缺失/不可解析→unknown/missing/unavailable/stale/blocked |
| 前端状态转换 | Phase 3 gate | ready/blocked/empty/error/stale 各路径有测试 |
| UI 渲染 smoke | Phase 4 gate | 组件/Streamlit 渲染证据，不得用 mock 冒充 |
| 受限模块审计 | 每阶段 gate | grep 断言未 import risk/execution/data_gateway/backtest/factor/strategy/stock_pool |
| Gate 文件确认 | Phase 5 gate | `python3 scripts/agent_pipeline.py check-gates --through-stage team_plan` 通过；后续阶段随报告落库通过 |
| 无密钥泄露 | 每阶段 gate | `git diff` 审查无 credentials/tokens/cookies |

## Exit Criteria

全部为真方可声明 epic 分支完成：

1. Phase 1 后端契约/reader/aggregator/sanitizer/errors 实现并通过测试。
2. Phase 2 只读 `/product/agentops` API 实现并通过 HTTP 契约测试，现有 `/product` 路由无回归。
3. 前端栈决策门禁已由 Architect 解除并落库。
4. Phase 3 状态中心按已选方案实现并通过状态转换测试。
5. Phase 4 Control Tower 页面按已选方案实现并通过 UI 渲染 smoke，无控制动作按钮。
6. Phase 5 全阶段中文报告齐备，后端与前端/Streamlit 回归通过。
7. 全程未触碰 restricted modules；未启用真实自动下单；未提交密钥；未绕过风控/股票池/人工确认/fail-closed。
8. gate 可从仓库文件独立确认（`check-gates` 通过对应阶段）。
9. OpenCode Lead Review、Codex Review、PM Acceptance 均完成且无阻断。

## Safety Confirmation

- 默认不真实自动下单：本功能全程只读，无交易入口。
- Risk Agent 一票否决未被绕过：不修改 `src/risk_engine/`。
- 股票池/人工确认/fail-closed 未被绕过：不修改对应模块与策略。
- 不自动合并 main、不执行 `git commit/push/merge`（由 GitHub Stage Runner 管理）。
- 不提交密钥/Token/Cookie/账户/Broker 凭据。
- mock/demo/fixture 仅用于测试，不在产品页面表现为真实 pipeline 状态。
- `LEVEL_3_AUTO` 不作为普通用户可选项暴露。
