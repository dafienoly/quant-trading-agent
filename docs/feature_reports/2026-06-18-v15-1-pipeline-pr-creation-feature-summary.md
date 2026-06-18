# V15.1 Pipeline PR 创建修复功能说明

## 解决的问题

本 PR 修复 issue-driven Agent pipeline 在 restart 场景中复用已关闭 PR 的问题。此前同一 `feature_id` 会生成固定 epic 分支，workflow 只按分支查询 PR 编号，没有检查 PR 是否仍为 open，导致后续 stage 继续绑定 closed PR #56。

## 新增和修改的功能

- 新建 issue pipeline 默认生成带 issue 编号的分支：`epic/<日期>-<feature_id>-issue-<issue_number>`。
- 手动 `workflow_dispatch` 没有 issue 编号时，使用 GitHub run id 生成分支后缀，避免复用旧分支。
- Bootstrap workflow 查询 PR 时读取 `number/state/merged/headRefName/url`，只允许复用 open 且 head ref 匹配的 PR。
- 如发现同名分支对应 closed 且未合并 PR，workflow 使用唯一 restart 分支继续创建新 PR；如果状态异常则 fail closed。
- PR 创建或确认后，会把 `pr_number`、`pr_url` 和 head branch 写入 `.agent/state.json` 与 `.agent/current_task.yaml`。
- Stage runner 在 workflow_dispatch 收到 `pr_number` 时，会先校验 PR 仍为 open 且 head ref 匹配当前 ref。
- Main Merge Gate 不再自动执行 `gh pr merge`，只添加人工审批标签和中文提示评论。

## 用户如何使用

用户照常创建带 `agent:pipeline` 和 `stage:pm-pending` 标签的 issue，或手动触发 Agent Issue Bootstrap。restart issue 会生成独立分支和 PR，不再继续绑定已关闭 PR。

## UI 变化

无应用 UI 变化。GitHub Actions 与 PR conversation 会出现中文人工合并提示。

## 配置变化

无新增 secret、token 或 GitHub Secrets 配置。workflow 使用已有 `github.token` 查询和标记 PR。

## 兼容性影响

- 旧的 `epic/<日期>-<feature_id>` 分支命名不再作为 issue pipeline 默认值。
- 后续 stage 更依赖 `.agent/state.json` 中记录的 PR metadata。
- 已关闭 PR 不再被静默复用；异常状态会 fail closed。

## 安全边界

- 不触碰交易敏感模块。
- 不启用真实交易、真实下单或绕过风控。
- 不自动合并 main。
- 不写入 secrets、token 或 API key。
- 不提交 `.agent/tmp/**` 或 `.agent/reports/**`。

## 不做什么

- 不重构完整 Agent pipeline。
- 不实现 dashboard artifact。
- 不验收 PR #3 DeepSeek Runtime。
- 不修改交易、账户、风控、下单相关代码。
