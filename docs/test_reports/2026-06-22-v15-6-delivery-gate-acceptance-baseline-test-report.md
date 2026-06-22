# V15.6 测试报告

## 变更范围

| 套件 | 用例 | 结果 |
|------|------|------|
| 门禁 + i18n 测试 | 20 | ✅ 全部通过 |
| Dashboard viewer 测试 | 27 | ✅ 全部通过 |
| Regression 测试 | 27 | ✅ 全部通过 |
| 自动化测试 | 48 | ✅ 全部通过 |
| 市场数据测试 | 17 | ✅ 全部通过 |
| 全量 `pytest tests -q` | 857 passed, 6 skipped | ✅ 零失败 |

## 测试命令

```
./.venv/bin/python -m pytest tests -q --basetemp=runtime/pytest-tmp-v15-6-full
./.venv/bin/python scripts/agent_pipeline_regression.py --strict
ruff check scripts/validate_pr_reports.py
```

## 注意事项

- 6 skipped 包括 E2E（需 RUN_PRODUCT_E2E=1）和浏览器测试（需 RUN_BROWSER_E2E=1）
- 市场数据测试已通过 monkeypatch 消除时间依赖
- 中文校验排除 Markdown 标题，阈值 30 个中文字符

## 安全确认

LEVEL_3_AUTO 已从 UI 移除。后端拒绝逻辑保留。不自动合并 main。

## 最终结论

PASS
