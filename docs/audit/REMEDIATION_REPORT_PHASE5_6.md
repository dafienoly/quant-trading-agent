# Phase 5.6 审计整改报告

**审计报告**: AUDIT_REPORT_PHASE5_6.md
**整改日期**: 2026-06-10
**整改人**: 开发团队

---

## 整改总览

| 级别 | 问题数 | 已修复 | 状态 |
|------|--------|--------|------|
| MUST (M) | 2 | 2 | 全部完成 |
| SHOULD (S) | 0 | 0 | - |
| LOW (L) | 5 | 5 | 全部完成 |
| 审计建议 | 1 | 1 | 全部完成 |
| **合计** | **8** | **8** | **全部完成** |

---

## MUST 级别修复

### M1: `analyzing→open` 状态转换缺失，API 不可用时 Bug 卡死

**问题描述**: `VALID_TRANSITIONS["analyzing"]` 仅允许 `["proposed", "blocked"]`，当 DeepSeek API 不可用时 `analyze()` 返回 error，`process_bug()` 尝试回退到 `open` 状态但转换被拒绝，导致 Bug 永久卡在 `analyzing` 状态无法恢复。

**根因**: 状态机设计时未考虑分析失败需要回退的场景，`analyzing` 状态缺少回到 `open` 的出口。

**修复方案**: `VALID_TRANSITIONS["analyzing"]` 增加 `"open"` 允许回退：
```python
# 修复前
"analyzing": ["proposed", "blocked"],

# 修复后
"analyzing": ["proposed", "blocked", "open"],
```

**修复文件**: `src/product_app/bug_fix_workflow.py` (VALID_TRANSITIONS 定义)

**验证**: `process_bug()` 在 DeepSeek API 返回 error 时，Bug 状态正确回退到 `open`，不再卡死

---

### M2: `git add -A` 暂存所有变更，可能误提交无关文件

**问题描述**: `_execute_and_verify()` 使用 `git add -A` 暂存所有文件变更，如果工作区中存在用户正在编辑的其他文件，这些无关变更也会被一并提交到自动修复的 commit 中。

**根因**: 修复执行后直接 `git add -A`，未区分修复涉及的文件和无关文件。

**修复方案**: 改为仅暂存修复涉及的文件，遍历 `proposal.code_changes` 逐个 `git add`：
```python
# 修复前
subprocess.run(["git", "add", "-A"], cwd=str(_PROJECT_ROOT), ...)

# 修复后
code_changes = proposal.get("code_changes", [])
for change in code_changes:
    file_path = change.get("file_path", "")
    if file_path:
        subprocess.run(["git", "add", file_path], cwd=str(_PROJECT_ROOT), ...)
```

**修复文件**: `src/product_app/bug_fix_workflow.py` (_execute_and_verify 方法)

**验证**: 修复提交仅包含 `code_changes` 中指定的文件，无关文件不会被暂存

---

## LOW 级别修复

### L1: `test_bug_auto_fix.py` 6 个未使用 import (ruff F401)

**问题描述**: ruff 静态检查发现测试文件中 6 个导入未被使用：`os`、`subprocess`、`threading`、`Any`、`BugReport`、`FeedbackService`。

**修复方案**: 移除所有未使用导入：
```python
# 修复前
import json
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.product_app.bug_fix_agent import BugFixAgent
from src.product_app.bug_fix_workflow import BugFixWorkflow
from src.product_app.bug_watchdog import BugWatchdog
from src.product_app.feedback import BugReport, FeedbackService

# 修复后
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.product_app.bug_fix_agent import BugFixAgent
from src.product_app.bug_fix_workflow import BugFixWorkflow
from src.product_app.bug_watchdog import BugWatchdog
```

**修复文件**: `tests/test_bug_auto_fix.py`

**验证**: `ruff check` 零错误

---

### L2: `_update_bug_report()` 访问 FeedbackService 私有方法

**问题描述**: `BugFixWorkflow._update_bug_report()` 直接调用 `self.feedback_service._render_markdown(report)`，违反封装原则，且在 L2 修复后 `_update_bug_report()` 整体逻辑与 FeedbackService 内部实现耦合过深。

**修复方案**: 在 `FeedbackService` 中新增公开方法 `update_bug_fields()`，封装查找→更新字段→写回 JSON→重新渲染 Markdown 的完整流程：

```python
# FeedbackService 新增公开方法
def update_bug_fields(self, bug_id: str, **fields) -> bool:
    """更新 Bug 报告的指定字段并重新渲染 Markdown"""
    source_dir, report = self._find_bug(bug_id)
    if report is None:
        return False
    for key, value in fields.items():
        if hasattr(report, key):
            setattr(report, key, value)
    report.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 写回 JSON + 重新渲染 Markdown
    ...
    return True

# BugFixWorkflow._update_bug_report 简化为
def _update_bug_report(self, bug_id: str, **fields) -> bool:
    return self.feedback_service.update_bug_fields(bug_id, **fields)
```

**修复文件**: `src/product_app/feedback.py` (新增方法) + `src/product_app/bug_fix_workflow.py` (简化调用)

**验证**: 21/21 测试通过，所有 `_MockFeedbackService` 已同步添加 `update_bug_fields` 方法

---

### L3: API 端点每次创建新 BugFixWorkflow 实例

**问题描述**: 4 个新增 API 端点（analysis/approve/reject/fix-status）各自 `BugFixWorkflow()` 创建新实例，每次都重新初始化 FeedbackService 和 BugFixAgent，浪费资源且无法共享状态。

**修复方案**: 新增 `_get_bug_fix_workflow()` 模块级单例函数，4 个端点共享同一实例：
```python
def _get_bug_fix_workflow():
    """获取共享的 BugFixWorkflow 单例"""
    from src.product_app.bug_fix_workflow import BugFixWorkflow
    if not hasattr(_get_bug_fix_workflow, "_instance"):
        _get_bug_fix_workflow._instance = BugFixWorkflow()
    return _get_bug_fix_workflow._instance
```

**修复文件**: `src/api/product_routes.py`

**验证**: API 端点调用共享同一 BugFixWorkflow 实例

---

### L4: `_execute_and_verify()` 不检查 git stash 结果

**问题描述**: 当工作区无变更时 `git stash` 输出 "No local changes to save"，此时执行 `git stash pop` 会恢复错误的 stash 条目（可能是之前遗留的），导致意外变更。

**修复方案**: 记录 `stashed` 标志，仅在 stash 确实保存了变更时才执行 `git stash pop`：
```python
# 记录 stash 是否实际保存了变更
stash_result = subprocess.run(["git", "stash"], ...)
stashed = "No local changes to save" not in (stash_result.stdout or "")

# 修复失败回滚时条件执行
if stashed:
    subprocess.run(["git", "stash", "pop"], ...)
```

**修复文件**: `src/product_app/bug_fix_workflow.py` (_execute_and_verify 方法)

**验证**: 工作区无变更时不会执行 stash pop

---

### L5: `execute_fix()` 运行全部测试，改为仅运行相关测试

**问题描述**: `_run_tests()` 执行 `pytest -x` 运行全量测试套件，修复一个小 Bug 可能触发大量无关测试失败（如其他模块的已知问题），导致修复被误判为失败并回滚。

**修复方案**: `_run_tests()` 新增 `code_changes` 参数，根据修改文件路径推断相关测试文件并优先运行：
```python
def _run_tests(self, code_changes: list | None = None) -> dict[str, Any]:
    test_args = ["python", "-m", "pytest", "-x", "--tb=short"]

    # 根据修改文件选择相关测试
    if code_changes:
        test_paths = set()
        for change in code_changes:
            file_path = change.get("file_path", "")
            parts = file_path.replace("\\", "/").split("/")
            if len(parts) >= 2:
                module = parts[-2]  # e.g. "product_app"
                test_file = self.project_root / "tests" / f"test_{module}.py"
                if test_file.exists():
                    test_paths.add(str(test_file))
        if test_paths:
            test_args.extend(sorted(test_paths))
    ...
```

**修复文件**: `src/product_app/bug_fix_agent.py` (_run_tests + execute_fix)

**验证**: 修复 `product_app` 模块时仅运行 `tests/test_product_app.py`（如存在），否则回退全量测试

---

## 审计建议修复

### 补充: `execution_engine` 纳入受限模块

**问题描述**: 审计报告建议将 `execution_engine`（订单执行引擎）纳入自动修复的受限模块列表，防止 BugFix Agent 自动修改交易执行逻辑，避免产生错误交易。

**修复方案**: `_BLOCKED_PATTERNS` 增加 `"execution_engine"`：
```python
# 修复前
_BLOCKED_PATTERNS = ("risk_engine", "trading_log", "backtest_report")

# 修复后
_BLOCKED_PATTERNS = ("risk_engine", "execution_engine", "trading_log", "backtest_report")
```

**修复文件**: `src/product_app/bug_fix_agent.py` (_BLOCKED_PATTERNS 常量)

**验证**: `_is_blocked_module()` 正确拦截包含 `execution_engine` 路径的修复方案

---

## 测试验证结果

### pytest 集成测试

```
tests/test_bug_auto_fix.py — 21 passed, 1 warning
```

| 测试类 | 测试数 | 结果 |
|--------|--------|------|
| TestBugFixAgent | 8 | 8 passed |
| TestBugFixdog | 3 | 3 passed |
| TestBugFixWorkflow | 6 | 6 passed |
| TestBugFixAPIEndpoints | 4 | 4 passed |

### ruff 代码检查

```
All checks passed!
```

### 整改引入的额外修复

整改过程中发现并修复了以下额外问题：

| # | 问题 | 修复 |
|---|------|------|
| 1 | `_MockFeedbackService` 缺少 `update_bug_fields` 方法导致 3 个测试失败 | 6 个 mock 类全部添加 `update_bug_fields` 方法 |
| 2 | `_get_bug_fix_workflow()` 单例缓存导致 API 测试 mock 注入失败 | 测试中清除单例缓存 `delattr(_get_bug_fix_workflow, "_instance")` |
| 3 | `bug_fix_workflow.py` 中 `datetime` 导入未使用 (ruff F401) | 移除未使用导入 |

---

## 修改文件清单

| # | 文件 | 修改类型 | 涉及问题 |
|---|------|----------|---------|
| 1 | `src/product_app/bug_fix_workflow.py` | 修改 | M1: 状态转换 + M2: git add + L2: 公开方法 + L4: stash 检查 + 移除未使用导入 |
| 2 | `src/product_app/bug_fix_agent.py` | 修改 | L5: 相关测试 + 补充: execution_engine 受限 |
| 3 | `src/product_app/feedback.py` | 修改 | L2: 新增 update_bug_fields 公开方法 |
| 4 | `src/api/product_routes.py` | 修改 | L3: 单例函数 |
| 5 | `tests/test_bug_auto_fix.py` | 修改 | L1: 移除未使用导入 + mock 类同步更新 |

---

## 结论

Phase 5.6 审计报告中 2 个 MUST 级别和 5 个 LOW 级别问题以及 1 项审计建议，共计 8 项全部修复完成。整改过程中额外发现并修复了 3 项关联问题。全部 21 项集成测试通过，ruff 代码检查零错误。BUG 自动处理系统功能完整，状态机流转健壮，安全约束完备。
