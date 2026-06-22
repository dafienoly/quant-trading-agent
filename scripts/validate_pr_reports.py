#!/usr/bin/env python
"""PR Report Governance — validate that non-pure-doc PRs carry required reports.

Usage:
    python scripts/validate_pr_reports.py --base origin/main --head HEAD [--strict] [--json] [--output report.json]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_SECTIONS = (
    "变更范围",
    "测试命令",
    "测试结果",
    "安全确认",
    "最终结论",
)

REJECT_PATTERNS = (
    "TODO",
    "TBD",
    "待补充",
    "This is a placeholder",
    "placeholder",
)

# Required Chinese characters minimum for non-pure-doc reports
MIN_CHINESE_CHARS = 20

ALLOWED_PURE_DOC_DIRS = (
    "docs/",
)


def _git_command(command: str, cwd: str | Path) -> str:
    """Run a git command and return stdout."""
    result = subprocess.run(
        command.split(),
        capture_output=True, text=True, cwd=cwd, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(command.split()[:3])} failed: {result.stderr}")
    return result.stdout.strip()


def get_changed_files(base: str, head: str, repo_root: str | Path) -> list[str]:
    """Get list of changed files between base and head."""
    try:
        output = _git_command(f"git diff --name-only {base}...{head}", cwd=repo_root)
    except RuntimeError as exc:
        raise RuntimeError(f"Cannot diff {base}...{head}: {exc}") from exc
    if not output:
        return []
    return [f.strip() for f in output.split("\n") if f.strip()]


def is_pure_docs_changed(files: list[str]) -> bool:
    """Return True if all changed files are under docs/ (except dev_reports/ and acceptance/)."""
    if not files:
        return True
    return all(f.startswith("docs/") for f in files)


def _section_has_content(text: str, heading: str) -> bool:
    """Check that a Markdown section heading has substantive body content."""
    pattern = rf"(?m)^##\s*{re.escape(heading)}\s*$(.*?)(?=\n##\s|\Z)"
    m = re.search(pattern, text, re.DOTALL)
    if not m:
        return False
    body = m.group(1).strip()
    if not body:
        return False
    # Body consisting only of whitespace, dashes, or backticks is empty
    stripped = body.replace('-', '').replace('`', '').strip()
    if not stripped:
        return False
    return True


def check_report_content(path: str | Path, strict: bool, require_chinese: bool = False) -> list[str]:
    """Check a single report file for content rules. Returns list of issues."""
    issues: list[str] = []
    p = Path(path)
    if not p.exists():
        return ["_file_not_found"]
    if p.stat().st_size == 0:
        return ["_empty"]
    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ["_unreadable"]

    # Reject empty/whitespace-only
    if not text.strip():
        return ["_empty"]

    # Reject placeholder patterns (only in standalone context, not discussion)
    # A line is a "standalone placeholder" if it IS the line content, not discussed
    lines = text.split('\n')
    for pat in REJECT_PATTERNS:
        for line in lines:
            s = line.strip().rstrip('.。，,!！:：')
            # Match if line IS the pattern (possibly with colon) or is mostly the pattern
            if s.lower().startswith(pat.lower()):
                issues.append(f"contains standalone forbidden pattern: {pat}")
                break
        else:
            continue

    # Check required sections with content
    sections_found = 0
    sections_empty = []
    title_found = False
    for line in lines:
        if line.strip().startswith("# ") or line.strip().startswith("#　"):
            title_found = True
            break
    if not title_found:
        issues.append("missing Markdown title")

    for section in REQUIRED_SECTIONS:
        if section in text:
            if _section_has_content(text, section):
                sections_found += 1
            else:
                sections_empty.append(section)
        else:
            issues.append(f"missing section: {section}")

    if sections_empty:
        issues.append(f"empty sections (heading only): {', '.join(sections_empty)}")

    # Chinese content requirement
    if require_chinese:
        # Check at least 20 Chinese characters across the document
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        if chinese_chars < 20:
            issues.append("insufficient Chinese content")

    return issues


def validate_reports(
    base: str,
    head: str,
    repo_root: str | Path,
    *,
    strict: bool,
) -> dict[str, Any]:
    """Run PR report validation and return a diagnostic dict."""
    result: dict[str, Any] = {
        "base": base,
        "head": head,
        "passed": False,
        "pure_docs": False,
        "reports_required": False,
        "reports_present": False,
        "changed_files_count": 0,
        "issues": [],
        "report_files": {},
    }

    # Get changed files
    try:
        files = get_changed_files(base, head, repo_root)
    except RuntimeError as exc:
        result["issues"].append(str(exc))
        if strict:
            result["passed"] = False
            return result
        # In non-strict, we might continue with empty files list
        files = []

    result["changed_files_count"] = len(files)
    result["pure_docs"] = is_pure_docs_changed(files)

    # Pure docs PR — no reports required
    if result["pure_docs"]:
        result["passed"] = True
        return result

    # Non-pure-docs PR: reports required
    result["reports_required"] = True
    root = Path(repo_root)

    # Find dev reports
    dev_reports = _find_new_or_modified(files, "docs/dev_reports/", root)
    accept_reports = _find_new_or_modified(files, "docs/acceptance/", root)

    if not dev_reports:
        result["issues"].append("no docs/dev_reports/ file in diff")
    if not accept_reports:
        result["issues"].append("no docs/acceptance/ file in diff")

    result["reports_present"] = bool(dev_reports and accept_reports)

    # Content validation for each report
    for f in dev_reports + accept_reports:
        issues = check_report_content(root / f, strict)
        if issues:
            result["issues"].extend(f"{f}: {i}" for i in issues)
        result["report_files"][f] = {
            "path": f,
            "issues": issues,
            "valid": len(issues) == 0,
        }

    result["passed"] = len(result["issues"]) == 0 and result["reports_present"]
    return result


def _find_new_or_modified(files: list[str], prefix: str, root: Path) -> list[str]:
    """Return file paths from *files* that start with *prefix*."""
    return sorted(f for f in files if f.startswith(prefix))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PR Report Governance validator")
    parser.add_argument("--base", required=True, help="Base ref, e.g. origin/main")
    parser.add_argument("--head", required=True, help="Head ref, e.g. HEAD or feature-branch")
    parser.add_argument("--strict", action="store_true", help="Strict mode: base/diff errors → non-zero exit")
    parser.add_argument("--json", action="store_true", help="Output JSON diagnostic")
    parser.add_argument("--output", help="Write JSON diagnostic to file")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    result = validate_reports(
        args.base,
        args.head,
        Path.cwd(),
        strict=args.strict,
    )

    output_text = json.dumps(result, ensure_ascii=False, indent=2)

    if args.json or args.output:
        if args.json:
            print(output_text)
        if args.output:
            p = Path(args.output)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(output_text, encoding="utf-8")
    else:
        # Human-readable
        status = "PASS" if result["passed"] else "FAIL"
        print(f"PR Report Governance — {status}")
        print(f"  Base: {result['base']}  Head: {result['head']}")
        print(f"  Pure docs: {result['pure_docs']}")
        print(f"  Reports required: {result['reports_required']}")
        print(f"  Reports present: {result['reports_present']}")
        if result["issues"]:
            print("  Issues:")
            for i in result["issues"]:
                print(f"    - {i}")

    return 0 if result["passed"] else (2 if args.strict else 1)


if __name__ == "__main__":
    raise SystemExit(main())
