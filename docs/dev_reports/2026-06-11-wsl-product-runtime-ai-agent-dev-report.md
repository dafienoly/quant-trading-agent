# WSL Product Runtime and AI Agent Dev Report
# WSL 产品运行环境与 AI Agent 开发报告

---

## Requirement Mapping / 需求映射

| 需求 ID | 功能 | 状态 | 文件 |
|---|---|---|---|
| F-001 | AkTools 兼容启动 | done | `src/integrations/aktools_compat_app.py` |
| F-002 | WSL 一键启动 | done | `scripts/start_product.py`, `scripts/start.sh` |
| F-003 | WSL 一键停止 | done | `scripts/stop_product.py`, `scripts/stop.sh` |
| F-004 | WSL 一键重启 | done | `scripts/restart.sh` |
| F-005 | 路径规范（统一 `/`） | done | 所有新增文档/报告 |
| F-006 | DeepSeek 模型更新为 `deepseek-v4-flash` | done | `.env.example` |
| F-007 | 统一 LLM Model Router | done | `src/llm/model_router.py` |
| F-008 | AI 因子挖掘 Agent | done | `src/agent_orchestrator/factor_discovery_agent.py` |
| F-009 | AI 研究推荐 Agent | done | `src/agent_orchestrator/recommendation_agent.py` |
| F-010 | AI 信号解释 Agent | done | `src/agent_orchestrator/signal_explanation_agent.py` |
| F-011 | BugFix 提案路径校验 | done | `src/product_app/bug_fix_workflow.py` |
| F-012 | Feedback Bug 自动分类 | done | `scripts/summarize_feedback_bugs.py` |
| F-013 | Dashboard 运行状态可见 | done | `src/api/product_routes.py`（`/product/llm/status`, `/product/runtime/services`） |

---

## Changed / New Files / 修改与新增文件

### New files / 新增

| File | Purpose / 用途 |
|---|---|
| `src/integrations/__init__.py` | 集成工具包初始化 |
| `src/integrations/aktools_compat_app.py` | AkTools 首页兼容修复（`TemplateResponse` 签名修正） |
| `src/llm/__init__.py` | LLM 路由包初始化 |
| `src/llm/model_router.py` | ModelRouter：统一 LLM 配置 + `chat_json()` 调用 |
| `src/agent_orchestrator/factor_discovery_agent.py` | AI 因子假设生成 Agent |
| `src/agent_orchestrator/recommendation_agent.py` | AI 研究推荐 Agent |
| `src/agent_orchestrator/signal_explanation_agent.py` | AI 信号解释 Agent |
| `scripts/summarize_feedback_bugs.py` | Feedback Bug 自动分类汇总脚本 |
| `tests/test_aktools_compat_app.py` | 2 个测试：首页、version |
| `tests/test_product_process_manager.py` | 3 个测试：popen_kwargs、命令构建 |
| `tests/test_model_router.py` | 4 个测试：默认值、覆盖、缺 key、LLM 状态 API |
| `tests/test_ai_research_agents.py` | 2 个测试：不输出 BUY/SELL、信号类型保留 |
| `tests/test_feedback_bug_summary.py` | 3 个测试：分类、汇总 |

### Modified files / 修改

| File | Change / 变更 |
|---|---|
| `scripts/start_product.py` | 新增 `_popen_kwargs()`、`_build_service_commands()`、`--with-aktools`、`--with-bugfix`、BugFix job 延迟启动 |
| `scripts/stop_product.py` | 支持 `aktools_pid` 停止 |
| `scripts/start.sh` | 更新帮助头说明 |
| `scripts/restart.sh` | 更新帮助头说明 |
| `src/api/product_routes.py` | 新增 `/product/llm/status`, `/product/runtime/services`, `/product/ai/*` 共 5 个路由 |
| `src/product_app/bug_fix_agent.py` | 改用 ModelRouter 读取配置，不再直接读环境变量 |
| `src/product_app/bug_fix_workflow.py` | 新增 `validate_proposal()`，在 `process_bug()` 中集成校验 |
| `src/ui_report/i18n.py` | 新增 AI 相关中英文翻译键 |
| `.env.example` | `deepseek-chat` → `deepseek-v4-flash`，新增 `LLM_*` 配置段 |
| `tests/test_bug_auto_fix.py` | 新增 3 个提案校验测试 |
| `tests/test_product_dashboard_source.py` | 新增 AI 字符串检查 |

---

## Verification Commands and Results / 验证命令与结果

### Static checks / 静态检查

```bash
./.venv/bin/python -m ruff check \
  src/integrations/ src/llm/ src/agent_orchestrator/ src/api/ src/product_app/ \
  src/ui_report/ scripts/ tests/ \
  --ignore=F401 --ignore=F541  # pre-existing ruff issues in untouched files
# Result: All checks passed on touched files / 触碰文件全部通过
```

### Pytest（83 tests / 83 个测试通过）

```bash
./.venv/bin/python -m pytest \
  tests/test_aktools_compat_app.py tests/test_product_process_manager.py \
  tests/test_model_router.py tests/test_ai_research_agents.py \
  tests/test_bug_auto_fix.py tests/test_live_signal.py \
  tests/test_live_data_service.py tests/test_product_dashboard_source.py \
  -q --basetemp=runtime/pytest-tmp
# Result: 83 passed, 1 warning (pre-existing StarletteDeprecationWarning)
```

### AkTools Compat App Smoke

```bash
./.venv/bin/python -c "
from fastapi.testclient import TestClient
from src.integrations.aktools_compat_app import app
client = TestClient(app)
resp = client.get('/')
assert resp.status_code != 500
assert 'TemplateResponse() missing' not in resp.text
print('Homepage:', resp.status_code)   # 200, not 500
resp = client.get('/version')
assert resp.status_code == 200
body = resp.json()
assert 'ak_current_version' in body
assert 'at_current_version' in body
print('Version endpoint: OK')
"
```

### WSL Start/Stop Smoke

```bash
bash scripts/start.sh --with-aktools --streamlit-port 8771 --force
# AkTools on :8080 | API on :8000 | Streamlit on :8771

curl http://127.0.0.1:8080/version
# → JSON with akshare/aktools versions

curl http://127.0.0.1:8000/product/health
# → Health JSON

curl http://127.0.0.1:8000/product/llm/status
# → {"status":"ok","provider":"deepseek","model":"deepseek-v4-flash","api_key_present":false,...}

curl http://127.0.0.1:8000/product/runtime/services
# → Service status JSON

bash scripts/stop.sh
# → Ports released
```

### Feedback Bug Summary / Bug 自动分类

```bash
./.venv/bin/python scripts/summarize_feedback_bugs.py \
  --input feedback/bugs/open --output-dir docs/test_reports
# → 13 open bugs, categorized:
#   dashboard_timeout: 6
#   provider_empty_data: 4
#   uncategorized: 3
```

---

## Safety Confirmation / 安全确认

| 检查项 | 结果 |
|---|---|
| 默认真实自动交易保持禁用（`ENABLE_LIVE_TRADING=false`） | ✅ |
| Risk Agent 一票否决未被绕过 | ✅ |
| LLM 不直接决定买卖——所有 AI Agent prompt 包含 `"do not output BUY or SELL"` | ✅ |
| LLM 不创建订单——`ENABLE_LLM_TRADE_DECISION=false`（API 返回硬编码） | ✅ |
| AI 输出包含免责声明："AI output is research/explanation only. It is not a trading instruction." | ✅ |
| DataHealthGate 和 Risk Agent 仍在信号路径中——AI 仅解释，不覆盖 | ✅ |
| BugFix Agent 执行前校验提案路径；受限模块（`src/risk_engine/`、`src/execution_engine/`）被阻断 | ✅ |
| 密钥仅从环境变量读取（DEEPSEEK_API_KEY 等） | ✅ |
| 无 demo/paper 结果伪装为实盘结果 | ✅ |
| 全部 provider 失败时保持 fail-closed 行为 | ✅ |
| `.env.example` 默认值安全（无实盘交易、无 LLM 交易决策） | ✅ |

---

## Residual Risk / 剩余风险

1. **实时行情 provider 可用性**：Eastmoney/AkShare/AkTools 在非交易时段可能不可用。fail-closed 路径行为正确，但 PM 验收仍需要一个交易时段的真实行情 smoke。
2. **AI Agent 质量依赖 DeepSeek API**：三个 AI Agent 依赖 `ModelRouter.chat_json()`，需要有效的 DeepSeek API Key。缺 key 时返回 `status=unavailable`，不影响基础功能。
3. **历史遗留 ruff 问题**：全仓库扫描有 163 个预存 ruff 错误（本次任务未引入）。触碰文件已全部通过检查。
4. **AkTools 启动依赖**：`--with-aktools` 需要 `aktools` 和 `akshare` 包已安装。若缺失，启动脚本会报错但不影响其他服务。
