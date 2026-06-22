# V15.4 PR 报告门禁测试报告

## 测试范围

scripts/validate_pr_reports.py 的 CLI 功能

## 测试用例

| # | 用例 | 预期 | 结果 |
|---|------|------|------|
| 1 | 纯文档 PR | pass | ✅ |
| 2 | 无报告非文档 PR | fail | ✅ |
| 3 | 有报告非文档 PR | pass | ✅ |
| 4 | 空报告 | fail | ✅ |
| 5 | TODO 报告 | fail | ✅ |
| 6 | placeholder 报告 | fail | ✅ |
| 7 | JSON 输出格式 | pass | ✅ |
| 8 | base ref 不存在(strict) | fail | ✅ |
| 9 | 缺少 dev report | fail | ✅ |
| 10 | 缺必要章节 | fail | ✅ |

## 测试命令

```
./.venv/bin/python -m pytest tests/test_validate_pr_reports.py -q
=> 10 passed in 0.93s
```

## 结论

全部 10 个用例通过，覆盖纯文档、缺报告、空报告、占位报告、base 不可用和混合 PR 场景。
