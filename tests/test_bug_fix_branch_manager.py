"""Unit tests for BugFixBranchManager — branch-isolated fix execution."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from src.product_app.bug_fix_branch_manager import (
    BugFixBranchManager,
    BugFixWorktree,
)


class TestBranchNaming:
    def test_branch_name_starts_with_bugfix_prefix(self):
        """Branch name must start with bugfix/."""
        manager = BugFixBranchManager(project_root=Path("/tmp/project"))
        name, path = manager._make_worktree_info("BUG_001")
        assert name.startswith("bugfix/"), (
            f"Expected bugfix/ prefix, got {name}"
        )

    def test_branch_name_contains_bug_id(self):
        """Branch name must contain the bug ID."""
        manager = BugFixBranchManager(project_root=Path("/tmp/project"))
        name, path = manager._make_worktree_info("BUG_ABC123")
        assert "BUG_ABC123" in name

    def test_branch_name_formatted_correctly(self):
        """Branch name follows bugfix/<bug-id>-<YYYYMMDD-HHMMSS> pattern."""
        manager = BugFixBranchManager(project_root=Path("/tmp/project"))
        name, path = manager._make_worktree_info("BUG_001")
        # Expected: bugfix/BUG_001-20260612-143000
        assert name.startswith("bugfix/BUG_001-")
        # After prefix, we expect 15 chars: YYYYMMDD-HHMMSS
        suffix = name[len("bugfix/BUG_001-"):]
        assert len(suffix) == 15, f"Expected 15-char timestamp, got '{suffix}' (len={len(suffix)})"


class TestWorktreePath:
    def test_worktree_path_under_configured_root(self):
        """Worktree path must be under configured root."""
        manager = BugFixBranchManager(
            project_root=Path("/tmp/project"),
            worktree_root=Path("/tmp/project/runtime/bugfix_worktrees"),
        )
        name, path = manager._make_worktree_info("BUG_001")
        expected_parent = Path("/tmp/project/runtime/bugfix_worktrees")
        assert str(path).startswith(str(expected_parent)), (
            f"Worktree {path} not under {expected_parent}"
        )

    def test_worktree_path_includes_bug_id(self):
        """Worktree path contains the bug ID."""
        manager = BugFixBranchManager(
            project_root=Path("/tmp/project"),
            worktree_root=Path("/tmp/project/runtime/bugfix_worktrees"),
        )
        name, path = manager._make_worktree_info("BUG_ABC123")
        assert "BUG_ABC123" in str(path)


class TestPathValidation:
    def test_rejects_path_traversal_in_cleanup(self):
        """cleanup_worktree must reject paths outside configured root."""
        manager = BugFixBranchManager(
            project_root=Path("/tmp/project"),
            worktree_root=Path("/tmp/project/runtime/bugfix_worktrees"),
        )
        malicious = BugFixWorktree(
            bug_id="EVIL",
            base_branch="main",
            branch_name="bugfix/EVIL",
            path=Path("/tmp/important/config"),
            base_sha="abc123",
        )
        with pytest.raises(ValueError, match="outside|not under|invalid"):
            manager.cleanup_worktree(malicious, keep_on_failure=False)

    def test_cleanup_only_removes_known_worktree(self):
        """Cleanup returns early for unknown/nonexistent worktree paths."""
        manager = BugFixBranchManager(
            project_root=Path("/tmp/project"),
            worktree_root=Path("/tmp/project/runtime/bugfix_worktrees"),
        )
        # Non-existent path under allowed root should be ok to remove
        unknown = BugFixWorktree(
            bug_id="UNKNOWN",
            base_branch="main",
            branch_name="bugfix/UNKNOWN",
            path=Path("/tmp/project/runtime/bugfix_worktrees/UNKNOWN-20260612-120000"),
            base_sha="abc123",
        )
        # Should not raise or crash — just warn
        result = manager.cleanup_worktree(unknown, keep_on_failure=False)
        assert result is not None


class TestBaseBranchAndSHA:
    @patch("src.product_app.bug_fix_branch_manager.subprocess.run")
    def test_records_base_branch_and_sha(self, mock_run):
        """BugFixWorktree must record base_branch and base_sha."""
        # mock git rev-parse HEAD
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "abc123def456\n"
        mock_run.return_value = mock_result

        manager = BugFixBranchManager(
            project_root=Path("/tmp/project"),
            base_branch="main",
        )
        worktree = manager.prepare_worktree("BUG_001")
        assert worktree.base_branch == "main"
        assert worktree.base_sha == "abc123def456"


class TestCommit:
    @patch("src.product_app.bug_fix_branch_manager.subprocess.run")
    def test_commits_only_proposal_files(self, mock_run):
        """commit_fix must only commit files from the proposal."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "def789commit\n"
        mock_run.return_value = mock_result

        manager = BugFixBranchManager(project_root=Path("/tmp/project"))
        worktree = BugFixWorktree(
            bug_id="BUG_001",
            base_branch="main",
            branch_name="bugfix/BUG_001-20260612-120000",
            path=Path("/tmp/worktree"),
            base_sha="abc123",
        )
        sha = manager.commit_fix(
            worktree,
            files=["src/module.py", "tests/test_module.py"],
            message="fix(auto): BUG_001 - test fix",
        )
        assert sha == "def789commit"
        # Verify git add was called for each file
        add_calls = [
            c for c in mock_run.call_args_list
            if "add" in str(c)
        ]
        assert len(add_calls) >= 2  # at least 2 add commands

    @patch("src.product_app.bug_fix_branch_manager.subprocess.run")
    def test_commit_failure_raises_error(self, mock_run):
        """commit_fix must raise when git commit fails."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "commit failed"
        mock_run.return_value = mock_result

        manager = BugFixBranchManager(project_root=Path("/tmp/project"))
        worktree = BugFixWorktree(
            bug_id="BUG_001",
            base_branch="main",
            branch_name="bugfix/BUG_001",
            path=Path("/tmp/worktree"),
            base_sha="abc123",
        )
        with pytest.raises(RuntimeError, match="commit failed"):
            manager.commit_fix(worktree, files=["src/mod.py"], message="fix")


class TestMerge:
    @patch("src.product_app.bug_fix_branch_manager.subprocess.run")
    def test_refuses_merge_when_auto_merge_disabled(self, mock_run):
        """merge_fix must refuse when BUGFIX_AUTO_MERGE=false."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_run.return_value = mock_result

        manager = BugFixBranchManager(
            project_root=Path("/tmp/project"),
            base_branch="main",
        )
        worktree = BugFixWorktree(
            bug_id="BUG_001",
            base_branch="main",
            branch_name="bugfix/BUG_001",
            path=Path("/tmp/worktree"),
            base_sha="abc123",
        )
        result = manager.merge_fix(worktree)
        assert result.get("merged") is False
        assert "auto_merge_disabled" in result.get("reason", "") or "disabled" in result.get("reason", "").lower()

    @patch("src.product_app.bug_fix_branch_manager.subprocess.run")
    def test_merge_works_when_explicitly_allowed(self, mock_run):
        """merge_fix can succeed when explicitly allowed."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "merged_sha\n"
        mock_run.return_value = mock_result

        manager = BugFixBranchManager(
            project_root=Path("/tmp/project"),
            base_branch="main",
        )
        worktree = BugFixWorktree(
            bug_id="BUG_001",
            base_branch="main",
            branch_name="bugfix/BUG_001",
            path=Path("/tmp/worktree"),
            base_sha="abc123",
        )
        result = manager.merge_fix(worktree, force=True)
        assert result.get("merged") is True
        assert "merged_sha" in result.get("merge_commit", "")
