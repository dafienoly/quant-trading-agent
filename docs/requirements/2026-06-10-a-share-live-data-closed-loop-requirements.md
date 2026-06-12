# A股主板实盘数据闭环需求文档

> 角色：Product Manager Agent  
> 日期：2026-06-10  
> 阶段：首个新功能开发需求输入  
> 后续交付：Architect Agent 必须基于本文输出 `docs/design/2026-06-10-a-share-live-data-closed-loop-architecture.md`

---

## 1. 背景和用户问题

当前产品已经具备 API、Dashboard、Demo fallback、部分 AkShare/AkTools 接入和自动 feedback 能力，但用户反馈实盘数据没有跑通：AkShare 和 AkTools 当前都不可用或不稳定，导致实时盯盘、因子挖掘、回测、买卖信号生成无法基于真实数据形成闭环。

本功能是建立 Agent 开发管线后的第一个产品功能。目标不是继续堆叠 Demo，而是让用户在统一网页入口中使用真实 A股主板数据完成：

1. 实盘行情盯盘。
2. 基于真实历史/财务数据的因子计算。
3. 基于真实历史数据的回测。
4. 基于真实数据健康门禁的买卖信号生成。
5. 数据源失败时自动切源，全部失败时 fail closed。

---

## 2. 目标

### 2.1 产品目标

将当前“可演示的数据 fallback”升级为“A股主板真实数据闭环 MVP”：

- 用户可配置自选股票池和主题股票池。
- 系统可从多个免费真实数据源获取 A股主板实时行情、历史日线和基础财务数据。
- 系统可自动诊断数据源状态并切换备用 provider。
- 因子、回测、盯盘、信号必须明确使用真实数据还是失败阻断。
- Demo 数据不得计入实盘闭环验收。

### 2.2 非目标

本阶段不做以下事项：

1. 不启用真实自动下单。
2. 不提供 LEVEL_3 自动交易入口。
3. 不做全 A 主板高频实时扫描。
4. 不把分钟线作为验收阻断项。
5. 不把 Tavily / AnySearch / Firecrawl 作为行情或标准历史 K 线主数据源。
6. 不承诺免费数据源覆盖退市股、完整财报历史或机构级低延迟。
7. 不绕过现有 Risk Agent、股票池过滤器、人工确认下单规则。

---

## 3. 用户角色和使用流程

### 3.1 用户角色

- **Owner / Trader**：在网页中配置股票池、数据源、刷新频率，查看行情、因子、回测和信号。
- **Research Agent**：基于真实日线、财务和主题证据计算因子、做回测。
- **Signal Agent**：读取数据健康报告、因子结果和风控结果，生成可解释信号。
- **Developer / Tester Agent**：根据 feedback 和数据源诊断报告持续修复 provider。

### 3.2 核心用户流程

1. 用户启动产品 Demo。
2. 用户进入“数据源与股票池”页面。
3. 用户选择：
   - 自选池：10-100 只 A股主板股票。
   - 主题池：AI算力/半导体主题，100-300 只。
4. 用户配置实时刷新频率：
   - 自选池默认 30 秒，可手动调到 10-15 秒。
   - 主题池默认 60 秒。
5. 用户点击“数据源诊断”。
6. 系统对 AkShare、AkTools、至少一个直连免费源执行真实连接测试。
7. 系统选出当前可用 provider 并展示健康状态。
8. 用户进入“实时盯盘”，查看真实行情和数据延迟。
9. 用户触发因子计算，系统读取真实日线、基础财务和主题证据。
10. 用户触发回测，系统使用真实历史日线数据。
11. 用户触发信号生成，系统先检查数据健康和风控，通过后生成信号；若真实数据不可用，则阻断。

---

## 4. 功能点列表

| ID | 功能点 | 用户故事 | 预期行为 | 验收标准 | 优先级 |
|---|---|---|---|---|---|
| F-001 | 多真实数据源 Provider Hub | 作为用户，我希望系统不依赖单一 AkShare/AkTools | 系统支持 AkShare、AkTools、至少一个直连免费源，并统一输出数据契约 | 任一 provider 可用时，系统可返回真实行情；所有 provider 失败时返回严格失败态 | MUST |
| F-002 | 数据源诊断页 | 作为用户，我希望知道实盘数据为什么不可用 | 页面展示每个 provider 的连接状态、错误、延迟、字段覆盖率和最近成功时间 | 手动诊断后可看到 provider 级结果，不允许只显示“失败” | MUST |
| F-003 | 自动切源 | 作为用户，我希望主源失败时系统自动尝试备用源 | 按配置优先级切换真实 provider，记录 chosen_provider 和 fallback_chain | 模拟主源失败时，系统自动切到备用源并展示切源原因 | MUST |
| F-004 | 全部真实源失败 fail closed | 作为用户，我不希望系统用 demo 数据冒充实盘 | 所有真实源失败时，盯盘信号、买卖信号、订单草稿生成被阻断 | API/UI 明确显示 `data_status=FAILED`，信号结果为 blocked，写入 feedback Bug | MUST |
| F-005 | 自选池管理 | 作为用户，我希望维护 10-100 只关注股票 | 用户可配置、保存、加载自选池；仅允许 A股主板 | 输入创业板、科创板、ST、退市整理股时被拒绝或标红不可用 | MUST |
| F-006 | AI算力/半导体主题池 | 作为用户，我希望有内置主题池支持研究 | 系统提供 100-300 只候选股票池，按 PCB/先进封装/设备材料/存储/HBM/光模块等标签组织 | 主题池可被实时盯盘、因子计算、回测、信号生成选择 | MUST |
| F-007 | 实时行情闭环 | 作为用户，我希望看到真实 A股主板行情 | 展示价格、涨跌幅、成交量、成交额、开高低昨收、状态、延迟、provider、updated_at | 至少自选池 10 只股票在交易时段可刷新真实行情 | MUST |
| F-008 | 历史日线闭环 | 作为用户，我希望因子和回测使用真实日线 | 支持 OHLCV、成交额、raw price、adjusted price、复权方式、停牌/涨跌停字段 | 对自选池至少 10 只股票可拉取指定时间段日线并落库/缓存 | MUST |
| F-009 | 基础财务数据闭环 | 作为用户，我希望因子计算有基础基本面数据 | 支持 PE、PB、ROE、营收、利润、市值等基础字段，缺失显式标注 | 财务字段缺失不能静默填 0，必须有 missing report | MUST |
| F-010 | 主题/新闻证据增强 | 作为用户，我希望主题因子有证据来源 | Tavily / AnySearch / Firecrawl 采集新闻、公告、研报摘要、来源链接、event_date、confidence、tags | Theme 因子结果包含 evidence/source/confidence/version | SHOULD |
| F-011 | 数据源故障搜索诊断 | 作为开发者，我希望 provider 失败时自动生成诊断线索 | 当 provider 失败时，可调用搜索 API 查找接口变更、错误原因、替代 endpoint，并生成诊断报告 | 失败 Bug 包含 provider、错误、搜索摘要和候选修复方向 | SHOULD |
| F-012 | 分钟线接口预留 | 作为后续开发者，我希望未来可接分钟线 | 架构预留 minute bar provider 接口和数据契约，不作为本阶段验收阻断 | 架构文档包含分钟线扩展点；代码可不实现完整分钟线 | SHOULD |
| F-013 | 数据健康门禁 | 作为交易系统，我必须在数据异常时禁止交易 | 数据健康报告输出覆盖率、延迟、缺失字段、provider 状态、风险级别 | 数据不健康时 Signal Agent 不得生成实盘信号和订单草稿 | MUST |
| F-014 | 产品 UI 集成 | 作为用户，我希望在一个网页完成操作 | Dashboard 提供数据源诊断、股票池、实时盯盘、因子、回测、信号入口 | 用户无需调用零散脚本即可完成闭环操作 | MUST |
| F-015 | 自动 feedback | 作为开发者，我希望数据失败自动进入修复队列 | provider 异常、字段缺失、全部源失败、搜索诊断失败均生成结构化 Bug | `feedback/bugs/open/` 出现可追踪 Bug，含复现步骤和上下文 | MUST |

---

## 5. 数据需求

### 5.1 实时行情字段

每条实时行情至少包含：

- `symbol`
- `name`
- `market`
- `datetime`
- `last_price`
- `open`
- `high`
- `low`
- `pre_close`
- `pct_change`
- `change`
- `volume`
- `amount`
- `status`
- `delay_seconds`
- `currency`
- `timezone`
- `data_source`
- `updated_at`
- `data_version`
- `source_volume_unit`

内部 `volume` 必须统一为股。

### 5.2 历史日线字段

每条日线至少包含：

- `symbol`
- `trade_date`，格式 `YYYY-MM-DD`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `amount`
- `raw_open`
- `raw_high`
- `raw_low`
- `raw_close`
- `adjusted_open`
- `adjusted_high`
- `adjusted_low`
- `adjusted_close`
- `adjustment_type`
- `is_suspended`
- `is_limit_up`
- `is_limit_down`
- `currency`
- `timezone`
- `data_source`
- `updated_at`
- `data_version`

实盘交易相关价格必须使用 raw price；因子和回测可选择 adjusted price，但必须显式记录。

### 5.3 财务/基本面字段

第一版至少支持：

- `pe_ttm`
- `pb`
- `roe`
- `revenue`
- `net_profit`
- `market_cap`
- `report_period`
- `currency`
- `data_source`
- `updated_at`
- `data_version`

缺失字段必须进入 `data_missing_report`，不得静默填 0 冒充真实数据。

### 5.4 主题证据字段

搜索增强输出必须包含：

- `symbol`
- `topic`
- `event_date`
- `source`
- `url`
- `title`
- `summary`
- `evidence`
- `tags`
- `confidence`
- `provider`
- `fetched_at`
- `data_version`

LLM 或搜索摘要不得直接输出数值因子；只能输出结构化标签和证据，由规则映射为 Theme 因子。

---

## 6. 配置项需求

必须支持以下用户配置：

| 配置项 | 默认值 | 说明 |
|---|---|---|
| `LIVE_DATA_PROVIDER_ORDER` | `eastmoney,akshare,aktools` | 真实数据源优先级，实际 provider 名称由架构确认 |
| `ENABLE_DEMO_FALLBACK_FOR_LIVE_LOOP` | `false` | 实盘闭环验收必须为 false |
| `WATCHLIST_REFRESH_SECONDS` | `30` | 自选池刷新间隔 |
| `THEME_POOL_REFRESH_SECONDS` | `60` | 主题池刷新间隔 |
| `WATCHLIST_MIN_REFRESH_SECONDS` | `10` | 自选池最小刷新间隔 |
| `MAX_WATCHLIST_SIZE` | `100` | 自选池最大规模 |
| `MAX_THEME_POOL_SIZE` | `300` | 主题池最大规模 |
| `ENABLE_SEARCH_ENRICHMENT` | `true` | 是否启用搜索增强 |
| `SEARCH_PROVIDER_ORDER` | `tavily,anysearch,firecrawl` | 搜索增强 provider 顺序 |
| `SEARCH_DAILY_CALL_BUDGET` | `2500` | 免费账号合计预算，需预留安全余量 |
| `DATA_FAIL_CLOSED` | `true` | 所有真实源失败时阻断信号和订单草稿 |

API Key 只能来自环境变量：

- `TAVILY_API_KEY`
- `ANYSEARCH_API_KEY`
- `FIRECRAWL_API_KEY`

禁止把任何 Key 写入仓库文件。

---

## 7. UI/交互需求

### 7.1 数据源诊断页

必须展示：

1. Provider 列表和优先级。
2. 每个 provider 的实时行情测试结果。
3. 每个 provider 的历史日线测试结果。
4. 每个 provider 的财务数据测试结果。
5. 最近成功时间。
6. 当前 chosen provider。
7. 错误消息和 feedback bug_id。
8. 一键重新诊断按钮。

### 7.2 股票池页

必须支持：

1. 自选池增删改查。
2. 导入 10-100 只股票。
3. 内置 AI算力/半导体主题池。
4. 股票池过滤结果可见：主板/创业板/科创板/ST/退市整理股。
5. 不可交易股票不能进入实盘闭环。

### 7.3 实时盯盘页

必须展示：

1. 行情表格。
2. 数据源与延迟。
3. 刷新频率。
4. 数据健康状态。
5. LIMIT_UP / LIMIT_DOWN / SUSPENDED 等状态。
6. 失败时明确显示 fail closed，而不是自动显示 demo。

### 7.4 因子/回测/信号页

必须展示：

1. 当前使用的数据源。
2. 数据覆盖率和缺失报告。
3. 因子计算结果。
4. 回测参数和结果。
5. 信号解释。
6. 风控和数据健康阻断原因。
7. 主题证据来源和 confidence。

---

## 8. 安全与风控约束

1. 默认不得真实自动下单。
2. Risk Agent 一票否决。
3. 数据源异常时默认禁止交易。
4. 全部真实源失败时，禁止生成实盘买卖信号和订单草稿。
5. Demo 数据不得进入实盘信号链路。
6. 不能买创业板、科创板、ST、退市整理股。
7. 任何策略不得绕过股票池过滤器。
8. LLM / 搜索增强不得直接决定买卖。
9. 所有数据源调用失败必须可追溯。
10. 所有密钥只能来自环境变量。

---

## 9. Demo / Paper / Live 边界

本阶段允许：

- Demo 模式用于教学入口和离线展示。
- Paper broker 用于订单草稿和人工确认流程演示。
- LEVEL_1 信号模式和 LEVEL_2 人工确认模式的 UI 验证。

本阶段禁止：

- 将 Demo 数据标记为实盘数据。
- 用 Demo 数据通过实盘闭环验收。
- 开启 LEVEL_3 自动交易。
- 在真实数据失败时继续生成实盘订单草稿。

---

## 10. 可观测性和自动 feedback

系统必须输出：

1. `data_quality_report`
2. `data_missing_report`
3. `data_delay_report`
4. `provider_health_report`
5. `fallback_chain`
6. `feedback_bug_id`

以下情况必须生成 feedback Bug：

1. 所有真实 provider 失败。
2. 单个 provider 连续失败超过阈值。
3. 实时行情字段缺失。
4. 历史日线字段缺失。
5. 财务字段缺失超过阈值。
6. 搜索增强 API 失败或超预算。
7. 数据健康门禁阻断信号。

---

## 11. 测试范围建议

### 11.1 单元测试

- symbol 规范化和 A股主板过滤。
- provider 统一数据契约映射。
- volume 单位转换。
- raw / adjusted price 保留。
- provider fallback 顺序。
- fail closed 状态。
- 搜索增强字段结构。

### 11.2 集成测试

- `/product/quotes` 使用真实 provider hub。
- 数据源诊断 API。
- 自选池保存与过滤。
- 日线拉取和缓存。
- 财务数据拉取和缺失报告。
- 因子计算读取真实数据。
- 回测读取真实日线。
- 信号生成被数据健康门禁阻断。

### 11.3 产品验收测试

- 交易时段选择 10 只 A股主板股票，刷新真实行情。
- 主 provider 失败时自动切到备用 provider。
- 所有 provider 失败时 UI 显示 fail closed，信号和订单草稿被阻断。
- 对 10 只股票拉取至少 1 年日线并运行回测。
- 对 AI算力/半导体主题池生成主题证据和 Theme 因子解释。

---

## 12. PM 门禁

本文档可交给 Architect Agent 的条件：

- 每个 MUST 功能均有可测试验收标准。
- 非目标明确，避免开发 Agent 扩大到自动交易或全市场扫描。
- 数据来源、延迟容忍、fallback 行为明确。
- UI 用户路径明确。
- 交易安全边界明确：真实数据失败时 fail closed，默认不真实自动下单。

结论：**PM 需求文档通过，可进入架构设计阶段。**
