# WSL Product Runtime and AI Agent Requirements

> 角色：Product Manager Agent  
> 日期：2026-06-11  
> 状态：READY_FOR_ARCHITECTURE  
> 输入来源：用户试用反馈、`feedback/bugs/` 现有缺陷、当前 WSL 运行体验  
> 适用管线：`docs/process/AGENT_DEVELOPMENT_PIPELINE.md`

---

## 1. 背景

当前产品已经具备 Dashboard、FastAPI、Live Data、Feedback、BugFix Agent、因子、回测、信号草稿等分散能力，但 WSL 用户试用时仍存在明显交付断点：

1. AkTools 本地服务启动后打开首页 `/` 报错：

```text
TypeError: Jinja2Templates.TemplateResponse() missing 1 required positional argument: 'name'
```

2. 用户需要分别启动 Dashboard、API、BugFix Agent，且 AkTools 又是额外服务，试用流程复杂。
3. 文档和报告示例中仍有 Windows 路径风格，WSL 用户执行不顺。
4. Roadmap 中提到因子挖掘、荐股、买卖信号需要 Agent/AI 参与，但当前产品主链路更像规则和量化服务，并未清晰展示 DeepSeek 模型参与。
5. DeepSeek 默认模型名仍使用旧值 `deepseek-chat`，用户要求更新为 `deepseek-v4-flash`，并预留后续切换其他模型能力。
6. 试用反馈目录已经出现多类 Bug，包括 Dashboard/API timeout、fundamentals provider 缺方法或字段、daily/realtime 数据为空、BugFix Agent 生成无效修复方案。

本需求文档目标是把这轮较大的产品化修复拆成可验收的功能包，交给架构师输出设计，再由开发和测试 Agent 按管线执行。

---

## 2. 目标

### 2.1 产品目标

让 WSL 用户能够通过一组脚本完成产品试用闭环：

```bash
bash scripts/start.sh --with-aktools --with-bugfix --streamlit-port 8771
bash scripts/stop.sh
bash scripts/restart.sh --with-aktools --with-bugfix --streamlit-port 8771
```

启动后用户可以访问：

```text
http://127.0.0.1:8771
http://127.0.0.1:8000/product/health
http://127.0.0.1:8080/version
```

并在产品中明确看到：

- AkTools 是否可用。
- API 是否可用。
- Dashboard 是否可用。
- BugFix Agent 是否运行。
- 当前 AI Provider 和模型。
- AI Agent 参与了哪些环节，哪些环节仍由规则和风控控制。

### 2.2 工程目标

1. 修复 AkTools 首页兼容性，不修改 `.venv` 或第三方包源码。
2. 一键启动、停止、重启管理 AkTools、FastAPI、Streamlit 和 BugFix Agent。
3. 所有新文档、报告和命令示例使用 `/` 路径。
4. DeepSeek 默认模型更新为 `deepseek-v4-flash`。
5. 引入统一 LLM 配置和模型路由，为后续切换模型预留接口。
6. 将 AI Agent 接入因子挖掘、研究推荐、信号解释，但不允许 LLM 直接决定买卖或绕过风控。
7. 加固 BugFix Agent，避免生成不存在路径的修复方案并进入执行阶段。

---

## 3. 非目标

1. 本轮不启用真实自动交易。
2. 本轮不允许 LLM 直接下单、直接决定买入或卖出。
3. 本轮不要求解决所有免费数据源不可用问题，但必须把 provider 缺方法、缺字段和 fail-closed 状态解释清楚。
4. 本轮不要求接入付费行情源。
5. 本轮不重写整个 Dashboard，不做 UI 大改版。
6. 本轮不把 BugFix Agent 变成无需审批的全自动改代码系统。

---

## 4. 用户角色

| 角色 | 诉求 |
|---|---|
| Owner | 一键启动产品，确认当前阶段能否交给其他 Agent 开发和测试 |
| Trader | 盯盘、查看信号解释和风险状态，不被误导为自动交易 |
| Research User | 使用 AI 辅助挖掘因子假设和股票研究线索 |
| Developer Agent | 按架构文档实现，不猜测业务边界 |
| Test Engineer Agent | 在 WSL 环境可重复验证启动、数据、AI、feedback 和安全边界 |

---

## 5. 功能点列表

| ID | 功能点 | 用户故事 | 预期行为 | 验收标准 | 优先级 |
|---|---|---|---|---|---|
| F-001 | AkTools 兼容启动 | 作为用户，我希望 AkTools 本地服务首页和 API 都能打开 | 系统提供兼容 app 或启动方式，不修改第三方包源码 | `curl http://127.0.0.1:8080/`、`/version`、`/api/public/stock_zh_a_spot_em` 不返回 500 | MUST |
| F-002 | WSL 一键启动 | 作为用户，我希望一条命令启动试用所需服务 | `scripts/start.sh` 可启动 AkTools、FastAPI、Dashboard，并按配置启动 BugFix Agent | start 后 8080、8000、8771 可访问，PID 文件记录服务 | MUST |
| F-003 | WSL 一键停止 | 作为用户，我希望一条命令停止所有项目服务 | `scripts/stop.sh` 停止 AkTools、FastAPI、Dashboard，并尽量停止 BugFix Agent job | stop 后端口释放，PID 文件清理 | MUST |
| F-004 | WSL 一键重启 | 作为用户，我希望端口被旧进程占用时可安全重启 | `scripts/restart.sh` 先 stop 后 start，支持 `--force` 清理旧项目进程 | restart 后服务可用，无重复进程 | MUST |
| F-005 | 路径规范 | 作为 WSL 用户，我希望文档命令可以直接复制执行 | 新增文档、报告、命令示例统一使用 `/` | 本轮新增文档中无 Windows 路径分隔符示例 | MUST |
| F-006 | DeepSeek 模型更新 | 作为用户，我希望默认模型是当前可用模型 | 默认模型从 `deepseek-chat` 改为 `deepseek-v4-flash` | `.env.example`、配置服务、UI/API 展示一致 | MUST |
| F-007 | 模型路由 | 作为 Owner，我希望后续可切换其他模型 | 提供统一 LLM 配置和 `ModelRouter`，兼容 DeepSeek/OpenAI-compatible Provider | 单测覆盖默认 DeepSeek、缺 key、模型切换 | SHOULD |
| F-008 | AI 因子挖掘 | 作为研究用户，我希望 AI 帮我提出因子假设 | AI 输出结构化因子假设、证据、来源、置信度，不输出数值因子 | API 返回 `hypothesis/evidence/source/confidence/risk_notes` | SHOULD |
| F-009 | AI 研究推荐 | 作为研究用户，我希望 AI 辅助股票研究排序 | AI 基于已有数据和主题标签输出研究推荐，不输出交易指令 | UI/API 明示“研究推荐，不是买卖建议” | SHOULD |
| F-010 | AI 信号解释 | 作为交易用户，我希望理解信号草稿原因 | 对已有量化信号生成解释和风险提示，不能改变信号结果 | 信号解释中包含 evidence 和 risk，原信号类型由规则/风控生成 | SHOULD |
| F-011 | BugFix 提案校验 | 作为 Owner，我希望自动修复不会胡乱改不存在的文件 | BugFix Agent 在 proposal 阶段校验文件路径和受限模块 | 不存在路径进入 `invalid_proposal` 或 `blocked`，不可 approve 执行 | MUST |
| F-012 | Feedback Bug 分类 | 作为开发负责人，我希望已有 Bug 能被自动归类 | 提供脚本或服务聚合 open Bug，按 data_gateway/dashboard/bugfix/config 分类 | 输出分类报告，保留原始 Bug 文件 | SHOULD |
| F-013 | Dashboard 运行状态可见 | 作为用户，我希望一眼看懂服务状态 | Dashboard 展示 AkTools/API/BugFix/LLM 模型状态 | 页面中可看到服务状态和当前模型 | SHOULD |

---

## 6. 用户流程

### 6.1 首次试用流程

```bash
cp .env.example .env
# 填入 DEEPSEEK_API_KEY
bash scripts/start.sh --with-aktools --with-bugfix --streamlit-port 8771
```

用户打开：

```text
http://127.0.0.1:8771
```

页面应显示：

1. API 正常。
2. AkTools 正常或明确失败原因。
3. BugFix Agent 正常或因缺少 key 明确未启动。
4. 当前 LLM：`deepseek-v4-flash`。
5. 自动交易未启用。

### 6.2 AI 研究流程

1. 用户选择股票池或主题池。
2. 点击“AI 因子挖掘”或调用 API。
3. 系统汇总行情、主题、财务、搜索证据。
4. LLM 输出结构化研究假设。
5. 规则层映射到可回测或待验证标签。
6. 用户可把假设送入回测或信号解释。

### 6.3 信号解释流程

1. 系统先由数据健康、因子、回测、风控生成信号草稿。
2. 若信号被阻断，AI 只能解释阻断原因。
3. 若生成 draft，AI 解释证据链和风险。
4. 人工确认仍是唯一进入订单草稿或确认流程的路径。

---

## 7. 配置需求

`.env.example` 必须包含：

```text
AKTOOLS_BASE_URL=http://127.0.0.1:8080
DEEPSEEK_API_KEY=
DEEPSEEK_API_BASE=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-v4-flash
LLM_API_BASE=https://api.deepseek.com
LLM_API_KEY_ENV=DEEPSEEK_API_KEY
ENABLE_AI_RESEARCH_AGENTS=true
ENABLE_LLM_SIGNAL_EXPLANATION=true
ENABLE_LLM_TRADE_DECISION=false
```

约束：

1. 所有密钥只能来自环境变量。
2. 缺少 key 时 AI 功能应降级为明确错误，不阻断基础 Dashboard。
3. `ENABLE_LLM_TRADE_DECISION` 必须默认 `false`，且当前阶段即使设为 `true` 也不得绕过风控和人工确认。

---

## 8. 数据与安全约束

1. 实盘数据失败时，信号和订单路径必须 fail-closed。
2. LLM 不能编造行情、财务、新闻、政策证据。
3. LLM 输出必须带 `source` 或说明 `source_unavailable`。
4. LLM 不能直接输出数值因子。
5. LLM 不能直接输出 `BUY/SELL` 决策。
6. Risk Agent 保持一票否决。
7. 默认不真实自动下单。
8. 不得买创业板、科创板、ST、退市整理股。
9. 任何策略不得绕过股票池过滤器。

---

## 9. Feedback 现有缺陷纳入范围

本轮必须至少处理或分类以下缺陷类型：

| 类型 | 示例 | 期望处理 |
|---|---|---|
| AkTools 首页崩溃 | `TemplateResponse() missing ... name` | 兼容 app 修复 |
| Dashboard API timeout | `GET /product/live-data/quotes read timeout=8` | 超时提示、服务状态检查、一键启动降低误用 |
| fundamentals 缺方法 | `AkShareProvider object has no attribute get_fundamentals` | provider 能力清单和明确 fallback，不把缺能力当未知错误 |
| daily/realtime empty | `All providers failed ... empty_data` | 保持 fail-closed，输出可理解错误和 Bug 分类 |
| BugFix 无效提案 | `src/dashboard/routes.py` 不存在 | proposal 校验并阻断 |
| DeepSeek key 错误 | `OPENAI_API_KEY` credentials error | 统一 LLM/DeepSeek key 读取，错误信息指向正确 key |
| 测试依赖缺失 | `No module named playwright` | 测试分层或依赖声明，不让无关浏览器测试阻断自动修复 |

---

## 10. 验收标准

### 10.1 MUST 验收

```bash
./.venv/bin/python -m ruff check src scripts tests
./.venv/bin/python -m pytest tests/test_bug_auto_fix.py tests/test_live_signal.py tests/test_live_data_service.py tests/test_product_dashboard_source.py -q --basetemp=runtime/pytest-tmp
bash scripts/start.sh --with-aktools --with-bugfix --streamlit-port 8771
curl http://127.0.0.1:8080/
curl http://127.0.0.1:8080/version
curl http://127.0.0.1:8000/product/health
curl http://127.0.0.1:8000/product/jobs
bash scripts/stop.sh
```

通过条件：

1. `curl http://127.0.0.1:8080/` 不返回 500。
2. start 后 Dashboard/API/AkTools 可访问。
3. stop 后端口释放。
4. 无 DeepSeek key 时 BugFix Agent 不误报 running。
5. 有 DeepSeek key 时 BugFix Agent 可进入 running。
6. 默认模型显示为 `deepseek-v4-flash`。
7. 本轮新增文档使用 `/` 路径。

### 10.2 SHOULD 验收

1. AI 因子挖掘 API 返回结构化假设。
2. AI 研究推荐 API 返回研究列表和风险说明。
3. AI 信号解释 API 能解释已有信号草稿。
4. Dashboard 展示当前 LLM provider/model。
5. Feedback Bug 分类报告可生成。

---

## 11. 测试建议

测试工程师必须覆盖：

1. WSL 一键启动/停止/重启。
2. AkTools 首页、version、public API。
3. 缺少 DeepSeek key 和配置 DeepSeek key 两种路径。
4. BugFix Agent 无效 proposal 阻断。
5. AI Agent 输出边界：不直接输出交易决策。
6. Live data fail-closed 回归。
7. Dashboard 文案和服务状态显示。

---

## 12. PM 门禁结论

本需求文档已明确：

1. MUST 功能和验收命令。
2. 非目标和交易安全边界。
3. WSL 路径规范。
4. AI Agent 的允许能力与禁止能力。
5. Feedback 现有 Bug 的处理范围。

结论：`READY_FOR_ARCHITECTURE`
