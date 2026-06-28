# V16.1 App Split 测试报告

## 变更范围

本测试报告覆盖前端主页面组件拆分、现有卡片抽离和 Adapter Status 占位卡挂载。

## 测试命令

```bash
cd apps/web
npm run test
npm run build
cd ../..
python scripts/validate_pr_reports.py --base origin/main --head HEAD --strict --json
git diff --check
```

## 测试结果

预期结果如下：

1. 现有前端测试通过。
2. TypeScript build 通过。
3. 报告门禁通过。
4. diff 格式检查通过。

PR 打开后以仓库轻量验证结果作为最终依据。

## 安全确认

测试不访问真实外部服务，不处理凭据，不触发写操作。

## 最终结论

PASS_WITH_NOTES
