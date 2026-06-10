# 量化交易智能体系统 (Quant Trading Agent)

A股主板/中小板 + 港股通方向的量化交易智能体系统，基于多 Agent 协同架构，融合政策、情绪、基本面、技术趋势四维因子评分，提供从信号生成到风控执行的完整交易链路。

---

## 目录

- [系统架构](#系统架构)
- [技术栈](#技术栈)
- [目录结构](#目录结构)
- [快速开始](#快速开始)
- [仪表板](#仪表板)
- [API 接口](#api-接口)
- [环境变量](#环境变量)
- [测试](#测试)
- [安全机制](#安全机制)
- [许可证](#许可证)

---

## 系统架构

### Agent 角色

系统由 8 个 Agent 角色协同工作：

| Agent | 职责 |
|---|---|
| PolicyAgent | 政策主题因子分析，评估产业政策对板块的影响 |
| SentimentAgent | 情绪资金因子分析，追踪资金流向与市场情绪 |
| FundamentalAgent | 基本面因子分析，评估财务指标与估值水平 |
| TrendAgent | 技术趋势因子分析，判断价格趋势与动量信号 |
| RiskAgent | 实时风控检查，执行仓位限制与止损规则 |
| WatchlistMonitor | 候选股监控，追踪观察列表中的信号触发 |
| SignalService | 信号服务，汇总四维因子生成买卖信号 |
| ExecutionService | 执行服务，订单生成与成交管理 |

### 四因子评分模型

```
total_score = 0.25 * policy_score
            + 0.30 * sentiment_score
            + 0.20 * fundamental_score
            + 0.25 * trend_score
```

总评分范围 0~100，综合政策、情绪、基本面、趋势四个维度，加权计算得出最终评分。

### 三级交易模式

| 模式 | 说明 | 默认 |
|---|---|---|
| LEVEL_1_SIGNAL_ONLY | 信号模式 -- 仅生成买卖建议，不执行交易 | 是 |
| LEVEL_2_HUMAN_CONFIRM | 人工确认模式 -- 信号生成后需逐笔人工确认方可执行 | 否 |
| LEVEL_3_AUTO | 自动交易模式 -- 信号经风控检查后自动执行 | 否 |

### 风控规则

| 规则 | 限制 |
|---|---|
| 单股仓位上限 | <= 15% |
| 板块仓位上限 | <= 60% |
| 最低现金比例 | >= 20% |
| 单股亏损预警 | -5% |
| 单股亏损止损 | -8% |
| 日亏损预警 | -2% |
| 日亏损止损 | -3% |
| 最大回撤防御线 | -8% |
| 最大回撤熔断线 | -12% |

### 交易限制

- 不交易创业板（300xxx）
- 不交易科创板（688xxx）
- 不使用融资融券
- 仅支持 A 股主板 + 中小板 + 港股通标的

---

## 技术栈

| 类别 | 技术 |
|---|---|
| 语言 | Python 3.10+ |
| Web 框架 | FastAPI |
| 仪表板 | Streamlit + Plotly |
| 数据处理 | Pandas, NumPy |
| 数据源 | AkShare, AKTools |
| 数据库 | DuckDB / SQLite |
| 数据校验 | Pydantic v2 |
| 日志 | Loguru |
| 模拟券商 | PaperBroker（含 T+1 模拟） |
| 回测 | 事件驱动回测引擎 |

---

## 目录结构

```
quant-trading-agent/
├── src/
│   ├── agent_orchestrator/   # Agent 编排（WatchlistMonitor, SignalService）
│   ├── api/                  # FastAPI 路由与应用入口
│   ├── backtest_engine/      # 回测引擎（事件驱动、组合管理、绩效分析）
│   ├── config/               # 配置管理
│   ├── data_gateway/         # 数据网关（AkShare/AKTools/实时行情）
│   ├── execution_engine/     # 执行引擎（PaperBroker、订单检查、成交记录）
│   ├── factor_engine/        # 因子引擎（技术/情绪/政策/基本面）
│   ├── models/               # 数据模型（Pydantic schemas）
│   ├── product_app/          # 产品服务（配置、健康检查、反馈、作业管理）
│   ├── risk_engine/          # 风控引擎（运行时风控、Kill Switch）
│   ├── stock_pool/           # 股票池（主板过滤、半导体板块）
│   ├── strategy_engine/      # 策略引擎（评分模型、信号生成、板块轮动）
│   ├── ui_report/            # Web 仪表板（Streamlit）
│   └── utils/                # 工具函数（日历、数据质量、存储）
├── scripts/                  # 运维脚本（部署、启动、停止、重启）
├── tests/                    # 测试用例
├── docs/                     # 设计文档与审计报告
├── feedback/                 # Bug 反馈数据
├── config/                   # 股票池配置
├── data/                     # 数据目录
├── logs/                     # 日志目录
└── runtime/                  # 运行时状态（作业、回测结果）
```

---

## 快速开始

### 1. 一键部署

```bash
# Linux / macOS
bash scripts/setup.sh

# Windows
scripts\setup.bat
```

部署脚本将自动完成：创建虚拟环境、安装依赖、复制 `.env` 配置文件、初始化数据目录。

### 2. 一键启动

```bash
# Linux / macOS
bash scripts/start.sh

# Windows
scripts\start.bat
```

启动后访问：

- API 文档：http://localhost:8000/docs （Swagger UI）
- 仪表板：http://localhost:8501

### 3. 一键停止

```bash
# Linux / macOS
bash scripts/stop.sh

# Windows
scripts\stop.bat
```

### 4. 一键重启

```bash
# Linux / macOS
bash scripts/restart.sh

# Windows
scripts\restart.bat
```

---

## 仪表板

仪表板包含 9 个功能标签页：

| 标签页 | 功能说明 |
|---|---|
| 系统状态 | 健康检查、组件运行状态、Kill Switch 控制 |
| 实时行情 | AkShare/AkTools 数据源选择、实时刷新、后台快照、Demo fallback 明示 |
| 候选股监控 | 观察列表管理、信号触发提醒 |
| 因子分析 | 四因子评分详情、雷达图可视化 |
| 回测实验室 | 回测参数配置、回测结果展示 |
| 信号中心 | 买入/卖出/持有信号列表与详情 |
| 人工确认 | 待确认订单列表、逐笔确认或拒绝 |
| 配置中心 | 配置项查看与修改、恢复默认值 |
| 反馈中心 | Bug 报告提交与状态管理 |

---

## API 接口

系统提供 15 个产品端点，均以 `/product` 为前缀：

### 健康与仪表板

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/product/health` | 系统健康状态 |
| GET | `/product/quotes` | 实时行情快照（AkShare/AkTools，可显式 Demo fallback） |
| GET | `/product/dashboard` | 仪表板聚合数据 |

### 因子与回测

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/product/factors/compute` | 计算因子评分 |
| POST | `/product/jobs/backtest/start` | 启动回测任务 |

### 配置管理

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/product/config` | 获取当前配置（脱敏） |
| POST | `/product/config` | 更新单个配置项 |
| POST | `/product/config/confirm-upgrade` | 确认交易模式升级 |
| POST | `/product/config/restore-defaults` | 恢复默认配置 |

### 反馈管理

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/product/feedback` | 获取 Bug 列表 |
| POST | `/product/feedback` | 提交 UI/API 自动反馈 Bug |
| POST | `/product/feedback/{bug_id}/status` | 更新 Bug 状态 |

### 作业管理

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/product/jobs` | 作业列表 |
| POST | `/product/jobs/{job_name}/start` | 启动作业 |
| POST | `/product/jobs/{job_name}/stop` | 停止作业 |

---

## 环境变量

复制 `.env.example` 为 `.env` 并按需修改：

```bash
cp .env.example .env
```

核心配置项：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `MAX_TRADING_LEVEL` | `LEVEL_1_SIGNAL_ONLY` | 最高交易模式 |
| `ENABLE_LIVE_TRADING` | `false` | 是否启用实盘交易 |
| `REQUIRE_HUMAN_CONFIRMATION` | `true` | 是否需要人工确认 |
| `DATA_SOURCE` | `sina` | 数据源 |
| `DEFAULT_DATA_PROVIDER` | `akshare` | 产品行情默认数据源（akshare/aktools） |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `API_PORT` | `8000` | API 服务端口 |
| `STREAMLIT_PORT` | `8501` | 仪表板端口 |
| `MAX_SINGLE_STOCK_POSITION` | `0.15` | 单股仓位上限 |
| `MAX_SECTOR_POSITION` | `0.60` | 板块仓位上限 |
| `MIN_CASH_RATIO` | `0.20` | 最低现金比例 |
| `BROKER_ADAPTER` | `paper` | 券商适配器（paper 为模拟） |

完整配置项参见 `.env.example` 文件。

---

## 测试

```bash
# 运行全部单元测试
python -m pytest tests/ -v

# 端到端验收测试
python tests/test_e2e_acceptance.py

# 产品 API 端到端测试
python tests/test_product_api_e2e.py

# 本次产品实时行情/前端触碰范围验证
python -m pytest tests/test_phase4_api.py tests/test_phase4_realtime_health.py tests/test_realtime_provider.py tests/test_product_market_data.py tests/test_product_realtime_api.py tests/test_product_service_manager_quotes.py tests/test_product_dashboard_source.py -q --basetemp=runtime/pytest-tmp
python -m ruff check src/product_app/market_data.py src/product_app/service_manager.py src/api/product_routes.py src/data_gateway/realtime_provider.py src/data_gateway/aktools_provider.py src/ui_report/product_dashboard.py tests/test_realtime_provider.py tests/test_product_market_data.py tests/test_product_realtime_api.py tests/test_product_service_manager_quotes.py tests/test_product_dashboard_source.py
```

---

## 安全机制

- **LEVEL_3_AUTO 默认阻断**：全自动交易模式需通过配置中心显式确认升级后方可启用，防止误操作
- **LEVEL_2 人工确认**：人工确认模式下，每笔订单必须由人工逐笔确认或拒绝
- **Kill Switch**：一键停止所有交易活动，紧急情况下快速熔断
- **T+1 模拟**：模拟 A 股 T+1 交易规则，当日买入的股票次日方可卖出
- **配置脱敏**：API 返回的配置信息经过脱敏处理，不暴露敏感字段

---

## 许可证

MIT License
