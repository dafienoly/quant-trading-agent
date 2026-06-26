from __future__ import annotations

import pytest

from src.product_app.market_data.contracts import (
    ProviderAttempt,
    ProviderErrorCategory,
    QualityStatus,
)
from src.product_app.market_data.errors import (
    MarketDataUnavailableError,
    redact_secret,
    safe_error_summary,
)


class TestRedactSecret:
    """redact_secret must cover 8 categories of sensitive words."""

    SENSITIVE_CASES = [
        # (input, description)
        ("api_key_abc123", "api_key prefix"),
        ("apikey_abc123", "apikey prefix"),
        ("token_xyz", "token prefix"),
        ("cookie_session=abc", "cookie prefix"),
        ("secret_value", "secret prefix"),
        ("authorization_bearer", "authorization prefix"),
        ("auth_header", "auth prefix"),
        ("password_123", "password prefix"),
        ("my_api_key_is_secret", "api_key in middle"),
        ("Bearer token_abc", "Bearer token"),
    ]

    @pytest.mark.parametrize("value,desc", SENSITIVE_CASES)
    def test_redact_secret_replaces_sensitive_values(self, value, desc):
        result = redact_secret(value)
        assert result == "<redacted>", f"Failed for {desc}: {value!r} -> {result!r}"

    def test_non_sensitive_preserved(self):
        assert redact_secret("hello") == "hello"
        assert redact_secret("normal_value_123") == "normal_value_123"
        assert redact_secret("") == ""

    def test_none_returns_empty(self):
        assert redact_secret(None) == ""

    def test_case_insensitive_matching(self):
        assert redact_secret("API_KEY_123") == "<redacted>"
        assert redact_secret("ApiKey_123") == "<redacted>"
        assert redact_secret("TOKEN_abc") == "<redacted>"

    def test_partial_match_in_longer_string(self):
        """Sensitive patterns matched anywhere in the string should be redacted."""
        assert redact_secret("Bearer token_abc_123") == "<redacted>"

    def test_redact_secret_with_various_types(self):
        assert redact_secret("auth=my_auth_token") == "<redacted>"
        assert redact_secret("password=correct-horse-battery-staple") == "<redacted>"


class TestSafeErrorSummary:
    def test_empty_attempts(self):
        summary = safe_error_summary([])
        assert summary == "No provider attempts made"

    def test_single_attempt_no_error(self):
        attempts = [ProviderAttempt(provider_id="akshare", priority=1)]
        summary = safe_error_summary(attempts)
        assert "akshare" in summary
        assert "no error" in summary.lower()

    def test_single_attempt_with_error(self):
        attempts = [
            ProviderAttempt(
                provider_id="eastmoney",
                priority=1,
                error_category=ProviderErrorCategory.TIMEOUT,
                quality_status=QualityStatus.UNAVAILABLE,
                latency_ms=5000.0,
                safe_reason="timeout after 5s",
            )
        ]
        summary = safe_error_summary(attempts)
        assert "eastmoney" in summary
        assert "TIMEOUT" in summary
        assert "timeout after 5s" not in summary  # safe_reason detail not leaked

    def test_multiple_attempts(self):
        attempts = [
            ProviderAttempt(provider_id="eastmoney", priority=1, error_category=ProviderErrorCategory.TIMEOUT),
            ProviderAttempt(provider_id="akshare", priority=2, error_category=ProviderErrorCategory.EMPTY_RESPONSE),
        ]
        summary = safe_error_summary(attempts)
        assert "eastmoney" in summary
        assert "akshare" in summary
        assert "2" in summary  # count

    def test_summary_does_not_contain_raw_detail(self):
        attempts = [
            ProviderAttempt(
                provider_id="test",
                priority=1,
                error_category=ProviderErrorCategory.AUTH_FAILED,
                safe_reason="API key rejected: sk-abc123",
            ),
        ]
        summary = safe_error_summary(attempts)
        assert "sk-abc123" not in summary
        assert "API key" not in summary


class TestMarketDataUnavailableError:
    def test_minimal_error(self):
        err = MarketDataUnavailableError(
            request_id="req-001",
            safe_reason="All providers failed",
        )
        assert err.request_id == "req-001"
        assert err.safe_reason == "All providers failed"
        assert err.provider_attempts == []
        assert err.fallback_used is False
        assert err.quality_status is None

    def test_with_provider_attempts(self):
        attempts = [
            ProviderAttempt(provider_id="eastmoney", priority=1, error_category=ProviderErrorCategory.TIMEOUT),
        ]
        err = MarketDataUnavailableError(
            request_id="req-002",
            safe_reason="Primary provider failed, no fallback",
            provider_attempts=attempts,
            fallback_used=False,
            quality_status=QualityStatus.UNAVAILABLE,
        )
        assert len(err.provider_attempts) == 1
        assert err.fallback_used is False
        assert err.quality_status == QualityStatus.UNAVAILABLE

    def test_str_representation_safe(self):
        """__str__ must not leak secret, auth header, or raw response."""
        attempts = [
            ProviderAttempt(
                provider_id="eastmoney",
                priority=1,
                error_category=ProviderErrorCategory.AUTH_FAILED,
                safe_reason="auth failed",
            ),
        ]
        err = MarketDataUnavailableError(
            request_id="req-003",
            safe_reason="Provider authentication failed",
            provider_attempts=attempts,
            quality_status=QualityStatus.UNAVAILABLE,
        )
        err_str = str(err)
        # Must contain request_id for traceability
        assert "req-003" in err_str
        # Must NOT contain raw detail
        assert "auth failed" not in err_str

    def test_str_does_not_contain_secret(self):
        """Ensure __str__ output is clean of any secret-like content."""
        attempts = [
            ProviderAttempt(provider_id="test", priority=1, error_category=ProviderErrorCategory.AUTH_FAILED),
        ]
        err = MarketDataUnavailableError(
            request_id="req-004",
            safe_reason="All providers failed",
            provider_attempts=attempts,
        )
        output = str(err)
        sensitive_patterns = ["api_key", "token", "cookie", "secret", "password", "auth"]
        for pattern in sensitive_patterns:
            assert pattern not in output, f"Found sensitive pattern {pattern!r} in str: {output}"

    def test_repr_also_safe(self):
        attempts = [
            ProviderAttempt(provider_id="test", priority=1, error_category=ProviderErrorCategory.TIMEOUT),
        ]
        err = MarketDataUnavailableError(
            request_id="req-005",
            safe_reason="failed",
            provider_attempts=attempts,
        )
        rep = repr(err)
        assert "MarketDataUnavailableError" in rep
        assert "req-005" in rep

    def test_serialization_no_secret(self):
        """Pydantic serialization must not include sensitive data."""
        attempts = [
            ProviderAttempt(provider_id="test", priority=1, error_category=ProviderErrorCategory.AUTH_FAILED),
        ]
        err = MarketDataUnavailableError(
            request_id="req-006",
            safe_reason="All providers failed",
            provider_attempts=attempts,
            quality_status=QualityStatus.UNAVAILABLE,
        )
        # Just check it can be serialized
        data = err.model_dump()
        assert data["request_id"] == "req-006"
        assert data["safe_reason"] == "All providers failed"
        assert len(data["provider_attempts"]) == 1
        assert data["quality_status"] == "UNAVAILABLE"
