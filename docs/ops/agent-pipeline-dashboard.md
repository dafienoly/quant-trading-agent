# Agent Pipeline Dashboard / Report Viewer

## Purpose

The Agent Pipeline Dashboard provides a local read-only HTML report viewer that
consumes V13 regression JSON output and renders an interactive dashboard with
status cards, grouped checks, stage timeline, gate status, artifact inventory,
runtime temp hygiene, and restricted-file safety.

It is the V14 visibility layer between:

- **V13** — Regression Suite (data source)
- **V15** — Real quantitative trading business features

## Relationship to V13

V13 generates the regression JSON that V14 consumes:

```bash
python scripts/agent_pipeline_regression.py --output .agent/reports/v13_pipeline_regression.json
python scripts/agent_pipeline_report_viewer.py --input .agent/reports/v13_pipeline_regression.json --output .agent/reports/pipeline_dashboard.html
```

The dashboard does not re-run regression checks. It renders the V13 output
with optional artifact inventory and gate status from the repository.

## Relationship to V15

V15 will start real quantitative trading business feature development. V14
provides the observability to inspect pipeline health before and after V15
changes.

## Commands

### Generate dashboard HTML

```bash
python scripts/agent_pipeline_report_viewer.py \
  --input .agent/reports/v13_pipeline_regression.json \
  --output .agent/reports/pipeline_dashboard.html
```

### Open in browser automatically

```bash
python scripts/agent_pipeline_report_viewer.py \
  --input .agent/reports/v13_pipeline_regression.json \
  --output .agent/reports/pipeline_dashboard.html \
  --open
```

### Serve locally

```bash
python scripts/agent_pipeline_report_viewer.py \
  --input .agent/reports/v13_pipeline_regression.json \
  --output .agent/reports/pipeline_dashboard.html \
  --serve --port 8765
```

### JSON summary mode

```bash
python scripts/agent_pipeline_report_viewer.py \
  --input .agent/reports/v13_pipeline_regression.json \
  --json-summary
```

Output:

```json
{
  "status": "pass",
  "input": ".agent/reports/v13_pipeline_regression.json",
  "output": ".agent/reports/pipeline_dashboard.html",
  "summary": {
    "critical_count": 0,
    "warning_count": 0,
    "info_count": 4,
    "total_checks": 67
  },
  "categories": {
    "Workflow": {
      "passed": 13,
      "failed": 0
    }
  }
}
```

### Full workflow

```bash
# Step 1: Generate regression data
python scripts/agent_pipeline_regression.py --output .agent/reports/v13_pipeline_regression.json

# Step 2: Generate dashboard
python scripts/agent_pipeline_report_viewer.py \
  --input .agent/reports/v13_pipeline_regression.json \
  --output .agent/reports/pipeline_dashboard.html

# Step 3: View locally
python scripts/agent_pipeline_report_viewer.py \
  --input .agent/reports/v13_pipeline_regression.json \
  --output .agent/reports/pipeline_dashboard.html \
  --serve --port 8765
```

## Dashboard Sections

| Section | Description |
|---------|-------------|
| Status card | Overall pass/warn/fail |
| Summary counts | Critical, warning, info, total |
| Category breakdown | Per-category pass/fail |
| Failed / Warning checks | All non-passing checks |
| All checks | Complete check table |
| Pipeline stage timeline | Stage gate/artifact status |
| Gate status | Per-gate pass/decision |
| Artifact inventory | Files by docs subdirectory |
| Restricted-file safety | Trading-sensitive file diff |
| Runtime temp hygiene | .gitignore / .agent/tmp status |
| Raw JSON | Collapsible raw report data |

## Output file location

Generated HTML dashboards should be written to `.agent/reports/`.

These files are normally **not committed** to the repository because they are
workspace-specific generated outputs. Add to `.gitignore` if not already
present.

## Why `.agent/tmp/` must never be committed

The `.agent/tmp/` directory contains workspace-specific temporary files from the
Codex WSL runner. It is already in `.gitignore`.

## Why the dashboard is local / read-only

The dashboard reads local regression JSON, gate files, and artifact paths. It
has no write access to pipeline state, GitHub issues, PRs, or labels. It does
not merge branches or auto-approve anything.

## Why this must not bypass manual approval or merge gates

V14 is a read-only visibility tool. It does not change pipeline execution,
gate semantics, label advancement, Merge Gate behavior, or manual approval
requirements. All pipeline safety invariants from V10-V13 remain unchanged.
