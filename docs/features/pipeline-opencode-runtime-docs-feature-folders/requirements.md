# Pipeline OpenCode Runtime Docs Feature Folders 需求

## 背景

当前流水线交付物长期散落在 `docs/requirements/`、`docs/design/`、`docs/dev_reports/`、`docs/test_reports/`、`docs/review/`、`docs/acceptance/` 等目录中。随着 Issue-driven automation 和 OpenCode team automation 增多，按角色分散存放会降低 feature 级追溯效率。

本次需求是将新功能的 canonical 文档布局切换为 `docs/features/<feature-id>/` 聚合目录，同时保留旧路径兼容读取。

## 目标

1. 新建 feature state 时，默认生成 `docs/features/<feature-id>/` 下的需求、架构、计划、开发、测试、review、acceptance、user guide 和失败复盘路径。
2. Stage gate、report validation、acceptance entry 和 report viewer 能同时读取新路径和旧路径。
3. OpenCode team runtime 文档与 handoff prompt 使用当前指定模型：
   - OpenCode Lead: `opencode-go/deepseek-v4-pro`, `variant=max`
   - OpenCode Developer: `opencode-go/deepseek-v4-flash`, `variant=max`
   - OpenCode Test Engineer: `opencode-go/deepseek-v4-flash`, `variant=max`
4. 根级 `AGENTS.md` 和流程文档把 `docs/features/<feature-id>/` 作为新功能默认交付位置。

## 非目标

1. 不迁移所有历史文档内容。
2. 不删除旧目录。
3. 不改变真实交易、risk、execution、provider 或 stock pool 逻辑。
4. 不新增产品 API 或 UI。

## 验收标准

| ID | 验收项 | 标准 |
|---|---|---|
| R-001 | Feature state 路径 | `build_feature_state` 输出 `docs/features/<feature-id>/...` required docs |
| R-002 | 旧路径兼容 | report gate 能继续识别 legacy 目录下的报告 |
| R-003 | 新路径识别 | report gate 能识别 `docs/features/<feature-id>/phase-<n>-*.md` |
| R-004 | Delivery gate | feature 目录下交付报告被视为 delivery report，不误判为缺少业务变更 |
| R-005 | Runtime 文档 | OpenCode Lead / Tester 模型说明与 runner 配置一致 |
| R-006 | 安全边界 | 不新增真实交易能力，不绕过 risk、stock-pool、human confirmation、provider contract 或 fail-closed 行为 |

## 测试要求

必须覆盖：

- required docs 路径生成；
- feature-folder report gate；
- legacy report fallback；
- developer delivery gate 对 feature-folder 报告的判断；
- acceptance entry 对 required docs 和 latest fallback 的读取；
- touched Python 文件的 ruff、py_compile；
- 当前 diff 的 secret scan 和 whitespace check。
