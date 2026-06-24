"""Fetch PR diff and changed file lists via gh CLI."""

import subprocess
from pathlib import Path
from typing import Optional


def fetch_pr_diff(pr_number: int, output_dir: Optional[str] = None) -> str:
    """Fetch a PR's diff text via ``gh pr diff``.

    Args:
        pr_number: GitHub PR number.
        output_dir: Optional directory to save the diff file.

    Returns:
        Diff text content.

    Raises:
        subprocess.CalledProcessError: if gh CLI fails.
    """
    result = subprocess.run(
        ["gh", "pr", "diff", str(pr_number)],
        capture_output=True,
        text=True,
        check=True,
    )
    diff_text = result.stdout
    if output_dir:
        path = Path(output_dir) / f"PR-{pr_number}.diff"
        path.write_text(diff_text, encoding="utf-8")
    return diff_text


def fetch_pr_changed_files(pr_number: int) -> list[str]:
    """Get the list of files changed in a PR (``gh pr diff --name-only``)."""
    result = subprocess.run(
        ["gh", "pr", "diff", str(pr_number), "--name-only"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def fetch_pr_diffstat(pr_number: int) -> dict:
    """Get diff statistics (files changed, insertions, deletions).

    Parses ``gh pr diff --stat`` output.
    """
    result = subprocess.run(
        ["gh", "pr", "diff", str(pr_number), "--stat"],
        capture_output=True,
        text=True,
        check=True,
    )
    stat_lines = result.stdout.strip().splitlines()
    summary: dict = {"files_changed": 0, "insertions": 0, "deletions": 0}
    if stat_lines:
        last = stat_lines[-1]
        for part in last.split(","):
            part = part.strip()
            if "file" in part:
                summary["files_changed"] = _parse_stat_number(part)
            elif "insertion" in part:
                summary["insertions"] = _parse_stat_number(part)
            elif "deletion" in part:
                summary["deletions"] = _parse_stat_number(part)
    return summary


def _parse_stat_number(text: str) -> int:
    """Extract leading integer from stat text like ' 3 files changed'."""
    for i, ch in enumerate(text):
        if not ch.isdigit():
            return int(text[:i]) if i > 0 else 0
    return int(text) if text else 0
