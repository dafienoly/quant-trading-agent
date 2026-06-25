# pipeline-transaction-controller-hotfix Requirements

## User Goal

彻底修复 PR #77 暴露的重复调度、错误推进和持续红灯问题，使 Pipeline 根据真实开发与测试证据可靠推进。

## Functional Requirements

1. Stage Runner 必须只有一个自动执行入口。
2. 同一 PR 的阶段必须串行，过期阶段请求必须在 Agent 执行前失败关闭。
3. Developer 阶段必须同时通过报告门禁和真实交付门禁。
4. Tester `REJECTED` 只能按重试预算返回 Developer，不能越过到 Team Lead Review。
5. Tester 运行时索引不得污染原开发分支。
6. PR 报告校验必须区分中间阶段与最终验收阶段。
7. team plan 明确声明的纯文档回归阶段不得被错误要求新增业务代码。
8. 失败时保留诊断 artifact，不自动合并 main。

## Non-functional Requirements

- 所有路由判断必须由仓库内确定性 Python 逻辑完成。
- 关键控制行为必须有自动化测试。
- 用户可见报告使用中文。

## Acceptance Criteria

- Pipeline 聚焦测试、报告治理测试和严格回归全部通过。
- workflow 不含 label 触发 Stage Runner 的路径。
- 矛盾 gate 不会推进状态。
- `feedback/index.json` 不再被 Git 跟踪。
- PR #77 恢复前先通过独立 hotfix PR 的远端验证。

## Safety Constraints

- 不触碰交易敏感模块。
- 不启用真实交易。
- 不自动合并 main。
- 不通过放宽测试或伪造 gate 制造成功。
