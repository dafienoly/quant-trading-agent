"""Tests for scripts.triage.rebase_attempt."""

import os
import subprocess
import tempfile
from unittest.mock import patch

import pytest

from scripts.triage.rebase_attempt import (
    _parse_merge_tree_conflicts,
    attempt_rebase,
    save_conflict_patch,
)


class TestAttemptRebase:
    """Test attempt_rebase function."""

    @patch("scripts.triage.rebase_attempt.subprocess.run")
    def test_dry_run_no_conflicts(self, mock_run):
        """Should return success when no conflicts in dry-run mode."""
        mock_run.side_effect = [
            subprocess.CompletedProcess([], returncode=0, stdout="", stderr=""),
            subprocess.CompletedProcess([], returncode=0, stdout="abc123\n"),
            subprocess.CompletedProcess([], returncode=0, stdout="", stderr=""),
        ]
        result = attempt_rebase("feature/test", dry_run=True)
        assert result["success"] is True
        assert result["conflict_files"] == []
        assert result["error"] is None

    @patch("scripts.triage.rebase_attempt.subprocess.run")
    def test_dry_run_with_conflicts(self, mock_run):
        """Should detect conflicts in dry-run mode."""
        merge_output = "CONFLICT (content): Merge conflict in src/file.py"
        mock_run.side_effect = [
            subprocess.CompletedProcess([], returncode=0, stdout="", stderr=""),
            subprocess.CompletedProcess([], returncode=0, stdout="abc123\n"),
            subprocess.CompletedProcess([], returncode=0, stdout=merge_output, stderr=""),
        ]
        result = attempt_rebase("feature/test", dry_run=True)
        assert result["success"] is False
        assert "src/file.py" in result["conflict_files"]
        assert result["error"] == "conflicts detected"

    @patch("scripts.triage.rebase_attempt.subprocess.run")
    def test_merge_base_error(self, mock_run):
        """Should handle merge-base failure."""
        mock_run.side_effect = [
            subprocess.CompletedProcess([], returncode=0, stdout="", stderr=""),
            subprocess.CalledProcessError(1, ["git", "merge-base"]),
        ]
        result = attempt_rebase("feature/test", dry_run=True)
        assert result["success"] is False
        assert result["error"] == "merge-base not found"

    @patch("scripts.triage.rebase_attempt.subprocess.run")
    def test_live_rebase_success(self, mock_run):
        """Should perform live rebase when dry_run=False and no conflicts."""
        mock_run.side_effect = [
            subprocess.CompletedProcess([], returncode=0, stdout="", stderr=""),
            subprocess.CompletedProcess([], returncode=0, stdout="abc123\n"),
            subprocess.CompletedProcess([], returncode=0, stdout="", stderr=""),
            subprocess.CompletedProcess(
                [], returncode=0, stdout="Successfully rebased", stderr=""
            ),
        ]
        result = attempt_rebase("feature/test", dry_run=False)
        assert result["success"] is True
        assert result["conflict_files"] == []
        assert result["error"] is None

    @patch("scripts.triage.rebase_attempt.subprocess.run")
    def test_live_rebase_skipped_when_conflicts(self, mock_run):
        """Should skip live rebase when conflicts detected in merge-tree."""
        merge_output = "CONFLICT (content): Merge conflict in src/file.py"
        mock_run.side_effect = [
            subprocess.CompletedProcess([], returncode=0, stdout="", stderr=""),
            subprocess.CompletedProcess([], returncode=0, stdout="abc123\n"),
            subprocess.CompletedProcess([], returncode=0, stdout=merge_output, stderr=""),
        ]
        result = attempt_rebase("feature/test", dry_run=False)
        assert result["success"] is False
        assert result["error"] == "cannot rebase with unresolved conflicts"

    @patch("scripts.triage.rebase_attempt.subprocess.run")
    def test_live_rebase_failure_aborts(self, mock_run):
        """Should abort rebase when git rebase fails."""
        mock_run.side_effect = [
            subprocess.CompletedProcess([], returncode=0, stdout="", stderr=""),
            subprocess.CompletedProcess([], returncode=0, stdout="abc123\n"),
            subprocess.CompletedProcess([], returncode=0, stdout="", stderr=""),
            subprocess.CompletedProcess(
                [], returncode=1, stdout="", stderr="rebase failed"
            ),
            subprocess.CompletedProcess([], returncode=0, stdout="", stderr=""),
        ]
        result = attempt_rebase("feature/test", dry_run=False)
        assert result["success"] is False
        assert result["error"] == "rebase failed"

    @patch("scripts.triage.rebase_attempt.subprocess.run")
    def test_live_rebase_exception(self, mock_run):
        """Should handle CalledProcessError during rebase."""
        mock_run.side_effect = [
            subprocess.CompletedProcess([], returncode=0, stdout="", stderr=""),
            subprocess.CompletedProcess([], returncode=0, stdout="abc123\n"),
            subprocess.CompletedProcess([], returncode=0, stdout="", stderr=""),
            subprocess.CalledProcessError(1, ["git", "rebase"]),
        ]
        result = attempt_rebase("feature/test", dry_run=False)
        assert result["success"] is False


class TestParseMergeTreeConflicts:
    """Test _parse_merge_tree_conflicts helper."""

    def test_standard_format(self):
        """Should parse 'CONFLICT (content): Merge conflict in <file>' format."""
        output = "CONFLICT (content): Merge conflict in src/file.py"
        files = _parse_merge_tree_conflicts(output)
        assert "src/file.py" in files

    def test_multiple_conflicts(self):
        """Should parse multiple conflict lines."""
        output = (
            "CONFLICT (content): Merge conflict in src/a.py\n"
            "CONFLICT (content): Merge conflict in src/b.py\n"
        )
        files = _parse_merge_tree_conflicts(output)
        assert "src/a.py" in files
        assert "src/b.py" in files
        assert len(files) == 2

    def test_changed_in_both_format(self):
        """Should parse 'changed in both' fallback format."""
        output = "changed in both: src/file.py"
        files = _parse_merge_tree_conflicts(output)
        assert "src/file.py" in files

    def test_no_conflicts(self):
        """Should return empty list when no conflicts present."""
        assert _parse_merge_tree_conflicts("") == []
        assert _parse_merge_tree_conflicts("no conflicts") == []


class TestSaveConflictPatch:
    """Test save_conflict_patch function."""

    @patch("scripts.triage.rebase_attempt.subprocess.run")
    def test_saves_patch_file(self, mock_run):
        """Should write header and diff content to patch file."""
        mock_run.return_value = subprocess.CompletedProcess(
            [], returncode=0, stdout="--- a/src/file.py\n+++ b/src/file.py\n+new line"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False) as f:
            path = f.name
        try:
            result = save_conflict_patch(2, ["src/file.py"], path)
            assert result == path
            with open(path, encoding="utf-8") as fh:
                content = fh.read()
            assert "PR #2" in content
            assert "Conflict Patch" in content
            assert "src/file.py" in content
            assert "+new line" in content
        finally:
            os.unlink(path)

    @patch("scripts.triage.rebase_attempt.subprocess.run")
    def test_multiple_conflict_files_in_header(self, mock_run):
        """Should list all conflict files in patch header."""
        mock_run.return_value = subprocess.CompletedProcess(
            [], returncode=0, stdout="diff content"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False) as f:
            path = f.name
        try:
            save_conflict_patch(5, ["src/a.py", "src/b.py"], path)
            with open(path, encoding="utf-8") as fh:
                content = fh.read()
            assert "src/a.py, src/b.py" in content
        finally:
            os.unlink(path)
