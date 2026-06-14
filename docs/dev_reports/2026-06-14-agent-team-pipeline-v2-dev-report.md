# Agent Team Pipeline V2 Development Report

## Scope

Implemented the Team Pipeline V2 upgrade on top of the existing Issue-driven
Agent pipeline automation.

The corrected workflow is:

```text
Codex A PM
  -> Codex B Architect
  -> Claude A team plan
  -> Claude B phase development
  -> Claude C phase testing
  -> if more phases remain, back to Claude B
  -> if all phases pass, Claude A lead review
  -> Codex B final review
  -> Codex A PM acceptance
  -> merge gate
```

## Requirement and Architecture Documents

- `docs/requirements/2026-06-14-agent-team-pipeline-v2-requirements.md`
- `docs/design/2026-06-14-agent-team-pipeline-v2-architecture.md`

## Changed Files

- `AGENTS.md`
- `.agent/config/local_agent_commands.example.env`
- `.github/ISSUE_TEMPLATE/agent_feature_request.yml`
- `.github/workflows/agent-issue-bootstrap.yml`
- `.github/workflows/agent-stage-runner.yml`
- `docs/pipeline/AGENT_AUTOMATION_ARCHITECTURE.md`
- `docs/pipeline/AGENT_HANDOFF_CONTRACT.md`
- `docs/pipeline/GITHUB_LABEL_POLICY.md`
- `docs/pipeline/LOCAL_AGENT_RUNTIME_SETUP.md`
- `docs/pipeline/PIPELINE_STATE_MACHINE.md`
- `docs/pipeline/TEAM_PIPELINE_V2.md`
- `docs/requirements/2026-06-14-agent-team-pipeline-v2-requirements.md`
- `docs/design/2026-06-14-agent-team-pipeline-v2-architecture.md`
- `docs/dev_reports/2026-06-14-agent-team-pipeline-v2-dev-report.md`
- `scripts/agent_pipeline.py`
- `src/product_app/agent_pipeline_automation.py`
- `tests/test_agent_pipeline_automation.py`

## Feature Mapping

| Requirement | Implementation |
|---|---|
| Codex A and Codex B split | New handoff stages `codex_pm`, `codex_architect`, `codex_reviewer`, `codex_acceptance` |
| Claude A/B/C team loop | New handoff stages `claude_lead_plan`, `claude_developer`, `claude_tester`, `claude_lead_review` |
| Correct phase routing | `agent-stage-runner.yml` routes Claude C back to Claude B unless `team_pipeline.all_phases_tested=true` |
| Three-strike review alert | State now includes `max_codex_review_attempts` and postmortem handoff |
| Parallel team support | V2 docs define team, phase, test, fix, and postmortem branch patterns |
| Local Windows/WSL setup | `docs/pipeline/LOCAL_AGENT_RUNTIME_SETUP.md` and `.agent/config/local_agent_commands.example.env` |

## Verification

Executed in Windows PowerShell workspace.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_agent_pipeline_automation.py -q --basetemp=runtime/pytest-tmp-agent-team-pipeline-v2
```

Result: `11 passed, 1 warning`.

```powershell
.\.venv\Scripts\python.exe -m ruff check src/product_app/agent_pipeline_automation.py scripts/agent_pipeline.py tests/test_agent_pipeline_automation.py
```

Result: `All checks passed!`

```powershell
.\.venv\Scripts\python.exe -m py_compile src/product_app/agent_pipeline_automation.py scripts/agent_pipeline.py tests/test_agent_pipeline_automation.py
```

Result: passed.

```powershell
@'
from pathlib import Path
import yaml
for path in sorted(Path('.github/workflows').glob('agent-*.yml')):
    with path.open(encoding='utf-8') as fh:
        yaml.safe_load(fh)
    print(f'OK {path}')
'@ | .\.venv\Scripts\python.exe -
```

Result: all agent workflow YAML files parsed.

```powershell
git diff --check
```

Result: no whitespace errors. Git reported a CRLF conversion warning for
`AGENTS.md`.

## GitHub Configuration

Configured labels in `dafienoly/quant-trading-agent` with `gh label create
--force`:

- `stage:team-plan-pending`
- `stage:team-dev-pending`
- `stage:team-test-pending`
- `stage:claude-lead-review-pending`
- `stage:codex-review-pending`
- `stage:pm-acceptance-pending`
- `stage:postmortem-pending`
- `stage:team-incompetent-alert`
- `agent:claude-lead`
- `agent:claude-developer`
- `agent:claude-tester`

Command variables/secrets were not written to GitHub because they depend on the
user's local Codex/Claude wrapper paths and must not contain embedded tokens.
The required variable names and local command examples are documented in
`docs/pipeline/LOCAL_AGENT_RUNTIME_SETUP.md` and
`.agent/config/local_agent_commands.example.env`.

## Remaining Risks

- Full end-to-end GitHub execution requires either a self-hosted runner or
  configured API-backed command wrappers.
- The workflows can route labels automatically, but the external Codex/Claude
  commands must update `.agent/state.json` accurately after phase testing.
- GitHub-hosted runners cannot directly operate local Windows Codex or WSL
  Claude Code tools.

## Trading Safety

No trading, risk, execution, broker, account, strategy, or data-provider runtime
logic was modified. Auto-main merge policy remains fail-closed for sensitive
paths.
