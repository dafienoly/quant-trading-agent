# agentops-control-tower-foundationpipeline-api-re Architecture

## Architecture Summary

本设计为 AgentOps Control Tower Foundation 建立“只读、可观测、可追踪”的基础层，覆盖三条主线：

1. 后端定义稳定的 Pipeline 观测契约，用结构化模型表达 feature、issue、epic branch、阶段状态、角色状态、必需文档、风险提示、阻塞原因与数据来源。
2. 后端提供只读聚合 API，从本地 pipeline state、任务状态文件与必需文档路径聚合当前 feature / issue 的观测状态，不触发任何写操作。
3. 前端 React 状态中心统一消费聚合 API，向 Control Tower Foundation 页面提供 `loading`、`ready`、`empty`、`stale`、`error`、`blocked` 等状态，避免页面组件重复解析 pipeline 语义。

本功能不实现流水线控制动作，不修改交易、风控、执行、行情、回测、策略或股票池逻辑，不引入真实交易、模拟交易、审批、合并、重跑、评论、分支创建或 CI 触发能力。

建议目标 API：

```text
GET /product/agentops/pipelines/{feature_id}
GET /product/agentops/pipelines/by-issue/{issue_number}
```

API 所有响应必须来自明确数据来源，并在数据缺失、不可解析或过期时显式返回 `unknown`、`missing`、`stale`、`blocked` 或结构化错误，不得伪造通过状态。

核心数据流：

```text
local pipeline state / .agent / docs paths
  -> AgentOpsPipelineStateReader
  -> AgentOpsPipelineAggregator
  -> Pydantic observation contract
  -> readonly FastAPI route
  -> React AgentOps store
  -> Control Tower Foundation page
```

## Module Plan

### 后端模块边界

新增或扩展模块应限制在 AgentOps / product API / UI 范围内，不触碰 restricted modules。

建议新增后端模块：

```text
src/product_app/agentops/
├── __init__.py
├── pipeline_contracts.py
├── pipeline_state_reader.py
├── pipeline_aggregator.py
├── pipeline_errors.py
└── pipeline_sanitizer.py
```

模块职责：

| 模块 | 职责 | 禁止事项 |
|---|---|---|
| `pipeline_contracts.py` | 定义 Pydantic 契约、枚举、响应模型、错误模型 | 不读取文件、不访问 GitHub、不包含业务聚合逻辑 |
| `pipeline_state_reader.py` | 只读读取本地 pipeline state、`.agent/current_task.yaml`、`.agent/handoff/*.md`、必需文档存在性 | 不写文件、不创建目录、不修改状态 |
| `pipeline_aggregator.py` | 将 reader 输出聚合为统一观测响应，计算文档状态、阶段汇总、阻塞提示、风险提示 | 不调用写操作、不触发 CI、不访问交易模块 |
| `pipeline_errors.py` | 定义参数错误、feature 不存在、数据源缺失、不可解析、内部异常等错误类型 | 不暴露堆栈或敏感路径 |
| `pipeline_sanitizer.py` | 清洗错误信息、路径、环境变量疑似内容、token-like 字符串 | 不返回 `.env` 内容或敏感环境值 |

API 层建议新增：

```text
src/api/agentops_routes.py
```

并在 app factory 或 product route 聚合入口中注册只读 router：

```text
/product/agentops
```

如果项目现有规范要求所有产品路由集中在 `src/api/product_routes.py`，则由 Developer 按现有模式接入，但 AgentOps 聚合逻辑不得写入 `product_routes.py` 内部，避免形成臃肿路由文件。

### 后端契约模型

状态枚举建议统一为小写字符串，供 API 与 React 共享语义：

```text
PipelineStageStatus:
- pending
- in_progress
- passed
- failed
- blocked
- skipped
- unknown

DocumentStatus:
- present
- missing
- stale
- unreadable
- unknown

DataQualityStatus:
- complete
- incomplete
- unavailable
- unparsable
- stale
- unknown

ControlTowerViewStatus:
- ready
- empty
- stale
- error
- blocked
```

核心响应模型建议：

```text
AgentOpsPipelineObservation
├── contract_version: "agentops.pipeline_observation.v1"
├── generated_at
├── feature
│   ├── feature_id
│   ├── title
│   ├── risk_level
│   └── current_stage
├── issue
│   ├── number
│   └── url
├── branch
│   └── epic_branch
├── stages[]
│   ├── name
│   ├── status
│   ├── source
│   └── notes[]
├── roles[]
│   ├── agent
│   ├── responsibilities[]
│   └── status
├── required_docs[]
│   ├── kind
│   ├── path
│   ├── status
│   ├── source
│   └── required
├── safety
│   ├── readonly
│   ├── trading_modules_touched
│   ├── restricted_module_change
│   ├── warnings[]
│   └── blockers[]
├── data_quality
│   ├── status
│   ├── missing_sources[]
│   ├── unparsable_sources[]
│   └── stale_sources[]
└── errors[]
    ├── code
    ├── message
    ├── source
    └── safe_detail
```

字段要求：

- `contract_version` 必须存在，后续破坏性变更升级为 `v2`。
- `source` 必须指向可追踪来源，例如 `.agent/current_task.yaml`、`.agent/handoff/codex_architect.md`、`docs/requirements/...`、`pipeline_state.required_docs`。
- `path` 使用仓库相对路径，不返回本地绝对路径。
- 错误信息必须经过 sanitizer，不能包含 secrets、token、cookies、环境变量值、CI 凭证或完整堆栈。

### 数据来源优先级

聚合器按以下优先级读取：

1. 显式请求参数：`feature_id` 或 `issue_number`。
2. `.agent/current_task.yaml` 中的当前任务状态。
3. `.agent/handoff/<stage>.md` 中的 handoff 信息。
4. `docs/requirements/<feature>-requirements.md` 与 pipeline state 中声明的 `required_docs`。
5. 文件系统只读检查得到的文档存在性。

本阶段不要求实时 GitHub API。若后续接入 GitHub，只允许只读查询，并且网络失败必须显示 `unavailable` 或 `stale`，不得阻塞服务进程或回退为伪成功。

### 前端模块边界

React 状态中心建议放在现有 React 应用目录下。若仓库存在标准前端目录，优先遵循现有结构；建议逻辑边界如下：

```text
<react-root>/src/features/agentops/
├── api/
│   └── pipelineClient.ts
├── state/
│   └── pipelineStore.ts
├── types/
│   └── pipeline.ts
├── components/
│   ├── ControlTowerPage.tsx
│   ├── PipelineSummary.tsx
│   ├── StageStatusList.tsx
│   ├── RequiredDocsList.tsx
│   └── SafetyBlockersPanel.tsx
└── __tests__/
```

职责：

| 前端模块 | 职责 | 禁止事项 |
|---|---|---|
| `pipelineClient.ts` | 调用只读 API，处理 HTTP 错误到统一错误结构 | 不调用任何写接口 |
| `pipelineStore.ts` | 统一管理 loading、ready、empty、stale、error、blocked、refresh | 不重复实现后端聚合规则 |
| `pipeline.ts` | 镜像后端契约 TypeScript 类型 | 不定义与后端冲突的状态枚举 |
| 页面组件 | 展示 feature、issue、branch、阶段、文档、安全提示 | 不伪造通过状态、不隐藏 missing/unknown |

前端状态中心对外暴露：

```text
state:
- viewStatus
- observation
- error
- lastLoadedAt
- isRefreshing

actions:
- loadByFeatureId(featureId)
- loadByIssueNumber(issueNumber)
- refresh()
- clear()
```

状态转换规则：

```text
idle -> loading
loading + 200 complete -> ready
loading + 200 incomplete with blockers -> blocked
loading + 200 stale -> stale
loading + 404 -> empty
loading + 400/422 -> error
loading + 500 -> error
refresh failure with previous data -> stale
```

### 页面展示范围

Control Tower Foundation 页面必须展示：

- feature 标题、`feature_id`、risk level、当前阶段。
- issue number、issue URL。
- epic branch。
- 阶段总览：`pm`、`architecture`、`team_plan`、`phase_dev`、`phase_test`、`claude_lead_review`、`codex_review`、`acceptance`。
- 角色分工：Codex A、Codex B、OpenCode Lead、Claude Developer、OpenCode Tester。
- 必需文档清单与状态。
- 数据质量状态。
- 安全提示与阻塞原因。
- API 错误、缺失数据、不可解析数据时的可理解失败状态。

不得展示任何 approve、reject、merge、rerun、trigger、assign、label、comment、trade、order 等操作按钮。

## Technical Decisions

### 1. 使用 Pydantic 作为后端契约源

后端以 Pydantic 模型作为 API 契约源，FastAPI 自动生成 schema。React 侧可手写轻量类型或通过后续阶段引入 schema 生成，但本阶段不要求新增复杂 codegen。

原因：

- 项目后端已有 FastAPI / Pydantic 使用背景。
- 契约能被单元测试直接验证。
- API 响应字段稳定，便于后续 AgentOps 页面复用。

### 2. API 只读聚合，不引入控制命令

本阶段 API 仅支持 `GET`。任何 `POST`、`PUT`、`PATCH`、`DELETE`、workflow trigger、GitHub mutation、文件写入、状态更新都不属于本 feature。

API 层必须避免调用以下能力：

```text
git commit
git push
git merge
gh workflow run
gh pr merge
GitHub comment / label / assign / review mutation
filesystem write
CI rerun
agent state update
trading order / broker API
```

测试中应通过 monkeypatch / mock 验证聚合路径没有调用写入函数。

### 3. 缺失和异常默认不可通过

聚合规则必须 fail-visible：

```text
required doc missing -> document.status = missing
stage state absent -> stage.status = unknown
pipeline state unreadable -> data_quality.status = unavailable
pipeline state unparsable -> data_quality.status = unparsable
required current gate failed -> safety.blockers includes reason
unknown risk_level -> safety.warnings includes unknown risk
```

不得将缺失值默认为 `passed`、`complete` 或 `ready`。

### 4. 错误响应结构化

API 错误响应建议：

```json
{
  "error": {
    "code": "PIPELINE_STATE_UNPARSABLE",
    "message": "流水线状态不可解析",
    "safe_detail": "无法解析 .agent/current_task.yaml",
    "source": ".agent/current_task.yaml"
  }
}
```

HTTP 状态建议：

| 场景 | HTTP |
|---|---|
| 参数格式错误 | `400` 或 `422` |
| feature / issue 不存在 | `404` |
| 数据源缺失且无法形成观测响应 | `503` |
| 数据不可解析 | `422` |
| 内部异常 | `500` |

如果仍能形成部分观测响应，优先返回 `200` 并在 `data_quality` / `errors` 中表达不完整状态；如果无法确定目标 feature，则返回错误响应。

### 5. 路径安全与敏感信息清洗

API 只返回仓库相对路径：

```text
docs/requirements/...
docs/design/...
docs/dev_reports/...
```

不得返回：

```text
/mnt/d/actions-runner/...
C:\...
.env
token values
cookies
broker credentials
GitHub Actions secrets
完整 traceback
```

sanitizer 应处理：

- 绝对路径转相对路径或隐藏为 `<workspace>`.
- token-like 字符串替换为 `<redacted>`.
- 环境变量值不进入响应。
- 异常只保留错误类型和安全说明。

### 6. React 状态中心只消费契约，不重新推导核心语义

后端负责聚合和核心状态解释，前端负责展示与用户态转换。前端可以将 `data_quality.status` 和 `safety.blockers` 映射为 `viewStatus`，但不得重新判断“文档是否齐备即 passed”这类核心规则。

### 7. UI 风格

Control Tower 页面是运维 / AgentOps 工具，应采用密集、清晰、可扫描的工作台布局：

- 顶部显示 feature 摘要和当前阶段。
- 中部展示阶段状态列表和必需文档清单。
- 侧栏或下方展示安全提示、阻塞原因、数据质量。
- 状态颜色保持克制：failed / blocked 明确突出，unknown / stale 不应弱化为成功。
- 不使用营销式 hero、装饰性大图或无关视觉素材。
- 不出现自动化控制按钮或交易相关入口。

### 8. 聚合伪代码

```python
def get_pipeline_observation(feature_id: str | None, issue_number: int | None):
    target = resolve_target(feature_id, issue_number)

    if target.invalid:
        raise ParameterError(...)

    read_result = reader.read_current_state(target)

    if read_result.not_found:
        raise FeatureNotFound(...)

    if read_result.unparsable and not read_result.partial:
        raise PipelineStateUnparsable(...)

    required_docs = build_required_doc_list(read_result.state)
    doc_statuses = []

    for doc in required_docs:
        status = check_doc_status_readonly(doc.path)
        doc_statuses.append({
            "kind": doc.kind,
            "path": sanitize_repo_relative_path(doc.path),
            "status": status,
            "required": doc.required,
            "source": doc.source,
        })

    stages = normalize_stage_statuses(read_result.state.stage_status)
    roles = normalize_roles(read_result.state.agent_roles)

    data_quality = evaluate_data_quality(
        read_result=read_result,
        doc_statuses=doc_statuses,
        stages=stages,
    )

    safety = evaluate_safety(
        readonly=True,
        risk_level=read_result.state.risk_level,
        doc_statuses=doc_statuses,
        data_quality=data_quality,
    )

    return AgentOpsPipelineObservation(
        contract_version="agentops.pipeline_observation.v1",
        generated_at=now_utc(),
        feature=feature_from_state(read_result.state),
        issue=issue_from_state(read_result.state),
        branch=branch_from_state(read_result.state),
        stages=stages,
        roles=roles,
        required_docs=doc_statuses,
        safety=safety,
        data_quality=data_quality,
        errors=read_result.safe_errors,
    )
```

前端状态中心伪代码：

```typescript
async function loadByFeatureId(featureId: string) {
  setState({ viewStatus: "loading", error: null })

  try {
    const observation = await pipelineClient.getByFeatureId(featureId)
    const viewStatus = deriveViewStatus(observation)

    setState({
      viewStatus,
      observation,
      error: null,
      lastLoadedAt: new Date().toISOString(),
    })
  } catch (error) {
    if (state.observation) {
      setState({
        viewStatus: "stale",
        error: normalizeError(error),
      })
      return
    }

    setState({
      viewStatus: isNotFound(error) ? "empty" : "error",
      observation: null,
      error: normalizeError(error),
    })
  }
}
```

## Safety Impact

本功能安全影响为低到中等，原因是它新增可观测 API 和 UI 状态中心，但不应进入交易、执行、风控、行情或自动化写操作路径。

必须遵守以下安全边界：

1. 不修改 `src/risk_engine/`、`src/execution_engine/`、`src/data_gateway/`、`src/backtest_engine/`、`src/factor_engine/`、`src/strategy_engine/`、`src/stock_pool/`。
2. 不新增任何交易、下单、撤单、自动交易、模拟交易或 broker 调用。
3. 不暴露 `LEVEL_3_AUTO` 为普通用户可选项。
4. 不绕过 Risk Agent 一票否决、人工确认、stock pool filter、execution policy、risk policy 或 fail-closed 规则。
5. 不改变自动合并政策、分支工作流、Agent 角色职责、CI 策略或 GitHub workflow 行为。
6. Pipeline 数据源缺失、不可解析、过期或必需文档缺失时必须显示 `unknown`、`missing`、`unavailable`、`stale` 或 `blocked`。
7. API 和 UI 不得泄露 secrets、tokens、cookies、broker credentials、`.env` 内容、CI 凭证、完整 traceback 或敏感本地绝对路径。
8. mock、fixture、demo 数据只能用于测试，不得在产品页面表现为真实 pipeline 状态。
9. 若开发过程中必须触碰 restricted modules，应停止当前实现，升级为受限模块变更，补充人工审批、负向测试和架构复审。

只读保证建议测试点：

- API route 只注册 `GET`。
- 聚合器不调用文件写入 API。
- 不调用 GitHub mutation、workflow rerun、branch / PR mutation。
- 不调用交易执行、风控放行或 broker 相关模块。
- 错误路径不写 bug 文件、不更新 `.agent` 状态、不生成报告文件。

## Development Guidance

### Phase Slice 1：后端契约与聚合器

目标：

- 新增 AgentOps pipeline 观测契约。
- 实现只读 state reader、document status checker、aggregator、sanitizer。
- 覆盖契约解析、缺失字段、未知状态、不可解析输入、敏感信息清洗测试。

建议 touched files：

```text
src/product_app/agentops/pipeline_contracts.py
src/product_app/agentops/pipeline_state_reader.py
src/product_app/agentops/pipeline_aggregator.py
src/product_app/agentops/pipeline_errors.py
src/product_app/agentops/pipeline_sanitizer.py
tests/product_app/agentops/test_pipeline_contracts.py
tests/product_app/agentops/test_pipeline_aggregator.py
```

测试重点：

- 完整 pipeline state 返回 `complete` / `ready` 候选数据。
- 缺失 required doc 返回 `missing`，不得返回 passed。
- 未知 stage status 归一化为 `unknown`。
- 不可解析 YAML 返回结构化错误或 partial observation。
- 绝对路径、token-like 字符串、`.env` 内容不出现在响应模型中。
- reader 和 aggregator 不执行写操作。

### Phase Slice 2：只读 API

目标：

- 新增 `/product/agentops` 只读 router。
- 支持按 `feature_id` 和 `issue_number` 查询。
- 返回统一 observation 或结构化错误。
- 保持与现有 `/product` 路由兼容。

建议 touched files：

```text
src/api/agentops_routes.py
src/api/app.py 或现有 router 注册入口
tests/api/test_agentops_routes.py
```

测试重点：

- `GET /product/agentops/pipelines/{feature_id}` 成功。
- `GET /product/agentops/pipelines/by-issue/{issue_number}` 成功。
- 参数错误返回 `400` / `422`。
- feature 不存在返回 `404`。
- 数据源缺失返回明确错误或 partial observation。
- 内部异常返回安全错误，不含 traceback / secret。
- API 不注册写方法。
- route mock aggregator，避免依赖真实 GitHub 网络。

### Phase Slice 3：React 状态中心

目标：

- 新增 TypeScript 类型、API client、状态中心。
- 实现 loading、ready、empty、stale、error、blocked 状态转换。
- 避免组件重复请求和重复解析核心 pipeline 状态。

建议 touched files：

```text
<react-root>/src/features/agentops/types/pipeline.ts
<react-root>/src/features/agentops/api/pipelineClient.ts
<react-root>/src/features/agentops/state/pipelineStore.ts
<react-root>/src/features/agentops/__tests__/pipelineStore.test.ts
```

测试重点：

- 正常 200 响应进入 `ready`。
- 有 blockers 的 observation 进入 `blocked`。
- 404 进入 `empty`。
- 500 或网络错误进入 `error`。
- refresh 失败但已有旧数据时进入 `stale`。
- 状态中心缓存同一 feature，避免重复并发请求。
- 不存在写 API client 方法。

### Phase Slice 4：Control Tower Foundation 页面集成

目标：

- 页面展示 feature、issue、branch、当前阶段、阶段总览、文档清单、安全 / 阻塞提示。
- API 失败、不完整、缺失文档、未知风险时页面可见。
- 不展示任何控制动作按钮。

建议 touched files：

```text
<react-root>/src/features/agentops/components/ControlTowerPage.tsx
<react-root>/src/features/agentops/components/PipelineSummary.tsx
<react-root>/src/features/agentops/components/StageStatusList.tsx
<react-root>/src/features/agentops/components/RequiredDocsList.tsx
<react-root>/src/features/agentops/components/SafetyBlockersPanel.tsx
<react-root>/src/features/agentops/__tests__/ControlTowerPage.test.tsx
```

测试重点：

- 正常 observation 展示 feature 基础信息。
- missing doc 明确显示未生成 / missing。
- failed / blocked / unknown 状态可见。
- API 错误显示错误面板，不白屏，不显示为通过。
- 页面不存在 approve / merge / rerun / trigger / trade 等按钮文案或 action。
- 组件不重复实现后端阶段聚合规则。

### Phase Slice 5：文档、报告与回归

目标：

- Claude Developer 产出中文开发报告。
- OpenCode Tester 产出中文测试报告。
- 后续验收阶段产出中文 acceptance。
- 根据 touched scope 运行后端和前端测试。

建议报告路径：

```text
docs/dev_reports/20260624-agentops-control-tower-foundationpipeline-api-re-phase-<n>-dev-report.md
docs/test_reports/20260624-agentops-control-tower-foundationpipeline-api-re-phase-<n>-test-report.md
docs/acceptance/20260624-agentops-control-tower-foundationpipeline-api-re-acceptance.md
```

报告必须包含：

- 变更范围。
- 测试命令。
- 测试结果。
- 安全确认。
- 最终结论。
- 未运行测试与剩余风险。

### 后端测试命令建议

Developer 根据实际 touched files 缩小或扩大范围：

```bash
git status --short --branch
git diff --stat
./.venv/bin/python -m ruff check src/product_app/agentops src/api/agentops_routes.py tests/product_app/agentops tests/api/test_agentops_routes.py
./.venv/bin/python -m py_compile src/product_app/agentops/*.py src/api/agentops_routes.py
./.venv/bin/python -m pytest tests/product_app/agentops tests/api/test_agentops_routes.py -q --basetemp=runtime/pytest-tmp-agentops-control-tower
git diff --check
```

如触及 app factory、product route 注册或共享 API 入口，追加：

```bash
./.venv/bin/python -m pytest tests/api -q --tb=short --basetemp=runtime/pytest-tmp-agentops-control-tower-api
```

### 前端测试命令建议

根据现有前端工具链选择等效命令，例如：

```bash
npm run lint -- --quiet
npm test -- --run
npm run build
```

若项目使用 `pnpm`、`yarn`、`vitest` 或其他命令，以仓库现有脚本为准，并在报告中记录实际命令和结果。

### OpenCode Lead Handoff

OpenCode Lead 应负责：

- 将本设计拆分为上述 phase slices，控制每个 phase 的 touched scope。
- 先确认仓库现有 React 根目录、测试框架和 router 接入方式。
- 确认后端 route 注册遵循现有 FastAPI 模式。
- 明确每个 phase 的输入、输出、测试命令和报告路径。
- 确保 Claude Developer 不触碰 restricted modules。
- 确保所有 phase 完成后再进入 team lead review。
- 如任何 phase 需要写操作、GitHub mutation、CI trigger 或交易模块变更，立即退回架构审查。

### Claude Developer Handoff

Claude Developer 应负责：

- 严格按 phase 实现，不跨 phase 引入控制动作。
- 开始前运行 `git status --short --branch` 和 `git diff --stat`。
- 优先补充契约和聚合器测试，再实现最小代码。
- 所有数据读取保持只读，不创建、不修改、不删除 pipeline state 或文档。
- 所有 API 错误走 sanitizer，不暴露敏感信息。
- 前端组件只展示状态，不加入 approve、reject、rerun、merge、trigger、trade 等操作。
- 每个 phase 产出中文 dev report，记录 exact commands 和结果。
- 若测试失败，不得删除或弱化测试制造通过。

### OpenCode Tester Handoff

OpenCode Tester 应负责：

- 在临时 test branch 上验证，结束后回到原开发分支并删除临时分支。
- 重跑 Developer 报告中的关键命令。
- 建立 requirement-to-test coverage matrix。
- 覆盖正常、缺失数据、不可解析、API 错误、敏感信息清洗、只读保证、前端错误展示。
- 验证页面不会白屏，不会将 missing / unknown / failed / blocked 显示为通过。
- 验证没有控制动作按钮或写接口暴露。
- 若发现运行时缺陷且 feedback generation 在范围内，创建 `feedback/bugs/open/BUG_*.md` 与 `.json`。
- 产出中文 test report，最终结论只能是 `PASS`、`PASS_WITH_NOTES` 或 `REJECTED`。