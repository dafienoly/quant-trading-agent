# Agent Pipeline Regression Suite

## Purpose

The Agent Pipeline Regression Suite validates the full Agent Pipeline without
requiring real LLM calls, GitHub Actions dispatch, network access, or external
services. It is the deterministic safety foundation before:

- **V14** — Agent Pipeline Dashboard / Report Viewer
- **V15** — Real quantitative trading business feature development

The suite runs locally and checks workflow definitions, runner safety invariants,
gate mappings, artifact content validation, pipeline state synchronization,
runtime temp-file hygiene, and restricted trading-sensitive file boundaries.

## Why V13 was added after V12/V12.1

V12 integrated real `codex_pm` and `codex_architect` into the Agent Stage Runner
workflow. V12.1 fixed Codex output capture by switching to a file-based no-pipe
WSL runner. These integration changes touched critical workflow and runner files.

The regression suite ensures that future changes to these files do not regress
the validated stage order, gate mappings, label triggers, runner safety, or
artifact generation behavior.

## Commands

### Run regression suite (human-readable)

```bash
python scripts/agent_pipeline_regression.py
```

Exit code:

- `0` – all critical checks pass
- `1` – warnings exist (only when `--strict` is not used)
- `2` – critical failures exist

### Run with strict mode (warnings become failures)

```bash
python scripts/agent_pipeline_regression.py --strict
```

### JSON output

```bash
python scripts/agent_pipeline_regression.py --json
```

### Write report to file

```bash
python scripts/agent_pipeline_regression.py --output .agent/reports/v13_pipeline_regression.json
```

### Run targeted tests

```bash
python -m pytest tests/test_agent_pipeline_regression.py -q
```

## Pass / Warn / Fail

| Severity | Meaning |
|----------|---------|
| critical | Must pass. Failure blocks pipeline safety validation. |
| warning  | Should pass. Failure indicates possible but non-blocking issue. |
| info     | Pass or fail is informative only. |

## What the simulation covers

The suite creates a deterministic temporary fixture and simulates the full
pipeline lifecycle:

1. **Init** — `build_feature_state`, `write_feature_state`
2. **Handoffs** — `write_handoff` for all 8 canonical stages
3. **Artifacts** — Creates mock artifacts with correct section headings
4. **Gates** — `check_required_reports` for every stage
5. **State sync** — `check_state_gate_consistency`, `sync_state_from_gates`
6. **Gate validation** — Verifies corrupted artifacts fail appropriate checks

No real LLM calls are made.

## Why it avoids real LLM calls

The regression suite is intentionally deterministric:

- It does not require network access.
- It does not call real Codex, Claude, or any OpenAI API.
- It does not require GitHub Actions.
- It does not require pandas, fastapi, akshare, or other business runtime
  dependencies (except `pyyaml` which is already installed in CI pipelines).

This makes it suitable as a pre-commit check and CI safety gate.

## Why `.agent/tmp/` must not be tracked

The `.agent/tmp/` directory is where the Codex wrapper writes temporary output
files for reading back into PowerShell. These files are workspace-specific and
must not be committed to the repository.

The `.gitignore` includes `.agent/tmp/` to prevent accidental commits.

## Why full `pytest` may fail

The repository contains tests for trading strategy, execution, broker, order,
risk, miniQMT, and live trading modules. These tests require optional business
dependencies (pandas, fastapi, akshare, etc.) that are not installed in a
default development environment.

**Run only the V13-specific tests:**

```bash
python -m pytest tests/test_agent_pipeline_regression.py -q
```

## How V14 can consume the JSON output

The V14 Dashboard / Report Viewer can use `--json` or `--output <path>` to
consume the regression report. The JSON schema is:

```json
{
  "status": "pass",
  "summary": {
    "critical_count": 0,
    "warning_count": 0,
    "info_count": 0
  },
  "checks": [
    {
      "name": "workflow_has_codex_pm",
      "severity": "critical",
      "passed": true,
      "message": "workflow supports codex_pm"
    }
  ],
  "artifacts": {
    "report_path": ".agent/reports/v13_pipeline_regression.json"
  }
}
```

## Relationship between V13, V14, and V15

```
V12/V12.1 ──► Integration of real Codex stages
     │
     ▼
V13 ──────────► Regression Suite (this)
     │              Safety foundation
     ▼
V14 ──────────► Dashboard / Report Viewer
     │              Consumes V13 JSON output
     ▼
V15 ──────────► Real quantitative trading business features
                    Built on V13 safety + V14 observability
```

No version starts until the previous one is complete and validated.
