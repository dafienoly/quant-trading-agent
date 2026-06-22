# V15.4 PR 报告门禁验收报告

## 验收范围

- git diff --name-only 纯文档判定
- 非纯文档 PR 的 dev report + acceptance report 检查
- 拒绝规则（空、TODO、TBD、placeholder）
- 错误处理（base ref 不存在时的 strict 模式）
- JSON 诊断输出

## 验收命令

```
./.venv/bin/python scripts/validate_pr_reports.py --base origin/main --head HEAD
```

## 验收结果

所有用例通过。10 个测试涵盖纯文档 PR、缺报告、空报告、占位报告、base 不可用和混合 PR。

## 安全确认

- ✅ 不修改交易敏感模块
- ✅ 不修改 Merge Gate
- ✅ 不修改 Claude/Codex 执行逻辑
- ✅ 不自动合并 main
- ✅ 不变更 V14.1 fail-closed 策略

## 最终结论

ACCEPTED
