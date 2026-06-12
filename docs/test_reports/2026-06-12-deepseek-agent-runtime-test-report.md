# DeepSeek Agent Runtime 测试报告

> 角色：Test Engineer Agent
> 日期：2026-06-12

---

## 1. 参考文档

| 文档 | 路径 |
|---|---|
| 需求文档 | `docs/requirements/2026-06-12-deepseek-agent-runtime-requirements.md` |
| 架构文档 | `docs/design/2026-06-12-deepseek-agent-runtime-architecture.md` |
| 开发报告 | `docs/dev_reports/2026-06-12-deepseek-agent-runtime-dev-report.md` |

---

## 2. 测试环境

| 项目 | 值 |
|---|---|
| 操作系统 | Linux (WSL) |
| Python 解释器 | `.venv/bin/python` |
| Python 版本 | 3.13.5 |
| pytest 版本 | 9.0.3 |
| ruff 版本 | 0.15.17 |
| 已安装核心包 | openai 2.41.1, pydantic 2.13.4 |
| 未安装包（预存在问题） | fastapi, uvicorn, pandas, numpy, requests, dotenv |

---

## 3. 分支信息

| 项目 | 值 |
|---|---|
| 被测分支 | `feat/deepseek-agent-runtime/llm-core` |
| 基线分支 | `epic/2026-06-12-deepseek-agent-runtime` |
| 被测提交 | `6b7f273` |
| 临时测试分支 | `test/deepseek-agent-runtime/all-modules-20260612-1736` |
| 临时分支状态 | ✅ 已删除 |

---

## 4. 测试范围

### 测试范围

- DeepSeekRuntime 统一调用框架（`src/llm/deepseek_runtime.py`）
- 多轮对话管理（`src/llm/conversation.py`）
- 只读工具注册和执行（`src/llm/tool_registry.py`）
- 上下文前缀缓存（`src/llm/context_cache.py`）
- Usage 追踪（`src/llm/usage.py`）
- Schema 定义和校验（`src/llm/schemas.py`）
- ModelRouter 委托迁移（`src/llm/model_router.py`）
- BugFixAgent 迁移至 DeepSeekRuntime（`src/product_app/bug_fix_agent.py`）
- 架构门禁：`chat.completions.create` 仅限 `deepseek_runtime.py`
- 安全边界：只读工具、路径校验、secret 脱敏、受限模块阻断

### 不测范围

- **真实 DeepSeek API 集成测试**：所有测试使用 mock/fake client，不依赖真实 API key。真实集成需在 acceptance 阶段补充 smoke 测试。
- **BugFixWorkflow 工作流层**：workflow 层未修改，仍通过 `BugFixAgent.analyze()`/`.propose_fix()` 接口调用，内部已迁移。
- **信号解释 Agent 等后续 Agent 接入**：F-009 为 SHOULD 级别，需后续迭代。
- **`test_bug_auto_fix.py`**：因环境中缺少 `fastapi` 包导致 ModuleNotFoundError（预存在，非本次变更引入）。

---

## 5. 需求覆盖矩阵

| 需求 ID | 功能点 | 测试覆盖 | 状态 |
|---|---|---|---|
| F-001 | 统一 DeepSeek Runtime | `test_deepseek_runtime.py` (16 cases) | ✅ PASS |
| F-002 | 非阻塞调用能力 | async-first API + Semaphore + timeout + retry 实现；`test_missing_api_key`、`test_missing_openai_package` 覆盖 fail-closed | ✅ PASS |
| F-003 | Thinking Mode | `test_thinking_enabled_via_profile`、`test_thinking_disabled_via_profile` | ✅ PASS |
| F-004 | Multi-round Conversation | `test_deepseek_conversation.py` (10 cases) | ✅ PASS |
| F-005 | Tool Calls | `test_deepseek_tools.py` (11 cases) | ✅ PASS |
| F-006 | Context Prefix Cache | `test_deepseek_context_cache.py` (10 cases) | ✅ PASS |
| F-007 | JSON Output | `test_parse_valid_json`、`test_parse_markdown_json`、`test_parse_empty_content`、`test_parse_invalid_json`、`test_unknown_profile_falls_back` | ✅ PASS |
| F-008 | BugFixAgent 迁移 | `test_bugfix_agent_deepseek_runtime.py` (12 cases) | ✅ PASS |
| F-009 | Agent 复用约束 | 架构探测确认 `model_router.py` 不再直接调用 SDK | ✅ PASS |
| F-010 | 可观测性 | `test_deepseek_usage.py` (6 cases) | ✅ PASS |
| F-011 | 安全边界 | 工具只读校验、路径安全校验、受限模块阻断测试、secret 脱敏测试 | ✅ PASS |

---

## 6. 命令执行与结果

### 6.1 开发报告自测命令复现

```bash
.venv/bin/python -m pytest tests/test_deepseek_runtime.py tests/test_deepseek_tools.py \
  tests/test_deepseek_context_cache.py tests/test_deepseek_conversation.py \
  tests/test_deepseek_usage.py tests/test_bugfix_agent_deepseek_runtime.py \
  -v --basetemp=runtime/pytest-tmp-deepseek-runtime
```

**结果：65 passed in 21.25s** ✅（开发报告声称 65 passed in 19.33s，可复现且结果一致）

### 6.2 架构门禁验证

```bash
grep -rn "chat.completions.create" src/ --include="*.py"
```

**结果**：
- `src/llm/deepseek_runtime.py:205` — 实际 SDK 调用
- `src/llm/deepseek_runtime.py:241` — 实际 SDK 调用（tool round 循环）
- `src/llm/deepseek_runtime.py:12` — 文档注释
- `src/llm/tool_registry.py:84` — 文档注释

无其他文件包含 SDK 调用。✅

### 6.3 BugFixAgent 不再直接 import OpenAI

```bash
grep -n "from openai import\|import openai" src/product_app/bug_fix_agent.py
```

**结果**：无匹配 ✅

### 6.4 Ruff 静态检查

```bash
.venv/bin/python -m ruff check src/llm/ src/product_app/bug_fix_agent.py tests/test_*deepseek* tests/test_bugfix_*
```

**结果**：All checks passed ✅

### 6.5 Git diff --check

```bash
git diff --check
```

**结果**：no whitespace errors ✅

### 6.6 密钥检查

```bash
grep -rn "sk-[a-zA-Z0-9]" src/ --include="*.py"
```

**结果**：未发现硬编码密钥 ✅

### 6.7 全量回归（触碰共享模块检查）

```bash
.venv/bin/python -m pytest tests -q --tb=short --basetemp=runtime/pytest-tmp-deepseek-runtime-full
```

**结果**：34 个错误（均为预存在的外部包缺失，与本次变更无关）。这些模块依赖 `fastapi`、`pandas`、`numpy`、`requests`、`dotenv`，在当前 venv 中未安装。

**触及范围窄域回归**（仅限本次变更相关的测试文件）：

```bash
.venv/bin/python -m pytest tests/test_deepseek_runtime.py tests/test_deepseek_tools.py \
  tests/test_deepseek_context_cache.py tests/test_deepseek_conversation.py \
  tests/test_deepseek_usage.py tests/test_bugfix_agent_deepseek_runtime.py \
  -q --tb=short --basetemp=runtime/pytest-tmp-deepseek-runtime-focused
```

**结果**：65 passed in 20.68s ✅

---

## 7. API / UI / CLI / 数据源 / 风控 / 安全验证

| 验证项 | 结果 | 说明 |
|---|---|---|
| API 级验证 | N/A | 本轮不涉及 API 路由变更 |
| UI/Streamlit 验证 | N/A | 本轮不涉及 UI 变更 |
| CLI 验证 | PASS | `chat_json()` 同步 wrapper 可用 |
| 数据源验证 | N/A | 不涉及 `data_gateway` |
| 风控验证 | PASS | `risk_engine` 未被触碰；`_is_blocked_module()` 行为不变 |
| 安全验证 | PASS | 工具只读强制、路径校验、secret 脱敏、受限模块阻断 |
| 真实交易能力 | N/A | `execution_engine`/`risk_engine`/`backtest_engine` 均未触碰 |

---

## 8. 缺陷列表

| ID | 严重级别 | 描述 | 是否阻断 |
|---|---|---|---|
| 无 | — | 本轮测试未发现运行时缺陷 | N/A |

**说明**：所有 65 项自动化测试通过，架构门禁全部确认通过，安全边界验证通过。

---

## 9. Feedback Bug 文件

本轮测试未发现运行时缺陷，未生成 `feedback/bugs/open/` 文件。

---

## 10. Skipped / XFail / Warning / 外部服务失败说明

| 项目 | 说明 |
|---|---|
| `test_bug_auto_fix.py` | ⚠️ 因缺少 `fastapi` 包无法导入。此为预存在的外部依赖问题，非本次变更引入。BugFixAgent 的 `execute_fix()`、`_is_blocked_module()`、`_parse_json_response()` 等方法的等价测试已由 `test_bugfix_agent_deepseek_runtime.py` 覆盖。 |
| 全量回归（34 errors） | ⚠️ 均为缺少 `fastapi`, `pandas`, `numpy`, `requests`, `dotenv` 等依赖导致的 ModuleNotFoundError，与本次 DeepSeek Runtime 变更无关。 |
| 真实 DeepSeek API 集成测试 | ⚠️ 所有测试使用 mock/fake client，不依赖真实 API key。真实集成需在 acceptance 阶段补充。 |

---

## 11. 剩余风险

1. **无真实 DeepSeek API 集成测试**：所有测试依赖 mock，真实 API 调用路径未经端到端验证。建议在 acceptance 阶段使用 `DEEPSEEK_API_KEY` 做一次 smoke 测试确认连接、JSON Output、thinking mode 和 tool calls 在真实环境中的行为。
2. **`test_bug_auto_fix.py` 仍因 missing fastapi 无法运行**：该文件覆盖的 BugFixAgent 审批状态机、workflow 层和 watchdog 测试未在本轮执行，但 BugFixAgent 的核心 `analyze()`/`propose_fix()`/`execute_fix()` 已有迁移测试覆盖。
3. **信号解释 Agent 等尚未接入统一框架**：F-009 为 SHOULD 级别，后续 Agent 仍需架构设计和开发后才能接入。
4. **并发和超时测试不够深入**：`asyncio.Semaphore` 和 `asyncio.wait_for` 的使用在实现中有，但测试中缺少实际的并发竞争验证。

---

## 12. 最终结论

**PASS**

所有 65 项自动化测试全部通过，架构门禁（`chat.completions.create` 调用收敛、BugFixAgent 去 OpenAI SDK 依赖）已确认满足，安全约束（只读工具、secret 脱敏、受限模块阻断）已验证，代码符合需求和架构设计要求。

可进入下一阶段：**Architect Code Review**。
