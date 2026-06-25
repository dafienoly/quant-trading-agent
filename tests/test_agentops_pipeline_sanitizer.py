from __future__ import annotations

from src.product_app.agentops.pipeline_sanitizer import (
    redact_secrets,
    sanitize_error_message,
    sanitize_repo_relative_path,
)


class TestSanitizeRepoRelativePath:
    def test_absolute_linux_path(self):
        result = sanitize_repo_relative_path("/mnt/d/actions-runner/work/quant-trading-agent/docs/req.md")
        assert result == "docs/req.md"

    def test_relative_path_unchanged(self):
        result = sanitize_repo_relative_path("docs/requirements/test.md")
        assert result == "docs/requirements/test.md"

    def test_windows_absolute_path(self):
        result = sanitize_repo_relative_path("C:\\Users\\test\\project\\docs\\req.md")
        assert result == "docs/req.md"

    def test_empty_path(self):
        assert sanitize_repo_relative_path("") == ""

    def test_none_path(self):
        assert sanitize_repo_relative_path(None) == ""  # type: ignore[arg-type]

    def test_dot_env_stripped(self):
        result = sanitize_repo_relative_path(".env")
        assert result == "<redacted>"

    def test_env_example_allowed(self):
        result = sanitize_repo_relative_path(".env.example")
        assert result == ".env.example"


class TestRedactSecrets:
    def test_token_pattern_sk_like(self):
        result = redact_secrets("my token is sk-live-abc123def456")
        assert "<redacted>" in result
        assert "sk-live-abc123def456" not in result

    def test_github_token(self):
        result = redact_secrets("ghp_abcdefghijklmnopqrstuvwxyz0123456789")
        assert "<redacted>" in result
        assert "ghp_" not in result

    def test_env_var_value(self):
        result = redact_secrets("API_KEY=super-secret-value")
        assert "<redacted>" in result

    def test_no_secrets_unchanged(self):
        result = redact_secrets("just a normal message")
        assert result == "just a normal message"


class TestSanitizeErrorMessage:
    def test_absolute_path_removed(self):
        result = sanitize_error_message("Error reading /mnt/d/actions-runner/file.yaml")
        assert "/mnt/d/actions-runner/file.yaml" not in result

    def test_token_redacted(self):
        result = sanitize_error_message("Token: ghp_abcdefghijklmnopqrstuvwxyz0123456789")
        assert "<redacted>" in result
        assert "ghp_" not in result

    def test_traceback_sanitized(self):
        trace = 'File "/mnt/d/project/src/file.py", line 10, in func'
        result = sanitize_error_message(trace)
        assert "File " not in result

    def test_empty_message(self):
        assert sanitize_error_message("") == ""
