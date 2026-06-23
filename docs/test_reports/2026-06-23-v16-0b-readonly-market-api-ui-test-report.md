# V16.0b 测试报告

## 变更范围

| 套件 | 用例 | 结果 |
|------|------|------|
| V16.0b 专注（8 文件） | 52 | ✅ 全部通过 |
| 全量 tests | 882 | ✅ 全部通过 |
| Ruff V16.0b 文件 | — | ✅ All checks passed |

## 覆盖场景

| 场景 | 状态 |
|------|------|
| 自选股 GET | ✅ |
| 自选股 PUT（合法） | ✅ |
| 拒绝重复代码 | ✅ |
| 拒绝非法代码 | ✅ |
| 行情健康端点 | ✅ |
| 刷新状态端点 | ✅ |
| 信号观测端点 | ✅ |
| STALE 禁止信号 | ✅ |
| Demo 禁止信号 | ✅ |
| 全部 provider 失败 fail closed | ✅ |
| quote_refresh 写入 SUCCEEDED/FAILED | ✅ |

## 最终结论

PASS_WITH_NOTES
