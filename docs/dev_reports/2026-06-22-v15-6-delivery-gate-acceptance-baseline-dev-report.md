# V15.6 交付门禁与验收基线修复功能说明

## 变更范围

- 修复 V15.4 报告门禁的章节内容检测
- workflow 中 report_gate 结果纳入诊断并上传 artifact
- 修复 TRACKED_OUTCOME 变量名拼写错误
- 启用中文正文校验（require_chinese=True）
- 移除安全 UI 中 LEVEL_3_AUTO 选项
- 修复测试基线（test_product_api_e2e.py 网络请求）
- 完成 process/handoff 中文要求更新
- 历史验收复验报告

## 测试命令

```
./.venv/bin/python -m pytest tests/test_validate_pr_reports.py tests/test_agent_pipeline_report_viewer.py tests/test_agent_pipeline_regression.py tests/test_agent_pipeline_automation.py -q
./.venv/bin/python scripts/agent_pipeline_regression.py --strict
ruff check scripts/validate_pr_reports.py src/ui_report/product_dashboard.py tests
```

## 测试结果

- 19 个门禁测试通过
- 121 个核心 pipeline 测试通过
- 回归 Status: PASS
- Ruff 无错误
- 无交易敏感模块修改

## 安全确认

LEVEL_3_AUTO 已从 UI 下拉框移除。后端拒绝逻辑保留。不自动合并 main。

## 最终结论

ACCEPTED
