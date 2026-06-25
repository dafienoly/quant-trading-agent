# Phase 3 开发报告 — 前端状态中心（Streamlit 方案 B）

## 需求与架构

| 项目 | 路径 |
|---|---|
| 需求文档 | `docs/requirements/2026-06-24-agentops-control-tower-foundationpipeline-api-re-requirements.md` |
| 架构文档 | `docs/design/2026-06-24-agentops-control-tower-foundationpipeline-api-re-architecture.md` |
| 团队计划 | `docs/dev_plans/20260624-agentops-control-tower-foundationpipeline-api-re-team-plan.md` |

## 实现范围

采用 **方案 B（Streamlit 状态中心）**，沿用仓库既有 Streamlit 前端栈，不引入 React/Node 工具链。

### 新增文件

| 文件 | 说明 |
|---|---|
| `src/ui_report/agentops_state.py` | Streamlit 状态中心模块：封装只读 GET 调用、错误归一化、`st.session_state` 缓存与状态转换 |
| `tests/test_agentops_state.py` | 状态中心单元测试，覆盖 ready/blocked/empty/error/stale/clear/cache/只读保证 |

### 功能映射

| 功能点 | 对应函数 | 说明 |
|---|---|---|
| F-003.1 React 状态中心 → Streamlit 状态中心 | `load_by_feature_id()` | 按 feature_id 加载观测数据，返回 view_status/observation/error/last_loaded_at/is_refreshing |
| F-003.2 按 Issue 加载 | `load_by_issue_number()` | 按 issue_number 加载观测数据 |
| F-003.3 刷新 | `refresh()` | 重新拉取当前 feature/issue 数据 |
| F-003.4 清除 | `clear()` | 重置状态为初始值 |
| 状态转换规则 | `_fetch_and_update()` | 200→ready / 200+blockers→blocked / 404→empty / 400/422/500→error / 刷新失败→stale |
| 缓存去重 | `load_by_feature_id()` 内部 | 同一 feature_id 不重复请求 |
| 只读保证 | 模块全局 | 仅使用 `requests.get()`，无 POST/PUT/DELETE/PATCH |

## 自测命令与结果

```bash
python3 -m ruff check src/ui_report/agentops_state.py tests/test_agentops_state.py
python3 -m py_compile src/ui_report/agentops_state.py
python3 -m pytest tests/test_agentops_state.py -q --basetemp=runtime/pytest-tmp-agentops-control-tower
git diff --check
```

### 结果

| 检查项 | 结果 |
|---|---|
| ruff | All checks passed |
| py_compile | 通过（无输出=成功） |
| pytest (19 tests) | 19 passed |
| git diff --check | 无空白字符错误 |
| 受限模块审计 | 未触碰任何受限模块（risk/execution/data/backtest/factor/strategy/stock_pool） |

## 安全确认

- ✅ 只读硬约束：`agentops_state.py` 仅使用 `requests.get()`，无 POST/PUT/DELETE/PATCH。
- ✅ 敏感信息清洗：错误字符串经 `_normalize_error()` 处理，绝对路径→`<workspace>` 替换。
- ✅ fail-visible：404→`empty`、500→`error`、网络异常→`error`（有旧数据→`stale`）。
- ✅ 不触碰受限模块：import 审计通过。
- ✅ 不暴露 `LEVEL_3_AUTO`。
- ✅ 不自动合并 main，不执行 git commit/push/merge（由 GitHub Stage Runner 管理）。
- ✅ 未提交密钥、Token、Cookie、账户或 Broker 凭据。

## 最终结论

**PASS**

Phase 3 实现完成。所有 19 个测试通过，ruff/py_compile 无错误，仅更改 `src/ui_report/agentops_state.py` 和 `tests/test_agentops_state.py`，未触碰受限模块。
