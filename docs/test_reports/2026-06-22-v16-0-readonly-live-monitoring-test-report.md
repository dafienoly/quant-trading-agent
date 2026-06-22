# V16.0 测试报告

## 变更范围

| 套件 | 用例 | 结果 |
|------|------|------|
| 聚焦测试（7 文件） | 53 | ✅ 全部通过 |
| 全量测试 | 857 passed, 6 skipped | ✅ 零失败 |
| Ruff | — | ✅ All checks passed |

## 测试命令

```
./.venv/bin/python -m pytest tests -q --basetemp=runtime/pytest-tmp-v16-0-full
ruff check src/product_app src/api src/ui_report tests
```

## 注意事项

- 6 skipped 为 E2E 和浏览器测试（需显式启用）
- 行情时间依赖已通过 DataHealthGate 延迟评估处理
- 健康门禁阈值 30 秒

## 结论

PASS
