# Pipeline OpenCode WSL Runtime Hotfix 验收报告

## 变更范围

修复 Issue 自动 Pipeline 的实际运行阻断：

- Windows runner 使用 WSL 登录 shell；
- OpenCode 默认安装目录进入 PATH；
- 删除无效和危险权限参数；
- 新增三角色真实 Runtime Preflight；
- 更新 Issue 模板角色和人工合并文案。

## 测试命令

```bash
../../../.venv/bin/python -m pytest \
  tests/test_agent_pipeline_automation.py \
  tests/test_agent_pipeline_regression.py \
  -q --basetemp=runtime/pytest-tmp-pipeline-runtime-hotfix-focused

../../../.venv/bin/python scripts/agent_pipeline_regression.py --strict

../../../.venv/bin/python -m pytest tests -q --tb=short \
  --basetemp=runtime/pytest-tmp-pipeline-runtime-hotfix-full
```

## 测试结果

- 聚焦测试：`81 passed in 3.01s`。
- Strict regression：`PASS`。
- 全量测试：`990 passed, 6 skipped, 2 warnings in 60.41s`。
- 本地 GLM 5.2、DeepSeek V4 Pro max、Claude ultracode-xhigh 真实探针通过。
- Windows self-hosted Runtime Preflight：待 Draft PR 运行。

## 安全确认

- 不触碰交易敏感模块。
- 不执行真实交易或订单提交。
- 不使用危险权限跳过。
- Preflight 不修改仓库，不推进 Pipeline。
- main 继续人工审阅、手动合并。
- 不提交 `.agent/tmp/**`、`.agent/reports/**` 或任何凭据。

## 验收说明

| 验收项 | 结果 |
|---|---|
| WSL 登录 shell | 通过 |
| OpenCode PATH | 通过 |
| 删除危险权限参数 | 通过 |
| 三模型本地真实探针 | 通过 |
| Runtime Preflight workflow | 通过 |
| Issue 模板当前角色 | 通过 |
| Main 人工合并 | 通过 |
| Windows self-hosted 动态探针 | 待 PR Actions |

## 最终结论

`ACCEPTED_WITH_NOTES`。代码与本地验证满足需求；Windows self-hosted
Runtime Preflight 成功并完成人工审阅前不得合并。
