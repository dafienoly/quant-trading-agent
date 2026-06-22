# V16.0 测试报告

## 需求和架构路径

- 需求：docs/requirements/2026-06-22-v16-0-readonly-live-monitoring-requirements.md
- 架构：docs/design/2026-06-22-v16-0-readonly-live-monitoring-architecture.md
- 开发：docs/dev_reports/2026-06-22-v16-0-readonly-live-monitoring-dev-report.md

## 测试环境

Python 3.14, ruff 0.11

## 覆盖矩阵

| 测试文件 | 用例数 | 结果 |
|----------|--------|------|
| test_quote_health.py | 10 | ✅ 全部通过 |
| 已有测试（7 文件） | 53 | ✅ 全部通过 |
| 全量 tests | 867 | ✅ 全部通过 |

## 测试场景覆盖

| 场景 | 状态 | 说明 |
|------|------|------|
| 正常行情返回 HEALTHY | ✅ | get_quote_health 测试 |
| 过期行情返回 STALE | ✅ | 60s 过期检测 |
| None 行情返回 UNAVAILABLE | ✅ | |
| Demo 数据返回 DEMO | ✅ | |
| 无时间戳返回 STALE | ✅ | |
| STALE 禁止信号和订单 | ✅ | evaluate 测试 |
| 正常允许研究和信号 | ✅ | |
| 刷新任务初始 IDLE | ✅ | ServiceManager |
| 刷新结果设置/读取 | ✅ | _set_refresh_result |
| REFRESH 常量可导入 | ✅ | |

## 遗漏列表

- API 端点（获取/更新自选股、行情快照、健康状态、启动刷新、刷新状态、信号观测）
- Dashboard 展示（源代码修改、最新价、涨跌幅、数据来源、行情时间等）
- 去重反馈记录
- 自选股存储

## 最终结论

PASS_WITH_NOTES
