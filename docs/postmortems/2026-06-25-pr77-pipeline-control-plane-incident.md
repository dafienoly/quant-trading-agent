# PR #77 Pipeline 控制面事故报告

## 事故结论

本次事故为 S1 流程可靠性缺陷。PR #77 的 Agent 输出并非唯一问题，GitHub Actions 控制面同时存在重复触发、过期任务继续执行、门禁结论互相矛盾、测试副作用污染分支和报告校验生命周期错位。此前将单次 Action 成功视为“Pipeline 已跑通”是不充分的验收结论。

## 用户影响

- 同一阶段可能被 label 事件和显式 dispatch 同时启动。
- Tester 已给出 `REJECTED` 时，旧队列或错误路由仍可能继续进入 Developer 或 Team Lead。
- `phase_dev_gate` 显示 `PASS`，但交付门禁显示没有实现代码时，流程仍可能推进或输出矛盾日志。
- Tester 执行测试后生成 `feedback/index.json`，被原分支路径保护器判定为越权修改，导致测试命令结束后失败。
- PR 轻量验证把中间阶段报告当成最终验收报告，造成持续红灯。

## 直接证据

1. `agent-stage-runner.yml` 同时监听 `pull_request:labeled` 和 `workflow_dispatch`，阶段推进又同时添加 label 并显式 dispatch。
2. 原并发键包含阶段名，同一 PR 的相邻阶段不会互斥。
3. 原流程仅从报告 gate 读取 `gate_passed`，没有把 `phase_dev_delivery_gate.json` 纳入一个原子结论。
4. 原流程在组合判断前执行 `sync-state-from-gates`，可能先推进状态再发现交付失败。
5. PR #77 Tester 运行记录显示 `feedback/index.json` 触发 “modified a disallowed path”。
6. PR #77 Phase 5 在 team plan 中明确为“无代码变更；仅文档与回归”，通用交付门禁却强制要求实现文件和测试文件。

## 根因

### 控制面缺少单一事实来源

label、workflow dispatch、gate JSON 和 state JSON 都可以推动流程，但没有事务控制器统一判断“当前允许哪个阶段执行、哪些证据共同构成通过”。

### 验收只覆盖静态路径

既有测试验证了 workflow 中存在某些命令，却没有验证触发器数量、同一 PR 并发语义、过期队列、矛盾 gate 和 Tester 真实副作用。

### 阶段与最终交付规则混用

阶段报告、最终验收报告和 docs-only 阶段使用了同一套静态规则，导致合法中间态被判失败。

## 修复措施

1. Stage Runner 只接受 `workflow_dispatch`，label 仅作可见状态。
2. 并发键只按 PR 编号分组，`cancel-in-progress=false`，保证同一 PR 串行。
3. Agent 执行前验证 `.agent/state.json.current_stage` 与请求阶段一致，拒绝旧队列。
4. 新增组合 transition gate；Developer 必须同时通过报告 gate 和交付 gate。
5. 组合 gate 通过后才同步状态；Developer 自身失败不自动自循环。
6. `feedback/index.json` 改为运行时文件并停止跟踪，Tester 路径校验前进行防御性清理。
7. PR 报告门禁区分 Pipeline 进行中与最终验收状态。
8. team plan 明确声明的 docs-only 阶段按文档交付规则验证。

## 防复发验证

- 静态测试断言 Stage Runner 不再监听 `pull_request` 或读取 label 事件。
- 单元测试覆盖 stale stage lease、报告通过但交付失败、Tester 驳回路由和 docs-only 阶段。
- 报告门禁测试覆盖中间阶段报告通过、最终验收占位报告失败。
- Pipeline 回归脚本检查单入口、PR 级串行和组合 gate 标记。

## 安全确认

修复只涉及 Agent Pipeline、报告治理和运行时反馈索引，不涉及真实交易、风控放行、股票池、订单执行或自动合并 main。

## 最终结论

事故根因已定位为控制面设计缺陷，不能用重复重跑规避。必须完成本报告列出的事务化修复并在远端以独立 hotfix PR 验证后，才能恢复 PR #77 自动阶段调度。
