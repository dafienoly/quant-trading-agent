# V15.5 中文规范与初步改造功能说明

## 变更范围

- 新增 docs/policy/CHINESE_CONTENT_STANDARD.md 中文内容规范
- 中文化 scripts/agent_pipeline_regression.py 的人类可读输出
- 中文化 scripts/agent_pipeline_report_viewer.py 的 Dashboard 标题、状态标签与等级标签
- 新增 i18n/英文泄漏检测测试

### 不修改
- 内部日志和 JSON message 字段保持英文
- 代码标识、环境变量、JSON key、第三方术语均保持英文

## 测试命令
```
./.venv/bin/python -m pytest tests/test_validate_pr_reports.py -q
./.venv/bin/python scripts/agent_pipeline_regression.py --strict
./.venv/bin/python -m pytest tests/test_agent_pipeline_automation.py tests/test_agent_pipeline_regression.py -q
```

## 测试结果
- 门禁+i18n 测试: 14 passed
- 回归: 状态：通过
- 自动化测试 75 passed

## 安全确认
- 不修改交易敏感模块
- 不修改 Merge Gate
- 不修改 Claude/Codex 执行逻辑
- 不自动合并 main

## 最终结论
V15.5 中文规范与初步改造完成，可提交 Draft PR 审阅。
