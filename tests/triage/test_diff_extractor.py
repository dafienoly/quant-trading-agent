"""Tests for scripts.triage.diff_extractor."""

import subprocess
from unittest.mock import ANY, patch

import pytest

from scripts.triage.diff_extractor import (
    _parse_stat_number,
    fetch_pr_changed_files,
    fetch_pr_diff,
    fetch_pr_diffstat,
)


class TestFetchPrDiff:
    """Test diff fetching functions."""

    FAKE_DIFF = """diff --git a/src/example.py b/src/example.py
index abc..def 100644
--- a/src/example.py
+++ b/src/example.py
@@ -1,3 +1,4 @@
+new line
 old line
"""

    @patch("scripts.triage.diff_extractor.subprocess.run")
    def test_fetch_pr_diff_returns_text(self, mock_run):
        """Should return diff text from gh pr diff."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=self.FAKE_DIFF
        )
        diff = fetch_pr_diff(2)
        assert "diff --git" in diff
        assert "new line" in diff

    @patch("scripts.triage.diff_extractor.subprocess.run")
    def test_fetch_pr_diff_calls_correct_command(self, mock_run):
        """Should call gh pr diff with correct PR number."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=self.FAKE_DIFF
        )
        fetch_pr_diff(42)
        mock_run.assert_called_once_with(
            ["gh", "pr", "diff", "42"],
            capture_output=True,
            text=True,
            check=True,
        )

    @patch("scripts.triage.diff_extractor.subprocess.run")
    def test_fetch_pr_diff_saves_to_output_dir(self, mock_run):
        """Should write diff to file when output_dir is given."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=self.FAKE_DIFF
        )
        with patch("scripts.triage.diff_extractor.Path.write_text") as mock_write:
            result = fetch_pr_diff(2, output_dir="/tmp/diffs")
            mock_write.assert_called_once_with(self.FAKE_DIFF, encoding="utf-8")
            assert result == self.FAKE_DIFF

    @patch("scripts.triage.diff_extractor.subprocess.run")
    def test_fetch_pr_diff_gh_error(self, mock_run):
        """Should propagate CalledProcessError."""
        mock_run.side_effect = subprocess.CalledProcessError(1, ["gh", "pr", "diff"])
        with pytest.raises(subprocess.CalledProcessError):
            fetch_pr_diff(999)


class TestFetchPrChangedFiles:
    """Test changed file listing."""

    @patch("scripts.triage.diff_extractor.subprocess.run")
    def test_returns_file_list(self, mock_run):
        """Should return list of changed file paths."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="src/example.py\ndocs/README.md\ntests/test_example.py\n",
        )
        files = fetch_pr_changed_files(2)
        assert files == ["src/example.py", "docs/README.md", "tests/test_example.py"]

    @patch("scripts.triage.diff_extractor.subprocess.run")
    def test_skips_empty_lines(self, mock_run):
        """Should filter out empty lines from output."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="file1.py\n\nfile2.py\n"
        )
        files = fetch_pr_changed_files(2)
        assert files == ["file1.py", "file2.py"]


class TestFetchPrDiffstat:
    """Test diff statistics parsing."""

    @patch("scripts.triage.diff_extractor.subprocess.run")
    def test_parses_full_stat(self, mock_run):
        """Should parse files changed, insertions, deletions."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=" src/example.py | 10 +++++++++-\n 1 file changed, 9 insertions(+), 1 deletion(-)\n",
        )
        stat = fetch_pr_diffstat(2)
        assert stat["files_changed"] == 1
        assert stat["insertions"] == 9
        assert stat["deletions"] == 1

    @patch("scripts.triage.diff_extractor.subprocess.run")
    def test_handles_no_changes(self, mock_run):
        """Should return zeros when there are no changes."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=""
        )
        stat = fetch_pr_diffstat(2)
        assert stat == {"files_changed": 0, "insertions": 0, "deletions": 0}


class TestParseStatNumber:
    """Test _parse_stat_number helper."""

    def test_parses_leading_number(self):
        assert _parse_stat_number(" 3 files changed") == 3
        assert _parse_stat_number("10 insertions(+)") == 10
        assert _parse_stat_number("0") == 0

    def test_returns_zero_when_no_digits(self):
        assert _parse_stat_number("no changes") == 0
        assert _parse_stat_number("") == 0
