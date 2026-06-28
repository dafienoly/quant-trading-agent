# V16.1 Adapter Live 设计

## 设计目标

将 Adapter Status 从静态占位卡升级为独立只读数据绑定，同时避免把 context 读取逻辑塞回主页面。

## 文件结构

```text
apps/web/src/App.tsx
apps/web/src/components/AdapterStatusPanel.tsx
```

## 数据流

1. `App.tsx` 继续加载 Ops Summary、Runtime Profile 和 Quality Summary。
2. `AdapterStatusPanel` 独立读取 context snapshot。
3. `AdapterStatusPanel` 使用 `toContextDisplay` 转换展示数据。
4. `AdapterStatusCard` 只负责展示。

## 故障隔离

如果 context 读取失败，panel 只展示 Adapter Status 的 error fallback，不影响主页面其他卡片。

## 安全边界

本阶段只做前端 GET 读取和展示，不新增后端接口，不新增写操作，不读取凭据，不修改交易相关模块。