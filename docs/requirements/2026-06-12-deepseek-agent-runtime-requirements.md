# DeepSeek Agent Runtime Upgrade Requirements

> 角色：Product Manager Agent  
> 日期：2026-06-12  
> 状态：READY_FOR_ARCHITECTURE  
> 适用管线：`docs/process/AGENT_DEVELOPMENT_PIPELINE.md`  
> 官方参考：
> - https://api-docs.deepseek.com/zh-cn/guides/thinking_mode
> - https://api-docs.deepseek.com/zh-cn/guides/multi_round_chat
> - https://api-docs.deepseek.com/zh-cn/guides/tool_calls
> - https://api-docs.deepseek.com/zh-cn/guides/kv_cache
> - https://api-docs.deepseek.com/zh-cn/guides/json_mode

---

## 1. 背景

当前项目已经引入 DeepSeek 作为 BugFixAgent、因子挖掘、研究推荐和信号解释的 LLM 能力来源，但接入方式仍偏原始：

1. `src/product_app/bug_fix_agent.py` 直接调用 OpenAI-compatible SDK，调用路径同步阻塞，缺少统一超时、并发、取消和运行状态管理。
2. `src/llm/model_router.py` 只提供简单 `chat_json()`，缺少统一 conversation、tool calls、thinking、JSON Output、usage 和 cache 观测。
3. 各 Agent 后续若直接接入 DeepSeek，容易重复封装、重复处理 JSON、重复处理 key 缺失和错误恢复。
4. BugFixAgent 需要更强的多轮分析能力：先读 Bug、再按需调用只读工具收集上下文、再输出结构化分析和修复提案。
5. DeepSeek 官方文档已经提供 Thinking Mode、Multi-round Chat、Tool Calls、Context Caching 和 JSON Output 能力，项目应形成统一运行框架，供所有 Agent 复用。

本轮目标不是扩大自动交易能力，而是把 Agent 的 LLM 调用层工程化、可观测、可测试，并保持交易安全边界。

---

## 2. 产品目标

让项目内所有 DeepSeek-backed Agent 通过统一框架调用模型：

- BugFixAgent 不再直接裸调 DeepSeek API。
- 所有 Agent 使用统一配置、统一 JSON schema、统一工具注册、统一上下文缓存策略、统一错误模型。
- 复杂任务支持 thinking mode 和多轮对话。
- Agent 可通过受控 tool calls 读取项目上下文和反馈 Bug 信息，但不得直接写文件、下单、修改风控或绕过审批。
- JSON 输出必须由框架层强制解析、校验和降级处理。
- DeepSeek 服务端硬盘缓存能力通过稳定 prompt prefix 和 usage 观测被充分利用。

---

## 3. 非目标

1. 不启用真实自动交易。
2. 不允许 LLM 直接决定买卖、下单、修改订单、绕过 Risk Agent。
3. 不让 tool calls 暴露任意 shell、任意文件写入、Git 写操作或网络访问。
4. 不把 DeepSeek 原始 `reasoning_content` 直接展示给普通用户或写入公开报告。
5. 不要求本轮完成所有 Agent 的业务质量优化；本轮重点是统一运行框架和 BugFixAgent 迁移。
6. 不在代码中硬编码任何 API key。

---

## 4. 官方能力约束摘要

### 4.1 Thinking Mode

DeepSeek Thinking Mode 可通过 OpenAI-compatible 参数启用或关闭，并可配置 `reasoning_effort`。官方示例显示 `thinking` 需要通过 `extra_body` 传入。响应 message 可能包含 `reasoning_content`。

项目要求：

- 框架层支持 `thinking.enabled` 和 `reasoning_effort`。
- 默认只对复杂 Agent 任务启用 thinking，例如 BugFix 分析、架构审查辅助、复杂因子假设生成。
- 默认不持久化原始 `reasoning_content`；仅记录是否启用、token usage、模型和请求 ID。
- 若多轮任务需要延续模型思考状态，可在内部 conversation 中携带 `reasoning_content`，但不得出现在用户可见 UI、Bug 报告和普通日志中。

### 4.2 Multi-round Chat

DeepSeek 官方多轮对话要求调用方维护 `messages`，将 assistant response 追加回 conversation。Thinking 和 tool calls 场景下，assistant message 还可能包含 `reasoning_content` 和 `tool_calls`。

项目要求：

- 框架层提供 `AgentConversation`，负责追加 user、assistant、tool 消息。
- conversation 可保存到 `runtime/llm_conversations/`，默认 TTL 7 天。
- conversation 文件不得包含 API key、broker key、用户密钥或未脱敏 traceback secret。

### 4.3 Tool Calls

DeepSeek Tool Calls 允许模型请求外部工具。官方文档包含普通工具调用和 thinking mode 下的工具调用示例，并提到 strict schema 支持范围有限。

项目要求：

- 框架层提供 `ToolRegistry`。
- 默认只允许只读工具。
- Tool schema 必须使用显式 JSON schema，且避免 DeepSeek strict mode 不支持的复杂约束。
- 工具执行结果必须进入 conversation，但要限制长度、脱敏、记录来源。
- 任何写文件、执行命令、Git 操作、真实交易相关工具默认禁止注册。

### 4.4 Context Caching / KV Cache

DeepSeek 官方说明上下文硬盘缓存默认开启，命中依赖稳定的完整前缀，usage 中会返回 `prompt_cache_hit_tokens` 和 `prompt_cache_miss_tokens`。

项目要求：

- 本项目不假装本地控制 DeepSeek 服务端 KV Cache。
- 本项目实现本地 `ContextPrefixCache`，把稳定 system prompt、项目不变量、Agent 规则、schema 说明组合为稳定 prefix，以提高服务端 cache 命中概率。
- 每次调用记录 DeepSeek usage 中的 cache hit/miss token 字段；若 SDK 未返回，则记录为 `unknown`。
- 本地缓存只保存 prompt prefix 和指纹，不保存 API key，不保存完整敏感 Bug traceback。

### 4.5 JSON Output

DeepSeek JSON Output 要求设置 `response_format={"type":"json_object"}`，prompt 中必须包含 `json` 字样和目标 JSON 格式示例，并合理设置 `max_tokens`，官方也提示可能出现空 content。

项目要求：

- 框架层提供 `chat_json()` / `chat_json_async()`，必须设置 `response_format`。
- 所有 JSON 输出都必须通过 Pydantic 或等价 schema 校验。
- 空 content、非法 JSON、schema 校验失败必须返回结构化错误，不得静默 fallback 为成功。
- BugFixAgent 的 analysis/proposal 必须使用 JSON Output，不再依赖“提示词要求只返回 JSON”。

---

## 5. 功能点列表

| ID | 功能点 | 预期功能 | 达标准则 | 优先级 |
|---|---|---|---|---|
| F-001 | 统一 DeepSeek Runtime | 新建统一 runtime，封装配置、请求、响应、错误、usage | 所有新 Agent 不直接调用 OpenAI SDK；BugFixAgent 迁移完成 | MUST |
| F-002 | 非阻塞调用能力 | 提供 async API、超时、重试、取消、并发限制；同步调用只作为兼容 wrapper | 单测覆盖 timeout、retry、cancel、missing key | MUST |
| F-003 | Thinking Mode | 支持 `extra_body.thinking`、`reasoning_effort`，可按任务启停 | 请求体测试能看到 thinking 参数；默认不泄露 `reasoning_content` | MUST |
| F-004 | Multi-round Conversation | 支持多轮 messages、assistant/tool 消息追加、conversation 存储和 TTL | 单测验证多轮上下文追加和脱敏持久化 | MUST |
| F-005 | Tool Calls | 支持只读工具注册、工具 schema、工具执行循环、最大轮数 | BugFixAgent 可用工具读取相关文件/报告；禁止写工具 | MUST |
| F-006 | Context Prefix Cache | 本地稳定 prefix 缓存，提高 DeepSeek 服务端 KV cache 命中概率 | 缓存文件含 fingerprint、prefix version、created_at；usage 记录 hit/miss | SHOULD |
| F-007 | JSON Output | 支持 `response_format={"type":"json_object"}` 和 schema 校验 | 非法 JSON、空 content、schema mismatch 均返回结构化错误 | MUST |
| F-008 | BugFixAgent 迁移 | BugFixAgent 使用统一 runtime 完成 analyze/propose_fix | 现有 BugFix 测试通过；新增多轮工具调用测试通过 | MUST |
| F-009 | Agent 复用约束 | 因子、推荐、信号解释等 Agent 通过统一 runtime | 代码搜索无新增裸 `chat.completions.create` | SHOULD |
| F-010 | 可观测性 | 记录模型、provider、latency、tokens、cache hit/miss、tool calls 数量 | `/product/llm/status` 或日志可见非敏感状态 | SHOULD |
| F-011 | 安全边界 | 工具调用、JSON 输出、BugFix 提案不得绕过交易系统不变量 | 单测覆盖交易/风控路径工具禁止 | MUST |

---

## 6. 用户故事

### 6.1 Owner

作为 Owner，我希望 BugFixAgent 和未来所有 Agent 都复用同一套 DeepSeek 调用框架，避免每个 Agent 自己处理 API、JSON、工具和错误。

验收：

- 新框架有明确模块和测试。
- BugFixAgent 已迁移。
- 后续 Agent 接入只需要声明 prompt、schema、tools 和 task profile。

### 6.2 Developer Agent

作为开发工程师 Agent，我希望有标准接口：

```python
result = await runtime.chat_json_async(request)
```

并拿到结构化结果，而不是手工解析模型字符串。

验收：

- 缺 key、缺 SDK、超时、非法 JSON 都返回统一错误。
- 不需要在业务 Agent 中写 DeepSeek SDK 调用细节。

### 6.3 Test Engineer Agent

作为测试工程师 Agent，我希望能用 fake DeepSeek client 验证所有分支，不依赖真实 API key。

验收：

- 单测不访问真实 DeepSeek。
- 可用 fixture 构造 thinking/tool/json/timeout/error 响应。

---

## 7. 配置要求

`.env.example` 必须包含或保持以下配置：

```text
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-v4-flash
LLM_API_BASE=https://api.deepseek.com
LLM_API_KEY_ENV=DEEPSEEK_API_KEY
DEEPSEEK_API_KEY=
LLM_TIMEOUT_SECONDS=45
LLM_MAX_RETRIES=3
LLM_MAX_CONCURRENCY=2
LLM_THINKING_DEFAULT=disabled
LLM_THINKING_EFFORT=high
LLM_CONTEXT_CACHE_DIR=runtime/llm_context_cache
LLM_CONVERSATION_DIR=runtime/llm_conversations
LLM_TOOL_MAX_ROUNDS=4
```

复杂任务可在代码中通过 task profile 覆盖 thinking：

```text
bugfix_analysis: thinking enabled, effort high
bugfix_proposal: thinking enabled, effort high
factor_hypothesis: thinking enabled, effort high
signal_explanation: thinking disabled by default
```

---

## 8. 安全与合规要求

1. 所有密钥只能来自环境变量。
2. 默认不能真实自动下单。
3. LLM 不得直接决定买卖。
4. Risk Agent 一票否决不可被 Agent 工具绕过。
5. Tool calls 默认只读。
6. BugFixAgent 自动修复仍需审批和测试门禁。
7. 核心交易逻辑、风控、执行、订单相关模块不得由 BugFixAgent 自动修改。
8. 原始 `reasoning_content` 默认不写入用户可见文档。
9. LLM 输出必须经过 schema 校验和安全校验。

---

## 9. 验收标准

本轮可进入架构 Review 的最低标准：

- `src/llm/` 下存在统一 DeepSeek runtime。
- BugFixAgent 已迁移到 runtime。
- 无新增裸 DeepSeek/OpenAI SDK 调用。
- JSON Output 强制启用并有 schema 校验。
- Thinking、多轮、tool calls、context prefix cache、usage 记录均有单测。
- 缺 key、缺 SDK、API timeout、空 content、非法 JSON 均 fail closed。
- 所有测试不依赖真实 DeepSeek API。
- 文档和报告全部使用 `/` 路径风格。
