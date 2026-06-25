# Phase 2 开发报告 — 只读 AgentOps API 路由

## 基本信息

| 项目 | 内容 |
|------|------|
| 需求文档 | `docs/requirements/2026-06-24-agentops-control-tower-foundationpipeline-api-re-requirements.md` |
| 架构文档 | `docs/design/2026-06-24-agentops-control-tower-foundationpipeline-api-re-architecture.md` |
| 团队计划 | `docs/dev_plans/20260624-agentops-control-tower-foundationpipeline-api-re-team-plan.md` |
| 阶段 | Phase 2 — 只读 AgentOps API 路由 |
| 开发者 | OpenCode Developer（`claude_developer` stage） |
| 运行时 | `opencode-go/deepseek-v4-flash` + superpowers |

## 实现范围

### 变更文件

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `src/api/agentops_routes.py` | 只读 AgentOps API 路由，定义 `APIRouter()`，仅注册 GET 端点 |
| 修改 | `src/api/app.py` | 在 `create_app()` 中注册 agentops router（`prefix="/product/agentops"`） |
| 新增 | `tests/test_agentops_routes.py` | 路由测试：成功路径、错误映射、只读保证、参数验证 |

### 功能映射

| 功能点 | 对应文件 | 说明 |
|--------|----------|------|
| `GET /product/agentops/pipelines/{feature_id}` | `agentops_routes.py:66` | 按 feature_id 查询 pipeline 观测数据 |
| `GET /product/agentops/pipelines/by-issue/{issue_number}` | `agentops_routes.py:82` | 按 issue_number 查询 pipeline 观测数据 |
| ParameterError → 422 | `agentops_routes.py:30` | 错误映射 |
| FeatureNotFoundError → 404 | `agentops_routes.py:31` | 错误映射 |
| PipelineStateUnavailableError → 503 | `agentops_routes.py:32` | 错误映射 |
| PipelineStateUnparsableError → 422 | `agentops_routes.py:33` | 错误映射 |
| 未知异常 → 500 | `agentops_routes.py:39-40` | 通过 sanitizer 清洗错误消息 |

## 依赖关系

- 复用 Phase 1 `src.product_app.agentops.pipeline_aggregator.get_pipeline_observation()`
- 复用 Phase 1 `src.product_app.agentops.pipeline_errors.*` 错误模型和映射
- 复用 Phase 1 `src.product_app.agentops.pipeline_sanitizer.sanitize_error_message()`
- 在 `app.py` 中新增一行 `include_router` 注册

## 自测结果

### 静态检查

```bash
.venv/bin/python -m ruff check src/api/agentops_routes.py src/api/app.py tests/test_agentops_routes.py
# 结果: All checks passed!

.venv/bin/python -m py_compile src/api/agentops_routes.py src/api/app.py
# 结果: 通过（无输出）
```

### 单元测试

```bash
.venv/bin/python -m pytest tests/test_agentops_routes.py -q --basetemp=runtime/pytest-tmp-agentops-control-tower-api
# 结果: 10 passed

.venv/bin/python -m pytest tests/test_product_routes.py tests/test_v16_0b_watchlist_api.py tests/test_v16_0b_signal_observation.py -q --tb=short --basetemp=runtime/pytest-tmp-agentops-control-tower-api-regression
# 结果: 18 passed（无回归）
```

### 测试覆盖（Route 测试）

| 测试 | 验证内容 |
|------|----------|
| `test_get_pipeline_by_feature_id_success` | feature_id 路径返回 200 + contract_version |
| `test_get_pipeline_by_issue_number_success` | issue_number 路径返回 200 |
| `test_missing_both_params_returns_422` | 无参数时 FastAPI 返回 404（路径不匹配） |
| `test_feature_not_found_returns_404` | FeatureNotFoundError → 404 + 错误码 |
| `test_pipeline_state_unavailable_returns_503` | PipelineStateUnavailableError → 503 |
| `test_pipeline_state_unparsable_returns_422` | PipelineStateUnparsableError → 422 |
| `test_internal_error_returns_500_without_traceback` | 未知异常 → 500，响应不含 traceback/绝对路径 |
| `test_agentops_router_only_has_get_methods` | `/product/agentops` 前缀下仅注册 GET |
| `test_aggregator_called_with_correct_params` | get_pipeline_observation 被正确调用 |
| `test_aggregator_called_with_issue_number` | issue_number 参数正确传递 |

## 安全确认

- ✅ 只限 GET，无任何写操作端点
- ✅ 错误响应经 `pipeline_sanitizer.sanitize_error_message()` 清洗，不含 traceback、绝对路径、token
- ✅ 不修改 `src/risk_engine/`、`src/execution_engine/`、`src/data_gateway/` 等受限模块
- ✅ 不发起 GitHub mutation、不写入文件、不修改 `.agent` 状态
- ✅ 未启用真实自动下单
- ✅ 未提交密钥、Token、Cookie、账户或 Broker 凭据

## 剩余风险

- 当 `.agent/state.json` 完全不可用时，`get_pipeline_observation` 抛出 `PipelineStateUnavailableError`，路由层返回 503。该行为已在测试中覆盖。
- 本阶段不涉及前端，前端栈决策门禁尚未解除，Phase 3/4 不可开始。

## 最终结论

PASS

Phase 2 实现完成。所有 10 项路由测试通过，ruff/py_compile 静态检查通过，现有 product 路由回归（18 项）无退化。已满足开发门禁条件，可交由 Test Engineer Agent 验证。
