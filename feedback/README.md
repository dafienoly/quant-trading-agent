# Bug 报告系统

## 目录结构

```
feedback/
├── README.md              # 本文档
├── index.json             # Bug 索引（自动维护）
└── bugs/
    ├── open/              # 新建/未处理的 Bug
    ├── triaged/           # 已分类/已分配的 Bug
    ├── fixed/             # 已修复的 Bug
    └── ignored/           # 已忽略的 Bug
```

## Bug 报告生命周期

```
  [创建] → open → triaged → fixed
                    └→ ignored
```

### 状态说明

| 状态 | 目录 | 说明 |
|------|------|------|
| `open` | `bugs/open/` | 新创建的 Bug，等待开发人员分类 |
| `triaged` | `bugs/triaged/` | 已确认并分类，已分配给开发人员 |
| `fixed` | `bugs/fixed/` | 已修复，等待验证 |
| `ignored` | `bugs/ignored/` | 已评估但不予处理（非 Bug / 重复 / 低优先级） |

### 状态流转规则

1. **open → triaged**：开发人员确认 Bug 有效，分配严重程度和负责人
2. **triaged → fixed**：开发人员完成修复
3. **triaged → ignored**：评估后决定不处理，需记录原因
4. **open → ignored**：直接确认为非 Bug 或重复问题

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

### 4. 修复验证

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
