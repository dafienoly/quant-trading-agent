# V16.2 Market Data Relay 收尾补强测试报告

## 变更范围

本报告验证 `PR #90` 已合并基线上的 V16.2 follow-up：

- envelope 可观测字段
- provider health fallback 计数
- signal / execution cache 语义保持
- dashboard 健康面板可见性

## 文档引用

- Requirement：`docs/requirements/2026-06-27-v16-2-market-data-relay-fallback-observability-requirements.md`
- Architecture：`docs/design/2026-06-27-v16-2-market-data-relay-fallback-observability-architecture.md`
- Development report：`docs/dev_reports/2026-06-27-v16-2-market-data-relay-fallback-observability-dev-report.md`

## Roadmap 对应

- V16.2 Market Data Relay & Provider Contract

## 测试环境

- WSL / Linux workspace
- Python：`.venv`
- 外部行情源：未直接访问公网，使用 deterministic fixture / monkeypatch / route patch

## Requirement Coverage Matrix

| 要求 | 覆盖方式 | 结果 |
| --- | --- | --- |
| R-001 Envelope 可观测字段 | `tests/test_market_data_relay_service.py`, `tests/test_market_routes.py` | PASS |
| R-002 Provider Health 补强 | `tests/test_market_relay_provider.py` | PASS |
| R-003 V16.2 cache 语义保持 | `tests/test_market_data_relay_service.py` | PASS |
| R-004 Dashboard 可见性 | `tests/test_market_routes.py`, `tests/test_product_dashboard_source.py` | PASS |
| R-005 测试补强 | 7 个 touched-scope 文件 + 兼容回归 | PASS |

## 测试命令

```bash
./.venv/bin/python -m py_compile src/data_gateway/provider_contracts.py src/data_gateway/provider_hub.py src/product_app/market_data_relay.py src/ui_report/product_dashboard.py tests/test_market_data_relay_service.py tests/test_market_relay_provider.py tests/test_market_routes.py

./.venv/bin/python -m pytest tests/test_market_data_relay_service.py tests/test_market_relay_provider.py tests/test_market_routes.py tests/test_product_dashboard_source.py -q --tb=short --basetemp=runtime/pytest-tmp-v16-2-followup-focused

./.venv/bin/python -m pytest tests/test_market_data_quality.py tests/test_market_data_relay_service.py tests/test_market_routes.py tests/test_market_data_routes.py tests/test_market_relay_provider.py tests/test_market_data_health.py tests/test_market_data_provider_registry.py tests/test_product_market_data.py tests/test_product_dashboard_source.py tests/test_live_data_service.py -q --tb=short --basetemp=runtime/pytest-tmp-v16-2-followup-broad

./.venv/bin/python -m pytest tests -q --tb=short --basetemp=runtime/pytest-tmp-v16-2-followup-full

TMPDIR=/tmp/codex-pytest ./.venv/bin/python scripts/agent_pipeline_regression.py --strict

./.venv/bin/python -m ruff check src/data_gateway/provider_contracts.py src/data_gateway/provider_hub.py src/product_app/market_data_relay.py src/ui_report/product_dashboard.py tests/test_market_data_relay_service.py tests/test_market_relay_provider.py tests/test_market_routes.py

git diff --check
```

## 测试结果

- `py_compile`：通过
- focused 回归：`20 passed, 1 warning`
- broad 兼容回归：`129 passed, 2 warnings`
- 全量测试：`1365 passed, 6 skipped, 2 warnings`
- Pipeline 严格回归：`PASS`
- Ruff：`All checks passed!`
- `git diff --check`：通过

## 重点验证结论

1. `signal` 在 live 成功时仍可拿到 `complete` 数据。
2. live 失败后，`signal` 仍可看到 cache 证据，但 `blocking_for_signal=true`，没有被错误升级成 `execution` 语义。
3. `execution` 在 live 失败时不会消费 cache fallback。
4. route 返回结构已包含新增的 observability 字段。
5. provider hub 在 fallback success 场景下会累计 `fallback_activation_count`。
6. dashboard 源码存在 `Fallback 次数` 与 `字段覆盖` 展示入口。

## 缺陷列表

无阻断缺陷。

## 剩余风险

1. 第三方依赖告警仍在，但与本次补强无直接关系。

## 安全确认

1. 未新增真实交易路径。
2. 未触碰 `src/broker/**`、`src/execution/**`、`src/order/**`、`src/account/**`、`src/risk/**`、`miniQMT/**`。
3. 未提交 `.agent/tmp/**`、`.agent/reports/**`、`runtime/**`、`feedback/index.json`。

## 最终结论

PASS
