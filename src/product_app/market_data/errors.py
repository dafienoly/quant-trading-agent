from __future__ import annotations

import re
from typing import Any

from src.product_app.market_data.contracts import (
    ProviderAttempt,
    QualityStatus,
)

_SENSITIVE_PATTERNS = re.compile(
    r"(api_key|apikey|token|cookie|secret|authorization|auth|password)",
    re.IGNORECASE,
)


def redact_secret(value: str | None) -> str:
    if not value:
        return ""
    if _SENSITIVE_PATTERNS.search(value):
        return "<redacted>"
    return value


def safe_error_summary(attempts: list[ProviderAttempt]) -> str:
    if not attempts:
        return "No provider attempts made"
    parts: list[str] = []
    for a in attempts:
        error_label = a.error_category.value if a.error_category else "no error"
        parts.append(f"{a.provider_id}(priority={a.priority},error={error_label})")
    return f"Provider attempts ({len(attempts)}): {'; '.join(parts)}"


class MarketDataUnavailableError(Exception):
    def __init__(
        self,
        request_id: str,
        safe_reason: str,
        provider_attempts: list[ProviderAttempt] | None = None,
        fallback_used: bool = False,
        quality_status: QualityStatus | None = None,
    ):
        self.request_id = request_id
        self.safe_reason = safe_reason
        self.provider_attempts = provider_attempts or []
        self.fallback_used = fallback_used
        self.quality_status = quality_status
        super().__init__(self.__str__())

    def __str__(self) -> str:
        return (
            f"MarketDataUnavailableError(request_id={self.request_id}, "
            f"safe_reason={self.safe_reason}, "
            f"provider_attempts={len(self.provider_attempts)}, "
            f"fallback_used={self.fallback_used}, "
            f"quality_status={self.quality_status})"
        )

    def __repr__(self) -> str:
        return (
            f"MarketDataUnavailableError(request_id={self.request_id!r}, "
            f"safe_reason={self.safe_reason!r})"
        )

    def model_dump(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "safe_reason": self.safe_reason,
            "provider_attempts": [a.model_dump() for a in self.provider_attempts],
            "fallback_used": self.fallback_used,
            "quality_status": self.quality_status.value if self.quality_status else None,
        }
