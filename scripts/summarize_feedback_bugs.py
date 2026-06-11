#!/usr/bin/env python3
"""Summarize open feedback bugs by category.

Usage:
    .venv/bin/python scripts/summarize_feedback_bugs.py \\
        --input feedback/bugs/open \\
        --output-dir docs/test_reports
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path


def classify_bug(bug: dict) -> str:
    text = " ".join(str(bug.get(k, "")) for k in ("title", "summary", "exception_message", "component"))
    if "TemplateResponse" in text or "Jinja2Templates" in text:
        return "aktools_compat"
    if "read timeout" in text or "product_dashboard" in text:
        return "dashboard_timeout"
    if "object has no attribute get_fundamentals" in text:
        return "provider_capability_gap"
    if "empty_data" in text or "All providers failed" in text:
        return "provider_empty_data"
    if "OPENAI_API_KEY" in text or "src/dashboard" in text:
        return "bugfix_invalid_proposal"
    if "No module named 'playwright'" in text or "No module named playwright" in text:
        return "test_dependency_gap"
    return "uncategorized"


def summarize_bug_dir(bug_dir: Path) -> dict:
    total = 0
    by_category: dict[str, int] = {}

    if not bug_dir.exists():
        return {"total": 0, "by_category": {}}

    for f in bug_dir.iterdir():
        if not f.name.endswith(".json"):
            continue
        try:
            bug = json.loads(f.read_text(encoding="utf-8"))
            category = classify_bug(bug)
            by_category[category] = by_category.get(category, 0) + 1
            total += 1
        except (json.JSONDecodeError, OSError):
            continue

    return {"total": total, "by_category": by_category}


def _write_reports(summary: dict, output_dir: Path, ts: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / f"feedback-bug-summary-{ts}.json"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        f"# Feedback Bug Summary ({ts})",
        "",
        f"**Total open bugs**: {summary['total']}",
        "",
        "## By Category",
        "",
    ]
    for cat, count in sorted(summary.get("by_category", {}).items()):
        md_lines.append(f"- **{cat}**: {count}")
    if not summary.get("by_category"):
        md_lines.append("_(no bugs)_")
    md_lines.append("")

    md_path = output_dir / f"feedback-bug-summary-{ts}.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print("Summary written to:")
    print(f"  {json_path}")
    print(f"  {md_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize open feedback bugs by category")
    parser.add_argument("--input", default="feedback/bugs/open", help="Path to open bug directory")
    parser.add_argument("--output-dir", default="docs/test_reports", help="Output directory for reports")
    args = parser.parse_args()

    bug_dir = Path(args.input)
    output_dir = Path(args.output_dir)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")

    summary = summarize_bug_dir(bug_dir)
    _write_reports(summary, output_dir, ts)

    print(f"\nTotal open bugs: {summary['total']}")
    for cat, count in sorted(summary.get("by_category", {}).items()):
        print(f"  {cat}: {count}")


if __name__ == "__main__":
    main()
