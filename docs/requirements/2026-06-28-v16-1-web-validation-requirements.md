# V16.1 Web Validation 需求

## 背景

V16.1 前端已经具备基础页面、路由、context adapter、主页面组件拆分和 Adapter Status 数据绑定。当前需要补充一个可落地的验证收尾切片，让现有轻量验证能够覆盖前端关键结构。

## 本阶段目标

1. 新增 `apps/web/VALIDATION.md`。
2. 新增仓库级前端结构检查测试。
3. 校验 web workspace 关键文件存在。
4. 校验 package scripts 中包含 test 和 build。
5. 校验未提交生成目录。
6. 不新增 workflow，不提交 dependency lock。

## 非目标

1. 不修改前端业务页面。
2. 不新增后端接口。
3. 不新增写操作。
4. 不关闭 V16.1 总 Issue。

## 验收标准

1. pytest 能检查前端关键文件。
2. 文档给出本地验证命令。
3. PR 轻量验证通过。
4. 后续仍可单独补 frontend workflow 和 dependency lock。
