"""Tests for scripts.triage.report_generator."""


from scripts.triage.report_generator import generate_triage_report


class TestGenerateTriageReport:
    """Test generate_triage_report function."""

    MINIMAL_PR_STATE = {
        "number": 2,
        "title": "Test PR",
        "author": "testuser",
        "source_branch": "feature/test",
        "base_branch": "main",
        "state": "OPEN",
        "merged": False,
        "mergeable_state": "MERGEABLE",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-02T00:00:00Z",
        "labels": ["bug"],
    }

    MINIMAL_DIFF_STATS = {"files_changed": 1, "insertions": 5, "deletions": 2}

    MINIMAL_COMPAT = {
        "existing_files": ["src/main.py"],
        "missing_files": [],
        "restricted_hits": [],
        "safety_pattern_hits": [],
        "obsolete_paths": [],
        "test_files": [],
        "doc_files": [],
        "code_files": ["src/main.py"],
    }

    def _make_report(
        self,
        pr_state=None,
        diff_stats=None,
        changed_files=None,
        rebase_result=None,
        compatibility=None,
        reviews=None,
        comments=None,
        commits=None,
        ci_status=None,
        disposition="ADOPT_AS_IS",
        manual_approval_required=False,
        follow_up="PR appears compatible. Proceed through normal pipeline.",
    ):
        """Helper to generate a report with defaults."""
        return generate_triage_report(
            pr_number=2,
            pr_state=pr_state or self.MINIMAL_PR_STATE,
            diff_stats=diff_stats or self.MINIMAL_DIFF_STATS,
            changed_files=changed_files or ["src/main.py"],
            rebase_result=rebase_result
            or {"success": True, "conflict_files": [], "error": None},
            compatibility=compatibility or self.MINIMAL_COMPAT,
            reviews=reviews or [],
            comments=comments or [],
            commits=commits or [],
            ci_status=ci_status or {},
            disposition=disposition,
            manual_approval_required=manual_approval_required,
            follow_up=follow_up,
        )

    def test_basic_report_structure(self):
        """Should generate a report with expected sections."""
        report = self._make_report()
        assert isinstance(report, str)
        assert len(report) > 100
        # Key sections should be present
        assert "PR #2" in report
        assert "Triage Report" in report
        assert "Summary" in report
        assert "Diff Statistics" in report
        assert "Rebase Result" in report
        assert "Compatibility Scan" in report
        assert "Reviews" in report
        assert "Comments" in report
        assert "Commits" in report
        assert "CI Status" in report
        assert "Disposition" in report
        assert "Safety Confirmation" in report

    def test_disposition_in_summary(self):
        """Should show disposition at the top and in disposition table."""
        report = self._make_report(disposition="ADOPT_WITH_CHANGES")
        assert "ADOPT_WITH_CHANGES" in report
        assert "Manual approval required" in report

    def test_manual_approval_yes(self):
        """Should show Yes when manual approval required."""
        report = self._make_report(manual_approval_required=True)
        assert "Yes" in report.split("Manual approval required")[1].split("\n")[0]

    def test_reviews_section(self):
        """Should render reviews list."""
        reviews = [
            {"author": "reviewer1", "state": "APPROVED", "body": "Looks good"},
        ]
        report = self._make_report(reviews=reviews)
        assert "reviewer1" in report
        assert "APPROVED" in report
        assert "Looks good" in report

    def test_comments_section(self):
        """Should render comments list."""
        comments = [
            {
                "author": "commenter1",
                "body": "Have you considered edge cases?",
            }
        ]
        report = self._make_report(comments=comments)
        assert "commenter1" in report
        assert "edge cases" in report

    def test_commits_section(self):
        """Should render commits with truncated SHA."""
        commits = [
            {
                "sha": "abcdef1234567890",
                "message": "Fix critical bug",
                "author": "dev1",
            }
        ]
        report = self._make_report(commits=commits)
        assert "abcdef12" in report
        assert "Fix critical bug" in report
        assert "dev1" in report

    def test_ci_status_section(self):
        """Should render CI status checks."""
        ci_status = {
            "CI / tests": {
                "conclusion": "SUCCESS",
                "status": "COMPLETED",
                "detailsUrl": "https://github.com/owner/repo/actions/runs/1",
            }
        }
        report = self._make_report(ci_status=ci_status)
        assert "CI / tests" in report
        assert "SUCCESS" in report

    def test_no_reviews_placeholder(self):
        """Should show placeholder when no reviews."""
        report = self._make_report(reviews=[])
        assert "No reviews recorded" in report

    def test_no_comments_placeholder(self):
        """Should show placeholder when no comments."""
        report = self._make_report(comments=[])
        assert "No comments recorded" in report

    def test_no_commits_placeholder(self):
        """Should show placeholder when no commits."""
        report = self._make_report(commits=[])
        assert "No commits recorded" in report

    def test_no_ci_placeholder(self):
        """Should show placeholder when no CI data."""
        report = self._make_report(ci_status={})
        assert "No CI data available" in report

    def test_restricted_hits_listed(self):
        """Should list restricted module hits."""
        compat = {**self.MINIMAL_COMPAT, "restricted_hits": ["src/risk_engine/main.py"]}
        report = self._make_report(compatibility=compat)
        assert "src/risk_engine/main.py" in report
        assert "Restricted Module Hits" in report

    def test_safety_pattern_hits_listed(self):
        """Should list safety pattern hits."""
        compat = {**self.MINIMAL_COMPAT, "safety_pattern_hits": ["api_key detected"]}
        report = self._make_report(compatibility=compat)
        assert "api_key detected" in report
        assert "Safety Pattern Hits" in report

    def test_missing_files_listed(self):
        """Should list missing files."""
        compat = {**self.MINIMAL_COMPAT, "missing_files": ["src/old.py"]}
        report = self._make_report(compatibility=compat)
        assert "Missing Files" in report
        assert "src/old.py" in report

    def test_conflict_files_listed(self):
        """Should list conflicting files when rebase has conflicts."""
        rebase_result = {
            "success": False,
            "conflict_files": ["src/file.py"],
            "error": "conflicts detected",
        }
        report = self._make_report(rebase_result=rebase_result)
        assert "src/file.py" in report
        assert "Conflicting Files" in report

    def test_safety_confirmation_restricted_no(self):
        """Should show No for restricted modules when none hit."""
        report = self._make_report()
        assert "Restricted modules touched? **No**" in report

    def test_safety_confirmation_restricted_yes(self):
        """Should show Yes for restricted modules when hit."""
        compat = {**self.MINIMAL_COMPAT, "restricted_hits": ["src/risk_engine/x.py"]}
        report = self._make_report(compatibility=compat)
        assert "Restricted modules touched? **Yes**" in report

    def test_safety_confirmation_tests_no(self):
        """Should show No for tests when none exist."""
        report = self._make_report()
        assert "Tests exist? **No**" in report

    def test_safety_confirmation_tests_yes(self):
        """Should show Yes for tests when they exist."""
        compat = {**self.MINIMAL_COMPAT, "test_files": ["tests/test_main.py"]}
        report = self._make_report(compatibility=compat)
        assert "Tests exist? **Yes**" in report

    def test_safety_confirmation_secrets_no(self):
        """Should show No for secrets when none detected."""
        report = self._make_report()
        assert "Secrets detected? **No**" in report

    def test_safety_confirmation_secrets_yes(self):
        """Should show Yes for secrets when safety hits exist."""
        compat = {**self.MINIMAL_COMPAT, "safety_pattern_hits": ["api_key detected"]}
        report = self._make_report(compatibility=compat)
        assert "Secrets detected? **Yes (see safety pattern hits)**" in report
