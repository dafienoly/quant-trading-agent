# DeepSeek Agent Runtime Development and Test Guide

> 日期：2026-06-12  
> 适用任务：DeepSeek Agent Runtime Upgrade  
> 需求文档：`docs/requirements/2026-06-12-deepseek-agent-runtime-requirements.md`  
> 架构文档：`docs/design/2026-06-12-deepseek-agent-runtime-architecture.md`  
> 管线约束：`docs/process/AGENT_DEVELOPMENT_PIPELINE.md`

---

## 1. 通用执行规则

所有 Agent 必须先读取：

1. `AGENTS.md`
2. `SYSTEM_INVARIANTS.md`
3. `docs/process/AGENT_DEVELOPMENT_PIPELINE.md`
4. `docs/policy/SELF_TEST_CHECKLIST.md`
5. `docs/requirements/2026-06-12-deepseek-agent-runtime-requirements.md`
6. `docs/design/2026-06-12-deepseek-agent-runtime-architecture.md`

环境默认是 WSL/Linux，必须优先使用：

```bash
./.venv/bin/python
```

如果不存在，记录实际解释器：

```bash
which python
python -V
ls .venv/bin/python
```

禁止事项：

- 不得使用真实 DeepSeek API 做单元测试。
- 不得提交 API key。
- 不得新增任意 shell tool、写文件 tool、Git tool、交易 tool。
- 不得让 LLM 直接决定买卖或修改风控。
- 不得删除失败测试来制造通过。
- 不得把 `reasoning_content` 写入用户可见报告。

---

## 2. Developer Agent 指导

### 2.1 开发目标

实现统一 DeepSeek Agent Runtime，并迁移 BugFixAgent：

- `src/llm/deepseek_runtime.py`
- `src/llm/conversation.py`
- `src/llm/context_cache.py`
- `src/llm/tool_registry.py`
- `src/llm/schemas.py`
- `src/llm/usage.py`
- 修改 `src/llm/model_router.py`
- 修改 `src/product_app/bug_fix_agent.py`
- 补充或修改相关测试

### 2.2 推荐任务拆分

#### Task 1: Runtime Schema and Config

先写测试：

```bash
./.venv/bin/python -m pytest tests/test_deepseek_runtime.py::test_runtime_config_defaults_to_deepseek_v4_flash -q
```

期望先失败。

实现：

- `LLMTaskProfile`
- `DeepSeekRequest`
- `DeepSeekResult`
- `LLMUsage`
- 从环境变量读取 timeout、retry、concurrency、thinking 默认值。

验收：

- 缺 key 返回 `status="unavailable"`。
- 默认模型为 `deepseek-v4-flash`。

#### Task 2: JSON Output Runtime

先写测试覆盖：

- `response_format={"type":"json_object"}` 被传入 SDK。
- prompt 中包含 `json` 和 schema 示例。
- 空 content 返回 `invalid_response`。
- 非法 JSON 返回 `invalid_response`。
- schema mismatch 返回 `invalid_response`。

实现：

- fake OpenAI-compatible client。
- `DeepSeekRuntime.chat_json_async()`。
- 同步 wrapper `chat_json()`。

#### Task 3: Thinking Mode

先写测试覆盖：

- profile 开启 thinking 时，请求包含 `extra_body={"thinking":{"type":"enabled"}}`。
- `reasoning_effort` 被设置为 `high` 或 `max`。
- 原始 `reasoning_content` 不出现在返回给业务层的 `data`。

实现：

- thinking 参数构造。
- assistant message 内部保留策略。
- 默认日志脱敏。

#### Task 4: Conversation Store

先写测试覆盖：

- user turn append。
- assistant turn append。
- tool result append。
- conversation 持久化到 `runtime/llm_conversations/`。
- `.env`、API key、broker key 字样被拒绝或脱敏。

实现：

- `AgentConversation`
- `ConversationStore`
- TTL 清理函数。

#### Task 5: Context Prefix Cache

先写测试覆盖：

- 相同 profile 和 source files 生成稳定 fingerprint。
- source file 变化后 fingerprint 变化。
- 缓存文件不包含密钥。
- usage 中提取 `prompt_cache_hit_tokens` 和 `prompt_cache_miss_tokens`。

实现：

- `ContextPrefixCache`
- prefix version。
- cache usage extraction。

#### Task 6: Tool Registry

先写测试覆盖：

- 注册只读工具成功。
- 注册写工具被拒绝。
- `read_project_file` 不能读 `.env`。
- `read_project_file` 不能路径穿越。
- tool result 被截断。
- max tool rounds 生效。

实现工具：

- `read_project_file`
- `search_project_text`
- `list_feedback_bugs`
- `read_feedback_bug`
- `read_test_report`
- `read_dev_report`

所有工具必须只读。

#### Task 7: BugFixAgent Migration

先写测试覆盖：

- `BugFixAgent.analyze()` 使用 runtime。
- `BugFixAgent.propose_fix()` 使用 runtime。
- analysis/proposal schema 校验失败不会进入可审批状态。
- DeepSeek unavailable 时 Bug 回退 open，不会卡在 analyzing。
- 受限模块仍被阻断。

实现：

- 保持 `BugFixAgent` public API 不变。
- 删除直接 OpenAI client 调用。
- 保留 execute_fix 的审批和安全边界。

#### Task 8: Integration and Docs

补充：

- `/product/llm/status` 可显示 runtime capability。
- `.env.example` 更新新增配置。
- 开发报告。

### 2.3 必跑命令

开发完成后至少运行：

```bash
git status --short --branch
git diff --stat

./.venv/bin/python -m ruff check src/llm src/product_app/bug_fix_agent.py tests/test_deepseek_runtime.py tests/test_deepseek_tools.py tests/test_deepseek_context_cache.py tests/test_bugfix_agent_deepseek_runtime.py

./.venv/bin/python -m pytest tests/test_deepseek_runtime.py tests/test_deepseek_tools.py tests/test_deepseek_context_cache.py tests/test_bugfix_agent_deepseek_runtime.py -q --basetemp=runtime/pytest-tmp-deepseek-runtime

./.venv/bin/python -m pytest tests/test_bug_auto_fix.py tests/test_ai_research_agents.py -q --basetemp=runtime/pytest-tmp-deepseek-regression

rg "chat.completions.create" src
rg "OpenAI" src
git diff --check
```

`rg "chat.completions.create" src` 期望只剩：

```text
src/llm/deepseek_runtime.py
```

如果有历史兼容注释，必须在开发报告中解释。

### 2.4 开发报告路径

```text
docs/dev_reports/2026-06-12-deepseek-agent-runtime-dev-report.md
```

报告必须包含：

- 功能点完成矩阵。
- 修改文件列表。
- DeepSeek 官方能力映射。
- 安全边界说明。
- 所有命令和结果。
- 未覆盖风险。

---

## 3. Test Engineer Agent 指导

### 3.1 分支规则

测试必须从当前开发分支新拉本地测试分支：

```bash
git status --short --branch
git switch -c test/deepseek-agent-runtime-$(date +%Y%m%d-%H%M)
```

测试分支只允许临时新增测试或验证脚本。测试完成后：

1. 记录测试分支 commit 或工作区状态。
2. 切回原开发分支。
3. 删除本地测试分支。
4. 在原开发分支提交测试报告。

测试工程师不允许在原开发分支修改业务代码。

### 3.2 测试重点

测试不是证明开发通过，而是判断本轮能否交付：

- DeepSeek API 不可用时是否 fail closed。
- 缺 key 是否不崩溃。
- JSON Output 是否真正设置 `response_format`。
- thinking 参数是否按 profile 启用。
- `reasoning_content` 是否不泄露。
- tool calls 是否只读。
- tool calls 是否不能读 `.env`、不能路径穿越。
- max tool rounds 是否防止无限循环。
- BugFixAgent 是否不再裸调 DeepSeek。
- Agent 是否仍不能触碰真实交易。

### 3.3 必跑命令

```bash
git status --short --branch
git diff --stat

./.venv/bin/python -m pytest tests/test_deepseek_runtime.py tests/test_deepseek_tools.py tests/test_deepseek_context_cache.py tests/test_bugfix_agent_deepseek_runtime.py -q --basetemp=runtime/pytest-tmp-test-deepseek-runtime

./.venv/bin/python -m pytest tests/test_bug_auto_fix.py tests/test_ai_research_agents.py tests/test_product_routes.py -q --basetemp=runtime/pytest-tmp-test-deepseek-regression

./.venv/bin/python -m ruff check src/llm src/product_app/bug_fix_agent.py tests/test_deepseek_runtime.py tests/test_deepseek_tools.py tests/test_deepseek_context_cache.py tests/test_bugfix_agent_deepseek_runtime.py

rg "chat.completions.create" src
rg "reasoning_content" docs feedback src tests
git diff --check
```

如果全量测试有历史失败，必须列出：

- 测试名。
- 失败原因。
- 是否与本轮相关。
- 是否阻断。

### 3.4 测试报告路径

```text
docs/test_reports/2026-06-12-deepseek-agent-runtime-test-report.md
```

测试报告必须包含：

- 测试矩阵。
- 命令和输出摘要。
- 缺陷列表。
- 未覆盖风险。
- 最终结论：`PASS`、`PASS_WITH_NOTES` 或 `FAIL`。

---

## 4. 发给 Developer Agent 的提示词

```text
你现在作为本项目 Developer Agent 执行 DeepSeek Agent Runtime Upgrade。

请先读取并严格遵守：
1. AGENTS.md
2. SYSTEM_INVARIANTS.md
3. docs/process/AGENT_DEVELOPMENT_PIPELINE.md
4. docs/policy/SELF_TEST_CHECKLIST.md
5. docs/requirements/2026-06-12-deepseek-agent-runtime-requirements.md
6. docs/design/2026-06-12-deepseek-agent-runtime-architecture.md
7. docs/design/2026-06-12-deepseek-agent-runtime-development-test-guide.md

你在 WSL/Linux 虚拟环境中工作，默认 Python 为 ./.venv/bin/python。不得使用真实 DeepSeek API 进行单元测试，必须使用 fake client 或 monkeypatch。

本轮目标：
- 新建统一 DeepSeek Runtime，支持 thinking mode、多轮对话、tool calls、context prefix cache、JSON Output、usage 记录和结构化错误。
- 迁移 BugFixAgent，使其不再直接调用 OpenAI-compatible SDK。
- 保证后续所有 DeepSeek-backed Agent 复用 src/llm/ 统一框架。
- 保持交易安全边界：LLM 不能直接决定买卖，不能下单，不能绕过 Risk Agent。

请按 TDD 执行：
1. 先写失败测试。
2. 再实现最小代码。
3. 每完成一个小任务运行对应测试。
4. 最后运行指导文档中的全部命令。

开发完成后输出：
docs/dev_reports/2026-06-12-deepseek-agent-runtime-dev-report.md

报告必须包含功能点完成矩阵、修改文件、测试命令和结果、安全边界说明、未覆盖风险。
```

---

## 5. 发给 Test Engineer Agent 的提示词

```text
你现在作为本项目 Test Engineer Agent 验证 DeepSeek Agent Runtime Upgrade。

请先读取并严格遵守：
1. AGENTS.md
2. SYSTEM_INVARIANTS.md
3. docs/process/AGENT_DEVELOPMENT_PIPELINE.md
4. docs/policy/SELF_TEST_CHECKLIST.md
5. docs/requirements/2026-06-12-deepseek-agent-runtime-requirements.md
6. docs/design/2026-06-12-deepseek-agent-runtime-architecture.md
7. docs/design/2026-06-12-deepseek-agent-runtime-development-test-guide.md
8. docs/dev_reports/2026-06-12-deepseek-agent-runtime-dev-report.md

你在 WSL/Linux 虚拟环境中工作，默认 Python 为 ./.venv/bin/python。

测试必须从当前开发分支新拉本地测试分支：
git status --short --branch
git switch -c test/deepseek-agent-runtime-$(date +%Y%m%d-%H%M)

测试分支只用于验证，不允许在原开发分支改业务代码。测试完成后切回原开发分支，删除测试分支，并在原开发分支提交测试报告。

你的任务不是证明开发通过，而是从安全、数据契约、Agent 行为和产品交付角度判断是否可交付。

重点验证：
- 不依赖真实 DeepSeek API。
- 缺 key、缺 SDK、timeout、空 content、非法 JSON 全部 fail closed。
- JSON Output 确实设置 response_format。
- thinking 参数按 profile 启用。
- reasoning_content 不进入用户可见报告。
- tool calls 只读，不能读 .env，不能路径穿越。
- BugFixAgent 不再裸调 DeepSeek。
- 无任何真实自动交易能力被启用。

完成后输出：
docs/test_reports/2026-06-12-deepseek-agent-runtime-test-report.md

报告必须包含测试矩阵、命令结果、缺陷列表、未覆盖风险和最终结论。
```
