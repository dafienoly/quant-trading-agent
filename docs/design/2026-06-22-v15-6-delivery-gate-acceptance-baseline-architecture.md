# V15.6 交付门禁与验收基线修复架构

## 功能到代码映射

| 需求 | 修改文件 | 说明 |
|------|----------|------|
| R-001 | scripts/validate_pr_reports.py | Markdown 章节内容验证 |
| R-001 | .github/workflows/agent-pr-validation.yml | report_gate outcome 集成 |
| R-002 | AGENTS.md, docs/process/* | 中文输出要求 |
| R-002 | .agent/handoff/* | 中文报告要求 |
| R-002 | docs/policy/CHINESE_CONTENT_STANDARD.md | 补充规范 |
| R-003 | src/ui_report/product_dashboard.py | 移除 LEVEL_3_AUTO |
| R-004 | tests/test_product_api_e2e.py | 网络访问修复 |
| R-004 | tests/test_browser_simple.py | URL 配置化 |
| R-004 | tests/test_product_market_data.py | 时间 mock |
| R-005 | docs/acceptance/*-revalidation.md | 复验报告 |

## fail-closed 策略

不自动合并 main，Draft 等待人工审阅。
