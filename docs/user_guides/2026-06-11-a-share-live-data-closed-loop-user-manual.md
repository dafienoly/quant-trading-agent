# A股主板实盘数据闭环体验手册

> 面向用户：Owner / Trader / Research 用户  
> 适用功能：A股主板实盘数据盯盘、主题池、因子、回测、信号草稿、数据源诊断  
> 当前状态：产品入口和安全闭环可体验；真实行情成功刷新仍需在 A股交易时段、网络可访问 provider 的环境中验证。

---

## 1. 你可以用这个功能做什么

本功能的目标是让你在一个产品入口里完成 A股主板真实数据闭环：

1. 查看数据源是否可用。
2. 管理自选池。
3. 使用内置 AI算力/半导体主题池。
4. 获取实时行情并盯盘。
5. 基于真实数据计算因子。
6. 基于真实历史数据运行回测。
7. 在数据健康和风控检查后生成信号草稿。
8. 当数据源异常时自动生成 feedback bug，方便开发持续修复。

本功能不会默认真实下单，也不会启用自动交易。

---

## 2. 使用前必须知道的边界

### 2.1 不会真实自动下单

系统默认只允许信号模式或人工确认流程。`LEVEL_3_AUTO` 自动交易模式不会作为普通入口开放。

### 2.2 Demo 不等于实盘

本功能的 live closed-loop 不允许用 demo 数据冒充真实行情。看到 `is_demo=false` 才表示当前结果没有使用 demo fallback。

### 2.3 数据失败会阻断信号

如果所有真实数据源都失败，系统会显示 `data_status=FAILED`，并阻断信号草稿和真实交易路径。这是安全设计，不是按钮坏了。

### 2.4 当前验收限制

截至本手册生成时，本功能已经能够：

- 启动产品网页。
- 展示内置 AI算力/半导体主题池。
- 诊断 provider。
- 在真实数据失败时 fail-closed。
- 生成 feedback bug。

但本轮 PM 验收尚未通过，因为官方 10 只股票实时行情 smoke 在非交易时段返回 `0/10` 成功。最终验收仍需要在 A股交易时段拿到至少 10 只主板股票的非 demo 实时行情。

---

## 3. 启动方式

### 3.0 必要环境变量

复制 `.env.example` 为 `.env` 后，至少确认以下配置：

```text
AKTOOLS_BASE_URL=http://127.0.0.1:8080
DEEPSEEK_API_KEY=你的 DeepSeek Key
DEEPSEEK_API_BASE=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
LIVE_DATA_PROVIDER_ORDER=eastmoney,akshare,aktools
ENABLE_DEMO_FALLBACK_FOR_LIVE_LOOP=false
DATA_FAIL_CLOSED=true
```

`AKTOOLS_BASE_URL` 只告诉本项目去哪里访问 AkTools；它不会自动启动 AkTools 本地 HTTP 服务。`DEEPSEEK_API_KEY` 用于 feedback Bug 自动分析和修复方案生成；没有该 key 时，BugFix Agent 会拒绝启动，Open Bug 不会进入分析流程。

### 3.1 Windows PowerShell

启动 AkTools 本地 HTTP 服务：

```powershell
.\.venv\Scripts\python.exe -m aktools --host 127.0.0.1 --port 8080
```

验证 AkTools：

```powershell
curl http://127.0.0.1:8080/version
curl "http://127.0.0.1:8080/api/public/stock_zh_a_spot_em"
```

启动产品 Dashboard：

```powershell
.\.venv\Scripts\python.exe -m streamlit run src\ui_report\product_dashboard.py --server.address 127.0.0.1 --server.port 8771 --server.headless true
```

打开：

```text
http://127.0.0.1:8771
```

启动 API：

```powershell
.\.venv\Scripts\python.exe -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000
```

API 健康检查：

```powershell
curl http://127.0.0.1:8000/product/health
```

### 3.2 WSL / Linux — 一键启动（推荐）

默认启动 AkTools + FastAPI + Streamlit：

```bash
bash scripts/start.sh
```

全量启动（含 BugFixAgent，需要 `DEEPSEEK_API_KEY`）：

```bash
export DEEPSEEK_API_KEY="your_key"
bash scripts/start.sh --full
```

仅启动 API 和 Dashboard（不启动 AkTools）：

```bash
bash scripts/start.sh --no-aktools
```

Dry-run 预览：

```bash
bash scripts/start.sh --dry-run
bash scripts/start.sh --dry-run --no-aktools
bash scripts/start.sh --dry-run --full
```

验证服务：

```bash
curl http://127.0.0.1:8000/product/health
curl http://127.0.0.1:8080/version
curl http://127.0.0.1:8000/product/runtime/services
```

停止服务：

```bash
bash scripts/stop.sh
```

> **AkShare 不是独立服务。** AkShare 是 Python 包，由 FastAPI 内部的数据提供者按需导入，不应作为守护进程启动。AkTools 兼容服务（`src/integrations/aktools_compat_app.py`）通过 `scripts/start_product.py` 自动管理。

### 3.3 WSL / Linux — 手动启动（排查用）

个别排查场景下可手动启动某个服务：

```bash
# AkTools（仅在需要单独调试时）
./.venv/bin/python -m uvicorn src.integrations.aktools_compat_app:app --host 127.0.0.1 --port 8080

# Streamlit Dashboard
./.venv/bin/python -m streamlit run src/ui_report/product_dashboard.py --server.address 127.0.0.1 --server.port 8771 --server.headless true

# FastAPI
./.venv/bin/python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000

# 验证
curl http://127.0.0.1:8000/product/health
```

### 3.4 WSL 与 Windows 混合运行

如果 API 在 WSL 中运行，AkTools 也建议在同一个 WSL 环境启动，并保持：

```text
AKTOOLS_BASE_URL=http://127.0.0.1:8080
```

如果 AkTools 跑在 Windows、API 跑在 WSL，则 WSL 内的 `127.0.0.1` 指向 WSL 自己，不是 Windows。此时应把 `.env` 改成 Windows Host 地址，例如：

```bash
AKTOOLS_BASE_URL=http://$(grep nameserver /etc/resolv.conf | awk '{print $2}'):8080
```

更稳定的做法是让 AkTools 监听 `0.0.0.0`：

```powershell
.\.venv\Scripts\python.exe -m aktools --host 0.0.0.0 --port 8080
```

然后在 WSL 的 `.env` 中使用 Windows Host IP。

---

## 4. 推荐体验流程

### Step 1：进入产品网页

打开 Dashboard 后，先确认页面能够正常加载，没有明显异常或报错。

如果页面无法打开：

1. 确认虚拟环境是否存在。
2. 确认端口 `8771` 是否被占用。
3. 查看终端日志。

### Step 2：查看数据源状态

进入数据源或 Live Data 相关页面，查看系统当前配置的数据源。

默认 provider 顺序通常是：

```text
eastmoney -> akshare -> aktools
```

你需要重点看：

- provider 是否可用。
- 是否有错误信息。
- 当前选择了哪个 provider。
- fallback chain 是否记录了切源过程。
- 是否生成 feedback bug。

对应 API：

```powershell
curl http://127.0.0.1:8000/product/live-data/providers
```

诊断接口：

```powershell
curl -X POST "http://127.0.0.1:8000/product/live-data/diagnose?symbols=600000.SH,000001.SZ"
```

### Step 3：查看股票池

先查看内置主题池是否可用：

```powershell
curl http://127.0.0.1:8000/product/pools
curl http://127.0.0.1:8000/product/pools/ai_semiconductor
```

你应该看到：

- `ai_semiconductor` 主题池。
- 100-300 只 A股主板股票。
- 标签包括 `ai_chip`、`optical_module` 等。

当前内置主题池为 AI算力/半导体方向，覆盖 AI芯片、先进封装、设备材料、存储、HBM、光模块、PCB、EDA/IP 等标签。

### Step 4：验证实时行情

在 A股交易时段运行官方 smoke：

```powershell
.\.venv\Scripts\python.exe scripts\smoke_live_quotes.py --symbols 600000.SH,000001.SZ,600584.SH,002463.SZ,603986.SH,601138.SH,000021.SZ,600703.SH,603228.SH,002371.SZ --min-success 10 --output docs\test_reports\live-quote-smoke-user.json
```

WSL / Linux：

```bash
./.venv/bin/python scripts/smoke_live_quotes.py --symbols 600000.SH,000001.SZ,600584.SH,002463.SZ,603986.SH,601138.SH,000021.SZ,600703.SH,603228.SH,002371.SZ --min-success 10 --output docs/test_reports/live-quote-smoke-user.json
```

通过标准：

- exit code 为 `0`。
- JSON 中 `status="passed"`。
- `symbols_succeeded >= 10`。
- `is_demo=false`。
- `provider` 非空。
- `updated_at_min` / `updated_at_max` 有值。

如果失败但 `is_demo=false`、`data_status=FAILED`、有 `fallback_chain` 和 `feedback_bug_id`，说明系统安全地阻断了错误数据。

### Step 5：体验因子计算

在网页中进入因子或 Factor 页面，选择自选池或主题池，触发计算。

你需要关注：

- 使用的数据源。
- 数据是否真实。
- 数据缺失报告。
- 因子结果是否为空。
- 若失败，是否显示原因。

如果实时行情、日线或财务数据失败，因子计算可能返回 `status=failed` 或被阻断。这是正常安全行为。

### Step 6：体验回测

进入回测页面，选择股票池和时间区间，运行快速回测。

你需要关注：

- 是否使用真实日线。
- 是否显示手续费、滑点、印花税等成本。
- 是否提示停牌、涨跌停、幸存者偏差风险。
- 数据失败时是否停止回测。

如果日线数据源不可用，回测应失败或阻断，而不是自动用 demo 数据补上。

### Step 7：体验信号草稿

进入信号页面，选择股票池和交易模式。

推荐先使用：

```text
LEVEL_1_SIGNAL_ONLY
```

你需要关注：

- 数据健康状态。
- 风控是否通过。
- 信号解释。
- 是否生成订单草稿。
- 如果数据失败，是否 `blocked`。

如果选择 `LEVEL_3_AUTO`，系统应拒绝。

---

## 5. 常见状态说明

| 状态 | 含义 | 用户该怎么做 |
|---|---|---|
| `status=ok` | 请求成功完成 | 继续查看数据和结果 |
| `status=failed` | 功能失败 | 查看 `data_status`、错误信息、feedback bug |
| `status=blocked` | 被安全门禁阻断 | 检查数据源、风控、交易模式 |
| `status=rejected` | 请求不被允许 | 检查是否选择了不可用模式，如 `LEVEL_3_AUTO` |
| `data_status=OK` | 数据健康 | 可继续研究或信号流程 |
| `data_status=WARN` | 数据部分可用 | 谨慎使用，查看缺失和延迟报告 |
| `data_status=FAILED` | 数据不可用 | 不应继续生成实盘信号或订单 |
| `is_demo=false` | 没有使用 demo 数据 | live 验收要求 |
| `feedback_bug_id` | 已生成或命中 bug | 提供给开发修复 |

---

## 6. 怎么判断体验是否成功

### 最小成功体验

满足以下条件，可以认为产品入口和安全闭环体验成功：

- Dashboard 能打开。
- 主题池能显示 100-300 只股票。
- 数据源诊断能显示 provider 级结果。
- 真实数据失败时不展示 demo 数据。
- 信号草稿被阻断，订单为空。
- feedback bug 被生成。

### 完整成功体验

满足以下条件，才可以认为实盘数据闭环体验成功：

- 交易时段 10 只 A股主板股票实时行情 smoke 通过。
- 因子计算基于真实数据返回结果。
- 回测基于真实日线返回结果。
- 信号草稿基于真实数据健康检查和风控生成。
- 全流程 `is_demo=false`。

---

## 7. 当前已知限制

1. 免费公开数据源可能不稳定，尤其是 AkShare、AkTools、Eastmoney 直连接口。
2. 非 A股交易时段无法证明实时行情刷新能力。
3. AkTools 需要本地服务可用，否则会连接失败。
4. 搜索增强需要配置 Tavily / AnySearch / Firecrawl API Key。
5. 数据源全部失败时，因子、回测、信号会被阻断，这是预期安全行为。

---

## 8. 排障建议

### 8.1 页面打不开

检查：

- 虚拟环境是否存在。
- `streamlit` 是否安装。
- 端口是否被占用。
- 终端是否有 Python import error。

### 8.2 实时行情失败

检查：

- 是否在 A股交易时段。
- 网络是否能访问 Eastmoney / AkShare。
- AkTools 本地服务是否启动。
- `.env` 中 `AKTOOLS_BASE_URL` 是否指向 API 进程能访问的地址。
- `docs/test_reports/` 下 smoke JSON 的 `fallback_chain`。
- `feedback/bugs/open/` 中对应 bug。

AkTools 相关错误通常有两类：

| 错误 | 常见原因 | 处理 |
|---|---|---|
| `Connection refused` | AkTools HTTP 服务未启动 | 先运行 `python -m aktools --host 127.0.0.1 --port 8080` |
| `ConnectTimeout` | API 进程访问不到 AkTools 地址 | 检查 WSL/Windows 网络边界和 `AKTOOLS_BASE_URL` |

项目调用路径是：

```text
Quant API -> AkToolsProvider -> AKTOOLS_BASE_URL/api/public/<akshare_function>
```

例如实时 A股行情会访问：

```text
http://127.0.0.1:8080/api/public/stock_zh_a_spot_em
```

### 8.3 主题池为空

检查文件是否存在：

```text
data/reference/theme_pools/ai_semiconductor.json
```

运行：

```powershell
.\.venv\Scripts\python.exe scripts\validate_theme_pool.py
```

应返回：

```text
VALIDATION PASSED
```

### 8.4 信号一直 blocked

通常原因：

- 实时行情失败。
- 日线数据失败。
- 财务数据失败。
- 数据延迟超阈值。
- Risk Agent 拒绝。
- 选择了不允许的交易模式。

先查看数据源诊断和 feedback bug。

### 8.5 Feedback Bug 一直 Open

Open Bug 只代表“系统已经记录了问题”，不代表自动修复 Agent 已经处理。

自动修复链路如下：

```text
open -> analyzing -> proposed -> approved -> fixing -> verified -> fixed
```

要让 Open Bug 被处理，需要满足：

1. `.env` 中配置了 `DEEPSEEK_API_KEY`。
2. API 服务正在运行。
3. Dashboard 的“反馈”页中点击“启动修复 Agent”，或调用：

```powershell
curl -X POST http://127.0.0.1:8000/product/jobs/bug_fix_agent/start
```

4. Bug 被分析后进入 `proposed`。
5. 用户在“反馈”页审批修复方案，或调用：

```powershell
curl -X POST "http://127.0.0.1:8000/product/feedback/BUG_ID/approve?comment=approved"
```

审批后系统才会尝试自动修改代码、运行测试并提交修复。涉及风控、交易、成交、回测报告等受限模块时，自动修复会被阻断，需要开发工程师按管线处理。

如果“启动修复 Agent”后显示 `DEEPSEEK_API_KEY is required before starting bug_fix_agent`，说明 `.env` 未配置 DeepSeek Key，或 API 服务启动时没有加载到该环境变量。配置后需要重启 API。

---

## 9. 安全提醒

- 不要把 `.env`、API Key、账号、券商凭证提交到仓库。
- 不要用 demo 数据做实盘决策。
- 不要绕过 Risk Agent。
- 不要绕过股票池过滤器。
- 不要在数据失败时强行生成订单。
- 当前阶段不接受真实自动交易体验。

---

## 10. 推荐给用户的验收命令

Windows：

```powershell
.\.venv\Scripts\python.exe scripts\validate_theme_pool.py
.\.venv\Scripts\python.exe scripts\smoke_live_quotes.py --symbols 600000.SH,000001.SZ,600584.SH,002463.SZ,603986.SH,601138.SH,000021.SZ,600703.SH,603228.SH,002371.SZ --min-success 10 --output docs\test_reports\live-quote-smoke-user.json
```

WSL / Linux：

```bash
./.venv/bin/python scripts/validate_theme_pool.py
./.venv/bin/python scripts/smoke_live_quotes.py --symbols 600000.SH,000001.SZ,600584.SH,002463.SZ,603986.SH,601138.SH,000021.SZ,600703.SH,603228.SH,002371.SZ --min-success 10 --output docs/test_reports/live-quote-smoke-user.json
```

最终通过标准：

```json
{
  "status": "passed",
  "symbols_succeeded": 10,
  "is_demo": false
}
```
