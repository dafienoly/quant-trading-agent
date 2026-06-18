# V15.1 Pipeline PR 创建修复验收报告

## 验收范围

本次验收覆盖 issue bootstrap 分支命名、closed PR 防复用、PR metadata 写入、stage runner PR 校验、Main Merge Gate 禁止自动合并，以及交易敏感路径边界检查。

## 验收命令

```bash
TMPDIR=/tmp/codex-pytest .venv/bin/python -m pytest -s tests/test_agent_pipeline_automation.py -q
TMPDIR=/tmp/codex-pytest .venv/bin/python scripts/agent_pipeline_regression.py --strict
TMPDIR=/tmp/codex-pytest .venv/bin/python -m pytest tests/test_agent_pipeline_automation.py tests/test_agent_pipeline_regression.py -q
git diff --check
git diff --name-only origin/main...HEAD | grep -E '^(src/(broker|execution|order|account|risk)/|miniQMT|.*live.*trading|.*real.*order)' || true
git ls-files .agent/tmp
```

## 验收结果

| 命令 | 结果 |
| --- | --- |
| `TMPDIR=/tmp/codex-pytest .venv/bin/python -m pytest -s tests/test_agent_pipeline_automation.py -q` | PASS，42 passed |
| `TMPDIR=/tmp/codex-pytest .venv/bin/python scripts/agent_pipeline_regression.py --strict` | PASS，Status: PASS，Critical failures: 0 |
| `TMPDIR=/tmp/codex-pytest .venv/bin/python -m pytest tests/test_agent_pipeline_automation.py tests/test_agent_pipeline_regression.py -q` | PASS，67 passed |
| `git diff --check` | PASS，无输出 |
| restricted module 检查 | PASS，无敏感路径命中 |
| `git ls-files .agent/tmp` | PASS，无输出 |

## 失败场景验证

- closed PR 不允许作为后续 stage 的 `pr_number` 继续流转。
- workflow_dispatch 传入的 PR 若不是 open，stage runner fail closed。
- workflow_dispatch 传入的 PR head ref 若不等于当前 ref，stage runner fail closed。
- Merge Gate 即使检查通过，也不会自动合并 main。

## 安全检查

本 PR 只修改 Agent pipeline workflow、pipeline 状态脚本、测试与文档报告，不修改交易敏感模块。

## fallback/smoke marker 检查

本 PR 不生成 fallback、mock、smoke 或 handoff-preview 正式产物。

## BOM 检查

`agent_pipeline_regression.py --strict` 中 `utf8_bom_artifacts` 检查通过，未发现正式产物 BOM 问题。

## restricted module 检查

变更文件列表中未出现 `src/broker/**`、`src/execution/**`、`src/order/**`、`src/account/**`、`src/risk/**`、`miniQMT/**` 或真实下单相关路径。

## 是否可合并建议

建议进入人工审阅。自动化验收通过，但本仓库禁止自动合并 main，必须由用户人工审阅和手动合并。
