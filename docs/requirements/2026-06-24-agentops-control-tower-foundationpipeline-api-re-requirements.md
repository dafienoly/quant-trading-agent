# agentops-control-tower-foundationpipeline-api-re Requirements

## User Goal

构建 AgentOps Control Tower Foundation 的首个可验收基础层，使项目维护者能够在一个只读控制塔界面中查看 Issue 驱动流水线的关键状态、文档产物、阶段进度与异常提示，并为后续 AgentOps 操作能力打下稳定的数据契约、聚合 API 与 React 状态中心基础。

本阶段目标是“可观测、只读、可追踪”，不是上线自动化控制、交易执行或流水线写操作。

用户成功标准：

- 用户可以通过产品界面快速判断当前 feature / issue 的流水线阶段、各角色状态、必要文档是否齐备、是否存在阻塞或高风险信号。
- 用户可以通过只读 API 获取同一份聚合状态，供 React 页面和后续 AgentOps 页面复用。
- 用户看到的状态必须来自明确的数据契约，不依赖散乱的前端硬编码或不可追踪的临时字段。
- 当数据缺失、异常、过期或不可解析时，系统应明确展示“不完整 / 不可用 / 阻塞”，不得伪装为正常通过。

## Functional Requirements

### 功能范围

1. Pipeline 观测契约
   - 定义 AgentOps Control Tower Foundation 所需的流水线观测数据字段。
   - 覆盖 feature 基础信息、Issue 信息、epic branch、当前阶段、阶段状态、角色分工、必需文档路径、测试 / 评审 / 验收状态、风险提示和阻塞原因。
   - 契约必须支持缺失值、未知状态、外部系统不可用、文档未生成、阶段未开始、阶段失败等状态表达。
   - 契约字段命名应稳定、可版本化，并适合 API 与 React 状态中心共同使用。

2. 只读聚合 API
   - 提供只读 API，用于返回指定 feature / issue 的 AgentOps 流水线聚合状态。
   - API 不得触发任何写操作，不得创建分支、提交、评论、审批、合并、运行 CI、修改任务状态或更新文档。
   - API 应聚合当前可用的本地 pipeline state、必需文档存在性、阶段状态和安全提示。
   - API 应返回结构化错误信息，区分参数错误、feature 不存在、数据源缺失、状态不可解析和内部异常。
   - API 响应不得泄露 secrets、tokens、本地绝对敏感路径、环境变量值或 CI 凭证。

3. React 状态中心
   - 为 AgentOps Control Tower 页面建立统一的前端状态中心，用于加载、缓存、刷新和消费只读聚合 API 数据。
   - 状态中心必须表达 loading、ready、empty、stale、error、blocked 等用户可理解状态。
   - 状态中心应避免各组件重复请求、重复解析和重复维护阶段状态映射。
   - 状态中心应为后续页面扩展保留清晰边界，但本阶段不得加入写操作、审批操作或自动化触发操作。

4. Control Tower Foundation 页面集成
   - 页面应展示 feature 标题、feature_id、issue number / issue URL、epic branch、当前阶段、阶段状态总览、必需文档清单和安全 / 阻塞提示。
   - 页面应突出显示 pending、in_progress、passed、failed、blocked、unknown 等状态。
   - 文档路径展示必须清晰，不得把未生成文档显示为已完成。
   - 当 API 返回错误或数据不完整时，页面应展示可理解的失败状态，而不是空白页或成功状态。

5. 非目标
   - 本阶段不实现流水线控制动作，例如 approve、reject、rerun、merge、create branch、create PR、comment、assign、label、trigger workflow。
   - 本阶段不修改交易策略、风控、执行、行情、回测、股票池或真实交易相关逻辑。
   - 本阶段不改变现有 Agent 角色职责、自动合并政策、CI 策略或 GitHub workflow 行为。
   - 本阶段不引入真实交易能力、模拟交易能力或任何交易下单入口。
   - 本阶段不要求接入完整实时 GitHub API；如后续架构选择接入，必须保持只读和失败可见。

## Non-functional Requirements

1. 可追踪性
   - API 与页面展示的每个关键状态应能追溯到明确来源，例如 pipeline state、文档路径、阶段状态或聚合规则。
   - 不允许用无来源的前端常量伪造通过状态。

2. 稳定性
   - 缺失或异常数据不得导致服务崩溃或页面白屏。
   - 未知状态必须显式表示为 `unknown` 或等价安全状态。

3. 安全性
   - 所有接口必须只读。
   - 不得暴露 secrets、tokens、cookies、broker credentials、`.env` 内容或 CI 凭证。
   - 错误响应应避免输出敏感环境信息和完整内部堆栈。

4. 兼容性
   - 新增契约和 API 应尽量不破坏现有 `/product` 路由、现有 dashboard、现有测试和现有 pipeline 文档规则。
   - React 状态中心应支持后续扩展更多 AgentOps 卡片和阶段详情。

5. 可测试性
   - 必须包含契约解析、API 正常响应、缺失数据、异常数据、只读保证和前端状态转换相关测试。
   - 外部依赖必须 mock，不得在单元测试中依赖真实 GitHub 网络状态。
   - 触及 API 或 UI 入口时，应包含对应 smoke 或组件级验证。

6. 用户体验
   - 页面状态文案应清楚区分未开始、进行中、失败、阻塞、未知和数据不可用。
   - 用户不应需要阅读日志才能理解当前 pipeline 是否可继续推进。
   - 页面不得把 demo、mock 或占位数据表现为真实 pipeline 状态。

## Acceptance Criteria

1. 契约验收
   - 存在明确的 AgentOps pipeline 观测契约，覆盖 feature 信息、issue 信息、branch、阶段状态、角色、必需文档、风险提示和阻塞原因。
   - 契约支持 `unknown`、`pending`、`in_progress`、`passed`、`failed`、`blocked` 或等价状态。
   - 契约测试覆盖正常、缺失字段、未知状态和不可解析输入。

2. API 验收
   - 存在只读聚合 API，可返回指定 feature / issue 的结构化 pipeline 状态。
   - API 对不存在或不可解析的 feature 返回明确错误，不返回伪成功。
   - API 不执行任何写入、审批、触发、合并或状态变更动作。
   - API 测试覆盖成功响应、参数错误、数据缺失、内部异常和敏感信息不泄露。

3. React 状态中心验收
   - 存在统一状态中心消费只读 API，并向页面提供 loading、ready、error、empty、stale / blocked 等状态。
   - 页面组件不重复实现核心 pipeline 状态解析规则。
   - 前端测试或 smoke 证据覆盖正常加载、错误响应和缺失数据展示。

4. 页面验收
   - Control Tower Foundation 页面能展示 feature 基础信息、当前阶段、阶段总览、必需文档清单和安全 / 阻塞提示。
   - 未生成文档、失败阶段、未知风险必须在页面上可见。
   - API 失败时页面不得白屏，不得显示为通过。

5. 文档与报告验收
   - 后续开发阶段必须产出中文 `docs/dev_reports/` 开发报告。
   - 后续验收阶段必须产出中文 `docs/acceptance/` 验收报告。
   - 报告必须包含变更范围、测试命令、测试结果、安全确认和最终结论。

6. 测试命令验收
   - 至少运行与 touched files 相关的 `ruff`、`py_compile`、`pytest` 或前端等效测试命令。
   - 若触及共享 API、product route、UI entrypoint 或数据契约，应运行相应更广范围回归。
   - 若存在未运行测试，必须在报告中说明原因和剩余风险。

## Safety Constraints

1. 本功能必须保持只读，不得引入任何交易、下单、撤单、审批、自动合并或 pipeline 写操作能力。
2. 不得修改或绕过 `Risk Agent` 一票否决、人工确认、stock pool filter、execution policy、risk policy 或 fail-closed 规则。
3. 不得触碰真实交易路径；如实现过程中必须接触 `src/risk_engine/`、`src/execution_engine/`、`src/data_gateway/`、`src/backtest_engine/`、`src/strategy_engine/` 等 restricted modules，必须升级为受限模块变更并要求额外审查和负向测试。
4. 当 pipeline 数据源不可用、状态不可解析或必需文档缺失时，系统必须显示不可用、未知或阻塞状态，不得默认通过。
5. 不得把 mock、demo、fixture 或占位数据伪装为真实 live pipeline 状态。
6. API 和 UI 不得泄露 secrets、tokens、cookies、broker credentials、`.env` 内容、CI 凭证或敏感环境变量。
7. `LEVEL_3_AUTO` 不得作为普通用户可选项暴露。
8. 本阶段不得改变自动合并政策、分支工作流、Agent 角色职责或现有安全门禁。
9. 所有核心行为变更必须有测试证据；不得删除、弱化或跳过失败测试来制造通过。
10. 若发现可能影响真实交易安全、执行策略、风控策略或数据 fail-closed 行为的问题，必须停止本功能推进并回到架构 / 安全审查阶段。