# AI算力半导体轮动策略量化交易系统 — 用户指南

> 版本：0.5.0 | Phase 5（人工确认交易）| 最后更新：2026-06-09

---

## 目录

1. [系统概述](#1-系统概述)
2. [环境要求与安装](#2-环境要求与安装)
3. [配置说明](#3-配置说明)
4. [完整使用流程](#4-完整使用流程)
5. [交易模式说明](#5-交易模式说明)
6. [风控参数说明](#6-风控参数说明)
7. [安全注意事项](#7-安全注意事项)
8. [常见问题](#8-常见问题)
9. [目录结构](#9-目录结构)

---

## 1. 系统概述

### 1.1 系统简介

本系统是一套面向 **A 股主板及港股半导体板块** 的量化交易 Agent 系统，核心策略为 **AI 算力半导体轮动策略**。系统通过多维度因子分析（技术面、基本面、情绪面、主题面）对半导体板块个股进行综合评分与轮动择时，生成结构化的买卖信号，并支持从信号研究、回测验证到人工确认交易的完整闭环。

### 1.2 系统架构

系统采用六层架构设计，各层职责明确、数据单向流动：

```
数据层 (Data Gateway)
  ↓ 日线/实时行情、交易日历
因子层 (Factor Engine)
  ↓ 技术因子、基本面因子、情绪因子、主题因子
策略层 (Strategy Engine)
  ↓ 评分模型、择时模型、板块轮动、信号生成
回测层 (Backtest Engine)
  ↓ 佣金模型、风控检查、绩效评估、报告生成
风控层 (Risk Engine)
  ↓ 仓位控制、亏损止损、回撤防守、Kill Switch
执行层 (Execution Engine)
  ↓ 订单检查、人工确认、券商适配、成交记录
```

### 1.3 目标市场

| 市场 | 范围 | 交易时段 |
|------|------|----------|
| A 股 | 主板（沪市 6 开头、深市 0 开头） | 09:30–11:30 / 13:00–15:00 |
| 港股 | 半导体方向标的（5 位数字代码） | 09:30–12:00 / 13:00–16:00 |

> **注意：** 创业板（3 开头）和科创板（688 开头）已被系统排除，禁止买入。

---

## 2. 环境要求与安装

### 2.1 环境要求

| 项目 | 要求 |
|------|------|
| Python | 3.10+（推荐 3.13） |
| 操作系统 | Windows / macOS / Linux |
| 网络 | 需访问 AkShare / AkTools 数据源 |

### 2.2 依赖说明

核心依赖（安装时自动安装）：

- **pandas** ≥ 2.0 — 数据处理
- **numpy** ≥ 1.24 — 数值计算
- **akshare** ≥ 1.10 — A 股/港股数据源
- **aktools** ≥ 0.0.91 — AkShare HTTP API 客户端
- **httpx** ≥ 0.25 — 异步 HTTP 客户端
- **pydantic** ≥ 2.0 — 数据模型验证
- **loguru** ≥ 0.7 — 日志管理
- **python-dotenv** ≥ 1.0 — 环境变量加载
- **pyyaml** ≥ 6.0 — YAML 配置解析
- **duckdb** ≥ 0.9 — 本地数据库

可选依赖：

- **streamlit** ≥ 1.28 + **plotly** ≥ 5.18 — 盯盘面板 UI
- **vectorbt** ≥ 0.26 — 高级回测
- **pytest** ≥ 7.0 + **ruff** ≥ 0.1 — 开发测试

### 2.3 安装步骤

```bash
# 1. 克隆仓库
git clone <repo-url>
cd quant-trading-agent

# 2. 安装核心依赖
pip install -e .

# 3. 安装 UI 依赖（如需使用盯盘面板）
pip install -e ".[ui]"

# 4. 安装回测扩展依赖（如需高级回测）
pip install -e ".[backtest]"

# 5. 安装开发依赖（如需运行测试）
pip install -e ".[dev]"
```

### 2.4 配置环境变量

```bash
# 从模板创建 .env 文件
cp .env.example .env

# 编辑 .env，根据实际需求调整配置
# 详见第 3 节「配置说明」
```

---

## 3. 配置说明

所有配置通过项目根目录的 `.env` 文件管理，系统启动时自动加载。修改配置后需重启相关服务。

### 3.1 交易模式配置

| 配置项 | 说明 | 可选值 | 默认值 |
|--------|------|--------|--------|
| `MAX_TRADING_LEVEL` | 最高交易模式 | `LEVEL_0` / `LEVEL_1_SIGNAL_ONLY` / `LEVEL_2_HUMAN_CONFIRM` / `LEVEL_3_AUTO` | `LEVEL_1_SIGNAL_ONLY` |
| `ENABLE_LIVE_TRADING` | 是否启用实盘交易 | `true` / `false` | `false` |
| `REQUIRE_HUMAN_CONFIRMATION` | 是否要求人工确认 | `true` / `false` | `true` |

> **重要：** 默认为 `LEVEL_1_SIGNAL_ONLY` + `ENABLE_LIVE_TRADING=false`，系统仅生成信号建议，不会产生任何订单。

### 3.2 数据源配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `DEFAULT_DATA_PROVIDER` | 默认数据源（`akshare` 直接调用 / `aktools` HTTP API） | `akshare` |
| `TUSHARE_TOKEN` | Tushare 数据源 Token（按需填写） | 空 |
| `EASTMONEY_ENABLED` | 启用东方财富数据源 | `true` |
| `SINA_QUOTE_ENABLED` | 启用新浪实时行情 | `true` |

### 3.3 数据库配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `DATABASE_URL` | 数据库连接字符串 | `sqlite:///data/quant_trading.db` |

初期使用 SQLite，中期可切换为 PostgreSQL：

```env
DATABASE_URL=postgresql://user:password@localhost:5432/quant_trading
```

### 3.4 风控参数

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `MAX_SINGLE_STOCK_POSITION` | 单票仓位上限 | `0.15`（15%） |
| `MAX_SECTOR_POSITION` | 板块集中度上限 | `0.60`（60%） |
| `MIN_CASH_RATIO` | 现金最低比例 | `0.20`（20%） |
| `SINGLE_STOCK_LOSS_WARN` | 单票亏损警告线 | `-0.05`（-5%） |
| `SINGLE_STOCK_LOSS_STOP` | 单票亏损止损线 | `-0.08`（-8%） |
| `DAILY_LOSS_WARN` | 日亏损警告线 | `-0.02`（-2%） |
| `DAILY_LOSS_STOP` | 日亏损止损线 | `-0.03`（-3%） |
| `MAX_DRAWDOWN_DEFENSE` | 回撤防守线 | `-0.08`（-8%） |
| `MAX_DRAWDOWN_HALT` | 回撤停止线 | `-0.12`（-12%） |

### 3.5 回测参数

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `BACKTEST_COMMISSION_RATE` | 佣金费率 | `0.0003`（万三） |
| `BACKTEST_STAMP_DUTY` | 印花税费率 | `0.001`（千一） |
| `BACKTEST_SLIPPAGE` | 滑点费率 | `0.001`（千一） |

### 3.6 券商接口配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `BROKER_ADAPTER` | 券商适配器（`paper` 模拟 / 实际券商） | `paper` |

> `LEVEL_2` 及以上模式使用。默认 `paper` 为模拟交易，不会产生真实委托。

### 3.7 日志与通知

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `LOG_FILE` | 日志文件路径 | `logs/quant_trading.log` |
| `NOTIFY_EMAIL` | 通知邮箱（可选） | 空 |
| `NOTIFY_WEBHOOK_URL` | Webhook 通知地址（可选） | 空 |

---

## 4. 完整使用流程

### 4.1 数据获取

使用 `fetch_daily_data.py` 脚本获取历史日线数据：

```bash
python scripts/fetch_daily_data.py --pool semiconductor --start-date 20240101
```

#### 参数说明

| 参数 | 必填 | 说明 |
|------|------|------|
| `--pool` | 否 | 股票池选择：`semiconductor`（半导体主题，默认）/ `all`（全市场主板） |
| `--symbols` | 否 | 指定股票代码，逗号分隔（如 `002463,600584`），与 `--pool` 互斥 |
| `--start-date` | **是** | 起始日期，格式 YYYYMMDD |
| `--end-date` | 否 | 截止日期，格式 YYYYMMDD，默认当天 |
| `--provider` | 否 | 数据源：`akshare`（默认）/ `aktools` |
| `--index` | 否 | 同时获取关注指数日线数据 |

#### 使用示例

```bash
# 获取半导体池全部股票近两年数据
python scripts/fetch_daily_data.py --pool semiconductor --start-date 20240101

# 获取指定股票数据
python scripts/fetch_daily_data.py --symbols 002463,600584 --start-date 20240101

# 使用 aktools 数据源，同时获取指数数据
python scripts/fetch_daily_data.py --pool semiconductor --start-date 20240101 --provider aktools --index

# 获取全市场主板数据
python scripts/fetch_daily_data.py --pool all --start-date 20240101
```

#### 数据存储

- 原始数据：`data/raw/`
- 清洗后数据：`data/cleaned/`
- 质量报告：`data/quality/`

脚本会自动执行数据质量检查，生成完整率报告、缺失报告和延迟报告。

---

### 4.2 回测验证

使用 `run_backtest.py` 脚本执行策略回测：

```bash
python scripts/run_backtest.py --start-date 20240101 --end-date 20260601 --capital 1000000
```

#### 参数说明

| 参数 | 必填 | 说明 |
|------|------|------|
| `--start-date` | **是** | 回测起始日期，格式 YYYYMMDD |
| `--end-date` | **是** | 回测截止日期，格式 YYYYMMDD |
| `--capital` | 否 | 初始资金，默认 1,000,000 |
| `--in-sample-end` | 否 | 样本内截止日期（用于样本外测试），格式 YYYYMMDD |
| `--symbols` | 否 | 指定股票代码，逗号分隔 |
| `--commission-rate` | 否 | 佣金费率，默认 0.0003 |
| `--stamp-duty-rate` | 否 | 印花税费率，默认 0.001 |
| `--slippage-rate` | 否 | 滑点费率，默认 0.001 |
| `--output-dir` | 否 | 输出目录，默认 `data/backtest_results` |

#### 使用示例

```bash
# 基本回测
python scripts/run_backtest.py --start-date 20240101 --end-date 20260601 --capital 1000000

# 样本内/样本外分割回测
python scripts/run_backtest.py --start-date 20240101 --end-date 20260601 --in-sample-end 20250601

# 指定股票回测
python scripts/run_backtest.py --start-date 20240101 --end-date 20260601 --symbols 002463,600584
```

#### 回测输出

回测完成后，在 `data/backtest_results/` 目录下生成：

| 文件 | 说明 |
|------|------|
| `backtest_report_{timestamp}.txt` | 绩效报告文本（年化收益、夏普比率、最大回撤等） |
| `daily_values_{timestamp}.csv` | 每日资产净值曲线 |
| `trade_records_{timestamp}.csv` | 完整交易记录 |

使用 `--in-sample-end` 参数时，系统会自动执行样本外测试，并比较样本内外年化收益的劣化程度。若劣化超过 10%，将提示可能存在过拟合。

---

### 4.3 启动 API 服务

```bash
uvicorn src.api.app:create_app --factory --host 0.0.0.0 --port 8000
```

#### API 端点一览

| 方法 | 路径 | 说明 | 模式要求 |
|------|------|------|----------|
| GET | `/health` | 系统健康检查 | 全部 |
| GET | `/risk/status` | 风控状态查询 | 全部 |
| GET | `/signals/latest` | 获取最新信号 | 全部 |
| POST | `/signals/refresh` | 手动刷新信号 | 全部 |
| GET | `/quotes/{symbol}` | 查询个股行情 | 全部 |
| GET | `/orders/pending` | 查询待确认订单 | LEVEL_2+ |
| GET | `/orders/{order_id}` | 查询订单详情 | LEVEL_2+ |
| POST | `/orders/{order_id}/confirm` | 确认订单 | LEVEL_2 |
| POST | `/orders/{order_id}/reject` | 拒绝订单 | LEVEL_2 |
| POST | `/orders/{order_id}/cancel` | 撤销订单 | LEVEL_2 |
| GET | `/account` | 查询账户信息 | LEVEL_2+ |
| GET | `/positions` | 查询持仓 | LEVEL_2+ |
| WS | `/ws/signals` | WebSocket 实时信号推送 | 全部 |

#### 端点详细说明

**GET /health** — 系统健康检查

```json
{
  "status": "ok",
  "max_trading_level": "LEVEL_1_SIGNAL_ONLY",
  "enable_live_trading": false
}
```

**GET /risk/status** — 风控状态

返回当前风控引擎的实时检查结果，包含风控是否通过、阻断原因、风险等级等信息。

**GET /signals/latest** — 最新信号

返回最近一次信号刷新的结果，包含信号列表、订单列表和风控消息。

**POST /signals/refresh** — 手动刷新信号

手动触发一次完整的信号生成流程（数据获取 → 因子计算 → 策略评分 → 信号生成 → 风控检查）。

**GET /orders/pending** — 待确认订单

返回当前等待人工确认的订单列表，每个订单包含股票名称、方向、价格、数量、止损位、止盈位、风险提示等完整信息。

**POST /orders/{order_id}/confirm** — 确认订单

逐笔确认待处理订单。确认后订单将发送至券商适配器执行。**禁止批量确认。**

**POST /orders/{order_id}/reject** — 拒绝订单

拒绝待处理订单，可附带拒绝原因。

**POST /orders/{order_id}/cancel** — 撤销订单

撤销待处理订单。

**GET /account** — 账户信息

返回账户总资产、可用现金、持仓市值、当日盈亏等信息。

**GET /positions** — 持仓查询

返回当前所有持仓的详细信息，包括股票代码、数量、成本价、现价、浮动盈亏等。

**WS /ws/signals** — WebSocket 实时信号推送

建立 WebSocket 连接后，系统每 5 秒推送最新信号数据。

---

### 4.4 启动盯盘面板

```bash
streamlit run src/ui_report/dashboard.py
```

启动后浏览器自动打开面板页面。面板包含四个标签页：

| 标签页 | 功能说明 |
|--------|----------|
| **风控状态** | 显示当前风控是否通过、交易模式、实盘状态、Kill Switch 状态 |
| **信号列表** | 展示最新买卖信号，买入信号绿色标注，卖出信号红色标注 |
| **候选股** | 展示候选股监控列表及综合评分 |
| **订单确认** | LEVEL_2 模式下的待确认订单列表，支持逐笔确认/拒绝 |

侧边栏显示当前系统信息：交易模式、实盘交易状态、下单确认是否可用。

---

### 4.5 人工确认交易流程（LEVEL_2）

以下为 LEVEL_2_HUMAN_CONFIRM 模式的完整操作流程：

#### 步骤 1：配置交易模式

编辑 `.env` 文件：

```env
MAX_TRADING_LEVEL=LEVEL_2_HUMAN_CONFIRM
ENABLE_LIVE_TRADING=false
REQUIRE_HUMAN_CONFIRMATION=true
BROKER_ADAPTER=paper
```

> 首次使用建议保持 `ENABLE_LIVE_TRADING=false` 和 `BROKER_ADAPTER=paper`，使用模拟交易验证流程。

#### 步骤 2：启动 API 服务

```bash
uvicorn src.api.app:create_app --factory --host 0.0.0.0 --port 8000
```

#### 步骤 3：启动盯盘面板

```bash
streamlit run src/ui_report/dashboard.py
```

#### 步骤 4：等待信号触发

系统运行后，当策略产生买卖信号且通过风控检查时，订单将自动出现在盯盘面板的 **「订单确认」** 标签页中。

也可通过 API 查询待确认订单：

```bash
curl http://localhost:8000/orders/pending
```

#### 步骤 5：审核订单

在「订单确认」标签页中，每个待确认订单以展开卡片形式展示，包含以下信息：

| 字段 | 说明 |
|------|------|
| 订单 ID | 唯一标识，格式 `ORD_{YYYYMMDD}_{6位随机码}` |
| 方向 | 买入 / 卖出 |
| 股票名称及代码 | 如 "沪硅产业(688126)" |
| 价格 | 委托价格 |
| 数量 | 委托数量（100 股整数倍） |
| 金额 | 预估成交金额 |
| 策略 | 产生该订单的策略名称 |
| 止损位 | 建议止损价格 |
| 止盈位 | 建议止盈价格 |
| 风险提示 | 风控引擎附加的风险说明 |

#### 步骤 6：逐笔确认或拒绝

- 点击 **「确认」** 按钮：订单发送至 PaperBroker（模拟交易）执行
- 点击 **「拒绝」** 按钮：订单被标记为已取消

> **安全约束：** 系统禁止「一键确认」和「批量确认」，每笔订单必须独立审核操作。

#### 步骤 7：查看执行结果

确认后可通过以下方式查看结果：

```bash
# 查询账户信息
curl http://localhost:8000/account

# 查询持仓
curl http://localhost:8000/positions

# 查询订单详情
curl http://localhost:8000/orders/{order_id}
```

或在盯盘面板的「风控状态」标签页查看账户概况。

---

## 5. 交易模式说明

系统提供四级交易模式，通过 `.env` 中的 `MAX_TRADING_LEVEL` 控制：

| 模式 | 功能描述 | 人工确认 | 适用场景 |
|------|----------|----------|----------|
| **LEVEL_0** | 仅数据研究，不生成任何信号和订单 | N/A | 数据探索、因子研究 |
| **LEVEL_1_SIGNAL_ONLY** | 生成买卖信号建议，不产生订单 | N/A | 信号验证、策略观察 |
| **LEVEL_2_HUMAN_CONFIRM** | 生成委托单，必须逐笔人工确认 | **必须逐笔确认** | 人工审核交易 |
| **LEVEL_3_AUTO** | 自动交易，无需人工确认 | 不需要（需 Kill Switch） | 全自动交易（需严格条件） |

### 模式切换规则

- 模式只能逐级升级，建议按 LEVEL_0 → LEVEL_1 → LEVEL_2 的顺序逐步验证
- 切换模式需修改 `.env` 中的 `MAX_TRADING_LEVEL`，然后重启系统
- LEVEL_3_AUTO 模式要求 `ENABLE_LIVE_TRADING=true`，系统启动时会发出警告
- 任何模式下 `ENABLE_LIVE_TRADING=false` 时，所有订单均走模拟交易（PaperBroker）

### 各模式下的系统行为

| 行为 | LEVEL_0 | LEVEL_1 | LEVEL_2 | LEVEL_3 |
|------|---------|---------|---------|---------|
| 数据获取 | ✅ | ✅ | ✅ | ✅ |
| 因子计算 | ✅ | ✅ | ✅ | ✅ |
| 信号生成 | ❌ | ✅ | ✅ | ✅ |
| 订单草稿 | ❌ | ❌ | ✅ | ✅ |
| 人工确认 | N/A | N/A | ✅ 必须 | ❌ |
| 自动执行 | ❌ | ❌ | 确认后执行 | ✅ |

---

## 6. 风控参数说明

系统风控分为 **仓位控制**、**亏损控制**、**回撤控制** 三个维度，所有参数可在 `.env` 中配置。

### 6.1 仓位控制

| 参数 | 默认值 | 说明 | 级别 |
|------|--------|------|------|
| 单票仓位上限 | 15% | 单只股票持仓占总资产比例上限 | 硬限制 |
| 板块集中度上限 | 60% | 同一板块持仓占总资产比例上限 | 硬限制 |
| 现金最低比例 | 20% | 账户现金占总资产最低比例 | 硬限制 |

> 硬限制：触发时直接阻断交易，不允许开新仓。

### 6.2 亏损控制

| 参数 | 默认值 | 说明 | 触发动作 |
|------|--------|------|----------|
| 单票亏损警告 | -5% | 单只股票浮动亏损达到此比例 | 减半提醒 |
| 单票亏损止损 | -8% | 单只股票浮动亏损达到此比例 | 强制止损卖出 |
| 日亏损警告 | -2% | 账户当日亏损达到此比例 | 停止开新仓 |
| 日亏损止损 | -3% | 账户当日亏损达到此比例 | 只允许减仓 |

### 6.3 回撤控制

| 参数 | 默认值 | 说明 | 触发动作 |
|------|--------|------|----------|
| 回撤防守 | -8% | 从历史最高净值的回撤达到此比例 | 进入防守模式，降低仓位 |
| 回撤停止 | -12% | 从历史最高净值的回撤达到此比例 | 停止所有交易 |

### 6.4 Kill Switch（紧急停止）

Kill Switch 是系统最高优先级的安全机制：

- 激活后，**所有交易立即停止**，包括已确认未执行的订单
- 可通过 API 或风控引擎手动激活
- 激活后需手动解除才能恢复交易
- 激活原因记录在风控日志中

---

## 7. 安全注意事项

### 7.1 默认安全配置

- 系统默认 `MAX_TRADING_LEVEL=LEVEL_1_SIGNAL_ONLY`，**不会生成任何订单**
- 系统默认 `ENABLE_LIVE_TRADING=false`，所有订单走模拟交易
- 系统默认 `REQUIRE_HUMAN_CONFIRMATION=true`，要求人工确认

### 7.2 交易安全约束

| 约束 | 说明 |
|------|------|
| 禁止一键确认 | 必须逐笔审核确认每笔订单，系统不提供批量确认功能 |
| 创业板/科创板禁止买入 | 代码以 3 开头（创业板）或 688 开头（科创板）的股票自动拦截 |
| 非交易时段禁止下单 | 不在 A 股/港股交易时段内的订单自动拒绝 |
| 尾盘禁止开新仓 | A 股 14:55 后禁止买入开仓（卖出不受限） |
| 风控不通过不能下单 | 任何风控检查未通过的信号不会生成订单 |

### 7.3 订单生命周期

每个订单经历以下状态流转：

```
CREATED → RISK_CHECKED → CONFIRMED → SENT → FILLED
                                    ↘ REJECTED
                      ↘ CANCELLED
```

- **CREATED**：订单已创建
- **RISK_CHECKED**：通过风控检查，等待人工确认（LEVEL_2）
- **CONFIRMED**：人工确认通过
- **SENT**：已发送至券商适配器
- **FILLED**：已成交
- **REJECTED**：被券商拒绝
- **CANCELLED**：已取消（人工拒绝或撤销）

### 7.4 数据安全

- 所有交易记录完整保存，确保可追溯
- 订单包含 `signal_id` 和 `risk_check_id`，可回溯至原始信号和风控决策
- 成交记录包含手续费、印花税等完整费用信息
- 模拟交易记录标记 `env=paper`，实盘交易标记 `env=live`

---

## 8. 常见问题

### Q1：如何切换数据源？

修改 `.env` 中的 `DEFAULT_DATA_PROVIDER`：

```env
# 使用 AkShare 直接调用
DEFAULT_DATA_PROVIDER=akshare

# 使用 AkTools HTTP API
DEFAULT_DATA_PROVIDER=aktools
```

或在数据获取脚本中通过 `--provider` 参数指定：

```bash
python scripts/fetch_daily_data.py --pool semiconductor --start-date 20240101 --provider aktools
```

修改后重启相关服务。

### Q2：如何查看回测报告？

回测完成后，在 `data/backtest_results/` 目录查看：

- 文本报告：`backtest_report_{timestamp}.txt`
- 每日资产：`daily_values_{timestamp}.csv`
- 交易记录：`trade_records_{timestamp}.csv`

回测结果也会在终端直接输出绩效摘要。

### Q3：信号不更新怎么办？

1. 检查 AkShare API 连接是否正常，确保网络通畅
2. 确认当前为交易日，非交易日和交易时段外不会产生新信号
3. 检查 API 服务是否正常运行：访问 `http://localhost:8000/health`
4. 尝试手动刷新信号：`POST /signals/refresh`
5. 查看日志文件 `logs/quant_trading.log` 中的错误信息

### Q4：如何升级到 LEVEL_2 人工确认模式？

1. 编辑 `.env` 文件，修改以下配置：

```env
MAX_TRADING_LEVEL=LEVEL_2_HUMAN_CONFIRM
ENABLE_LIVE_TRADING=false
REQUIRE_HUMAN_CONFIRMATION=true
BROKER_ADAPTER=paper
```

2. 重启 API 服务和盯盘面板
3. 建议先用模拟交易（`BROKER_ADAPTER=paper`）验证流程
4. 确认流程无误后，再考虑切换至实盘券商适配器

### Q5：如何激活/解除 Kill Switch？

Kill Switch 可通过风控引擎编程激活，激活后系统停止所有交易。解除需手动操作风控引擎实例，具体方式取决于部署配置。激活原因会记录在日志中。

### Q6：订单被拒绝的常见原因？

| 拒绝原因 | 说明 |
|----------|------|
| 非交易时段 | 当前时间不在 A 股/港股交易时段 |
| 尾盘禁止开新仓 | A 股 14:55 后的买入订单 |
| 创业板/科创板 | 代码被排除的股票 |
| 可用资金不足 | 买入金额超过可用现金 |
| 无持仓可卖 | 卖出股票无对应持仓 |
| 可卖数量不足 | 卖出数量超过可卖持仓 |
| 黑名单股票 | 在黑名单中的股票 |
| 风控未通过 | 风控引擎检查不通过 |

### Q7：如何查看系统当前配置？

访问 API 健康检查端点：

```bash
curl http://localhost:8000/health
```

返回当前交易模式和实盘交易状态。完整配置可通过 `src.config.settings.get_config_dict()` 查看（排除敏感信息）。

---

## 9. 目录结构

```
quant-trading-agent/
├── config/                  # 配置文件
│   └── stock_pool.yaml      # 股票池定义
├── data/                    # 数据存储
│   ├── raw/                 # 原始数据
│   ├── cleaned/             # 清洗后数据
│   ├── quality/             # 数据质量报告
│   └── backtest_results/    # 回测结果
├── docs/                    # 文档
│   ├── audit/               # 审计报告
│   ├── design/              # 设计文档
│   ├── log/                 # 开发日志
│   ├── policy/              # 策略规范
│   └── roadmap/             # 路线图
├── scripts/                 # 入口脚本
│   ├── fetch_daily_data.py  # 数据获取
│   └── run_backtest.py      # 回测执行
├── src/                     # 源代码
│   ├── agent_orchestrator/  # Agent 编排
│   │   ├── signal_service.py      # 信号服务
│   │   └── watchlist_monitor.py   # 候选股监控
│   ├── api/                 # FastAPI 接口
│   │   └── app.py                 # API 应用
│   ├── backtest_engine/     # 回测引擎
│   │   ├── engine.py              # 回测引擎核心
│   │   ├── commission_model.py    # 佣金模型
│   │   ├── performance.py         # 绩效计算
│   │   ├── report_generator.py    # 报告生成
│   │   ├── risk_check.py          # 回测风控
│   │   └── significance_test.py   # 显著性检验
│   ├── config/              # 配置管理
│   │   └── settings.py            # 系统配置
│   ├── data_gateway/        # 数据网关
│   │   ├── akshare_provider.py    # AkShare 数据源
│   │   ├── aktools_provider.py    # AkTools 数据源
│   │   ├── base.py                # 数据源基类
│   │   ├── column_mapper.py       # 列名映射
│   │   ├── realtime_health.py     # 实时健康检查
│   │   └── realtime_provider.py   # 实时行情
│   ├── execution_engine/    # 执行引擎
│   │   ├── broker_adapter.py      # 券商适配器
│   │   ├── execution_service.py   # 执行服务
│   │   ├── order_checker.py       # 订单检查器
│   │   └── trade_recorder.py      # 成交记录
│   ├── factor_engine/       # 因子引擎
│   │   ├── factor_evaluation.py   # 因子评估
│   │   ├── fundamental_factors.py # 基本面因子
│   │   ├── sentiment_factors.py   # 情绪因子
│   │   ├── technical_factors.py   # 技术因子
│   │   └── theme_factors.py       # 主题因子
│   ├── models/              # 数据模型
│   │   └── schemas.py             # Pydantic 模型定义
│   ├── risk_engine/         # 风控引擎
│   │   ├── models.py              # 风控模型
│   │   └── runtime.py             # 运行时风控
│   ├── stock_pool/          # 股票池
│   │   ├── mainboard_filter.py    # 主板过滤
│   │   └── semiconductor.py       # 半导体池
│   ├── strategy_engine/     # 策略引擎
│   │   ├── portfolio_model.py     # 组合模型
│   │   ├── scoring_model.py       # 评分模型
│   │   ├── sector_rotation.py     # 板块轮动
│   │   ├── signal_generator.py    # 信号生成
│   │   └── timing_model.py        # 择时模型
│   ├── ui_report/           # 可视化面板
│   │   └── dashboard.py           # Streamlit 面板
│   └── utils/               # 工具函数
│       ├── calendar.py            # 交易日历
│       ├── quality.py             # 数据质量
│       └── storage.py             # 数据存储
├── tests/                   # 测试
├── .env.example             # 环境变量模板
├── pyproject.toml           # 项目配置
└── .gitignore               # Git 忽略规则
```

---

> **免责声明：** 本系统仅供量化策略研究与模拟交易使用，不构成任何投资建议。系统默认不启用实盘交易，所有交易功能需用户主动配置。使用实盘交易功能前，请充分了解相关风险并确保合规。
