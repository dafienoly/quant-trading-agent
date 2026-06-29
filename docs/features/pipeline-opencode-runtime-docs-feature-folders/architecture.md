# Pipeline OpenCode Runtime Docs Feature Folders 架构

## 模块边界

| 模块 | 责任 |
|---|---|
| `src/product_app/agent_pipeline_automation.py` | 生成 feature state、stage report glob、delivery gate、handoff prompt |
| `scripts/agent_pipeline_acceptance_entry.py` | 根据 gate/state 查找 acceptance、test report、review、user guide |
| `scripts/validate_pr_reports.py` | 校验 PR 报告路径和中文交付证据 |
| `scripts/agent_pipeline_regression.py` | 流水线回归校验 |
| `.github/workflows/*` | GitHub Actions stage runner / preflight / bootstrap 路径与 runtime 文案 |
| `docs/process/*`、`docs/pipeline/*`、`AGENTS.md` | 人类和 Agent 可读的流程契约 |

## 数据流

```text
Issue / manual bootstrap
  -> build_feature_state()
  -> .agent/current_task.yaml required_docs
  -> stage handoff prompt
  -> Agent writes docs/features/<feature-id>/...
  -> report gate scans feature path first and legacy path second
  -> acceptance entry links canonical artifacts
  -> PR / merge gate reads reports and CI result
```

## 兼容策略

1. `REPORT_GLOBS_BY_STAGE` 按 stage 同时声明新旧路径。
2. `_glob_stage_reports` 统一处理 glob 和排序，避免各调用点重复拼 pattern。
3. `_is_delivery_report_path` 同时接受旧目录和 `docs/features/<feature-id>/` 下的交付报告，避免文档-only 阶段被误判。
4. Acceptance entry 优先读取 `.agent/current_task.yaml` 中的 required docs，如果文件不存在，再按新旧路径 fallback 查找最新 artifact。

## 安全影响

本次只改变流水线文档路径和 automation gate 识别逻辑，不触碰：

- `src/risk_engine/`
- `src/execution_engine/`
- market provider
- broker adapter
- stock pool filter
- signal / order / sizing runtime

真实交易能力不受影响。`LEVEL_3_AUTO` 没有新增暴露路径。

## 失败处理

- 新路径报告缺失时，report gate 仍 fail closed。
- 新路径不匹配合法命名时，delivery gate 不把它当作交付报告。
- 旧路径历史 feature 仍可通过 legacy glob 被识别。

## 测试策略

1. Unit tests 覆盖 required docs 生成、report gate、phase advance、delivery gate、acceptance entry。
2. Static checks 覆盖 touched Python files。
3. Script smoke 覆盖 `scripts/run-pipeline-team-agent.sh` 语法。
4. Diff checks 覆盖 whitespace/conflict marker 与当前 diff secrets。
