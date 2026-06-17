#!/usr/bin/env python
"""Agent Pipeline Dashboard / Report Viewer.

Consumes V13 regression JSON output and renders a static HTML dashboard
with status cards, grouped checks, stage timeline, gate status, artifact
inventory, runtime temp hygiene, and restricted-file safety.

Usage:
    python scripts/agent_pipeline_report_viewer.py \\
        --input .agent/reports/v13_pipeline_regression.json \\
        --output .agent/reports/pipeline_dashboard.html

    python scripts/agent_pipeline_report_viewer.py \\
        --input .agent/reports/v13_pipeline_regression.json \\
        --json-summary

    python scripts/agent_pipeline_report_viewer.py \\
        --input .agent/reports/v13_pipeline_regression.json \\
        --output .agent/reports/pipeline_dashboard.html \\
        --open

    python scripts/agent_pipeline_report_viewer.py \\
        --input .agent/reports/v13_pipeline_regression.json \\
        --output .agent/reports/pipeline_dashboard.html \\
        --serve --port 8765
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import webbrowser
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]

STAGE_ORDER = (
    "codex_pm",
    "codex_architect",
    "claude_lead_plan",
    "claude_developer",
    "claude_tester",
    "claude_lead_review",
    "codex_reviewer",
    "codex_acceptance",
    "merge_gate / manual_approval",
)

GATE_STAGES = (
    "pm", "architecture", "team_plan", "phase_dev", "phase_test",
    "claude_lead_review", "codex_review", "acceptance",
)

ARTIFACT_DIRS = (
    "docs/requirements",
    "docs/design",
    "docs/dev_plans",
    "docs/dev_reports",
    "docs/test_reports",
    "docs/review",
    "docs/acceptance",
    "docs/smoke",
)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

class DashboardModel:
    """Aggregated data model for the dashboard."""
    def __init__(self) -> None:
        self.title: str = "Agent Pipeline Dashboard"
        self.generated_at: str = datetime.now(timezone.utc).isoformat()
        self.input_path: str = ""
        self.output_path: str = ""
        self.status: str = "unknown"
        self.summary: dict[str, int] = {}
        self.checks: list[dict[str, Any]] = []
        self.categories: dict[str, dict[str, int]] = {}
        self.stage_timeline: list[dict[str, Any]] = []
        self.gates: dict[str, Any] = {}
        self.artifacts: dict[str, list[str]] = {}
        self.restricted: dict[str, Any] = {}
        self.temp_hygiene: dict[str, Any] = {}
        self.raw_report: dict[str, Any] = {}


def load_regression_report(path: str | Path) -> dict[str, Any]:
    """Load and validate V13 regression JSON."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"report not found: {p}")
    raw = p.read_text(encoding="utf-8")
    try:
        report = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {p}: {exc}") from exc
    if "status" not in report or "checks" not in report:
        raise ValueError(f"report missing required fields (status, checks): {p}")
    return report


def load_state(repo_root: Path) -> dict[str, Any]:
    """Load .agent/state.json if present."""
    p = repo_root / ".agent" / "state.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def load_gate_status(repo_root: Path) -> dict[str, Any]:
    """Read .agent/gates/*.json and compile gate status."""
    gates: dict[str, Any] = {}
    gates_dir = repo_root / ".agent" / "gates"
    if not gates_dir.is_dir():
        return gates
    for f in sorted(gates_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            gates[f.stem] = {
                "passed": data.get("passed", False),
                "decision": data.get("decision"),
                "found_count": len(data.get("found", {})),
                "missing_count": len(data.get("missing", {})),
                "filename": f.name,
            }
        except (json.JSONDecodeError, OSError):
            gates[f.stem] = {"passed": False, "error": str(f.name)}
    return gates


def scan_artifact_inventory(repo_root: Path) -> dict[str, list[str]]:
    """Scan docs subdirectories for artifacts."""
    inventory: dict[str, list[str]] = {}
    for subdir in ARTIFACT_DIRS:
        d = repo_root / subdir
        if d.is_dir():
            files = sorted(
                str(p.relative_to(repo_root))
                for p in d.glob("*")
                if p.is_file() and ".gitkeep" not in p.name
            )
            if files:
                inventory[subdir] = files
    return inventory


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def _categorize_check_name(name: str) -> str:
    """Extract a human-readable category from a check name."""
    if name.startswith("workflow"):
        return "Workflow"
    if name.startswith("runner"):
        return "Runner"
    if name.startswith("gate"):
        return "Gates"
    if name.startswith("artifact"):
        return "Artifacts"
    if name.startswith("handoff"):
        return "Handoffs"
    if name.startswith("sim"):
        return "Pipeline Simulation"
    if name.startswith("restricted"):
        return "Restricted Files"
    if name.startswith("gitignore") or name.startswith("agent_tmp") or name.startswith("branch_no"):
        return "Runtime Temp"
    if name.startswith("cmd_step") or name.startswith("label_func"):
        return "Workflow"
    return "Other"


def summarize_checks(report: dict[str, Any]) -> dict[str, int]:
    """Return summary counts."""
    checks = report.get("checks", [])
    return {
        "critical_count": sum(1 for c in checks if c.get("severity") == "critical" and not c.get("passed")),
        "warning_count": sum(1 for c in checks if c.get("severity") == "warning" and not c.get("passed")),
        "info_count": sum(1 for c in checks if c.get("severity") == "info"),
        "total_checks": len(checks),
    }


def group_checks_by_category(report: dict[str, Any]) -> dict[str, dict[str, int]]:
    """Group checks by category and return pass/fail counts."""
    categories: dict[str, dict[str, int]] = {}
    for c in report.get("checks", []):
        cat = _categorize_check_name(c["name"])
        if cat not in categories:
            categories[cat] = {"passed": 0, "failed": 0, "total": 0}
        categories[cat]["total"] += 1
        if c.get("passed"):
            categories[cat]["passed"] += 1
        else:
            categories[cat]["failed"] += 1
    return categories


def build_stage_timeline(
    report: dict[str, Any],
    gates: dict[str, Any],
    artifacts: dict[str, list[str]],
) -> list[dict[str, Any]]:
    """Build stage timeline from gates and artifact presence."""
    timeline: list[dict[str, Any]] = []
    for stage in STAGE_ORDER:
        gate_key = stage.replace("codex_", "").replace("claude_", "").replace("_", "")
        # Try to find matching gate
        gate_data: dict[str, Any] = {"exists": False, "passed": False}
        for gk, gv in gates.items():
            if stage.replace("codex_", "").replace("claude_", "") in gk:
                gate_data = gv
                break
        # Check artifact presence
        stage_artifacts: list[str] = []
        for subdir, files in artifacts.items():
            for f in files:
                if stage.replace("codex_", "").replace("claude_", "").replace("_", "-") in f:
                    stage_artifacts.append(f)

        timeline.append({
            "name": stage,
            "gate_passed": gate_data.get("passed", False),
            "gate_exists": gate_data.get("exists", True) if gate_data.get("error") is None else True,
            "artifacts": stage_artifacts,
            "has_artifacts": len(stage_artifacts) > 0,
        })
    return timeline


def build_model(
    input_path: str,
    output_path: str,
    repo_root: Path | None = None,
) -> DashboardModel:
    """Build the full dashboard model from inputs."""
    root = repo_root or REPO_ROOT
    report = load_regression_report(input_path)
    state = load_state(root)
    gates = load_gate_status(root)
    artifacts = scan_artifact_inventory(root)

    model = DashboardModel()
    model.input_path = str(input_path)
    model.output_path = str(output_path)
    model.status = report.get("status", "unknown")
    model.summary = summarize_checks(report)
    model.checks = report.get("checks", [])
    model.categories = group_checks_by_category(report)
    model.gates = gates
    model.artifacts = artifacts
    model.stage_timeline = build_stage_timeline(report, gates, artifacts)
    model.raw_report = report

    # Extract restricted and temp hygiene
    for c in report.get("checks", []):
        if c["name"] == "restricted_diff":
            model.restricted = c
        if c["name"] == "gitignore_agent_tmp":
            model.temp_hygiene["gitignore"] = c
        if c["name"] == "agent_tmp_not_tracked":
            model.temp_hygiene["tracked"] = c

    return model


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _status_color(status: str) -> str:
    return {"pass": "#28a745", "warn": "#ffc107", "fail": "#dc3545"}.get(status, "#6c757d")


def _severity_badge(severity: str) -> str:
    colors = {"critical": "#dc3545", "warning": "#ffc107", "info": "#17a2b8"}
    return f'<span style="background:{colors.get(severity,"#6c757f")};color:{"#000" if severity=="warning" else "#fff"};padding:2px 8px;border-radius:10px;font-size:0.8em">{severity}</span>'


def _check_icon(passed: bool) -> str:
    return "✅" if passed else "❌"


def render_dashboard_html(model: DashboardModel) -> str:
    """Render the full HTML dashboard."""
    sc = model.summary
    ts = datetime.fromisoformat(model.generated_at).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Category table rows
    cat_rows = ""
    for cat, counts in sorted(model.categories.items()):
        cat_rows += f"""<tr><td>{cat}</td><td>{counts['total']}</td><td style="color:#28a745">{counts['passed']}</td><td style="color:#dc3545">{counts['failed']}</td></tr>\n"""

    # Check details
    check_rows = ""
    failed_rows = ""
    for c in model.checks:
        row = f"""<tr><td>{_check_icon(c['passed'])}</td><td>{_severity_badge(c['severity'])}</td><td>{c['name']}</td><td>{c['message']}</td></tr>\n"""
        check_rows += row
        if not c["passed"]:
            failed_rows += row

    # Failed / warning section
    failed_section = ""
    if not failed_rows:
        failed_section = '<p style="color:#28a745">All checks passed. No failures or warnings.</p>'
    else:
        failed_section = f"""<h2>Failed / Warning Checks</h2><table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%"><tr><th>OK</th><th>Severity</th><th>Name</th><th>Message</th></tr>{failed_rows}</table>"""

    # Stage timeline
    stage_rows = ""
    for st in model.stage_timeline:
        gate_icon = "✅" if st["gate_passed"] else ("❌" if st["gate_exists"] else "⏳")
        art_icon = "✅" if st["has_artifacts"] else "❌"
        art_list = ", ".join(st["artifacts"][:3]) if st["artifacts"] else "(none)"
        stage_rows += f"<tr><td>{st['name']}</td><td>{gate_icon}</td><td>{art_icon}</td><td style='font-size:0.85em'>{art_list}</td></tr>\n"

    # Gate status
    gate_rows = ""
    for gk, gv in sorted(model.gates.items()):
        passed_icon = "✅" if gv.get("passed") else "❌"
        decision = gv.get("decision") or "—"
        gate_rows += f"<tr><td>{gk}</td><td>{passed_icon}</td><td>{decision}</td><td>{gv.get('found_count','?')}</td><td>{gv.get('missing_count','?')}</td></tr>\n"

    # Artifact inventory
    art_sections = ""
    for subdir, files in sorted(model.artifacts.items()):
        file_list = "".join(f"<li>{f}</li>" for f in files[:10])
        more = f"<li><em>... and {len(files)-10} more</em></li>" if len(files) > 10 else ""
        art_sections += f"<h3>{subdir}</h3><ul>{file_list}{more}</ul>\n"

    # Restricted file safety
    restricted_html = ""
    r = model.restricted
    if r:
        restricted_html = f"<p>{_check_icon(r['passed'])} {r['message']}</p>"
    else:
        restricted_html = "<p>No restricted-file data in report.</p>"

    # Temp hygiene
    temp_html = ""
    for k, v in sorted(model.temp_hygiene.items()):
        temp_html += f"<p>{_check_icon(v['passed'])} {v['message']}</p>"

    # Raw JSON
    raw_json = json.dumps(model.raw_report, indent=2, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{model.title}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 20px; background: #f8f9fa; color: #333; }}
h1, h2, h3 {{ color: #222; }}
table {{ background: #fff; }}
.status-card {{ padding: 20px; border-radius: 8px; color: #fff; font-size: 1.5em; text-align: center; margin: 10px 0; }}
.status-pass {{ background: #28a745; }}
.status-warn {{ background: #ffc107; color: #000; }}
.status-fail {{ background: #dc3545; }}
.summary-grid {{ display: flex; gap: 15px; flex-wrap: wrap; }}
.summary-item {{ background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 15px; flex: 1; min-width: 120px; text-align: center; }}
.summary-item h3 {{ margin: 0; font-size: 2em; }}
.summary-item p {{ margin: 5px 0 0; color: #666; }}
.collapsible {{ cursor: pointer; background: #e9ecef; padding: 10px; border-radius: 4px; }}
.collapsible + pre {{ display: none; }}
.collapsible:hover {{ background: #dee2e6; }}
</style>
</head>
<body>
<h1>{model.title}</h1>
<p>Generated: {ts}</p>
<p>Input: <code>{model.input_path}</code> | Output: <code>{model.output_path}</code></p>

<div class="status-card status-{model.status}">Status: {model.status.upper()}</div>

<div class="summary-grid">
<div class="summary-item"><h3 style="color:#dc3545">{sc['critical_count']}</h3><p>Critical</p></div>
<div class="summary-item"><h3 style="color:#ffc107">{sc['warning_count']}</h3><p>Warnings</p></div>
<div class="summary-item"><h3 style="color:#17a2b8">{sc['info_count']}</h3><p>Info</p></div>
<div class="summary-item"><h3>{sc['total_checks']}</h3><p>Total Checks</p></div>
</div>

<h2>Category Breakdown</h2>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%">
<tr><th>Category</th><th>Total</th><th>Passed</th><th>Failed</th></tr>
{cat_rows}
</table>

{failed_section}

<h2>All Checks</h2>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%">
<tr><th>OK</th><th>Severity</th><th>Name</th><th>Message</th></tr>
{check_rows}
</table>

<h2>Pipeline Stage Timeline</h2>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%">
<tr><th>Stage</th><th>Gate</th><th>Artifacts</th><th>Artifact Files</th></tr>
{stage_rows}
</table>

<h2>Gate Status</h2>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%">
<tr><th>Gate</th><th>Passed</th><th>Decision</th><th>Found</th><th>Missing</th></tr>
{gate_rows}
</table>

<h2>Artifact Inventory</h2>
{art_sections}

<h2>Restricted-File Safety</h2>
{restricted_html}

<h2>Runtime Temp Hygiene</h2>
{temp_html}

<h2>Raw JSON</h2>
<div class="collapsible" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='block'?'none':'block'">Click to toggle raw JSON</div>
<pre style="background:#fff;border:1px solid #ddd;padding:10px;overflow:auto;max-height:500px">{raw_json}</pre>

</body>
</html>"""
    return html


def write_dashboard(html: str, output_path: str | Path) -> Path:
    """Write HTML dashboard to file."""
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# JSON summary
# ---------------------------------------------------------------------------

def render_json_summary(model: DashboardModel) -> str:
    """Render a JSON summary of the dashboard model."""
    categories_summary: dict[str, dict[str, int]] = {}
    for cat, counts in sorted(model.categories.items()):
        categories_summary[cat] = {"passed": counts["passed"], "failed": counts["failed"]}

    summary = {
        "status": model.status,
        "input": model.input_path,
        "output": model.output_path,
        "generated_at": model.generated_at,
        "summary": model.summary,
        "categories": categories_summary,
    }
    return json.dumps(summary, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

def serve_dashboard(output_path: str | Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    """Serve the dashboard directory via a simple HTTP server."""
    p = Path(output_path)
    out_dir = p.parent.resolve()
    filename = p.name

    os.chdir(out_dir)

    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # quiet

    server = HTTPServer((host, port), Handler)
    print(f"Serving Agent Pipeline Dashboard at http://{host}:{port}/{filename}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Agent Pipeline Dashboard / Report Viewer"
    )
    parser.add_argument(
        "--input", required=True,
        help="Path to V13 regression JSON (e.g. .agent/reports/v13_pipeline_regression.json)"
    )
    parser.add_argument(
        "--output", default="",
        help="Path for generated HTML dashboard"
    )
    parser.add_argument(
        "--open", action="store_true",
        help="Open the generated HTML in browser after creation"
    )
    parser.add_argument(
        "--serve", action="store_true",
        help="Serve the dashboard via local HTTP server"
    )
    parser.add_argument(
        "--port", type=int, default=8765,
        help="Port for local server (default: 8765)"
    )
    parser.add_argument(
        "--json-summary", action="store_true",
        help="Output JSON summary instead of HTML"
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.json_summary and not args.output:
        print("error: --output is required unless --json-summary is used", file=sys.stderr)
        return 2

    try:
        model = build_model(
            input_path=args.input,
            output_path=args.output or "/dev/null",
        )
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json_summary:
        print(render_json_summary(model))
        return 0

    html = render_dashboard_html(model)
    out_path = write_dashboard(html, args.output)
    print(f"Dashboard written to {out_path.resolve()}")

    if args.open:
        try:
            webbrowser.open(str(out_path.resolve()))
        except Exception as exc:
            print(f"warning: could not open browser: {exc}", file=sys.stderr)

    if args.serve:
        serve_dashboard(args.output, port=args.port)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
