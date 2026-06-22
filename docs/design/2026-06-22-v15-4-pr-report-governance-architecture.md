# V15.4 PR 报告门禁架构

## 模块设计

### validate_pr_reports.py

独立 CLI 脚本，输入：
- `--base`：base ref
- `--head`：head ref
- `--strict`：strict 模式
- `--output`：结构化 JSON 输出路径

处理流程：
1. `git diff --name-only <base>...<head>` 获取文件列表
2. 判定是否为纯文档 PR
3. 非纯文档 → 检查 `docs/dev_reports/` 和 `docs/acceptance/` 报告
4. 验证报告内容和完整性
5. 输出结构化 JSON 诊断

### 规则引擎

```
PR 文件列表 → 纯文档判定 → [纯文档] → pass
                       → [非纯文档] → 
                           → docs/dev_reports/ 存在？→ [否] → fail
                           → docs/acceptance/ 存在？→ [否] → fail
                           → 内容拒绝规则 → [命中] → fail
                           → [全部通过] → pass
```

### 拒绝规则实现

```python
REJECT_PATTERNS = [
    "TODO", "TBD", "待补充",
    "This is a placeholder", "placeholder",
]
```

报告文件空或仅含空白 → fail
报告内容匹配拒绝规则 → fail
报告无标题/变更范围/测试命令/测试结果/安全确认 → fail

## 集成

接入 `.github/workflows/agent-pr-validation.yml`，在现有验证步骤之后增加报告门禁步骤。

使用 `if: always()` 确保诊断 artifact 始终上传。

## 安全边界

- 不修改交易敏感模块
- 不修改 Merge Gate
- 不自动合并 main
- 不修改 Claude/Codex 执行逻辑
