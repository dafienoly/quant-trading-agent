"""Tests for scripts.triage.run_triage."""

from unittest.mock import MagicMock, patch


from scripts.triage.run_triage import (
    _classify,
    _compat_to_dict,
    _pr_state_to_dict,
    parse_args,
    run_triage,
)


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def make_pr_state(**overrides):
    """Create a mock PR state object with default values."""
    obj = MagicMock()
    obj.number = overrides.get("number", 2)
    obj.title = overrides.get("title", "Test PR")
    obj.author = overrides.get("author", "testuser")
    obj.source_branch = overrides.get("source_branch", "feature/test")
    obj.base_branch = overrides.get("base_branch", "main")
    obj.state = overrides.get("state", "OPEN")
    obj.merged = overrides.get("merged", False)
    obj.mergeable_state = overrides.get("mergeable_state", "MERGEABLE")
    obj.created_at = overrides.get("created_at", "2024-01-01T00:00:00Z")
    obj.updated_at = overrides.get("updated_at", "2024-01-02T00:00:00Z")
    obj.labels = overrides.get("labels", ["bug"])
    obj.body = overrides.get("body", "Test body")
    # Wire to_dict
    obj.to_dict.return_value = {
        "number": obj.number,
        "title": obj.title,
        "author": obj.author,
        "source_branch": obj.source_branch,
        "base_branch": obj.base_branch,
        "state": obj.state,
        "merged": obj.merged,
        "mergeable_state": obj.mergeable_state,
        "created_at": obj.created_at,
        "updated_at": obj.updated_at,
        "labels": obj.labels,
        "body": obj.body,
    }
    return obj


def make_compat(**overrides):
    """Create a mock CompatibilityResult object with default values."""
    obj = MagicMock()
    obj.pr_number = overrides.get("pr_number", 2)
    obj.all_changed_files = overrides.get("all_changed_files", ["src/main.py"])
    obj.existing_files = overrides.get("existing_files", ["src/main.py"])
    obj.missing_files = overrides.get("missing_files", [])
    obj.restricted_hits = overrides.get("restricted_hits", [])
    obj.safety_pattern_hits = overrides.get("safety_pattern_hits", [])
    obj.obsolete_paths = overrides.get("obsolete_paths", [])
    obj.test_files = overrides.get("test_files", [])
    obj.doc_files = overrides.get("doc_files", [])
    obj.code_files = overrides.get("code_files", ["src/main.py"])
    return obj


# ---------------------------------------------------------------------------
# Test _pr_state_to_dict
# ---------------------------------------------------------------------------


class TestPrStateToDict:
    """Test _pr_state_to_dict helper."""

    def test_converts_pr_state(self):
        """Should convert PRState dataclass to plain dict."""
        pr = make_pr_state()
        d = _pr_state_to_dict(pr)
        assert d["number"] == 2
        assert d["author"] == "testuser"
        assert d["title"] == "Test PR"

    def test_author_dict_fallback(self):
        """Should extract login from nested author dict."""
        pr = make_pr_state()
        pr.to_dict.return_value = {
            "author": {"login": "nested_user"},
        }
        d = _pr_state_to_dict(pr)
        assert d["author"] == "nested_user"


# ---------------------------------------------------------------------------
# Test _compat_to_dict
# ---------------------------------------------------------------------------


class TestCompatToDict:
    """Test _compat_to_dict helper."""

    def test_converts_compat_result(self):
        """Should convert CompatibilityResult to plain dict."""
        compat = make_compat()
        d = _compat_to_dict(compat)
        assert d["pr_number"] == 2
        assert d["code_files"] == ["src/main.py"]
        assert d["restricted_hits"] == []


# ---------------------------------------------------------------------------
# Test parse_args
# ---------------------------------------------------------------------------


class TestParseArgs:
    """Test CLI argument parsing."""

    def test_requires_pr(self):
        """Should parse --pr argument."""
        args = parse_args(["--pr", "2", "--output", "report.md"])
        assert args.pr == 2

    def test_requires_output(self):
        """Should parse --output argument."""
        args = parse_args(["--pr", "2", "--output", "docs/report.md"])
        assert args.output == "docs/report.md"

    def test_default_diff_dir(self):
        """Should default to empty diff dir."""
        args = parse_args(["--pr", "2", "--output", "report.md"])
        assert args.diff_dir == ""

    def test_diff_dir_option(self):
        """Should parse --diff-dir argument."""
        args = parse_args(["--pr", "2", "--output", "report.md", "--diff-dir", "/tmp/diffs"])
        assert args.diff_dir == "/tmp/diffs"

    def test_dry_run_rebase_default(self):
        """Should default to dry-run rebase."""
        args = parse_args(["--pr", "2", "--output", "report.md"])
        assert args.no_dry_run_rebase is False

    def test_no_dry_run_rebase(self):
        """Should parse --no-dry-run-rebase flag."""
        args = parse_args(["--pr", "2", "--output", "report.md", "--no-dry-run-rebase"])
        assert args.no_dry_run_rebase is True


# ---------------------------------------------------------------------------
# Test _classify
# ---------------------------------------------------------------------------


class TestClassify:
    """Test _classify disposition logic."""

    def test_safety_hits_returns_needs_more_info(self):
        """Should return NEEDS_MORE_INFO when safety patterns hit."""
        pr = make_pr_state()
        compat = make_compat(safety_pattern_hits=["api_key detected"])
        disp, manual, follow = _classify(pr, compat, [])
        assert disp == "NEEDS_MORE_INFO"
        assert follow == "Safety pattern hits detected; manual review required before disposition."

    def test_restricted_hits_returns_adopt_with_changes(self):
        """Should return ADOPT_WITH_CHANGES for restricted module hits."""
        pr = make_pr_state()
        compat = make_compat(restricted_hits=["src/risk_engine/main.py"])
        disp, manual, follow = _classify(pr, compat, [])
        assert disp == "ADOPT_WITH_CHANGES"
        assert manual is True
        assert "Restricted module touch detected" in follow

    def test_missing_files_returns_partial_adopt(self):
        """Should return PARTIAL_ADOPT for missing files."""
        pr = make_pr_state()
        compat = make_compat(missing_files=["src/old.py"])
        disp, manual, follow = _classify(pr, compat, [])
        assert disp == "PARTIAL_ADOPT"
        assert manual is False
        assert "no longer exist" in follow

    def test_obsolete_paths_returns_partial_adopt(self):
        """Should return PARTIAL_ADOPT for obsolete paths."""
        pr = make_pr_state()
        compat = make_compat(obsolete_paths=["src/legacy_old.py"])
        disp, manual, follow = _classify(pr, compat, [])
        assert disp == "PARTIAL_ADOPT"
        assert "Obsolete paths detected" in follow

    def test_no_test_files_notes(self):
        """Should note missing tests but still adopt with changes."""
        pr = make_pr_state()
        compat = make_compat(test_files=[])
        disp, manual, follow = _classify(pr, compat, [])
        assert disp == "ADOPT_WITH_CHANGES"
        assert "does not include tests" in follow

    def test_merged_pr_note(self):
        """Should note when PR is already merged."""
        pr = make_pr_state(merged=True)
        compat = make_compat()
        disp, manual, follow = _classify(pr, compat, [])
        assert "already merged" in follow

    def test_clean_returns_adopt_as_is(self):
        """Should return ADOPT_AS_IS for fully compatible PR."""
        pr = make_pr_state()
        compat = make_compat(test_files=["tests/test_main.py"])
        disp, manual, follow = _classify(pr, compat, [])
        assert disp == "ADOPT_AS_IS"
        assert manual is False
        assert "PR appears compatible" in follow

    def test_restricted_hits_requires_manual_approval(self):
        """Should set manual_approval_required when restricted hits exist."""
        pr = make_pr_state()
        compat = make_compat(restricted_hits=["src/api/route.py"])
        disp, manual, follow = _classify(pr, compat, [])
        assert manual is True


# ---------------------------------------------------------------------------
# Test run_triage
# ---------------------------------------------------------------------------


class TestRunTriage:
    """Test run_triage orchestration."""

    @patch("scripts.triage.run_triage.Path.write_text")
    @patch("scripts.triage.run_triage.generate_triage_report")
    @patch("scripts.triage.run_triage.attempt_rebase")
    @patch("scripts.triage.run_triage.scan_changed_files")
    @patch("scripts.triage.run_triage.fetch_pr_diffstat")
    @patch("scripts.triage.run_triage.fetch_pr_changed_files")
    @patch("scripts.triage.run_triage.check_ci_status")
    @patch("scripts.triage.run_triage.query_pr_commits")
    @patch("scripts.triage.run_triage.query_pr_comments")
    @patch("scripts.triage.run_triage.query_pr_reviews")
    @patch("scripts.triage.run_triage.query_pr_state")
    def test_full_triage_flow(
        self,
        mock_qps,
        mock_qpr,
        mock_qpc,
        mock_qpco,
        mock_ci,
        mock_files,
        mock_stat,
        mock_scan,
        mock_rebase,
        mock_report,
        mock_write,
    ):
        """Should orchestrate full triage workflow and return result dict."""
        mock_qps.return_value = make_pr_state(source_branch="feature/test")
        mock_qpr.return_value = []
        mock_qpc.return_value = []
        mock_qpco.return_value = []
        mock_ci.return_value = {}
        mock_files.return_value = ["src/main.py"]
        mock_stat.return_value = {"files_changed": 1, "insertions": 5, "deletions": 2}
        mock_scan.return_value = make_compat()
        mock_rebase.return_value = {
            "success": True,
            "conflict_files": [],
            "error": None,
        }
        mock_report.return_value = "# Triage Report"

        result = run_triage(pr_number=2, output_path="/tmp/report.md")

        assert result["report_path"] == "/tmp/report.md"
        assert result["disposition"] == "ADOPT_AS_IS"
        assert result["manual_approval_required"] is False

        # Verify all steps called
        mock_qps.assert_called_once_with(2)
        mock_qpr.assert_called_once_with(2)
        mock_files.assert_called_once_with(2)
        mock_scan.assert_called_once_with(2, ["src/main.py"])
        mock_rebase.assert_called_once_with(source_branch="feature/test", dry_run=True)
        mock_report.assert_called_once()
        mock_write.assert_called_once()

    @patch("scripts.triage.run_triage.Path.write_text")
    @patch("scripts.triage.run_triage.generate_triage_report")
    @patch("scripts.triage.run_triage.attempt_rebase")
    @patch("scripts.triage.run_triage.scan_changed_files")
    @patch("scripts.triage.run_triage.fetch_pr_diffstat")
    @patch("scripts.triage.run_triage.fetch_pr_changed_files")
    @patch("scripts.triage.run_triage.check_ci_status")
    @patch("scripts.triage.run_triage.query_pr_commits")
    @patch("scripts.triage.run_triage.query_pr_comments")
    @patch("scripts.triage.run_triage.query_pr_reviews")
    @patch("scripts.triage.run_triage.query_pr_state")
    def test_triage_with_diff_output_dir(
        self,
        mock_qps,
        mock_qpr,
        mock_qpc,
        mock_qpco,
        mock_ci,
        mock_files,
        mock_stat,
        mock_scan,
        mock_rebase,
        mock_report,
        mock_write,
    ):
        """Should create diff output dir and fetch diff when dir specified."""
        mock_qps.return_value = make_pr_state(source_branch="feature/test")
        mock_qpr.return_value = []
        mock_qpc.return_value = []
        mock_qpco.return_value = []
        mock_ci.return_value = {}
        mock_files.return_value = []
        mock_stat.return_value = {"files_changed": 0, "insertions": 0, "deletions": 0}
        mock_scan.return_value = make_compat()
        mock_rebase.return_value = {
            "success": True,
            "conflict_files": [],
            "error": None,
        }
        mock_report.return_value = "# Triage Report"

        with patch("scripts.triage.run_triage.fetch_pr_diff") as mock_diff:
            with patch("scripts.triage.run_triage.Path.mkdir") as mock_mkdir:
                result = run_triage(
                    pr_number=2,
                    output_path="/tmp/report.md",
                    diff_output_dir="/tmp/diffs",
                )
                mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
                mock_diff.assert_called_once_with(2, output_dir="/tmp/diffs")
                assert result["report_path"] == "/tmp/report.md"

    @patch("scripts.triage.run_triage.Path.write_text")
    @patch("scripts.triage.run_triage.generate_triage_report")
    @patch("scripts.triage.run_triage.attempt_rebase")
    @patch("scripts.triage.run_triage.scan_changed_files")
    @patch("scripts.triage.run_triage.fetch_pr_diffstat")
    @patch("scripts.triage.run_triage.fetch_pr_changed_files")
    @patch("scripts.triage.run_triage.check_ci_status")
    @patch("scripts.triage.run_triage.query_pr_commits")
    @patch("scripts.triage.run_triage.query_pr_comments")
    @patch("scripts.triage.run_triage.query_pr_reviews")
    @patch("scripts.triage.run_triage.query_pr_state")
    def test_triage_without_dry_run_rebase(
        self,
        mock_qps,
        mock_qpr,
        mock_qpc,
        mock_qpco,
        mock_ci,
        mock_files,
        mock_stat,
        mock_scan,
        mock_rebase,
        mock_report,
        mock_write,
    ):
        """Should pass dry_run=False when specified."""
        mock_qps.return_value = make_pr_state(source_branch="feature/test")
        mock_qpr.return_value = []
        mock_qpc.return_value = []
        mock_qpco.return_value = []
        mock_ci.return_value = {}
        mock_files.return_value = []
        mock_stat.return_value = {"files_changed": 0, "insertions": 0, "deletions": 0}
        mock_scan.return_value = make_compat()
        mock_rebase.return_value = {
            "success": True,
            "conflict_files": [],
            "error": None,
        }
        mock_report.return_value = "# Triage Report"

        run_triage(pr_number=2, output_path="/tmp/report.md", dry_run_rebase=False)
        mock_rebase.assert_called_once_with(source_branch="feature/test", dry_run=False)


# ---------------------------------------------------------------------------
# Test main
# ---------------------------------------------------------------------------


class TestMain:
    """Test main CLI entry point."""

    @patch("scripts.triage.run_triage.run_triage")
    def test_main_success(self, mock_run):
        """Should return 0 on success."""
        mock_run.return_value = {
            "report_path": "report.md",
            "disposition": "ADOPT_AS_IS",
            "manual_approval_required": False,
        }
        from scripts.triage.run_triage import main

        exit_code = main(["--pr", "2", "--output", "report.md"])
        assert exit_code == 0
        mock_run.assert_called_once_with(
            pr_number=2,
            output_path="report.md",
            diff_output_dir="",
            dry_run_rebase=True,
        )

    @patch("scripts.triage.run_triage.run_triage")
    def test_main_with_all_options(self, mock_run):
        """Should pass all options to run_triage."""
        mock_run.return_value = {
            "report_path": "report.md",
            "disposition": "ADOPT_AS_IS",
            "manual_approval_required": False,
        }
        from scripts.triage.run_triage import main

        exit_code = main(
            [
                "--pr",
                "3",
                "--output",
                "docs/report.md",
                "--diff-dir",
                "/tmp/diffs",
                "--no-dry-run-rebase",
            ]
        )
        assert exit_code == 0
        mock_run.assert_called_once_with(
            pr_number=3,
            output_path="docs/report.md",
            diff_output_dir="/tmp/diffs",
            dry_run_rebase=False,
        )

    @patch("scripts.triage.run_triage.run_triage")
    def test_main_returns_1_on_error(self, mock_run):
        """Should return 1 when run_triage raises."""
        mock_run.side_effect = RuntimeError("Something went wrong")
        from scripts.triage.run_triage import main

        exit_code = main(["--pr", "2", "--output", "report.md"])
        assert exit_code == 1
