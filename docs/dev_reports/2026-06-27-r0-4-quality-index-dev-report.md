# R0.4 Quality Feedback Index 开发报告

## 变更范围

本次新增只读质量反馈索引能力。

| 文件 | 说明 |
| --- | --- |
| `src/product_app/quality_index/__init__.py` | package entrypoint |
| `src/product_app/quality_index/constants.py` | 版本常量 |
| `src/product_app/quality_index/models.py` | summary model |
| `src/product_app/quality_index/indexer.py` | 只读索引逻辑 |
| `scripts/quality_index_summary.py` | CLI JSON 输出 |
| `tests/test_quality_index.py` | 单元测试 |
| `docs/requirements/...` | 需求文档 |
| `docs/design/...` | 架构文档 |

## 实现说明

1. 新增 `quality_index.summary.v1` summary contract。
2. 新增只读 indexer，扫描固定质量反馈目录。
3. 支持 JSON、YAML、Markdown 输入。
4. 输出状态统计、优先级统计、条目列表与 warning。
5. Markdown 摘要限制长度，避免长文本进入 summary。
6. 新增 CLI：`scripts/quality_index_summary.py`。

## 测试命令

```bash
python -m py_compile src/product_app/quality_index/__init__.py src/product_app/quality_index/constants.py src/product_app/quality_index/models.py src/product_app/quality_index/indexer.py scripts/quality_index_summary.py tests/test_quality_index.py
python -m pytest tests/test_quality_index.py -q
python scripts/quality_index_summary.py --repo-root .
python scripts/validate_pr_reports.py --base origin/main --head HEAD --strict --json
git diff --check
```

## 测试结果

预期结果：

```text
py_compile: passed
pytest focused: passed
quality_index_summary.py: outputs JSON
validate_pr_reports.py --strict: passed
git diff --check: passed
```

PR 打开后以 GitHub 轻量验证结果为最终 CI 凭据。

## 安全确认

1. indexer 只读。
2. CLI 只输出 JSON。
3. 未新增 HTTP API。
4. 未改 workflow 编排。
5. 未修改行情、策略、风控、执行、账户、券商接入等业务模块。

## 剩余风险

1. 尚未接入 AgentOps UI。
2. 尚未在 workflow diagnostics 中生成固定报告文件。

## 最终结论

PASS_WITH_NOTES
