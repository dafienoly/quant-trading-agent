# V16.1 Web Validation 设计

## 设计目标

本阶段不直接新增 GitHub workflow，而是把前端验证纳入现有仓库验证路径。通过 Python 测试检查 `apps/web` 的关键结构，让现有 PR 轻量验证也能覆盖前端基础完整性。

## 文件结构

```text
apps/web/VALIDATION.md
tests/test_web_frontend_validation.py
```

## 验证策略

1. `VALIDATION.md` 说明本地前端 test 与 build 命令。
2. Python 测试检查 web workspace 是否存在。
3. Python 测试检查关键 TypeScript、Vite、API、selector、component 文件是否存在。
4. Python 测试检查 `package.json` 是否包含 test 和 build scripts。
5. Python 测试检查没有提交 `apps/web/node_modules`。

## 安全边界

本阶段只新增文档和只读结构测试，不新增 workflow，不提交 dependency lock，不修改后端接口，不修改业务执行模块。