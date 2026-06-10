# Self Test Checklist

> 本文档是 Developer Agent 的自测硬约束。任何代码、配置、前端、API、数据、交易逻辑变更，在交给测试工程师或架构师之前，必须按本文档完成自测，并在开发报告中记录命令、结果和未覆盖风险。

---

## 1. 基本原则

1. 自测失败不得提交为“完成”。
2. 不得删除失败测试来制造通过。
3. 不得用 mock 成功替代真实应验证的 API / UI / 浏览器 smoke。
4. 不得静默忽略 skipped、xfail、warning、外部服务失败。
5. 不得把 Demo fallback 说成真实数据。
6. 不得把 paper trading 说成实盘交易。
7. 核心交易逻辑、风控、执行、回测、数据契约变更必须有测试。
8. 每次自测必须说明：
   - 触碰范围
   - 执行命令
   - 结果
   - 未执行项及原因
   - 剩余风险

---

## 2. 自测分级

Developer Agent 必须先判断本次变更级别。若多个级别同时命中，执行最高级别以及所有相关专项检查。

| 级别 | 触碰范围 | 最低自测要求 |
|---|---|---|
| L0 文档轻改 | 仅 README、日志、注释、无行为变化文档 | Markdown 链接/路径检查、拼写和引用自查 |
| L1 普通代码 | 工具函数、非交易业务逻辑、非核心服务 | 相关 pytest + ruff + py_compile |
| L2 API / 配置 / 后台服务 | FastAPI、配置中心、ServiceManager、反馈系统 | L1 + API smoke + 配置安全检查 |
| L3 前端 / 产品入口 | Streamlit、用户工作流、页面交互 | L2 + Streamlit smoke + 浏览器渲染检查 |
| L4 数据 / 因子 / 回测 | data_gateway、factor_engine、backtest_engine、strategy_engine | L1 + 数据契约专项 + 回测/因子专项 |
| L5 风控 / 执行 / 订单 | risk_engine、execution_engine、真实/模拟订单路径 | L1 + 风控执行专项 + 负向测试 + 人工确认验证 |
| L6 自动修复 / Agent 修改代码 | bug_fix_agent、bug_fix_workflow、自动 patch | L2 + 审批状态机 + 受限模块阻断 + 回滚验证 |

---

## 3. 通用自测步骤

### Step 1: 工作区检查

```bash
git status --short --branch
git diff --stat
```

通过标准：

- 工作区只包含本次任务相关文件。
- 没有无意生成的日志、缓存、截图、PID 文件被暂存。
- 不得回滚用户或其他 Agent 的无关修改。

### Step 2: 静态检查

对本次触碰的 Python 文件运行：

```bash
.venv\Scripts\python.exe -m ruff check <touched-python-files-and-tests>
.venv\Scripts\python.exe -m py_compile <touched-src-python-files>
```

若项目环境不是 Windows，等价命令为：

```bash
python -m ruff check <touched-python-files-and-tests>
python -m py_compile <touched-src-python-files>
```

通过标准：

- ruff 无错误。
- py_compile 无错误。
- 若存在项目既有 lint 问题，本次报告必须说明“只对 touched scope 运行”，不得声称全量 ruff 通过。

### Step 3: 相关测试

```bash
.venv\Scripts\python.exe -m pytest <related-test-files> -q --basetemp=runtime\pytest-tmp
```

通过标准：

- 相关测试全部通过。
- 新增功能必须有新增或更新测试。
- 外部 API、交易时间、网络数据源必须 mock 或使用可控 fixture。

### Step 4: 全量或阶段回归

以下任一情况必须跑更大范围回归：

- 修改公共模型、配置、数据契约、风险、执行、回测。
- 修改被多个模块导入的函数。
- 修改产品入口主流程。
- 修复测试工程师报告的阻断 Bug。

推荐命令：

```bash
.venv\Scripts\python.exe -m pytest tests -q --tb=short --basetemp=runtime\pytest-tmp
```

若全量测试存在已知历史失败，开发报告必须列出：

- 失败测试名
- 是否与本次变更相关
- 为什么不阻断
- 相关 issue 或 Bug 报告路径

### Step 5: 差异检查

```bash
git diff --check
git diff --stat
```

通过标准：

- 无 trailing whitespace 或 conflict marker。
- diff 范围符合任务。

---

## 4. 专项自测清单

### 4.1 文档变更

适用：`README.md`、`docs/`。

必须检查：

1. 新增文档路径是否被相关索引或 AGENTS 文档引用。
2. 文档中命令是否能在当前项目结构下执行。
3. 不得出现 `TODO`、`TBD`、占位章节，除非明确标为后续计划。
4. 如果修改流程规则，必须更新 `docs/log/DEVELOPMENT_LOG.md`。

推荐命令：

```bash
rg -n "TODO|TBD|待补充" docs README.md
rg -n "AGENT_DEVELOPMENT_PIPELINE|SELF_TEST_CHECKLIST" docs README.md
```

### 4.2 API 变更

适用：`src/api/`、产品 API 路由、配置端点。

必须验证：

1. 正常请求返回预期 HTTP 状态码。
2. 非法参数返回可理解错误。
3. 响应字段与文档一致。
4. 配置端点不泄露密钥。
5. 不新增绕过人工确认或风控的端点。

Smoke 示例：

```bash
.venv\Scripts\python.exe -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000
```

另开终端：

```bash
curl http://127.0.0.1:8000/product/health
curl http://127.0.0.1:8000/product/config
```

通过标准：

- HTTP 200 或预期 4xx。
- 返回 JSON。
- `ENABLE_LIVE_TRADING`、密钥、Token、密码不明文泄露。

### 4.3 Streamlit / Dashboard 变更

适用：`src/ui_report/`。

必须验证：

1. 页面能启动。
2. 所有本次修改 Tab 可打开。
3. 页面没有 `stException`。
4. 控件有稳定唯一 key 或不会产生重复 element id。
5. 用户主流程可从页面完成。
6. 交易相关 UI 不提供批量确认买入，不默认暴露 LEVEL_3 自动交易。

Smoke 示例：

```bash
.venv\Scripts\python.exe -m streamlit run src\ui_report\product_dashboard.py --server.address 127.0.0.1 --server.port 8771 --server.headless true
```

HTTP 检查：

```bash
curl http://127.0.0.1:8771
```

浏览器检查必须覆盖：

- 页面标题或主入口可见。
- 修改的 Tab 可见。
- 修改的按钮、输入框、表格可见。
- 控件点击后无前端异常。

### 4.4 数据源 / 行情变更

适用：`src/data_gateway/`、实时行情、AkShare、AkTools。

必须验证：

1. `symbol` 规范化正确。
2. A 股、港股、港股通市场标识正确。
3. 内部 `volume` 单位为股；若数据源返回手，必须转换并记录 `source_volume_unit`。
4. 保留或明确区分 raw price 与 adjusted price。
5. 返回 `currency`、`timezone`、`data_source`、`updated_at`、`data_version`。
6. 数据源异常时默认不允许真实交易，并生成可追踪反馈。
7. Demo fallback 必须显式标注。

推荐命令：

```bash
.venv\Scripts\python.exe -m pytest tests/test_realtime_provider.py tests/test_product_market_data.py tests/test_product_realtime_api.py -q --basetemp=runtime\pytest-tmp
```

### 4.5 因子 / 策略变更

适用：`src/factor_engine/`、`src/strategy_engine/`。

必须验证：

1. 因子命名符合 `FACTOR_RESEARCH_GUIDE.md`。
2. Alpha、Risk、Theme、Timing 因子类型明确。
3. LLM 不直接输出数值因子，只能输出结构化标签，再由规则映射。
4. 无未来函数。
5. 信号包含解释、风险提示、止损/止盈或不适用原因。
6. 股票池过滤器不可绕过。

推荐命令：

```bash
.venv\Scripts\python.exe -m pytest tests/test_phase2.py tests/test_audit_phase2.py -q --basetemp=runtime\pytest-tmp
```

### 4.6 回测变更

适用：`src/backtest_engine/`。

必须验证：

1. 手续费、滑点、印花税。
2. 涨跌停无法成交。
3. 停牌无法成交。
4. 样本外测试。
5. 不同市场环境测试。
6. 指标完整：年化收益、最大回撤、Sharpe、Calmar、胜率、盈亏比、换手、超额收益。

推荐命令：

```bash
.venv\Scripts\python.exe -m pytest tests/test_phase3.py tests/test_audit_phase3.py -q --basetemp=runtime\pytest-tmp
```

### 4.7 风控 / 执行 / 订单变更

适用：`src/risk_engine/`、`src/execution_engine/`、订单 API。

必须验证：

1. Risk Agent 一票否决。
2. 默认不真实自动下单。
3. 非交易时间禁止真实委托，但允许信号和订单草稿。
4. A 股默认 LIMIT，不默认 MARKET。
5. 订单超时状态：`PENDING_ACK`、告警、暂停新订单。
6. 不允许买创业板、科创板、ST、退市整理股。
7. 不允许批量确认买入订单。
8. 所有真实订单可追溯。

推荐命令：

```bash
.venv\Scripts\python.exe -m pytest tests/test_phase4_risk_engine.py tests/test_phase5_order_checker.py tests/test_phase5_execution.py tests/test_phase5_e2e.py -q --basetemp=runtime\pytest-tmp
```

### 4.8 Bug 自动处理变更

适用：`src/product_app/bug_fix_agent.py`、`bug_fix_workflow.py`、`bug_watchdog.py`。

必须验证：

1. 修复方案必须人工审批。
2. `risk_engine`、`execution_engine`、交易日志、回测报告核心逻辑受限。
3. 测试失败自动回滚。
4. DeepSeek / OpenAI API Key 只来自环境变量。
5. 自动修复只运行相关测试时，不得漏掉核心安全测试。
6. `bug_fix_agent` 常驻监听作业启动后必须保持 `RUNNING`，停止后必须释放 watchdog。
7. 自动修复执行前必须校验 Git 工作区干净，禁止覆盖用户或其他 Agent 未提交修改。
8. git add / commit / rev-parse 失败时必须进入 `fix_failed`，不得标记为 `fixed`。
9. 分析 API 必须返回 `analysis_report`、`fix_proposal`、`fix_result` 和审批信息，不能只返回状态。
10. Watchdog 只能自动分析 `status=open` 的 Bug。

推荐命令：

```bash
.venv\Scripts\python.exe -m pytest tests/test_bug_auto_fix.py -q --basetemp=runtime\pytest-tmp
```

---

## 5. 开发报告自测模板

Developer Agent 必须在 `docs/dev_reports/` 中记录：

```markdown
# <Feature> Development Report

## Scope

- Requirements: `docs/requirements/...`
- Architecture: `docs/design/...`
- Changed files:
  - `src/...`
  - `tests/...`

## Self Test Level

- Level: L3 Frontend / API / Service
- Reason: touched `src/ui_report`, `src/api`, `src/product_app`

## Commands

| Command | Result |
|---|---|
| `.venv\Scripts\python.exe -m ruff check ...` | PASS |
| `.venv\Scripts\python.exe -m pytest ...` | PASS |
| API smoke | PASS |
| Browser smoke | PASS |

## Skipped / Not Run

- None

## Safety Confirmation

- Default live trading remains disabled.
- Risk Agent veto was not bypassed.
- No secrets committed.
- No batch buy confirmation introduced.

## Residual Risk

- ...
```

---

## 6. 失败处理

若任一自测失败：

1. 停止提交。
2. 记录失败命令和错误摘要。
3. 判断是否为本次变更引入。
4. 本次引入则修复并重新运行相关测试。
5. 非本次引入则创建或引用 Bug 报告，并说明为何不阻断。
6. 对核心交易安全相关失败，不允许以“历史问题”放行。

---

## 7. 提交前最终清单

提交前必须逐项确认：

- [ ] 已阅读需求文档和架构文档。
- [ ] 已按触碰范围选择自测级别。
- [ ] 新功能有测试。
- [ ] 相关测试通过。
- [ ] 静态检查通过。
- [ ] API / UI / 浏览器 smoke 已按需执行。
- [ ] 没有密钥、Token、Cookie、券商账号。
- [ ] 没有绕过 Risk Agent。
- [ ] 没有启用默认真实自动下单。
- [ ] 文档和开发日志已更新。
- [ ] `git diff --check` 通过。
- [ ] 工作区只包含本次任务相关文件。
