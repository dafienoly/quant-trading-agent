# 中文内容规范

## 适用版本

V15.5

## 规范目标

统一项目中文内容风格，明确用户输出、内部日志、代码标识、JSON 字段和
第三方术语的中文/英文使用边界。

## 分类规则

### 用户可见文案（User-Visible Text）

默认语言：**中文**
- Dashboard 标题、状态、说明、标签、按钮、提示
- 命令行输出的说明性文字
- 错误消息（用户可见部分）
- 报告中的标题、说明、字段标签
- HTML 页面中的空状态、错误状态

非默认：英文仅能通过 `LANG=en` 环境变量或 `--lang en` 参数切换启用。

### 内部日志（Internal Logs）

默认语言：**英文**
- print/logging 调试输出
- CI 步骤日志
- JSON 诊断中的 message 字段
- 这些仍用英文，便于工具管道处理

### 代码标识（Code Identifiers）

强制：**英文**
- 变量名、函数名、类名、常量
- 文件名
- 模块名、包名
- 异常类名
- 数据库表名/列名

### JSON 字段（JSON Fields）

强制：**英文**
- API 响应 key
- JSON schema 字段
- 配置文件 key
- 枚举值

### 环境变量（Environment Variables）

强制：**英文**
- 变量名、其值不包含自然语言内容

### 第三方术语（Third-Party Terms）

保持原文。

---

## 本轮中文化范围

### scripts/agent_pipeline_report_viewer.py

| 元素 | 当前文案 | 目标 |
|------|----------|------|
| Dashboard 标题 | "Agent Pipeline Dashboard" | "Agent Pipeline 诊断看板" |
| 状态卡 | "Status: FAIL" | "状态：失败" |
| 状态卡 | "Status: WARN" | "状态：警告" |
| 状态卡 | "Status: PASS" | "状态：通过" |
| Summary 标签 | "Critical" / "Warnings" / "Info" | "严重" / "警告" / "信息" |
| 表格列 | "OK" | "结果" |
| 表格列 | "Severity" | "等级" |
| 表格列 | "Name" | "检查项" |
| 表格列 | "Message" | "消息" |
| 空状态 | "No failed/warning checks" | "无失败项" |
| 各节标题 | English | 中文 |
| 文件生成时间 | "Generated:" | "生成时间：" |
| 查看提示 | "Click to toggle raw JSON" | "点击展开/收起原始 JSON" |
| 状态背景 | 颜色 | 颜色保持不变 |

### scripts/agent_pipeline_regression.py

| 元素 | 当前文案 | 目标 |
|------|----------|------|
| 标题 | "Agent Pipeline Regression Suite" | "Agent Pipeline 回归测试套件" |
| Status 行 | "Status: PASS" | "状态：通过" |
| Status 行 | "Status: FAIL" | "状态：失败" |
| Status 行 | "Status: WARN" | "状态：警告" |
| 统计 | "Critical failures: %d" | "严重失败：%d" |
| 统计 | "Warnings: %d" | "警告：%d" |
| 统计 | "Info checks: %d" | "信息：%d" |
| 状态列 | "PASS" | "通过" |
| 状态列 | "FAIL" | "失败" |
| 状态列 | "WARN" | "警告" |
| JSON output message 字段 | English | 保持英文（内部） |
| check name | English | 保持英文（代码标识） |

## 英文泄漏检测白名单

以下情况允许出现英文：
- 代码标识（函数名、变量名、类型名）
- JSON key
- 环境变量名
- 第三方术语
- 文件路径
- URL
- 内部日志/调试输出
- 技术缩写（API, SDK, JSON, HTML, HTTP, URL, CLI, CI, PR, WSL, SSH）

## i18n 复用

不允许多个文件重复硬编码同一翻译。
现有 i18n 字典位于 `src/ui_report/i18n.py`。
Dashboard 和 regression 的中文内容直接内嵌（因非 Streamlit 场景），
但相同文案不得在 dashboard 内重复硬编码；
提取为模块级常量或共用函数。

## 切换机制

- 默认：中文
- 切换：`--lang en` CLI 参数
- 环境变量：`LANG=en`
- 无切换开关时：使用中文

## V15.6 更新：中文报告门禁

- 非纯文档 PR 必须提交中文功能说明和中文验收报告。
- 报告正文（不含 Markdown 标题）必须包含至少 30 个中文字符。
- 英文仅正文（无中文内容的报告）将被门禁拒绝。
- 代码标识、JSON key、环境变量和第三方术语不受此限制。
