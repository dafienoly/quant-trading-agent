# Agent Issue Pipeline Automation Dev Report

## Scope

Implemented Level 2 Issue-driven automation and controlled Level 3 auto-main
merge infrastructure.

## Added Files

- `src/product_app/agent_pipeline_automation.py`
- `scripts/agent_pipeline.py`
- `tests/test_agent_pipeline_automation.py`
- `.github/ISSUE_TEMPLATE/agent_feature_request.yml`
- `.github/workflows/agent-issue-bootstrap.yml`
- `.github/workflows/agent-stage-runner.yml`
- `.github/workflows/agent-main-merge-gate.yml`
- `.agent/README.md`
- `docs/pipeline/AGENT_AUTOMATION_ARCHITECTURE.md`
- `docs/pipeline/PIPELINE_STATE_MACHINE.md`
- `docs/pipeline/GITHUB_LABEL_POLICY.md`
- `docs/pipeline/AGENT_HANDOFF_CONTRACT.md`
- `docs/pipeline/AUTO_MERGE_POLICY.md`
- requirement and architecture documents for this feature

## Modified Files

- `AGENTS.md`: added automation docs and `.agent` files to the read order.

## Behavior

- `scripts/agent_pipeline.py init-feature` creates `.agent` state and handoff prompts.
- `scripts/agent_pipeline.py classify-changes` creates deterministic auto-merge decisions.
- `scripts/agent_pipeline.py check-gates` checks required report presence through a selected stage.
- Workflows integrate the CLI with GitHub Issue/PR labels.
- Auto-main merge allowlist is intentionally narrow: docs, tests, Issue
  templates, and `.agent` state may auto-merge after all gates; workflows,
  scripts, API/UI, data providers, trading, risk, execution, broker, account,
  and unknown business code require manual approval.

## Safety Confirmation

- No real trading code was changed.
- No risk, execution, broker, order, account, or miniQMT module was changed.
- Auto-main merge is blocked when restricted paths or unknown business code are touched.
- Missing reports fail closed.
- External agent commands are configurable and not hard-coded.

## Self-Test Commands and Results

```bash
.\.venv\Scripts\python.exe -m py_compile src/product_app/agent_pipeline_automation.py scripts/agent_pipeline.py tests/test_agent_pipeline_automation.py
# PASS

.\.venv\Scripts\python.exe -m pytest tests/test_agent_pipeline_automation.py -q --basetemp=runtime/pytest-tmp-agent-pipeline
# PASS: 8 passed

.\.venv\Scripts\python.exe scripts/agent_pipeline.py init-feature --root <temp-dir> --title "[Feature] GitHub Issue Agent Pipeline" --feature-id agent-issue-pipeline --risk-level docs-only --issue-number 99 --issue-url https://github.com/dafienoly/quant-trading-agent/issues/99 --handoff-stage pm_architect --handoff-stage developer
# PASS: generated .agent state and handoff prompt in a temporary copy

.\.venv\Scripts\python.exe scripts/agent_pipeline.py classify-changes --root <temp-dir> --changed-file docs/pipeline/AUTO_MERGE_POLICY.md --changed-file tests/test_agent_pipeline_automation.py
# PASS: eligible_for_auto_main_merge=true

.\.venv\Scripts\python.exe scripts/agent_pipeline.py classify-changes --root <temp-dir> --changed-file .github/workflows/agent-main-merge-gate.yml --fail-on-manual-approval
# PASS: exited with status 2 and requires_manual_approval=true

.\.venv\Scripts\python.exe scripts/agent_pipeline.py check-gates --root <temp-dir> --feature-id agent-issue-pipeline --through-stage pm
# PASS: exited with status 2 because PM report is missing; fail-closed behavior confirmed
```

Targeted ruff check:

```bash
.\.venv\Scripts\python.exe -m ruff check src/product_app/agent_pipeline_automation.py scripts/agent_pipeline.py tests/test_agent_pipeline_automation.py
# PASS: All checks passed
```
