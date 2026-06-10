# Bug 报告与自动处理系统

## 目录结构

```
feedback/
├── README.md              # 本文档
├── index.json             # Bug 索引（自动维护）
└── bugs/
    ├── open/              # 新建/未处理的 Bug
    ├── triaged/           # 已分类/已分配的 Bug
    ├── fixed/             # 已修复的 Bug
    ├── ignored/           # 已忽略的 Bug
    └── analysis/          # Bug 自动分析报告和修复方案
```

## Bug 报告生命周期

### 基础流转（手动模式）

```
  [创建] → open → triaged → fixed
                    └→ ignored
```

### 自动处理流转（Phase 5.6+）

```
  [创建] → open → analyzing → proposed → approved → fixing → verified → fixed
                     │           │                         │
                     v           v                         v
                  blocked    rejected                 fix_failed
                                │                         │
                                └──→ analyzing (重新分析)    └──→ fixing (重试)
                                                                  └──→ open (重置)
```

### 状态说明

| 状态 | 目录 | 说明 |
|------|------|------|
| `open` | `bugs/open/` | 新创建的 Bug，等待开发人员分类或自动分析 |
| `analyzing` | `bugs/open/` | BugFix Agent 正在通过 DeepSeek API 分析根因 |
| `proposed` | `bugs/open/` | 分析完成，已生成修复方案，等待人工审批 |
| `approved` | `bugs/open/` | 审批通过，即将执行自动修复 |
| `rejected` | `bugs/open/` | 审批拒绝，可重新触发分析 |
| `fixing` | `bugs/open/` | 正在执行自动修复 |
| `fix_failed` | `bugs/open/` | 修复执行失败（测试不通过），已自动回滚 |
| `verified` | `bugs/open/` | 修复已执行且测试通过，等待确认 |
| `fixed` | `bugs/fixed/` | 修复完成并确认 |
| `blocked` | `bugs/open/` | 修复涉及受限模块，需人工处理 |
| `triaged` | `bugs/triaged/` | 已确认并分类，已分配给开发人员 |
| `ignored` | `bugs/ignored/` | 已评估但不予处理 |

### 自动处理新增字段

| 字段 | 说明 |
|------|------|
| `analysis_report` | DeepSeek API 生成的根因分析报告 |
| `fix_proposal` | DeepSeek API 生成的修复方案（含代码 diff） |
| `approval_status` | 审批状态：approved / rejected |
| `approval_comment` | 审批备注 |
| `fix_result` | 修复执行结果（成功/失败/测试输出） |
| `git_commit_hash` | 修复提交的 git commit hash |

---

## DeepSeek API 配置

Bug 自动分析系统使用 DeepSeek API 作为 LLM 引擎，需要配置以下环境变量。

### 配置方式

在项目根目录的 `.env` 文件中添加（可从 `.env.example` 复制）：

```bash
# ============================================================
# DeepSeek API (BugFix Agent)
# ============================================================
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
DEEPSEEK_API_BASE=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

### 配置项说明

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `DEEPSEEK_API_KEY` | **是** | 无 | DeepSeek API 密钥，从 [platform.deepseek.com](https://platform.deepseek.com) 获取 |
| `DEEPSEEK_API_BASE` | 否 | `https://api.deepseek.com` | API 基础地址，兼容 OpenAI 接口格式 |
| `DEEPSEEK_MODEL` | 否 | `deepseek-chat` | 使用的模型名称 |

### 获取 API Key

1. 访问 [DeepSeek 开放平台](https://platform.deepseek.com)
2. 注册/登录账号
3. 进入「API Keys」页面，创建新密钥
4. 将密钥填入 `.env` 文件的 `DEEPSEEK_API_KEY`

### 未配置时的行为

- 如果 `DEEPSEEK_API_KEY` 未配置，BugFixAgent 的 `analyze()` 和 `propose_fix()` 将因 API 认证失败而返回错误
- BugWatchdog 仍会正常监控新 Bug 文件，但自动分析流程会在 `analyzing` 阶段失败
- 失败后 Bug 状态会回退到 `open`，不会卡死
- 手动 Triage 流程不受影响

### 费用参考

| 模型 | 输入价格 | 输出价格 | 单次 Bug 分析预估费用 |
|------|---------|---------|---------------------|
| deepseek-chat | ¥0.001/千token | ¥0.002/千token | 约 ¥0.01-0.05 |

---

## 自动处理安全约束

| # | 约束 | 说明 |
|---|------|------|
| 1 | 修复方案必须审批后才能执行 | `proposed → approved` 不可跳过 |
| 2 | 禁止自动修改风控模块 | `risk_engine` 路径自动拦截 |
| 3 | 禁止自动修改执行引擎 | `execution_engine` 路径自动拦截 |
| 4 | 禁止自动修改交易日志 | `trading_log` 路径自动拦截 |
| 5 | 禁止自动修改回测报告 | `backtest_report` 路径自动拦截 |
| 6 | 修复前创建 git stash 回滚点 | 修复失败自动回滚 |
| 7 | 修复后运行 pytest 验证 | 测试不通过自动回滚 |
| 8 | API Key 不硬编码 | 从环境变量读取 |

---

## 开发人员 Triage 流程

### 1. 查看待处理 Bug

```bash
# 查看 open 目录中的 Bug 列表
ls feedback/bugs/open/

# 或查看索引
cat feedback/index.json
```

也可通过代码调用：

```python
from src.product_app.feedback import get_feedback_service

service = get_feedback_service()
open_bugs = service.get_open_bugs()
for bug in open_bugs:
    print(f"[{bug.severity}] {bug.bug_id}: {bug.title}")
```

### 2. 分类 Bug

阅读 Bug 报告的 `.md` 文件，确认以下信息：

- **是否为真实 Bug**：排除用户误操作、配置错误等
- **严重程度是否准确**：根据影响范围和严重性调整
- **所属组件是否正确**：确认或修正 component 字段
- **是否重复**：检查 dedupe_hash 和已有 Bug

### 3. 更新状态

```python
from src.product_app.feedback import get_feedback_service

service = get_feedback_service()

# 标记为已分类
service.update_bug_status("BUG_20260609_ABC123", "triaged")

# 标记为已修复
service.update_bug_status("BUG_20260609_ABC123", "fixed")

# 标记为忽略
service.update_bug_status("BUG_20260609_ABC123", "ignored")
```

### 4. 审批自动修复方案

当 Bug 进入 `proposed` 状态后，可通过 API 或面板审批：

```python
# 通过 API 审批
import requests
requests.post("http://localhost:8000/product/feedback/BUG_20260609_ABC123/approve?comment=LGTM")

# 通过 API 拒绝
requests.post("http://localhost:8000/product/feedback/BUG_20260609_ABC123/reject?comment=风险过高")
```

也可在 Streamlit 面板的「反馈中心」Tab 中点击 Approve / Reject 按钮。

### 5. 修复验证

修复完成后，验证 Bug 报告中记录的复现步骤不再触发问题。

## Bug 报告字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `bug_id` | 是 | 唯一标识，格式 `BUG_{YYYYMMDD}_{6位码}` |
| `created_at` | 是 | 创建时间 |
| `updated_at` | 是 | 最后更新时间 |
| `status` | 是 | Bug 状态 |
| `severity` | 是 | 严重程度：critical/high/medium/low |
| `component` | 是 | 所属组件 |
| `title` | 是 | Bug 标题 |
| `summary` | 是 | Bug 摘要 |
| `user_action` | 否 | 用户操作描述 |
| `endpoint_or_page` | 否 | 触发端点或页面 |
| `exception_type` | 否 | 异常类型 |
| `exception_message` | 否 | 异常消息 |
| `sanitized_traceback` | 否 | 脱敏后的堆栈跟踪 |
| `runtime_context` | 否 | 运行时上下文 |
| `config_snapshot_masked` | 否 | 脱敏后的配置快照 |
| `reproduction_steps` | 否 | 复现步骤 |
| `dedupe_hash` | 是 | 去重哈希（自动生成） |
| `related_log_files` | 否 | 相关日志文件路径 |
| `occurrence_count` | 是 | 出现次数（自动计数） |
| `analysis_report` | 否 | 自动分析报告（DeepSeek API 生成） |
| `fix_proposal` | 否 | 自动修复方案（DeepSeek API 生成） |
| `approval_status` | 否 | 审批状态：approved / rejected |
| `approval_comment` | 否 | 审批备注 |
| `fix_result` | 否 | 修复执行结果 |
| `git_commit_hash` | 否 | 修复提交的 git commit hash |

## 去重机制

系统基于以下字段组合计算去重哈希：

- `component`（组件）
- `exception_type`（异常类型）
- `exception_message`（归一化后的异常消息）
- `endpoint_or_page`（端点/页面）

**24小时窗口**内相同哈希的 Bug 被视为重复，自动增加 `occurrence_count` 而不创建新报告。

## 脱敏规则

所有包含以下关键字的字段值会被自动脱敏：

- TOKEN、KEY、SECRET、PASSWORD、COOKIE、ACCOUNT、BROKER

脱敏格式：保留前2位和后2位，中间用 `****` 替代。例如 `my_secret_key_123` → `my****23`。

堆栈跟踪也会进行脱敏处理，移除可能包含的敏感值。

## 创建 Bug 报告

```python
from src.product_app.feedback import get_feedback_service

service = get_feedback_service()

bug_id = service.write_bug_report(
    component="data_gateway",
    title="实时行情获取超时",
    summary="在交易时段获取 002463 实时行情时，请求超时超过30秒",
    severity="high",
    user_action="查看沪电股份实时行情",
    endpoint_or_page="/api/quotes/realtime/002463",
    exception_type="TimeoutError",
    exception_message="Request to akshare timed out after 30s",
    reproduction_steps=[
        "打开实时行情页面",
        "搜索 002463",
        "等待行情加载",
    ],
)
```

## 自动处理 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/product/feedback/{bug_id}/analysis` | GET | 获取 Bug 分析报告和修复方案 |
| `/product/feedback/{bug_id}/approve` | POST | 审批通过修复方案，自动执行修复 |
| `/product/feedback/{bug_id}/reject` | POST | 拒绝修复方案 |
| `/product/feedback/{bug_id}/fix-status` | GET | 获取 Bug 修复进度 |
