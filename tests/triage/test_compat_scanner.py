"""Tests for scripts.triage.compat_scanner."""

import os
import tempfile

import pytest

from scripts.triage.compat_scanner import (
    RESTRICTED_MODULES,
    SAFETY_SENSITIVE_PATTERNS,
    CompatibilityResult,
    scan_changed_files,
)


class TestCompatibilityResult:
    """Test CompatibilityResult dataclass."""

    def test_default_fields(self):
        """Should initialize with empty lists."""
        r = CompatibilityResult(pr_number=2)
        assert r.pr_number == 2
        assert r.all_changed_files == []
        assert r.restricted_hits == []
        assert r.safety_pattern_hits == []


class TestScanChangedFiles:
    """Test the scan_changed_files function."""

    def test_empty_changed_files(self):
        """Should handle empty changed file list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = scan_changed_files(2, [], repo_root=tmpdir)
            assert result.pr_number == 2
            assert result.all_changed_files == []
            assert result.missing_files == []

    def test_existing_file(self):
        """Should classify an existing file correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "src/example.py")
            os.makedirs(os.path.dirname(file_path))
            with open(file_path, "w") as f:
                f.write("x = 1")

            result = scan_changed_files(2, ["src/example.py"], repo_root=tmpdir)
            assert "src/example.py" in result.existing_files
            assert "src/example.py" in result.code_files
            assert "src/example.py" not in result.missing_files

    def test_missing_file(self):
        """Should report a non-existing file as missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = scan_changed_files(2, ["src/missing.py"], repo_root=tmpdir)
            assert "src/missing.py" in result.missing_files

    def test_restricted_module_detection(self):
        """Should flag files in restricted modules."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "src/risk_engine"))
            result = scan_changed_files(
                2, ["src/risk_engine/kill_switch.py"], repo_root=tmpdir
            )
            assert "src/risk_engine/kill_switch.py" in result.restricted_hits

    def test_restricted_no_hit_for_safe_modules(self):
        """Should not flag safe module files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "src/config"))
            result = scan_changed_files(2, ["src/config/settings.py"], repo_root=tmpdir)
            assert result.restricted_hits == []

    def test_test_file_classification(self):
        """Should classify test files correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = scan_changed_files(
                2,
                ["tests/test_foo.py", "src/bar.py", "docs/guide.md"],
                repo_root=tmpdir,
            )
            assert "tests/test_foo.py" in result.test_files
            assert "src/bar.py" in result.code_files
            assert "docs/guide.md" in result.doc_files

    def test_obsolete_path_detection(self):
        """Should flag obsolete/legacy paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = scan_changed_files(
                2,
                ["src/legacy_old_module.py", "scripts/old_deploy.sh", "src/main.py"],
                repo_root=tmpdir,
            )
            assert "src/legacy_old_module.py" in result.obsolete_paths
            assert "scripts/old_deploy.sh" in result.obsolete_paths
            assert "src/main.py" not in result.obsolete_paths

    def test_safety_pattern_scan(self):
        """Should detect safety-sensitive patterns in file content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "src/config.py")
            os.makedirs(os.path.dirname(file_path))
            with open(file_path, "w") as f:
                f.write('api_key = "sk-1234"')

            result = scan_changed_files(2, ["src/config.py"], repo_root=tmpdir)
            assert len(result.safety_pattern_hits) >= 1
            assert any("api_key" in hit for hit in result.safety_pattern_hits)


class TestRestrictedModules:
    """RESTRICTED_MODULES set covers expected areas."""

    def test_includes_risk_engine(self):
        assert "src/risk_engine" in RESTRICTED_MODULES

    def test_includes_execution_engine(self):
        assert "src/execution_engine" in RESTRICTED_MODULES

    def test_includes_data_gateway(self):
        assert "src/data_gateway" in RESTRICTED_MODULES

    def test_includes_backtest_engine(self):
        assert "src/backtest_engine" in RESTRICTED_MODULES

    def test_includes_factor_engine(self):
        assert "src/factor_engine" in RESTRICTED_MODULES

    def test_includes_strategy_engine(self):
        assert "src/strategy_engine" in RESTRICTED_MODULES

    def test_includes_stock_pool(self):
        assert "src/stock_pool" in RESTRICTED_MODULES

    def test_includes_api(self):
        assert "src/api" in RESTRICTED_MODULES

    def test_includes_product_app(self):
        assert "src/product_app" in RESTRICTED_MODULES

    def test_includes_ui_report(self):
        assert "src/ui_report" in RESTRICTED_MODULES


class TestSafetySensitivePatterns:
    """SAFETY_SENSITIVE_PATTERNS compile and match correctly."""

    def test_level_3_auto_pattern(self):
        pattern = [p for p in SAFETY_SENSITIVE_PATTERNS if "LEVEL_3_AUTO" in p.pattern][0]
        assert pattern.search("LEVEL_3_AUTO = True")
        assert not pattern.search("user_level = 3")

    def test_env_pattern(self):
        pattern = [p for p in SAFETY_SENSITIVE_PATTERNS if p.pattern == r"\.env"][0]
        assert pattern.search("load .env file")
        assert pattern.search(".env.example")

    def test_api_key_pattern(self):
        pattern = [p for p in SAFETY_SENSITIVE_PATTERNS if "api_key" in p.pattern][0]
        assert pattern.search('api_key = "secret"')
