"""Tests for scripts.triage.pr_state."""

import json
import subprocess
from unittest.mock import patch

import pytest

from scripts.triage.pr_state import (
    PRState,
    check_ci_status,
    query_pr_comments,
    query_pr_commits,
    query_pr_reviews,
    query_pr_state,
)


class TestPRState:
    """Test PR state query functions."""

    FAKE_PR_JSON = {
        "number": 2,
        "title": "Test PR",
        "author": {"login": "testuser"},
        "headRefName": "feature/test",
        "baseRefName": "main",
        "state": "OPEN",
        "merged": False,
        "mergeable": "MERGEABLE",
        "createdAt": "2024-01-15T10:00:00Z",
        "updatedAt": "2024-01-16T10:00:00Z",
        "labels": [{"name": "bug"}, {"name": "enhancement"}],
        "body": "This is a test PR body.",
    }

    @patch("scripts.triage.pr_state.subprocess.run")
    def test_query_pr_state(self, mock_run):
        """Should parse gh CLI JSON output into a PRState dataclass."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(self.FAKE_PR_JSON),
        )
        pr = query_pr_state(2)

        assert pr.number == 2
        assert pr.title == "Test PR"
        assert pr.author == "testuser"
        assert pr.source_branch == "feature/test"
        assert pr.base_branch == "main"
        assert pr.state == "OPEN"
        assert pr.merged is False
        assert pr.mergeable_state == "MERGEABLE"
        assert pr.labels == ["bug", "enhancement"]
        assert pr.body == "This is a test PR body."

    @patch("scripts.triage.pr_state.subprocess.run")
    def test_query_pr_state_empty_labels(self, mock_run):
        """Should handle PR with no labels."""
        data = {**self.FAKE_PR_JSON, "labels": []}
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(data)
        )
        pr = query_pr_state(2)
        assert pr.labels == []

    @patch("scripts.triage.pr_state.subprocess.run")
    def test_query_pr_state_gh_error(self, mock_run):
        """Should propagate CalledProcessError when gh fails."""
        mock_run.side_effect = subprocess.CalledProcessError(1, ["gh", "pr", "view"])
        with pytest.raises(subprocess.CalledProcessError):
            query_pr_state(999)

    @patch("scripts.triage.pr_state.subprocess.run")
    def test_pr_state_to_dict(self, mock_run):
        """to_dict() should return a plain dict with expected keys."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(self.FAKE_PR_JSON)
        )
        pr = query_pr_state(2)
        d = pr.to_dict()

        assert isinstance(d, dict)
        assert d["number"] == 2
        assert d["title"] == "Test PR"
        assert d["author"] == "testuser"
        assert d["labels"] == ["bug", "enhancement"]

    @patch("scripts.triage.pr_state.subprocess.run")
    def test_query_pr_reviews(self, mock_run):
        """Should parse review data from gh JSON."""
        reviews_data = {
            "reviews": [
                {
                    "author": {"login": "reviewer1"},
                    "state": "APPROVED",
                    "body": "Looks good",
                    "submittedAt": "2024-01-16T12:00:00Z",
                }
            ]
        }
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(reviews_data)
        )
        reviews = query_pr_reviews(2)
        assert len(reviews) == 1
        assert reviews[0]["author"] == "reviewer1"
        assert reviews[0]["state"] == "APPROVED"

    @patch("scripts.triage.pr_state.subprocess.run")
    def test_query_pr_reviews_empty(self, mock_run):
        """Should return empty list when PR has no reviews."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps({"reviews": []})
        )
        reviews = query_pr_reviews(2)
        assert reviews == []

    @patch("scripts.triage.pr_state.subprocess.run")
    def test_query_pr_comments(self, mock_run):
        """Should parse comment data."""
        comments_data = {
            "comments": [
                {
                    "author": {"login": "commenter1"},
                    "body": "Have you considered edge cases?",
                    "createdAt": "2024-01-16T13:00:00Z",
                    "url": "https://github.com/owner/repo/pull/2#issuecomment-1",
                }
            ]
        }
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(comments_data)
        )
        comments = query_pr_comments(2)
        assert len(comments) == 1
        assert comments[0]["author"] == "commenter1"

    @patch("scripts.triage.pr_state.subprocess.run")
    def test_query_pr_commits(self, mock_run):
        """Should parse commit data."""
        commits_data = {
            "commits": [
                {
                    "oid": "abc123def456",
                    "messageHeadline": "Fix critical bug",
                    "author": {"name": "dev1"},
                    "committedDate": "2024-01-15T11:00:00Z",
                }
            ]
        }
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(commits_data)
        )
        commits = query_pr_commits(2)
        assert len(commits) == 1
        assert commits[0]["sha"] == "abc123def456"
        assert commits[0]["message"] == "Fix critical bug"

    @patch("scripts.triage.pr_state.subprocess.run")
    def test_check_ci_status(self, mock_run):
        """Should parse CI status check rollup."""
        ci_data = {
            "statusCheckRollup": [
                {
                    "name": "CI / tests",
                    "status": "COMPLETED",
                    "conclusion": "SUCCESS",
                    "detailsUrl": "https://github.com/owner/repo/actions/runs/1",
                }
            ]
        }
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(ci_data)
        )
        ci = check_ci_status(2)
        assert ci is not None
        assert "CI / tests" in ci
        assert ci["CI / tests"]["conclusion"] == "SUCCESS"

    @patch("scripts.triage.pr_state.subprocess.run")
    def test_check_ci_status_unavailable(self, mock_run):
        """Should return None when gh CLI fails."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="gh error"
        )
        ci = check_ci_status(2)
        assert ci is None


class TestPRStateDataclass:
    """Test PRState dataclass directly."""

    def test_to_dict_returns_all_fields(self):
        """Verify to_dict covers all dataclass fields."""
        pr = PRState(
            number=3,
            title="Another PR",
            author="dev2",
            source_branch="fix/issue",
            base_branch="main",
            state="MERGED",
            merged=True,
            mergeable_state="",
            created_at="2024-02-01T08:00:00Z",
            updated_at="2024-02-02T08:00:00Z",
            labels=["docs"],
            body="Fixes an issue.",
        )
        d = pr.to_dict()
        assert d["number"] == 3
        assert d["title"] == "Another PR"
        assert d["merged"] is True
        assert d["labels"] == ["docs"]
