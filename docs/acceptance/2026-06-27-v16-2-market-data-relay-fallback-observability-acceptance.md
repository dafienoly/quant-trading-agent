# V16.2 Market Data Relay 收尾补强验收报告

## 变更范围

本次验收对象不是重新验收 `PR #90` 全量能力，而是确认在已合并的 V16.2 基线上，下面四件事已经补齐：

1. fallback / cache / usage 的用户可见字段更完整；
2. provider health 能看到字段覆盖和 fallback 次数；
3. `signal` / `execution` 的 cache 边界仍符合 V16.2；
4. Streamlit 健康入口能展示新增信息。

## 验收依据

- `docs/requirements/2026-06-27-v16-2-market-data-relay-fallback-observability-requirements.md`
- `docs/design/2026-06-27-v16-2-market-data-relay-fallback-observability-architecture.md`
- `docs/dev_reports/2026-06-27-v16-2-market-data-relay-fallback-observability-dev-report.md`
- `docs/test_reports/2026-06-27-v16-2-market-data-relay-fallback-observability-test-report.md`

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

## 验收检查

| 检查项 | 结果 |
| --- | --- |
| 是否仍属于 V16.2 而非提前改写 V16.3 | PASS |
| `/product/**` 边界是否保持 | PASS |
| Streamlit 是否仍为有效产品入口 | PASS |
| `signal` cache 语义是否保持 V16.2 | PASS |
| `execution` 是否继续 fail closed | PASS |
| provider fallback 健康信息是否可见 | PASS |
| 中文 dev/test/acceptance 文档是否齐备 | PASS |

## 安全确认

1. 未新增真实交易、自动下单、券商写操作。
2. 未触碰 `src/broker/**`、`src/execution/**`、`src/order/**`、`src/account/**`、`src/risk/**`、`miniQMT/**`。
3. 未暴露 `LEVEL_3_AUTO`。
4. 未允许 LLM 直接下单或覆盖风控。
5. 未提交 `.agent/tmp/**`、`.agent/reports/**`、`runtime/**`、`feedback/index.json`。

## 剩余风险

1. 真实外部 provider smoke 未执行。
2. 更完整的 provider fallback governance 和统一对外接口收敛仍留给 V16.3。

## 最终结论

PASS
