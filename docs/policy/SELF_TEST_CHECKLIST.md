# SELF_TEST_CHECKLIST.md — 开发完成后必须执行的自测流程

> 本文档为开发约束文档，所有开发者在完成功能开发后必须按此流程执行自测。
> 未通过自测的代码不得提交，不得进入代码审查阶段。

---

## 1. 总则

### 1.1 适用范围

- 所有涉及 `src/` 目录下代码变更的提交
- 所有涉及 `tests/` 目录下测试变更的提交
- 所有涉及配置文件（`.env`、`pyproject.toml`、Streamlit 配置等）变更的提交
- 所有涉及 API 端点新增或修改的提交
- 所有涉及 Streamlit Dashboard 面板新增或修改的提交

### 1.2 自测流程总览

```
代码变更 → Step 1 静态检查 → Step 2 单元测试 → Step 3 API 端点测试 → Step 4 功能实现检查 → Step 5 浏览器 E2E 测试 → Step 6 安全检查 → 通过后方可提交
```

任何 Step 失败，必须修复后重新从 Step 1 开始。

### 1.3 环境要求

| 工具 | 安装命令 | 用途 |
|------|---------|------|
| Python ≥ 3.11 | — | 运行时 |
| pytest | `pip install pytest` | 单元/集成测试 |
| ruff | `pip install ruff` | 静态代码检查 |
| Playwright | `pip install playwright && playwright install chromium` | 浏览器 E2E 测试 |

---

## 2. Step 1: 静态代码检查

### 2.1 ruff 检查

```bash
ruff check src/ tests/
```

**通过标准**: 零错误（warning 允许但需评估）

### 2.2 Streamlit Widget ID 冲突检查

**规则**: 同一 Streamlit 页面中，所有 `st.selectbox`、`st.text_input`、`st.checkbox`、`st.slider`、`st.number_input`、`st.date_input`、`st.multiselect`、`st.button` 等 widget 必须提供唯一 `key` 参数。

**检查方法**:

```bash
# 搜索缺少 key 的 widget 调用
grep -n "st\.selectbox\|st\.text_input\|st\.checkbox\|st\.slider\|st\.number_input\|st\.date_input\|st\.multiselect\|st\.button" src/ui_report/*.py
```

**通过标准**: 所有 widget 调用均包含 `key=` 参数，且同一文件内 key 值唯一。

### 2.3 硬编码密钥检查

```bash
# 搜索可能的硬编码密钥
grep -rn "TOKEN\s*=\s*['\"]" src/
grep -rn "API_KEY\s*=\s*['\"]" src/
grep -rn "SECRET\s*=\s*['\"]" src/
grep -rn "PASSWORD\s*=\s*['\"]" src/
```

**通过标准**: 无硬编码密钥，所有敏感配置从环境变量读取。

---

## 3. Step 2: 单元测试

### 3.1 运行完整测试套件

```bash
python -m pytest tests/ -q --tb=short
```

**通过标准**: 全部通过，0 failed。如有 skipped 需说明原因。

### 3.2 新增代码覆盖率

- 新增 Python 模块必须有对应测试文件
- 新增函数/方法必须有至少 1 个测试用例
- 新增 API 端点必须有对应测试

**检查方法**:

```bash
# 确认新增模块有对应测试
ls tests/test_*.py
```

### 3.3 测试独立性

- 所有测试必须可独立运行，不依赖执行顺序
- 不依赖外部服务（AkShare、DeepSeek API 等），使用 mock
- 不依赖特定交易时段，使用 mock `is_trading_hours()`

---

## 4. Step 3: API 端点测试

### 4.1 启动 FastAPI 服务

```bash
python -m uvicorn src.api.app:app --host 0.0.0.0 --port 8099
```

### 4.2 逐端点验证

对每个 API 端点（包括新增和修改的），验证：

| 检查项 | 要求 |
|--------|------|
| HTTP 状态码 | 200（正常）或预期的 4xx/5xx |
| 响应格式 | JSON 格式正确 |
| 必需字段 | 返回数据包含文档要求的字段 |
| 边界条件 | 空参数、非法参数返回合理错误 |

**验证脚本**:

```python
import requests

base = "http://localhost:8099"

# 健康检查
r = requests.get(f"{base}/product/health")
assert r.status_code == 200
assert r.json().get("status") in ("ok", "warn")

# Dashboard
r = requests.get(f"{base}/product/dashboard")
assert r.status_code == 200
assert "quotes" in r.json()

# 配置
r = requests.get(f"{base}/product/config")
assert r.status_code == 200
assert "config" in r.json()

# ... 对每个端点重复验证
```

**通过标准**: 所有端点返回预期状态码和数据结构。

### 4.3 安全端点验证

- `POST /product/config` 不接受 `TOKEN`/`KEY`/`SECRET`/`PASSWORD` 等敏感字段
- `POST /product/config/confirm-upgrade` 需要确认参数
- `LEVEL_3_AUTO` 配置被阻断
- 默认交易模式仍为 `LEVEL_1_SIGNAL_ONLY`

---

## 4. Step 4: 功能实现检查

> **此步骤对照需求文档和设计文档，逐个功能点验证实现是否完整、正确。** 仅通过 API 端点测试不能证明功能逻辑正确，必须从用户视角验证每个功能的行为。

### 4.1 检查原则

- **对照需求文档**: 以 `ROADMAP_AND_CONSTRAINTS.md` 各 Phase 验收标准、`AGENTS.md` 功能规则、`ARCHITECTURE.md` 模块职责为基准
- **逐功能点验证**: 每个需求条目至少有 1 个验证用例
- **从用户视角**: 验证用户可感知的行为，而非仅验证代码存在
- **正向 + 反向**: 每个功能既验证正常路径，也验证异常/边界路径

### 4.2 功能检查清单模板

对本次变更涉及的每个功能，填写以下检查表：

```markdown
### 功能: [功能名称]

**需求来源**: [文档名] §[章节号]

**需求描述**: [原文摘录或转述]

**验证用例**:

| # | 用例描述 | 输入/操作 | 预期结果 | 实际结果 | 通过 |
|---|---------|----------|---------|---------|------|
| 1 | 正常路径 | ... | ... | ... | ☐ |
| 2 | 边界条件 | ... | ... | ... | ☐ |
| 3 | 异常路径 | ... | ... | ... | ☐ |

**结论**: ☐ 功能完整实现 / ☐ 部分实现（说明缺失项）/ ☐ 未实现
```

### 4.3 各 Phase 功能检查要点

以下列出各 Phase 的核心功能检查要点，开发者应根据本次变更涉及的 Phase 选取对应检查项。

#### Phase 1: 数据层与股票池

| # | 功能点 | 需求来源 | 验证方法 |
|---|--------|---------|---------|
| 1.1 | 拉取指定股票日线数据 | ROADMAP §Phase1 验收1 | 调用数据接口，验证返回字段完整（OHLCV） |
| 1.2 | 拉取指数数据 | ROADMAP §Phase1 验收2 | 调用数据接口，验证指数代码可查询 |
| 1.3 | 生成可交易股票池 | ROADMAP §Phase1 验收3 | 验证排除 300/301/688/689/ST/停牌/低成交额 |
| 1.4 | 输出数据质量报告 | ROADMAP §Phase1 验收4 | 验证报告包含缺失率、延迟、异常值统计 |
| 1.5 | 识别停牌/ST/涨跌停 | ROADMAP §Phase1 验收5 | 验证标记正确性 |

#### Phase 2: 因子与策略评分

| # | 功能点 | 需求来源 | 验证方法 |
|---|--------|---------|---------|
| 2.1 | 4 类因子分生成 | ROADMAP §Phase2 验收1 | 验证 policy/sentiment/fundamental/trend 分值输出 |
| 2.2 | 总评分计算 | ROADMAP §Phase2 验收2 | 验证权重 0.25/0.30/0.20/0.25 |
| 2.3 | 买入/卖出/持有信号 | ROADMAP §Phase2 验收3 | 验证信号类型和触发条件 |
| 2.4 | 信号解释文本 | ROADMAP §Phase2 验收4 | 验证每个信号包含可读解释 |
| 2.5 | 信号无未来数据 | ROADMAP §Phase2 验收5 | 验证信号仅使用 T-1 及更早数据 |

#### Phase 3: 回测与评估

| # | 功能点 | 需求来源 | 验证方法 |
|---|--------|---------|---------|
| 3.1 | 回测结果可复现 | ROADMAP §Phase3 验收1 | 相同参数运行两次，结果一致 |
| 3.2 | 包含交易成本 | ROADMAP §Phase3 验收2 | 验证手续费/印花税/滑点已扣除 |
| 3.3 | 包含涨跌停限制 | ROADMAP §Phase3 验收4 | 验证涨停无法买入、跌停无法卖出 |
| 3.4 | 完整回测报告 | ROADMAP §Phase3 验收5 | 验证年化收益/最大回撤/夏普/胜率等指标 |

#### Phase 4: 实盘盯盘与信号生成

| # | 功能点 | 需求来源 | 验证方法 |
|---|--------|---------|---------|
| 4.1 | 实时行情获取 | ROADMAP §Phase4 验收1 | 验证行情数据实时更新 |
| 4.2 | 持仓盈亏监控 | ROADMAP §Phase4 验收2 | 验证持仓盈亏计算正确 |
| 4.3 | 候选股信号触发 | ROADMAP §Phase4 验收3 | 验证信号触发逻辑 |
| 4.4 | 不自动真实下单 | ROADMAP §Phase4 验收6 | 验证 LEVEL_1 模式无自动下单路径 |

#### Phase 5: 人工确认交易

| # | 功能点 | 需求来源 | 验证方法 |
|---|--------|---------|---------|
| 5.1 | 未确认不能下单 | ROADMAP §Phase5 验收1 | 验证订单草稿需人工确认后才执行 |
| 5.2 | 风控不通过不能下单 | ROADMAP §Phase5 验收2 | 验证风控拒绝时订单被阻止 |
| 5.3 | 非交易时间不能下单 | ROADMAP §Phase5 验收4 | 验证非交易时段下单被拒绝 |
| 5.4 | 所有订单有日志 | ROADMAP §Phase5 验收5 | 验证订单生命周期有完整记录 |

#### Phase 5.5: 产品化交付

| # | 功能点 | 需求来源 | 验证方法 |
|---|--------|---------|---------|
| 5.5.1 | 一键环境检查 | ROADMAP §Phase5.5 验收1 | 运行 bootstrap.py，验证 5 项检查 |
| 5.5.2 | 一键启动 | ROADMAP §Phase5.5 验收2 | 运行 start_product.py，验证 API+Dashboard 启动 |
| 5.5.3 | 统一产品入口 | ROADMAP §Phase5.5 验收3 | 浏览器打开 Dashboard，验证 9 Tab 可访问 |
| 5.5.4 | 配置中心可查看修改 | ROADMAP §Phase5.5 验收4 | 验证配置读取/修改/恢复默认 |
| 5.5.5 | 完整使用流程可跑通 | ROADMAP §Phase5.5 验收5 | 行情→因子→回测→信号→订单确认全流程 |
| 5.5.6 | 自动 BUG 报告 | ROADMAP §Phase5.5 验收6 | 触发异常，验证 feedback/bugs/open/ 生成报告 |
| 5.5.7 | 默认不启用真实交易 | ROADMAP §Phase5.5 验收7 | 验证 LEVEL_3 阻断、BROKER_ADAPTER=paper |

#### Phase 5.6: BUG 自动处理

| # | 功能点 | 需求来源 | 验证方法 |
|---|--------|---------|---------|
| 5.6.1 | Bug 自动分析 | ROADMAP §Phase5.6 验收1 | 创建 Bug，验证 Watchdog 自动触发分析 |
| 5.6.2 | 修复方案需人工审批 | ROADMAP §Phase5.6 验收2 | 验证 proposed 状态下才能 approve/reject |
| 5.6.3 | 修复后自动 pytest | ROADMAP §Phase5.6 验收3 | 验证 execute_fix 调用 _run_tests |
| 5.6.4 | 修复失败自动回滚 | ROADMAP §Phase5.6 验收4 | 验证测试失败时原始文件恢复 |
| 5.6.5 | 禁止修改风控/日志/回测模块 | ROADMAP §Phase5.6 验收5 | 验证 _is_blocked_module 拦截 |

### 4.4 AGENTS.md 规则合规性检查

对照 `AGENTS.md` 中的 Agent 规则，验证本次变更是否遵守：

| # | AGENTS.md 规则 | 验证方法 |
|---|---------------|---------|
| 1 | 不允许直接跳过验证 | 新增功能有对应测试 |
| 2 | 不允许默认自动下单 | 默认交易模式未变更 |
| 3 | 风控第一 | 风控模块未被绕过 |
| 4 | 数据约束 | 无未来数据、无静默填充 |
| 5 | LLM 输出结构化 | LLM 输出落到 summary/evidence/confidence/risk/suggestion 字段 |
| 6 | BugFix Agent 约束 | 修复需审批、受限模块拦截、pytest 验证 |

### 4.5 功能回归检查

每次变更后，验证未修改的功能仍正常工作：

```bash
# 运行完整测试套件（已在 Step 2 执行，此处关注功能级回归）
python -m pytest tests/ -q --tb=short

# 启动服务，手动验证核心功能流程
# 1. 行情数据可获取
# 2. 信号可生成
# 3. 订单草稿可创建
# 4. 风控检查正常
# 5. 配置可读取
```

---

## 5. Step 5: 浏览器端到端测试（Playwright）

> **此步骤为强制要求，不得跳过。** Phase 5.6 审计发现用户打开网页即报错但自测未发现的问题，根因是缺乏浏览器端到端测试。

### 5.1 前置条件

```bash
# 安装 Playwright（如未安装）
pip install playwright
playwright install chromium
```

### 5.2 启动服务

```bash
# 终端 1: FastAPI
python -m uvicorn src.api.app:app --host 0.0.0.0 --port 8099

# 终端 2: Streamlit
python -m streamlit run src/ui_report/product_dashboard.py --server.port 8502 --server.headless true
```

### 5.3 运行浏览器 E2E 测试

```bash
python tests/test_browser_e2e.py
```

### 5.4 浏览器 E2E 测试必须覆盖的检查项

| # | 检查项 | 说明 |
|---|--------|------|
| 1 | Streamlit 健康检查 | `GET /_stcore/health` 返回 `ok` |
| 2 | 页面加载无崩溃 | 无 `StreamlitDuplicateElementId` 异常 |
| 3 | 无 Streamlit 异常元素 | 页面无 `[data-testid="stException"]` 元素 |
| 4 | 所有 Tab 可点击 | 每个 Tab 点击后无异常 |
| 5 | 页面内容非空 | 页面渲染了实际内容 |

### 5.5 手动浏览器验证（补充）

在 Playwright 自动测试之外，开发者还需手动打开浏览器验证：

1. 打开 `http://localhost:8502`
2. 确认页面正常加载，无红色错误提示
3. 逐个点击每个 Tab，确认无报错
4. 在"配置中心" Tab 确认默认交易模式为 `LEVEL_1_SIGNAL_ONLY`
5. 在"订单确认" Tab 确认无自动下单入口

### 5.6 截图存档

每次自测必须保存浏览器截图至 `runtime/` 目录：

```bash
# Playwright 自动保存
runtime/dashboard_test.png
runtime/dashboard_final.png
```

---

## 6. Step 6: 安全检查

### 6.1 交易安全

| 检查项 | 要求 |
|--------|------|
| 默认交易模式 | `LEVEL_1_SIGNAL_ONLY` |
| 实盘交易开关 | `ENABLE_LIVE_TRADING=false` |
| 人工确认 | `REQUIRE_HUMAN_CONFIRMATION=true` |
| 券商适配器 | `BROKER_ADAPTER=paper` |
| LEVEL_3 阻断 | 配置中心不提供 LEVEL_3_AUTO 入口 |

### 6.2 风控完整性

| 检查项 | 要求 |
|--------|------|
| Kill Switch 可用 | `/product/health` 中 `kill_switch.active=false` |
| 风控模块未被修改 | `risk_engine/` 目录无未授权变更 |
| 执行引擎未被修改 | `execution_engine/` 目录无未授权变更 |

### 6.3 数据安全

| 检查项 | 要求 |
|--------|------|
| 无硬编码密钥 | `.env` 不在 git 跟踪中 |
| Bug 报告脱敏 | `feedback/bugs/` 中无明文密钥 |
| 配置掩码 | `/product/config` 返回的敏感字段已掩码 |

---

## 7. 自测结果记录

### 7.1 自测报告模板

每次自测完成后，在 `docs/audit/` 目录下记录自测结果：

```markdown
# 自测报告 — [日期] — [功能描述]

## 自测环境
- Python 版本:
- 操作系统:
- 交易时段: (交易中/非交易时段)

## Step 1: 静态检查
- [ ] ruff check: 通过/失败
- [ ] Widget ID 冲突: 通过/失败
- [ ] 硬编码密钥: 通过/失败

## Step 2: 单元测试
- [ ] pytest: ___ passed, ___ failed, ___ skipped
- [ ] 新增代码有对应测试: 是/否

## Step 3: API 端点测试
- [ ] 所有端点 200 OK: 是/否
- [ ] 安全端点验证: 通过/失败

## Step 4: 功能实现检查
- [ ] 对照需求文档逐功能验证: ___/___ 功能通过
- [ ] AGENTS.md 规则合规: 通过/失败
- [ ] 功能回归检查: 通过/失败
- [ ] 功能检查清单已填写: 是/否

## Step 5: 浏览器 E2E 测试
- [ ] Playwright 测试: ___/___ PASS
- [ ] 手动浏览器验证: 通过/失败
- [ ] 截图已保存: 是/否

## Step 6: 安全检查
- [ ] 交易安全: 通过/失败
- [ ] 风控完整性: 通过/失败
- [ ] 数据安全: 通过/失败

## 结论
- [ ] 可以提交
- [ ] 需修复后重测
```

### 7.2 提交前确认

在 `git commit` 前，确认：

```
□ Step 1-6 全部通过
□ 功能检查清单已填写（对照需求文档逐功能验证）
□ 自测报告已填写
□ 浏览器截图已保存
□ 无硬编码密钥
□ 默认安全配置未变更
```

---

## 8. 常见问题

### Q1: Playwright 安装失败（网络问题）

```bash
# 使用镜像
set PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright
playwright install chromium
```

### Q2: 非交易时段如何测试行情相关功能

使用 Demo 模式（默认在非交易时段自动启用）：

```bash
set DEMO_MODE=true
```

### Q3: 端口被占用

```bash
# 检查端口占用
netstat -ano | findstr :8099
netstat -ano | findstr :8502

# 使用其他端口
python -m uvicorn src.api.app:app --port 8098
python -m streamlit run src/ui_report/product_dashboard.py --server.port 8503
```

### Q4: Streamlit 首次加载慢

Streamlit 首次加载需要 10-20 秒，Playwright 测试中需设置足够等待时间（建议 15-20 秒）。

---

## 9. 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| 1.1 | 2026-06-10 | 新增 Step 4 功能实现检查，对照需求文档逐功能验证 |
| 1.0 | 2026-06-10 | 初始版本，基于 Phase 5.6 审计教训建立 |
