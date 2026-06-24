# Phase 1 开发报告：后端 Pipeline 观测契约与只读聚合器

## 需求文档

`docs/requirements/2026-06-24-agentops-control-tower-foundationpipeline-api-re-requirements.md`

## 架构文档

`docs/design/2026-06-24-agentops-control-tower-foundationpipeline-api-re-architecture.md`

## 实现范围

### 新增文件（6 个实现 + 4 个测试）

| 文件 | 说明 |
|---|---|
| `src/product_app/agentops/__init__.py` | 子包初始化 |
| `src/product_app/agentops/pipeline_contracts.py` | Pydantic 契约、枚举、响应/错误模型 |
| `src/product_app/agentops/pipeline_errors.py` | 结构化错误类型与错误码映射 |
| `src/product_app/agentops/pipeline_sanitizer.py` | 路径相对化、Token 清洗、错误信息清理 |
| `src/product_app/agentops/pipeline_state_reader.py` | 只读读取 `.agent/state.json`、`current_task.yaml`、handoff 文件、文档存在性 |
| `src/product_app/agentops/pipeline_aggregator.py` | 聚合为 `AgentOpsPipelineObservation`，含阶段归一化、文档状态、数据质量、安全提示 |
| `tests/test_agentops_pipeline_contracts.py` | 枚举、模型的单元测试（21 个） |
| `tests/test_agentops_pipeline_errors.py` | 错误类型与 `to_error_info` 测试（9 个） |
| `tests/test_agentops_pipeline_sanitizer.py` | 路径清洗、Token 红action、错误信息清理测试（11 个） |
| `tests/test_agentops_pipeline_state_reader.py` | 文件读取、解析、handoff 扫描、文档状态测试（13 个） |
| `tests/test_agentops_pipeline_aggregator.py` | 阶段归一化、角色、文档列表、数据质量、安全评估、完整观测测试（34 个） |

### 功能映射

| 功能 | 对应代码 |
|---|---|
| 枚举定义（4 个） | `pipeline_contracts.py` |
| 核心观测模型 `AgentOpsPipelineObservation` | `pipeline_contracts.py` |
| 支持模型 `ErrorInfo`/`PipelineStageInfo`/`RoleInfo`/`SafetyInfo`/`DataQualityInfo` | `pipeline_contracts.py` |
| 结构化错误 `ParameterError`/`FeatureNotFoundError`/`PipelineStateUnavailableError`/`PipelineStateUnparsableError` | `pipeline_errors.py` |
| 错误 → `ErrorInfo` 映射 | `pipeline_errors.py:to_error_info()` |
| 路径相对化、Token/Secret 清洗 | `pipeline_sanitizer.py` |
| 只读读取 `.agent/state.json`/`current_task.yaml` | `pipeline_state_reader.py:read_pipeline_state()` |
| Handoff 文件扫描 | `pipeline_state_reader.py:read_handoff_files()` |
| 文档存在性检查 | `pipeline_state_reader.py:check_doc_status_readonly()` |
| 阶段状态归一化（未知 → `unknown`） | `pipeline_aggregator.py:normalize_stage_statuses()` |
| 必需文档列表构建 | `pipeline_aggregator.py:build_required_doc_list()` |
| 数据质量评估 | `pipeline_aggregator.py:evaluate_data_quality()` |
| 安全提示与阻塞原因 | `pipeline_aggregator.py:evaluate_safety()` |
| 完整流水线观测 → `AgentOpsPipelineObservation` | `pipeline_aggregator.py:get_pipeline_observation()` |

## 自测命令与结果

### 1. Git 工作区状态

```bash
git status --short --branch
```
输出：当前分支 `epic/20260624-agentops-control-tower-foundationpipeline-api-re-issue-75`，仅新增未跟踪文件。

### 2. Ruff 静态检查

```bash
python3 -m ruff check src/product_app/agentops/ tests/test_agentops_*.py
```
结果：All checks passed!（0 errors）

### 3. py_compile

```bash
python3 -m py_compile src/product_app/agentops/*.py
```
结果：无输出（成功）

### 4. 单元测试

```bash
python3 -m pytest tests/test_agentops_pipeline_contracts.py tests/test_agentops_pipeline_errors.py tests/test_agentops_pipeline_sanitizer.py tests/test_agentops_pipeline_state_reader.py tests/test_agentops_pipeline_aggregator.py -v --basetemp=runtime/pytest-tmp-agentops-control-tower
```
结果：**88 passed in 1.47s**

### 5. Git diff 检查

```bash
git diff --check
```
结果：无输出（无冲突标记或空白错误）

### 6. 受限模块审计

```bash
grep -r "from src.\(risk_engine\|execution_engine\|data_gateway\|backtest_engine\|factor_engine\|strategy_engine\|stock_pool\)" src/product_app/agentops/
```
结果：无匹配（未触碰任何受限模块）

## 安全确认

- [x] 未启用真实自动下单（功能全程只读，无交易入口）
- [x] 未提交密钥/Token/Cookie/账户/Broker 凭据
- [x] 未绕过风控/股票池/人工确认/fail-closed 规则
- [x] 未触碰 restricted modules（`src/risk_engine/`、`src/execution_engine/`、`src/data_gateway/`、`src/backtest_engine/`、`src/factor_engine/`、`src/strategy_engine/`、`src/stock_pool/`）
- [x] 所有 API 错误走 sanitizer，不暴露敏感信息
- [x] fail-visible：缺失/不可解析返回 `unknown`/`missing`/`unavailable`/`stale`/`blocked`，不返回 `passed`
- [x] `contract_version` 必须存在且为 `agentops.pipeline_observation.v1`
- [x] reader/aggregator 不执行写操作（通过 mock 验证）

## 剩余风险

- `pipeline_sanitizer.py` 的绝对路径检测使用正则匹配，在极少数包含长路径的异常消息中可能误匹配；当前测试覆盖了已知用例。
- `pipeline_aggregator.py` 的 `get_pipeline_observation` 依赖真实 `.agent/state.json` 文件；当该文件缺失或 feature_id 不匹配时正确返回 `FeatureNotFoundError`。
- 当前未接入真实 GitHub API，`issue.url` 取自 state.json 中的静态值。

## 是否影响真实交易能力

否。本阶段未引入任何交易、风控、下单或 Broker 相关代码。

## 最终结论

PASS_WITH_NOTES。Phase 1 实现完成。88 个测试全绿，ruff/py_compile 通过，受限模块零触碰，安全确认全部通过。
