# V12 Real Codex PM / Architect Output Capture Dev Report

## Requirement Document

- Task prompt: V12.1 Real Codex PM / Architect output capture fix.
- Repository requirement document: not present for this runner fix.

## Architecture Document

- Task prompt architecture direction: deadlock-free file-based WSL Codex execution model.
- Repository architecture document: not present for this runner fix.

## Changed Files

- `docs/ops/agent-runners/run-codex-stage.ps1.reference`
- `src/product_app/agent_pipeline_automation.py`
- `tests/test_agent_pipeline_automation.py`
- `docs/dev_reports/2026-06-16-v12-real-codex-pm-architect-output-capture-dev-report.md`

## Feature-to-Code Mapping

- Real PM / Architect Codex execution now writes prompt, runner, stdout log, stderr log, last-message output, and exit code under `.agent/tmp/<stage>.*`.
- PowerShell starts `wsl.exe bash <runner-script>` without redirected stdout/stderr pipes and reads only the file outputs after process completion.
- Strict real mode exits non-zero when Codex execution or validated output fails; invalid real output is not written as the final artifact.
- PM and architecture gate validation now rejects literal EventArgs corruption and required-heading omissions.
- Runner regression tests cover no `Register-ObjectEvent`, no `ReadToEnd()`, `.agent/tmp` file usage, and no PowerShell stdout/stderr pipe capture.

## Added or Updated Tests

- Added gate tests for corrupted PM artifact failure.
- Added gate tests for corrupted architecture artifact failure.
- Added gate tests for PM missing-heading failure.
- Added gate tests for architecture missing-heading failure.
- Added runner-reference static tests for deadlock/corruption capture regressions.

## Commands and Results

- `git fetch origin --prune && git switch feat/v12-real-codex-pm-architect && git pull --ff-only origin feat/v12-real-codex-pm-architect`  
  Result: passed; branch already up to date.
- `python -m pytest tests/test_agent_pipeline_automation.py -q --basetemp=runtime/pytest-tmp-v12-output-capture-system-focused`  
  Result: passed, `36 passed`.
- `mkdir -p /mnt/d/agent-runners && cp docs/ops/agent-runners/run-codex-stage.ps1.reference /mnt/d/agent-runners/run-codex-stage.ps1 && diff -u <(sed 's/\r$//' /mnt/d/agent-runners/run-codex-stage.ps1) <(sed 's/\r$//' docs/ops/agent-runners/run-codex-stage.ps1.reference)`  
  Result: passed; no diff.
- `powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "[scriptblock]::Create((Get-Content -Raw 'D:\agent-runners\run-codex-stage.ps1')) | Out-Null; 'parse ok'"`  
  Result: passed; `parse ok`.
- `./.venv/bin/python -m py_compile src/product_app/agent_pipeline_automation.py`  
  Result: passed.
- `git diff --check`  
  Result: passed.
- `git diff --name-only origin/main...HEAD | grep -E '^(src/(broker|execution|order|account|risk)/|miniQMT|.*live.*trading|.*real.*order)' || true`  
  Result: passed; empty output.

## Skipped or Not-Run Items

- `./.venv/bin/python -m ruff check src/product_app/agent_pipeline_automation.py tests/test_agent_pipeline_automation.py` failed because `ruff` is not installed in the active venv (`No module named ruff`).
- `python -m pytest -q --basetemp=runtime/pytest-tmp-v12-output-capture-system-full` failed during collection because the local Python environment is missing project dependencies including `fastapi`, `requests`, `pandas`, `numpy`, `pydantic`, `loguru`, and `httpx`.
- `./.venv/bin/python -m pytest -q --basetemp=runtime/pytest-tmp-v12-output-capture-full` failed for the same missing dependency set.

## Remaining Risks

- Full local test coverage could not run until project runtime and dev dependencies are installed in the active environment.
- The smoke GitHub Actions run remains the authoritative validation for the Windows runner execution path.

## Trading Safety

- Real trading capability is not affected.
- No broker, execution, order, account, risk, miniQMT, live trading, or real order submission code was modified.
- Risk, stock-pool filtering, human confirmation, manual approval, and fail-closed behavior were not bypassed.
