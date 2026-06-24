# Pipeline 交付证据与失败路由 Hotfix 需求

## 用户目标

修复 V16.1 自动开发过程中出现的假完成问题：Developer 仅生成开发报告但没有实现代码，
Tester 已给出 `REJECTED`，Pipeline 却仍进入 Team Lead 和后续 Review。开发执行者改为
OpenCode DeepSeek V4 Flash `max`，并继续强制使用 superpowers。

## 功能需求

1. Developer 阶段必须验证真实 diff，非文档任务至少包含实现文件和测试文件。
2. 开发报告“变更范围”中声称的仓库路径必须存在，并出现在本阶段未提交 diff 中。
3. `phase_dev` gate 必须依赖独立的交付证据 gate，不能只检查开发报告存在。
4. Test、Lead Review、Codex Review、Acceptance 报告必须解析明确最终结论。
5. `REJECTED`、`CHANGES_REQUESTED`、`BLOCKED` 必须 fail closed，并路由回责任阶段。
6. 失败报告、gate 和 feedback Bug 文件必须先提交，再执行退回路由；Actions 保持失败状态。
7. gate 的 `feature_id` 必须与当前任务一致，陈旧 gate 不得污染新任务状态。
8. Team Plan 中的阶段总数必须进入状态；完成单个 phase 不得冒充全部阶段完成。
9. Developer 改用 `opencode-go/deepseek-v4-flash`、`variant=max`、OpenCode build Agent 和
   superpowers；兼容 stage ID `claude_developer` 暂不变更。

## 验收标准

- 仅开发报告、无实现 diff 时，Developer gate 失败。
- 报告声称文件不存在或未变更时，Developer gate 失败。
- Tester 报告为 `REJECTED` 时，不得进入 Team Lead Review，必须退回 Developer。
- Team Lead 报告为 `CHANGES_REQUESTED` 时，不得进入 Codex Review。
- 历史 feature 的 passed gate 不得令当前 feature 通过。
- 多阶段计划在中间阶段通过后进入下一 phase，只有最后阶段通过后进入 Lead Review。
- feedback Bug 文件可由 Stage Runner 提交。
- strict regression、聚焦测试、静态检查和全量测试通过。

## 安全约束

- 不触碰交易、风控、执行、行情、回测、因子、策略、股票池模块。
- 不启用真实交易，不改变 Risk Agent、人工确认或股票池过滤。
- 不自动合并 `main`，PR 保持人工审阅。
- 不提交 `.agent/tmp/**`、`.agent/reports/**` 或凭据。
- 不使用 fallback、mock、smoke 产物冒充正式 Agent 交付。
