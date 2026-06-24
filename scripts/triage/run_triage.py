#!/usr/bin/env python3
"""Main CLI entry point for running a full PR triage workflow."""

import argparse
import json
import sys
from pathlib import Path

from scripts.triage import __version__
from scripts.triage.pr_state import (
    check_ci_status,
    query_pr_comments,
    query_pr_commits,
    query_pr_reviews,
    query_pr_state,
)
from scripts.triage.diff_extractor import (
    fetch_pr_changed_files,
    fetch_pr_diff,
    fetch_pr_diffstat,
)
from scripts.triage.compat_scanner import scan_changed_files
from scripts.triage.rebase_attempt import attempt_rebase
from scripts.triage.report_generator import generate_triage_report


def _pr_state_to_dict(pr_state) -> dict:
    """Convert PRState dataclass to a plain dict, handling nested objects."""
    d = pr_state.to_dict()
    # Ensure author is a string
    if isinstance(d.get("author"), dict):
        d["author"] = d["author"].get("login", str(d["author"]))
    return d


def _compat_to_dict(compat_result) -> dict:
    """Convert CompatibilityResult dataclass to a plain dict."""
    return {
        "pr_number": compat_result.pr_number,
        "all_changed_files": list(compat_result.all_changed_files),
        "existing_files": list(compat_result.existing_files),
        "missing_files": list(compat_result.missing_files),
        "restricted_hits": list(compat_result.restricted_hits),
        "safety_pattern_hits": list(compat_result.safety_pattern_hits),
        "obsolete_paths": list(compat_result.obsolete_paths),
        "test_files": list(compat_result.test_files),
        "doc_files": list(compat_result.doc_files),
        "code_files": list(compat_result.code_files),
    }


def run_triage(
    pr_number: int,
    output_path: str,
    diff_output_dir: str = "",
    dry_run_rebase: bool = True,
) -> dict:
    """Execute full triage workflow for a single PR.

    Args:
        pr_number: GitHub PR number.
        output_path: Path for the generated Markdown report.
        diff_output_dir: Optional directory to save the raw diff.
        dry_run_rebase: If True, only dry-run the rebase conflict check.

    Returns:
        dict with keys: report_path, disposition, manual_approval_required.
    """
    # 1. PR state
    pr_state = query_pr_state(pr_number)
    reviews = query_pr_reviews(pr_number) or []
    comments = query_pr_comments(pr_number) or []
    commits = query_pr_commits(pr_number) or []
    ci_status = check_ci_status(pr_number) or {}

    # 2. Diff extraction
    if diff_output_dir:
        Path(diff_output_dir).mkdir(parents=True, exist_ok=True)
        fetch_pr_diff(pr_number, output_dir=diff_output_dir)

    changed_files = fetch_pr_changed_files(pr_number)
    diff_stats = fetch_pr_diffstat(pr_number)

    # 3. Compatibility scan
    compat = scan_changed_files(pr_number, changed_files)

    # 4. Rebase attempt (dry-run)
    rebase_result = attempt_rebase(
        source_branch=pr_state.source_branch,
        dry_run=dry_run_rebase,
    )

    # 5. Determine disposition
    disposition, manual_approval_required, follow_up = _classify(pr_state, compat, changed_files)

    # 6. Generate report
    report_md = generate_triage_report(
        pr_number=pr_number,
        pr_state=_pr_state_to_dict(pr_state),
        diff_stats=diff_stats,
        changed_files=changed_files,
        rebase_result=rebase_result,
        compatibility=_compat_to_dict(compat),
        reviews=reviews,
        comments=comments,
        commits=commits,
        ci_status=ci_status,
        disposition=disposition,
        manual_approval_required=manual_approval_required,
        follow_up=follow_up,
    )

    Path(output_path).write_text(report_md, encoding="utf-8")
    print(f"Triage report written to {output_path}")

    return {
        "report_path": output_path,
        "disposition": disposition,
        "manual_approval_required": manual_approval_required,
    }


def _classify(pr_state, compat, changed_files) -> tuple:
    """Automated triage classification logic.

    Returns (disposition, manual_approval_required, follow_up).
    """
    manual_approval_required = bool(compat.restricted_hits)
    follow_up_parts = []

    # Check for secrets
    if compat.safety_pattern_hits:
        return (
            "NEEDS_MORE_INFO",
            manual_approval_required,
            "Safety pattern hits detected; manual review required before disposition.",
        )

    # Check restricted module hits
    if compat.restricted_hits:
        manual_approval_required = True
        follow_up_parts.append(
            f"Restricted module touch detected: {', '.join(compat.restricted_hits)}. "
            "Requires architecture review and negative tests before adoption."
        )

    # Check missing files (deleted/renamed paths)
    if compat.missing_files:
        follow_up_parts.append(
            f"Some changed files no longer exist ({len(compat.missing_files)} missing). "
            "Changes may need reimplementation."
        )

    # Check obsolete paths
    if compat.obsolete_paths:
        follow_up_parts.append("Obsolete paths detected; reimplementation recommended.")

    # Check test coverage (only when changed_files failed to load)
    if not compat.test_files and not changed_files:
        follow_up_parts.append("PR does not include tests. Tests must be added before adoption.")

    # PR state-based checks
    if pr_state.merged:
        follow_up_parts.append("PR is already merged. Review whether changes are already applied.")

    if not follow_up_parts:
        disposition = "ADOPT_AS_IS"
        follow_up_parts.append("PR appears compatible. Proceed through normal pipeline.")
    else:
        if compat.restricted_hits:
            disposition = "ADOPT_WITH_CHANGES"
        elif compat.missing_files or compat.obsolete_paths:
            disposition = "PARTIAL_ADOPT"
        else:
            disposition = "ADOPT_WITH_CHANGES"

    return disposition, manual_approval_required, " | ".join(follow_up_parts)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Historical PR Triage Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example:\n"
            "  python -m scripts.triage.run_triage --pr 2 --output docs/triage/PR-2-triage-report.md\n"
        ),
    )
    parser.add_argument(
        "--pr",
        type=int,
        required=True,
        help="GitHub PR number to triage",
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output path for the Markdown triage report",
    )
    parser.add_argument(
        "--diff-dir",
        type=str,
        default="",
        help="Optional directory to save raw PR diff",
    )
    parser.add_argument(
        "--no-dry-run-rebase",
        action="store_true",
        help="Perform a real rebase instead of dry-run conflict detection",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"triage-framework {__version__}",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    args = parse_args(argv)
    try:
        result = run_triage(
            pr_number=args.pr,
            output_path=args.output,
            diff_output_dir=args.diff_dir or "",
            dry_run_rebase=not args.no_dry_run_rebase,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(f"Triage failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
