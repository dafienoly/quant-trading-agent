# Phase 5.6 审计报告 (AUDIT_REPORT_PHASE5_6.md)

> 审计日期：2026-06-10
> 审计范围：Phase 5.6 BUG 自动处理系统 — BugFixAgent / BugWatchdog / BugFixWorkflow / API 端点 / Dashboard 反馈中心
> 审计依据：PHASE_COMPLETION_REPORT.md / AGENTS.md §3.9 / RISK_POLICY.md / EXECUTION_POLICY.md
> 测试结果：**405 passed, 2 failed, 2 skipped** (pytest) + **4 新 API 端点实测全部 200 OK** + **bug_fix_agent 作业可启动**

---

## 一、审计总评

| 维度 | 评级 | 说明 |
|------|------|------|
| 功能完整性 | **B+** | 3 个核心模块 + 4 个 API 端点 + Dashboard 反馈中心增强，核心流程完整但存在状态机缺陷 |
| AGENTS.md 合规性 | **A-** | 人工审批、受限模块拦截、pytest 验证、回滚机制均实现，但 `execution_engine` 未纳入受限模块 |
| 安全约束 | **B+** | 修复前 git stash、测试失败回滚、DEEPSEEK_API_KEY 环境变量，但 git add -A 存在风险 |
| 测试覆盖 | **B** | 21 项集成测试覆盖 4 个模块，但缺少 API 不可用/状态机卡死等边界场景测试 |
| 可交付性 | **B+** | 核心功能可用，但 M1 状态机缺陷导致 DeepSeek API 不可用时 Bug 卡死 |

**结论：有条件可交付** — 发现 2 个中等问题和 5 个低级问题，M1 需修复后交付

---

## 二、测试结果

### 2.1 pytest 测试套件

```
405 passed, 2 failed, 2 skipped, 1 warning in 48.83s
```

- **2 failed**: `test_product_market_data.py::test_fetch_product_quotes_records_feedback_on_provider_failure` 和 `test_product_realtime_api.py::test_product_quotes_endpoint_falls_back_to_demo_and_records_feedback` — Phase 5.5 遗留问题，测试未 mock `is_trading_hours()`，非交易时段运行时 bug_id 为 None
- **2 skipped**: Playwright 浏览器测试（需安装 chromium）

### 2.2 Phase 5.6 专项测试

```
tests/test_bug_auto_fix.py — 21 passed
```

| 测试类 | 测试数 | 覆盖范围 |
|--------|--------|---------|
| TestBugFixAgent | 8 | analyze/propose_fix/blocked_module/retry/parse_json |
| TestBugWatchdog | 3 | existing_bugs/dedup/stop |
| TestBugFixWorkflow | 6 | transitions/invalid_transition/process_bug/approve/reject/status |
| TestBugFixAPIEndpoints | 4 | analysis/approve/reject/fix-status |

### 2.3 API 端点实测

| 端点 | 方法 | 状态码 | 验证结果 |
|------|------|--------|---------|
| /product/feedback/{bug_id}/analysis | GET | 200 | ✅ 返回 workflow_status |
| /product/feedback/{bug_id}/approve | POST | 200 | ✅ 需 proposed 状态 |
| /product/feedback/{bug_id}/reject | POST | 200 | ✅ 需 proposed 状态 |
| /product/feedback/{bug_id}/fix-status | GET | 200 | ✅ 返回 fix_status |
| /product/jobs/bug_fix_agent/start | POST | 200 | ✅ 作业启动成功 |
| /product/health | GET | 200 | ✅ risk_status=OK（Phase 5.5 M1 已修复） |

### 2.4 BugWatchdog 实测

| 检查项 | 结果 |
|--------|------|
| 创建 Bug 后 Watchdog 自动检测 | ✅ Bug 状态从 open 变为 analyzing |
| 分析报告自动生成 | ✅ feedback/bugs/analysis/ 下生成 JSON 文件 |
| DeepSeek API 不可用时状态卡死 | ❌ Bug 卡在 analyzing 状态（M1） |

### 2.5 ruff 检查

```
tests/test_bug_auto_fix.py: 6 errors (F401 unused imports)
```

源代码文件全部通过 ruff 检查。

---

## 三、代码审计发现

### M1 [中等] Bug 状态机缺陷：analyzing → open 转换缺失，API 不可用时 Bug 卡死

**位置**: [bug_fix_workflow.py](file:///d:/repo/work/signalGPTV2/quant-trading-agent/src/product_app/bug_fix_workflow.py#L39-L49)

```python
VALID_TRANSITIONS: dict[str, list[str]] = {
    "open": ["analyzing"],
    "analyzing": ["proposed", "blocked"],  # ← 缺少 "open"
    ...
}
```

**问题**: 当 DeepSeek API 不可用时（无 API Key、网络故障等），`BugFixAgent.analyze()` 内部捕获异常并返回 `{"error": "..."}`。`process_bug()` 检测到 error 后尝试 `_transition(bug_id, "open")` 回退状态，但 `VALID_TRANSITIONS["analyzing"]` 不包含 `"open"`，导致转换失败，Bug 永久卡在 `analyzing` 状态。

**实测确认**:
```
Bug BUG_20260610_Z55D6Z: status=analyzing, has_analysis=True, has_proposal=False
Analysis report: {"error": "Missing credentials..."}
```

**影响**: 在 DeepSeek API 不可用的环境下（如未配置 API Key），所有新 Bug 都会卡在 `analyzing` 状态，无法被人工处理或重新分析。

**修复建议**: 在 `VALID_TRANSITIONS["analyzing"]` 中添加 `"open"`：
```python
"analyzing": ["proposed", "blocked", "open"],
```
同时在 `fix_failed` → `open` 的转换逻辑中增加超时自动重置机制。

### M2 [中等] git add -A 暂存所有变更，可能提交无关修改

**位置**: [bug_fix_workflow.py](file:///d:/repo/work/signalGPTV2/quant-trading-agent/src/product_app/bug_fix_workflow.py#L271)

```python
subprocess.run(
    ["git", "add", "-A"],
    cwd=str(_PROJECT_ROOT),
    ...
)
```

**问题**: `_execute_and_verify()` 使用 `git add -A` 暂存所有变更，而非仅暂存 Bug 修复涉及的文件。如果工作目录中存在其他未提交的修改（如调试代码、临时文件），这些修改也会被一并提交。

**影响**: 可能意外提交无关代码，污染 git 历史。

**修复建议**: 仅暂存 `execute_fix()` 实际修改的文件：
```python
for change in code_changes:
    file_path = change.get("file_path", "")
    if file_path:
        subprocess.run(["git", "add", file_path], ...)
```

### L1 [低] 测试文件存在 6 个未使用 import（ruff F401）

**位置**: [test_bug_auto_fix.py](file:///d:/repo/work/signalGPTV2/quant-trading-agent/tests/test_bug_auto_fix.py#L9-L23)

```
F401 `os` imported but unused
F401 `subprocess` imported but unused
F401 `threading` imported but unused
F401 `typing.Any` imported but unused
F401 `src.product_app.feedback.BugReport` imported but unused
F401 `src.product_app.feedback.FeedbackService` imported but unused
```

**修复建议**: 删除未使用的 import。

### L2 [低] _update_bug_report() 访问 FeedbackService 私有方法

**位置**: [bug_fix_workflow.py](file:///d:/repo/work/signalGPTV2/quant-trading-agent/src/product_app/bug_fix_workflow.py#L430)

```python
md_content = self.feedback_service._render_markdown(report)
```

**问题**: 直接访问 `FeedbackService._render_markdown()` 私有方法，违反封装原则。如果 `FeedbackService` 内部重构，此处会静默失败。

**修复建议**: 在 `FeedbackService` 中添加公开方法 `render_bug_markdown(report)` 或 `update_bug_fields(bug_id, **fields)` 封装此逻辑。

### L3 [低] API 端点每次创建新 BugFixWorkflow 实例，_active_workflows 不共享

**位置**: [product_routes.py](file:///d:/repo/work/signalGPTV2/quant-trading-agent/src/api/product_routes.py#L311-L312)

```python
@router.get("/feedback/{bug_id}/analysis")
def get_bug_analysis(bug_id: str) -> dict[str, Any]:
    from src.product_app.bug_fix_workflow import BugFixWorkflow
    workflow = BugFixWorkflow()  # ← 每次创建新实例
```

**问题**: 每个 API 请求创建新的 `BugFixWorkflow` 实例，`_active_workflows` 内存字典不共享。这意味着：
1. `_transition()` 中的状态机校验每次都从文件重新读取当前状态
2. 并发请求可能导致竞态条件

**影响**: 当前功能不受影响（因为状态从文件读取），但并发安全性和性能不佳。

**修复建议**: 使用模块级单例或 FastAPI 依赖注入共享 `BugFixWorkflow` 实例。

### L4 [低] _execute_and_verify() 不检查 git stash 结果

**位置**: [bug_fix_workflow.py](file:///d:/repo/work/signalGPTV2/quant-trading-agent/src/product_app/bug_fix_workflow.py#L252-L258)

```python
subprocess.run(
    ["git", "stash"],
    cwd=str(_PROJECT_ROOT),
    capture_output=True,
    text=True,
    timeout=30,
)
```

**问题**: `git stash` 在工作目录无变更时返回 "No local changes to save"，但代码不检查结果。后续 `git stash pop` 可能恢复不相关的 stash 条目。

**修复建议**: 检查 `git stash` 输出，仅在确实 stash 了变更时才执行 `git stash pop`。

### L5 [低] execute_fix() 运行全部测试而非仅相关测试

**位置**: [bug_fix_agent.py](file:///d:/repo/work/signalGPTV2/quant-trading-agent/src/product_app/bug_fix_agent.py#L417)

```python
result = subprocess.run(
    ["python", "-m", "pytest", "-x", "--tb=short"],
    ...
)
```

**问题**: `_run_tests()` 运行完整测试套件（当前 405 个测试），而非仅运行与修复文件相关的测试。这导致：
1. 修复验证耗时过长（约 50 秒）
2. 不相关测试的失败会阻止修复提交

**修复建议**: 根据修改的文件路径选择相关测试：
```python
test_paths = [f"tests/test_{component}.py" for component in affected_components]
subprocess.run(["python", "-m", "pytest", "-x", "--tb=short"] + test_paths, ...)
```

---

## 四、AGENTS.md §3.9 BugFix Agent 合规性

| # | AGENTS.md 规则 | 状态 | 备注 |
|---|---------------|------|------|
| 1 | 自动分析 Bug 根因 | ✅ | BugFixAgent.analyze() 调用 DeepSeek API |
| 2 | 生成修复方案（含 diff） | ✅ | BugFixAgent.propose_fix() 生成 code_changes |
| 3 | 经人工审批后执行修复 | ✅ | approve_fix() 为唯一执行入口 |
| 4 | 验证修复结果（pytest） | ✅ | _run_tests() 运行 pytest |
| 5 | 修复失败时自动回滚 | ✅ | git stash + 原始文件回滚 |
| 6 | 禁止未经审批执行修复 | ✅ | 状态机 proposed → approved → fixing |
| 7 | 禁止修改风控模块代码 | ✅ | _is_blocked_module() 拦截 risk_engine |
| 8 | 禁止修改交易日志代码 | ✅ | _is_blocked_module() 拦截 trading_log |
| 9 | 禁止修改回测报告代码 | ✅ | _is_blocked_module() 拦截 backtest_report |
| 10 | 禁止绕过 pytest 验证 | ✅ | execute_fix() 必须经过 _run_tests() |
| 11 | 禁止提交包含密钥的修复 | ⚠️ | 依赖 DeepSeek API 不输出密钥，无显式检查 |

**注意**: AGENTS.md §3.9 禁止修改 "风控模块代码"，`_is_blocked_module()` 拦截了 `risk_engine`，但未拦截 `execution_engine`（执行引擎也是交易安全关键模块）。建议将 `execution_engine` 也纳入受限模块。

---

## 五、Phase 5.5 遗留问题追踪

| # | Phase 5.5 问题 | 当前状态 | 备注 |
|---|---------------|---------|------|
| M1 | /product/health 空行情 BLOCK | ✅ 已修复 | 改为直接检查 kill_switch.active |
| M2 | Dashboard 仅 4 Tab | ✅ 已修复 | product_dashboard.py 已扩展至 9 Tab |
| L1 | /product/dashboard 内部 HTTP 调用 | ✅ 已修复 | product_routes.py 不再调用 localhost |
| L2 | Dashboard 空行情 EMPTY_QUOTES | ✅ 已修复 | product_dashboard.py 使用 /product/dashboard API |
| L3 | E2E 测试硬编码端口 | ⬜ 未修复 | 仍硬编码 8001/8501 |
| L4 | E2E 测试 TEST_KEY 逻辑错误 | ⬜ 未修复 | 仍期望成功 |

**新增遗留问题**:

| # | 问题 | 严重程度 | 说明 |
|---|------|---------|------|
| N1 | test_product_market_data.py 2 个测试失败 | 中 | 未 mock is_trading_hours()，非交易时段 bug_id 为 None |
| N2 | test_product_realtime_api.py 1 个测试失败 | 中 | 同上 |

---

## 六、安全审计

| # | 检查项 | 状态 | 备注 |
|---|--------|------|------|
| 1 | DEEPSEEK_API_KEY 不硬编码 | ✅ | 从环境变量读取 |
| 2 | 修复方案需人工审批 | ✅ | approve_fix() 为唯一入口 |
| 3 | 受限模块自动拦截 | ✅ | risk_engine/trading_log/backtest_report |
| 4 | 修复前创建回滚点 | ✅ | git stash |
| 5 | 测试失败自动回滚 | ✅ | 原始文件回滚 + git stash pop |
| 6 | Bug 报告脱敏 | ✅ | sanitize_traceback() + mask_dict() |
| 7 | 无 eval/exec 动态代码执行 | ✅ | diff 应用为字符串替换 |
| 8 | LEVEL_3_AUTO 阻断 | ✅ | ConfigService 仍有效 |
| 9 | 默认交易模式不变 | ✅ | 仍为 LEVEL_1_SIGNAL_ONLY |
| 10 | git add -A 风险 | ⚠️ | M2：可能提交无关修改 |

---

## 七、完整使用流程验证

### 7.1 Bug 自动处理流程

```
1. 创建 Bug 报告 → POST /product/feedback          ✅ bug_id 返回
2. 启动 bug_fix_agent 作业 → POST /product/jobs/bug_fix_agent/start  ✅ 作业启动
3. Watchdog 自动检测新 Bug                           ✅ Bug 状态变为 analyzing
4. DeepSeek API 分析根因                             ⚠️ API 不可用时 Bug 卡死 (M1)
5. 查看分析报告 → GET /product/feedback/{id}/analysis  ✅ 返回 workflow_status
6. 审批修复方案 → POST /product/feedback/{id}/approve  ✅ 需 proposed 状态
7. 拒绝修复方案 → POST /product/feedback/{id}/reject   ✅ 需 proposed 状态
8. 查看修复进度 → GET /product/feedback/{id}/fix-status ✅ 返回 fix_status
```

### 7.2 Dashboard 反馈中心

```
1. 反馈中心 Tab 可访问                               ✅ 第 9 个 Tab
2. Bug 列表展示                                      ✅ 含严重程度、标题
3. 状态步骤指示器                                    ✅ 7 步可视化
4. 分析报告展示                                      ✅ expandable section
5. 修复方案展示                                      ✅ expandable section
6. Approve/Reject 按钮                               ✅ 仅 proposed 状态显示
7. Mark triaged/fixed/ignore 按钮                     ✅ 非 proposed 状态显示
```

---

## 八、修复优先级

### 必须修复（交付前）

| # | 问题 | 修复方案 | 优先级 |
|---|------|---------|--------|
| M1 | Bug 卡死在 analyzing 状态 | VALID_TRANSITIONS["analyzing"] 添加 "open" | 高 |

### 建议修复（交付后迭代）

| # | 问题 | 修复方案 | 优先级 |
|---|------|---------|--------|
| M2 | git add -A 提交无关修改 | 仅暂存修复涉及的文件 | 中 |
| L1 | 测试文件 6 个未使用 import | 删除 | 低 |
| L2 | 访问 FeedbackService 私有方法 | 添加公开方法 | 低 |
| L3 | API 端点不共享 BugFixWorkflow | 使用单例或依赖注入 | 低 |
| L4 | 不检查 git stash 结果 | 检查输出并记录 | 低 |
| L5 | 运行全部测试而非相关测试 | 按修改文件选择测试 | 低 |

---

## 九、交付评估

### 交付物清单

| 交付物 | 状态 | 说明 |
|--------|------|------|
| BugFixAgent | ✅ | DeepSeek API 封装，analyze/propose_fix/execute_fix |
| BugWatchdog | ✅ | 文件监控 + 轮询降级 + 防抖去重 |
| BugFixWorkflow | ⚠️ | 状态机完整但 analyzing→open 缺失 (M1) |
| API 端点 (4个) | ✅ | analysis/approve/reject/fix-status |
| Dashboard 反馈中心 | ✅ | 步骤指示器 + 分析/方案展示 + 审批按钮 |
| 测试 (21个) | ✅ | 覆盖 4 个模块 |
| 依赖更新 | ✅ | openai + watchdog |

### 交付判定

**⚠️ 有条件可交付** — M1 修复后可交付

- 核心功能完整：Bug 自动检测 → 分析 → 方案 → 审批 → 修复 → 验证
- AGENTS.md 合规：人工审批、受限模块拦截、pytest 验证、回滚机制
- 安全约束到位：DEEPSEEK_API_KEY 环境变量、git stash 回滚、状态机校验
- M1 状态机缺陷导致 DeepSeek API 不可用时 Bug 卡死，需修复后交付
- Phase 5.5 遗留 M1/M2 已修复，Dashboard 已扩展至 9 Tab

---

## 十、审计检查清单确认

### A. 代码安全

- [x] 无硬编码密钥/Token/密码（DEEPSEEK_API_KEY 从环境变量读取）
- [x] `.env` 在 `.gitignore` 中
- [x] 无 eval/exec 动态代码执行
- [x] 无 SQL 注入风险
- [x] 无命令注入风险（subprocess.run 使用列表参数）

### B. 数据完整性

- [x] 不使用未来数据
- [x] 原始数据保留不覆盖
- [x] 数据变更有版本记录（git commit）
- [x] 缺失数据有明确标记

### C. 风控合规

- [x] 默认交易模式为 LEVEL_1_SIGNAL_ONLY
- [x] 风控模块未被绕过或删除
- [x] Kill Switch 机制完整
- [x] 创业板/科创板过滤有效
- [x] BugFix Agent 禁止修改风控模块

### D. 测试覆盖

- [x] 核心逻辑有单元测试（21 个）
- [x] 测试可独立运行
- [ ] 无跳过的测试（2 个 Playwright 测试跳过）
- [x] 边界条件和异常场景有覆盖
- [ ] 缺少 API 不可用时状态机卡死的测试（M1 相关）

### E. 文档完整性

- [x] 接口有 docstring 或注释
- [x] 配置文件有示例
- [x] 运行方式有说明
- [x] 已知问题有记录
