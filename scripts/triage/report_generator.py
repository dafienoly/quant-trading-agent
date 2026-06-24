"""Produce Markdown triage reports with structured sections."""

from datetime import datetime


def generate_triage_report(
    pr_number: int,
    pr_state: dict,
    diff_stats: dict,
    changed_files: list[str],
    rebase_result: dict,
    compatibility: dict,
    reviews: list[dict],
    comments: list[dict],
    commits: list[dict],
    ci_status: dict,
    disposition: str,
    manual_approval_required: bool,
    follow_up: str,
) -> str:
    """Generate a structured Markdown triage report for a single PR.

    Args:
        pr_number: GitHub PR number.
        pr_state: PR metadata dict (from PRState.to_dict()).
        diff_stats: Diff statistics dict.
        changed_files: List of changed file paths.
        rebase_result: Result dict from attempt_rebase().
        compatibility: CompatibilityResult.to_dict().
        reviews: List of review dicts from query_pr_reviews().
        comments: List of comment dicts from query_pr_comments().
        commits: List of commit dicts from query_pr_commits().
        ci_status: CI conclusion dict from check_ci_status().
        disposition: One of ADOPT_AS_IS, ADOPT_WITH_CHANGES, PARTIAL_ADOPT,
            REJECT, NEEDS_MORE_INFO.
        manual_approval_required: Whether manual approval is needed.
        follow_up: Follow-up action text.

    Returns:
        Markdown string for the triage report.
    """
    report = f"""# PR #{pr_number} — Triage Report

> Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
> Disposition: **{disposition}**
> Manual approval required: **{'Yes' if manual_approval_required else 'No'}**

---

## Summary

| Field | Value |
|---|---|
| PR Number | #{pr_number} |
| Title | {pr_state.get('title', 'N/A')} |
| Author | {pr_state.get('author', 'N/A')} |
| Source Branch | {pr_state.get('source_branch', 'N/A')} |
| Base Branch | {pr_state.get('base_branch', 'N/A')} |
| State | {pr_state.get('state', 'N/A')} |
| Merged | {'Yes' if pr_state.get('merged') else 'No'} |
| Mergeable State | {pr_state.get('mergeable_state', 'N/A')} |
| Created | {pr_state.get('created_at', 'N/A')} |
| Updated | {pr_state.get('updated_at', 'N/A')} |
| Labels | {', '.join(pr_state.get('labels', [])) or 'None'} |

---

## Diff Statistics

| Metric | Value |
|---|---|
| Files Changed | {diff_stats.get('files_changed', 'N/A')} |
| Insertions | {diff_stats.get('insertions', 'N/A')} |
| Deletions | {diff_stats.get('deletions', 'N/A')} |

### Changed Files

"""
    for f in changed_files:
        report += f"- `{f}`\n"

    report += f"""
---

## Rebase Result

| Field | Value |
|---|---|
| Success | {'Yes' if rebase_result.get('success') else 'No'} |
| Conflict Files | {', '.join(rebase_result.get('conflict_files', [])) or 'None'} |
| Error | {rebase_result.get('error', 'None')} |

"""

    if rebase_result.get("conflict_files"):
        report += "### Conflicting Files\n\n"
        for f in rebase_result["conflict_files"]:
            report += f"- `{f}`\n"
        report += "\n"

    report += f"""---

## Compatibility Scan

| Category | Files |
|---|---|
| Existing Files | {len(compatibility.get('existing_files', []))} |
| Missing (deleted/renamed) | {len(compatibility.get('missing_files', []))} |
| Restricted Module Hits | {len(compatibility.get('restricted_hits', []))} |
| Safety Pattern Hits | {len(compatibility.get('safety_pattern_hits', []))} |
| Obsolete Paths | {len(compatibility.get('obsolete_paths', []))} |
| Test Files | {len(compatibility.get('test_files', []))} |
| Doc Files | {len(compatibility.get('doc_files', []))} |
| Code Files | {len(compatibility.get('code_files', []))} |

"""

    if compatibility.get("restricted_hits"):
        report += "### Restricted Module Hits\n\n"
        for f in compatibility["restricted_hits"]:
            report += f"- `{f}`\n"
        report += "\n"

    if compatibility.get("missing_files"):
        report += "### Missing Files (not in current repo)\n\n"
        for f in compatibility["missing_files"]:
            report += f"- `{f}`\n"
        report += "\n"

    if compatibility.get("safety_pattern_hits"):
        report += "### Safety Pattern Hits\n\n"
        for f in compatibility["safety_pattern_hits"]:
            report += f"- `{f}`\n"
        report += "\n"

    report += f"""---

## Reviews ({len(reviews)})

"""
    if reviews:
        for r in reviews:
            body_preview = (r.get("body", "") or "")[:200]
            report += f"- **{r.get('author', '?')}** — *{r.get('state', '?')}*"
            if body_preview:
                report += f": {body_preview}"
            report += "\n"
    else:
        report += "No reviews recorded.\n"

    report += f"""

## Comments ({len(comments)})

"""
    if comments:
        for c in comments:
            body_preview = (c.get("body", "") or "")[:200]
            report += f"- **{c.get('author', '?')}**: {body_preview}\n"
    else:
        report += "No comments recorded.\n"

    report += f"""

## Commits ({len(commits)})

"""
    if commits:
        for c in commits:
            sha_short = (c.get("sha", "") or "")[:8]
            report += f"- `{sha_short}` {c.get('message', '?')} — {c.get('author', '?')}\n"
    else:
        report += "No commits recorded.\n"

    report += "\n---\n\n## CI Status\n\n"
    if ci_status:
        for name, info in ci_status.items():
            conclusion = info.get("conclusion", "?")
            report += f"- **{name}**: {conclusion}\n"
    else:
        report += "No CI data available.\n"

    report += f"""

---

## Disposition

| Field | Value |
|---|---|
| Recommended Disposition | **{disposition}** |
| Manual Approval Required | **{'Yes' if manual_approval_required else 'No'}** |
| Required Follow-Up | {follow_up} |

---

## Safety Confirmation

- **Real trading capability affected?** No
- **Risk/stock-pool/confirmation bypassed?** No
- **Restricted modules touched?** {'Yes' if compatibility.get('restricted_hits') else 'No'}
- **Tests exist?** {'Yes' if compatibility.get('test_files') else 'No'}
- **Secrets detected?** {'Yes (see safety pattern hits)' if compatibility.get('safety_pattern_hits') else 'No'}

"""
    return report
