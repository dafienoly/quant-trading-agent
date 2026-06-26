# V16.2 Market Data Relay 与 Provider Contract 测试报告

## 测试依据

- 需求：`docs/requirements/2026-06-25-v16-2-market-data-relay-provider-contract-requirements.md`
- 架构：`docs/design/2026-06-25-v16-2-market-data-relay-provider-contract-architecture.md`
- 开发报告：`docs/dev_reports/2026-06-25-v16-2-market-data-relay-provider-contract-dev-report.md`

## 测试环境

- Linux / WSL
- Python 3.14.4
- pytest 9.1.0
- 外部 Provider 全部使用 monkeypatch fixture，不访问公网

## 测试范围

包含 Contract、Hub health、AkShare Relay Provider、本地缓存、fixture 边界、Relay 用途治理、质量门禁、API 路由注册、Streamlit 健康入口和既有 data gateway 回归。

不包含真实外部 Provider 连通性验收；真实源连通性不作为确定性自动测试。

## 需求覆盖矩阵

| 需求 | 测试证据 | 结果 |
|---|---|---|
| R-001 统一 Envelope | `test_market_relay_contracts.py` | PASS |
| R-002 个股行情 | `test_market_data_relay.py` | PASS |
| R-003 指数行情 | `test_market_relay_provider.py`、`test_market_data_relay.py` | PASS |
| R-004 ETF 行情 | `test_market_relay_provider.py` | PASS |
| R-005 历史日线 | stock/index/ETF bars fixture | PASS |
| R-006 行业板块 | sector fixture 与路由测试 | PASS |
| R-007 交易日历 | calendar fixture、区间过滤 | PASS |
| R-008 Provider 健康 | Hub health before/after 测试 | PASS |
| R-009 缓存用途治理 | display/signal/execution/stale 测试 | PASS |
| R-010 Fixture 边界 | 非 test_mode 抛错、mock 阻断 | PASS |
| R-011 质量门禁 | complete/incomplete/stale/unavailable/mock | PASS |
| R-012 UI 健康视图 | Dashboard source 与中文文案测试 | PASS |

## 异常与 Fail-Closed 测试

1. LiveDataService 抛异常：返回 unavailable，不向 API 冒泡。
2. Provider 空数据：Hub 视为失败。
3. 缺失关键字段：标记 incomplete，阻断信号。
4. 缓存过期：标记 stale，阻断信号。
5. execution 请求：实时失败时禁止缓存 fallback。
6. fixture：标记 mock，阻断信号。
7. cache 写入失败：保留有效 live 数据并显示 warning。
8. cache 文件损坏：忽略损坏缓存，不返回伪成功。

## 测试命令

```bash
./.venv/bin/python -m pytest \
  tests/test_market_relay_contracts.py \
  tests/test_market_relay_provider.py \
  tests/test_market_data_relay.py \
  tests/test_market_routes.py \
  tests/test_live_data_mapper.py \
  tests/test_live_data_service.py \
  tests/test_product_market_data.py \
  tests/test_realtime_provider.py \
  tests/test_eastmoney_provider.py \
  -q --tb=short --basetemp=runtime/pytest-tmp-v16-2-final-focused \
  -k 'not TestLiveDataAPI'
```

```bash
./.venv/bin/python -m pytest tests -q --tb=short \
  --basetemp=runtime/pytest-tmp-v16-2-broad-clean \
  --ignore=<16 个使用 TestClient 的文件>
```

```bash
./.venv/bin/python -m pytest \
  tests/test_product_dashboard_source.py \
  tests/test_market_routes.py::test_dashboard_contains_market_relay_health_entry \
  -q --basetemp=runtime/pytest-tmp-v16-2-ui-static
```

## 测试结果

- 数据与兼容聚焦回归：`113 passed, 6 deselected`
- 广泛非 TestClient 回归：`953 passed, 6 skipped`
- UI 静态回归：`4 passed`
- Ruff：通过
- py_compile：通过
- git diff check：通过
- Pipeline strict regression：通过，`8/8 gates`

唯一 warning 来自第三方 `py_mini_racer` 在 Python 3.14 下的弃用提示，与本次功能无关。

## 缺陷列表

未发现 V16.2 阻断缺陷。

环境备注：Python 3.14.4 下仓库既有 TestClient 测试挂起，完整 FastAPI HTTP 回归需在 Python 3.11 CI 复验。该问题不是 V16.2 新路由特有。

## 安全确认

1. 无真实交易能力。
2. mock、cache、stale、incomplete、unavailable 均不能进入信号。
3. execution cache 被明确禁止。
4. 未修改交易敏感模块。

## 最终结论

`PASS_WITH_NOTES`

备注不阻断 V16.2 进入代码 Review；合并前必须由 Python 3.11 CI 完成 TestClient 回归。
