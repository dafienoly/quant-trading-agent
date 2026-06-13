# DeepSeek Agent Runtime 开发报告

> Developer Agent Implementation Report  
> 日期：2026-06-12  
> 当前分支：`feat/deepseek-agent-runtime/llm-core`  
> 基线分支：`epic/2026-06-12-deepseek-agent-runtime`

---

## 1. 需求与架构

- **需求文档**：`docs/requirements/2026-06-12-deepseek-agent-runtime-requirements.md`
- **架构文档**：`docs/design/2026-06-12-deepseek-agent-runtime-architecture.md`
- **开发指导**：无独立开发指导文件（由架构文档 §12 开发顺序覆盖）

---

## 2. 自测级别

- **级别**: L1 普通代码 + L6 自动修复(BugFix迁移)
- **理由**: 触碰 `src/llm/`（全新 LLM 调用框架）及 `src/product_app/bug_fix_agent.py`（受限模块变更）

---

## 3. 修改/新增文件列表

### 新增文件（7 个源文件 + 6 个测试文件）

| 文件 | 说明 |
|---|---|
| `src/llm/schemas.py` | Pydantic schema 定义：DeepSeekRequest/Result、LLMTaskProfile、BugFixAnalysis/Proposal |
| `src/llm/usage.py` | UsageTracker：token、cache hit/miss、latency 统计 |
| `src/llm/context_cache.py` | ContextPrefixCache：本地稳定 prefix 缓存 |
| `src/llm/conversation.py` | AgentConversation：多轮对话管理、脱敏持久化、TTL |
| `src/llm/tool_registry.py` | ToolRegistry：只读工具注册、schema 暴露、安全校验 |
| `src/llm/deepseek_runtime.py` | DeepSeekRuntime：统一 async-first 调用框架（thinking/JSON/tool loop） |
| `tests/test_deepseek_runtime.py` | Runtime 单元测试（16 cases） |
| `tests/test_deepseek_tools.py` | Tool Registry 测试（11 cases） |
| `tests/test_deepseek_context_cache.py` | Context Prefix Cache 测试（10 cases） |
| `tests/test_deepseek_conversation.py` | Conversation 测试（10 cases） |
| `tests/test_deepseek_usage.py` | Usage Tracker 测试（6 cases） |
| `tests/test_bugfix_agent_deepseek_runtime.py` | BugFixAgent Runtime 迁移测试（12 cases） |

### 修改文件（4 个）

| 文件 | 变更说明 |
|---|---|
| `src/llm/__init__.py` | 更新 module docstring，添加 `__all__` 导出 |
| `src/llm/model_router.py` | 移除直接 OpenAI SDK 调用，改为委托 DeepSeekRuntime |
| `src/product_app/bug_fix_agent.py` | 迁移至 DeepSeekRuntime，移除直接 OpenAI SDK 调用 |
| `.env.example` | 添加 LLM runtime 配置项（LLM_TIMEOUT_SECONDS 等） |

---

## 4. 功能点到代码映射

| 需求 ID | 功能点 | 代码位置 | 说明 |
|---|---|---|---|
| F-001 | 统一 DeepSeek Runtime | `src/llm/deepseek_runtime.py` | DeepSeekRuntime 类，封装配置、请求、响应、错误、usage |
| F-002 | 非阻塞调用能力 | `src/llm/deepseek_runtime.py:chat_json_async()` | async-first，Semaphore 限流，await asyncio.wait_for 超时 |
| F-003 | Thinking Mode | `src/llm/deepseek_runtime.py:137-142` | extra_body.thinking 和 reasoning_effort 参数 |
| F-004 | Multi-round Conversation | `src/llm/conversation.py` | AgentConversation 消息管理/持久化/TTL |
| F-005 | Tool Calls | `src/llm/tool_registry.py` + `deepseek_runtime.py:150-190` | 工具注册、循环执行、最大轮数 |
| F-006 | Context Prefix Cache | `src/llm/context_cache.py` | 稳定 prefix 组合/fingerprint/持久化 |
| F-007 | JSON Output | `src/llm/deepseek_runtime.py:135,155-160` | response_format + Pydantic schema 校验 |
| F-008 | BugFixAgent 迁移 | `src/product_app/bug_fix_agent.py` | 使用 DeepSeekRuntime 替换直接 OpenAI SDK 调用 |
| F-009 | Agent 复用约束 | `src/llm/__init__.py` + schemas.py | 统一框架入口 |
| F-010 | 可观测性 | `src/llm/usage.py` | UsageTracker 记录/聚合/日志 |
| F-011 | 安全边界 | `src/llm/tool_registry.py:只读校验` + schemas.py | 只读工具、schema 校验、受限模块阻断 |

---

## 5. 测试结果

### 5.1 新增测试（65 passes, 0 failures）

```bash
pytest tests/test_deepseek_runtime.py tests/test_deepseek_tools.py \
      tests/test_deepseek_context_cache.py tests/test_deepseek_conversation.py \
      tests/test_deepseek_usage.py tests/test_bugfix_agent_deepseek_runtime.py \
      -v --basetemp=runtime/pytest-tmp-deepseek-runtime
```

结果：**65 passed in 19.33s**

各测试文件分解：

| 测试文件 | 通过 | 说明 |
|---|---|---|
| `test_deepseek_runtime.py` | 16 | missing key/SDK、profile、JSON parse、thinking、result model |
| `test_deepseek_tools.py` | 11 | 注册、执行、路径安全、只读约束 |
| `test_deepseek_context_cache.py` | 10 | build/load/fingerprint/persistence |
| `test_deepseek_conversation.py` | 10 | 消息管理、save/load、脱敏、TTL |
| `test_deepseek_usage.py` | 6 | record/summary/truncate/usage extraction |
| `test_bugfix_agent_deepseek_runtime.py` | 12 | runtime 迁移、schema 校验、blocked 模块、错误处理 |

### 5.2 现有测试影响

`tests/test_bug_auto_fix.py` 因缺少 `fastapi` 包无法导入（`ModuleNotFoundError`）。此为预存在的外部依赖问题，非本次变更引入。该测试引用的 `BugFixAgent` 的 `execute_fix()`、`_is_blocked_module()`、`_parse_json_response()` 等方法的测试等价逻辑已由 `tests/test_bugfix_agent_deepseek_runtime.py` 覆盖。

### 5.3 静态检查

```bash
ruff check src/llm/ src/product_app/bug_fix_agent.py tests/test_*deepseek* tests/test_bugfix_*
```
结果：**All checks passed**

```bash
py_compile src/llm/*.py src/product_app/bug_fix_agent.py
```
结果：**no errors**

### 5.4 Git diff 检查

```bash
git diff --check
```
结果：**no whitespace errors**

---

## 6. 架构 Review 门禁确认

| 门禁条件 | 状态 | 说明 |
|---|---|---|
| BugFixAgent 不再 direct import/use OpenAI client | ✅ 通过 | 改为使用 `self.runtime.chat_json()` |
| `model_router.py` 不再是唯一 LLM 抽象 | ✅ 通过 | runtime 已接管实际调用，model_router 委托给 runtime |
| `rg "chat.completions.create" src` 仅限 deepseek_runtime.py | ✅ 通过 | 仅 deepseek_runtime.py:205,241 有实际调用 |
| 所有 JSON 输出经过 schema 校验 | ✅ 通过 | BugFixAnalysis/BugFixProposal Pydantic 校验 |
| 所有 tool calls 只读且有测试 | ✅ 通过 | ToolRegistry 只读约束 + test_deepseek_tools.py |
| 缺 key/timeout/empty 不会卡死 workflow | ✅ 通过 | 返回 DeepSeekResult(status=unavailable/timeout/invalid_response) |
| 无真实自动交易能力被启用 | ✅ 通过 | 未改动 risk_engine/execution_engine/backtest_engine |

---

## 7. 安全与合规确认

- ✅ **默认不启用真实自动下单**：未修改交易相关配置
- ✅ **Risk Agent 一票否决未被绕过**：未触碰 risk_engine
- ✅ **LLM 不得直接决定买卖**：所有输出经过 schema 校验才被使用
- ✅ **所有密钥来自环境变量**：无硬编码 key
- ✅ **Tool calls 默认只读**：ToolRegistry 构造函数强制 read_only
- ✅ **受限模块阻断**：BugFixAgent._is_blocked_module() 行为不变
- ✅ **原始 reasoning_content 不写入用户可见文档**：仅记录是否启用、model、request_id

---

## 8. 剩余风险

1. **fastapi 包缺失**：`tests/test_bug_auto_fix.py` 因缺少 fastapi 跳过，不影响 runtime 本身的测试覆盖。
2. **无真实 DeepSeek API 集成测试**：所有测试使用 mock/fake，不依赖真实 API key。真实集成需在 acceptance 阶段补充 smoke 测试。
3. **BugFixWorkflow 未迁移**：`bug_fix_workflow.py` 仍使用 `BugFixAgent` 的 `analyze()`/`propose_fix()` 方法，但这些方法内部已迁移至 runtime，因此 workflow 层不受影响。
4. **信号解释 Agent 未接入**：F-009（Agent 复用约束）为 SHOULD 级别，信号解释 Agent 接入需在后续迭代完成。

---

## 9. 是否影响真实交易能力

**否**。本次变更只涉及：
- LLM 调用框架（`src/llm/`）
- BugFixAgent（`src/product_app/bug_fix_agent.py`）
- 配置文档（`.env.example`）

未触碰 `execution_engine`、`risk_engine`、`backtest_engine`、`data_gateway`、`strategy_engine` 等交易相关模块。

---

## 10. 交付结论

开发完成，65 项自动化测试全部通过，ruff 和 py_compile 静态检查通过。可以交给 **Test Engineer Agent** 进行验证。
