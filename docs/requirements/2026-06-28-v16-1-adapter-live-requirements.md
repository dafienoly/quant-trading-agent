# V16.1 Adapter Live 需求

## 背景

前端主页面已经完成组件拆分，并挂载了 Adapter Status 占位卡。上一轮也已经提供 context API client 和 display selector。本阶段目标是把占位卡升级为真实只读数据绑定。

## 本阶段目标

1. 新增 AdapterStatusPanel。
2. 由 panel 调用已有 context client。
3. 由 panel 使用已有 selector 转换展示数据。
4. 主页面只替换占位卡，不扩大主页面加载流程。
5. context 加载失败时只影响 Adapter Status 卡片，不阻塞其他卡片。

## 非目标

1. 不新增后端接口。
2. 不修改主页面已有三张卡片的数据加载流程。
3. 不新增写操作。
4. 不接入凭据或外部服务。
5. 不关闭 V16.1 总 Issue。

## 验收标准

1. Adapter Status 卡片通过独立 panel 读取 context 数据。
2. context 失败时显示 error fallback。
3. 主页面仍保留原有 loading、error、ready 流程。
4. PR 轻量验证通过。
