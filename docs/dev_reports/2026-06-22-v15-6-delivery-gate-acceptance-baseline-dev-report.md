# V15.6 交付门禁与验收基线修复功能说明

## 变更范围

- 修复 V15.4 报告门禁的章节内容检测
- workflow 中 report_gate 结果纳入诊断并上传 artifact
- 修复 TRACKED_OUTCOME 变量名拼写错误
- 启用中文正文校验（require_chinese=True，排除标题，阈值 30）
- 移除安全 UI 中 LEVEL_3_AUTO 选项
- 修复测试基线（test_product_api_e2e.py、test_browser_simple.py、market_data 时间依赖）
- 完成 process/handoff/中文规范更新
- 历史验收复验报告（V15.4、V15.5）
- 新增 pytest markers（e2e、browser）

## 修复说明

本次整改共经过四轮验收。最终提交 cd24e35 对齐了 feedback/index.json 时间戳到 origin/main，避免纯时间戳变化进入 PR diff。

## 测试命令

```
./.venv/bin/python -m pytest tests -q --basetemp=runtime/pytest-tmp-v15-6-full
./.venv/bin/python scripts/agent_pipeline_regression.py --strict
ruff check scripts/validate_pr_reports.py
```

## 测试结果

- 全量 857 passed, 6 skipped, 0 failed
- 回归 Status: PASS
- Ruff All checks passed
- 无交易敏感模块修改

## 安全确认

LEVEL_3_AUTO 已从 UI 下拉框移除。后端拒绝逻辑保留。不自动合并 main。

## 最终结论

ACCEPTED
