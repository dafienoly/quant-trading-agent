# V16.2 Market Data Relay 与 Provider Contract 验收报告

## 变更范围

本次交付建立统一 Market Data Relay、Provider Contract、数据质量状态、用途级缓存治理、指数/ETF/行业/交易日历适配、八个 `/product/market/**` 只读 API，以及 Streamlit 数据源健康入口。既有 `/product/live-data/**` 保持兼容。

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

./.venv/bin/python -m pytest tests -q --tb=short \
  --basetemp=runtime/pytest-tmp-v16-2-broad-clean \
  --ignore=<16 个使用 TestClient 的文件>

TMPDIR=/tmp/codex-pytest ./.venv/bin/python \
  scripts/agent_pipeline_regression.py --strict
```

## 测试结果

1. 数据与兼容聚焦回归：`113 passed, 6 deselected`。
2. 广泛非 TestClient 回归：`953 passed, 6 skipped`。
3. UI 静态回归：`4 passed`。
4. Ruff、py_compile、`git diff --check` 全部通过。
5. Pipeline 严格回归：`8/8 gates passed`。
6. 没有 V16.2 阻断缺陷。

本地环境为 Python 3.14.4，仓库既有 TestClient 用例在该版本挂起，因此完整 HTTP TestClient 集尚待 Python 3.11 CI 复验。

## 用户验收入口

```text
GET /product/market/health
GET /product/market/sources
GET /product/market/quotes?symbols=600000.SH
GET /product/market/indexes?symbols=000001.SH
GET /product/market/etfs?symbols=510300.SH
GET /product/market/sectors?symbols=半导体
GET /product/market/bars?symbol=600000.SH&start=20260601&end=20260625
GET /product/market/calendar?start=20260601&end=20260625
```

Streamlit：运行 `python main.py dashboard`，进入“实时数据”，查看 `Market Data Relay 健康状态`。

## 安全确认

1. V16.2 只读，不生成订单、不连接券商、不启用真实交易。
2. mock、cache、stale、incomplete、unavailable 默认阻断信号。
3. execution usage 禁止缓存和 fixture。
4. 未触碰风险、执行、订单、账户和 Broker 模块。
5. 未暴露 `LEVEL_3_AUTO`。
6. main 不自动合并，仍需人工审阅。

## 最终结论

`ACCEPTED_WITH_NOTES`

V16.2 的功能和安全目标已实现。非阻断备注为 Python 3.14 TestClient 兼容问题，以及 V16.3 将继续完成多源一致性、fallback 治理和完整 Provider 异常矩阵。
