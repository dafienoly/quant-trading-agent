"""Query PR metadata, labels, comments, linked issues via gh CLI."""

import json
import subprocess
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PRState:
    """Structured PR metadata from GitHub."""

    number: int
    title: str
    author: str
    source_branch: str
    base_branch: str
    state: str
    merged: bool
    mergeable_state: str
    created_at: str
    updated_at: str
    labels: list = field(default_factory=list)
    body: str = ""

    def to_dict(self) -> dict:
        """Convert to plain dict for serialization."""
        return {
            "number": self.number,
            "title": self.title,
            "author": self.author,
            "source_branch": self.source_branch,
            "base_branch": self.base_branch,
            "state": self.state,
            "merged": self.merged,
            "mergeable_state": self.mergeable_state,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "labels": list(self.labels),
            "body": self.body,
        }


def query_pr_state(pr_number: int) -> PRState:
    """Query PR metadata via ``gh pr view --json ...``.

    Args:
        pr_number: GitHub PR number.

    Returns:
        PRState dataclass with all available metadata fields.

    Raises:
        subprocess.CalledProcessError: if ``gh`` CLI is unavailable or the
            PR does not exist.
    """
    fields = (
        "number,title,author,headRefName,baseRefName,state,merged,"
        "mergeable,createdAt,updatedAt,labels,body"
    )
    result = subprocess.run(
        ["gh", "pr", "view", str(pr_number), "--json", fields],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)

    return PRState(
        number=data["number"],
        title=data["title"],
        author=data["author"]["login"],
        source_branch=data["headRefName"],
        base_branch=data["baseRefName"],
        state=data["state"],
        merged=data["merged"],
        mergeable_state=data.get("mergeable", "UNKNOWN"),
        created_at=data["createdAt"],
        updated_at=data["updatedAt"],
        labels=[label["name"] for label in data.get("labels", [])],
        body=data.get("body", ""),
    )


def _parse_gh_comment(raw: dict) -> dict:
    """Extract a structured comment record from raw gh JSON."""
    return {
        "author": raw.get("author", {}).get("login", "unknown"),
        "body": raw.get("body", ""),
        "created_at": raw.get("createdAt", ""),
        "url": raw.get("url", ""),
    }


def query_pr_reviews(pr_number: int) -> list[dict]:
    """Query PR review summaries via ``gh pr view --json reviews``.

    Returns a list of dicts with keys: author, state, body, submitted_at.
    """
    result = subprocess.run(
        ["gh", "pr", "view", str(pr_number), "--json", "reviews"],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    reviews = []
    for r in data.get("reviews", []):
        reviews.append(
            {
                "author": r.get("author", {}).get("login", "unknown"),
                "state": r.get("state", ""),
                "body": r.get("body", ""),
                "submitted_at": r.get("submittedAt", ""),
            }
        )
    return reviews


def query_pr_comments(pr_number: int) -> list[dict]:
    """Query issue-style comments on a PR via ``gh pr view --json comments``."""
    result = subprocess.run(
        ["gh", "pr", "view", str(pr_number), "--json", "comments"],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    return [_parse_gh_comment(c) for c in data.get("comments", [])]


def query_pr_commits(pr_number: int) -> list[dict]:
    """Query commit list for a PR via ``gh pr view --json commits``."""
    result = subprocess.run(
        ["gh", "pr", "view", str(pr_number), "--json", "commits"],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    commits = []
    for c in data.get("commits", []):
        commits.append(
            {
                "sha": c.get("oid", ""),
                "message": c.get("messageHeadline", ""),
                "author": c.get("author", {}).get("name", "unknown"),
                "committed_date": c.get("committedDate", ""),
            }
        )
    return commits


def check_ci_status(pr_number: int) -> Optional[dict]:
    """Check latest CI conclusion for a PR via ``gh pr view --json statusCheckRollup``.

    Returns None if no CI data is available.
    """
    result = subprocess.run(
        ["gh", "pr", "view", str(pr_number), "--json", "statusCheckRollup"],
        capture_output=True,
        text=True,
        # Do not raise on missing CI data
    )
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    checks = data.get("statusCheckRollup", [])
    if not checks:
        return None
    conclusions = {}
    for c in checks:
        name = c.get("name", "unknown")
        conclusions[name] = {
            "status": c.get("status", ""),
            "conclusion": c.get("conclusion", ""),
            "url": c.get("detailsUrl", ""),
        }
    return conclusions
