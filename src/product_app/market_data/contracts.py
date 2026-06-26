from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel


class QualityStatus(str, Enum):
    OK = "OK"
    STALE = "STALE"
    DEGRADED = "DEGRADED"
    FALLBACK = "FALLBACK"
    UNAVAILABLE = "UNAVAILABLE"
    INVALID = "INVALID"
    MOCK = "MOCK"
    DEMO = "DEMO"


class ProviderErrorCategory(str, Enum):
    AUTH_FAILED = "AUTH_FAILED"
    RATE_LIMITED = "RATE_LIMITED"
    TIMEOUT = "TIMEOUT"
    NETWORK_ERROR = "NETWORK_ERROR"
    EMPTY_RESPONSE = "EMPTY_RESPONSE"
    MALFORMED_RESPONSE = "MALFORMED_RESPONSE"
    MISSING_FIELD = "MISSING_FIELD"
    INVALID_VALUE = "INVALID_VALUE"
    STALE_DATA = "STALE_DATA"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    UNKNOWN_PROVIDER_ERROR = "UNKNOWN_PROVIDER_ERROR"


class AuthRequirement(BaseModel):
    requires_auth: bool = False
    auth_type: str = "none"


class RateLimitPolicy(BaseModel):
    max_requests_per_second: int = 10
    max_requests_per_minute: int = 600
    burst_size: int = 5


class TimeoutPolicy(BaseModel):
    connect_timeout_seconds: float = 10.0
    read_timeout_seconds: float = 30.0
    total_timeout_seconds: float = 60.0


class FreshnessPolicy(BaseModel):
    max_age_seconds: float = 60.0
    stale_age_seconds: float = 300.0
    acceptable_delay_ms: int = 5000


class CachePolicy(BaseModel):
    ttl_seconds: float = 30.0
    max_size: int = 1000


class FallbackEligibility(BaseModel):
    can_fallback: bool = True
    fallback_priority_offset: int = 1


class MarketDataProviderContract(BaseModel):
    provider_id: str
    provider_name: str
    market_scope: list[str]
    supported_asset_types: list[str]
    supported_granularities: list[str]
    supported_endpoints: list[str]
    auth_requirement: AuthRequirement
    rate_limit_policy: RateLimitPolicy
    timeout_policy: TimeoutPolicy
    freshness_policy: FreshnessPolicy
    cache_policy: CachePolicy
    fallback_eligibility: FallbackEligibility
    quality_status_mapping: dict[str, QualityStatus]
    error_mapping: dict[str, ProviderErrorCategory]


class DataQualityMetadata(BaseModel):
    source_provider: str
    source_priority: int
    as_of: datetime
    received_at: datetime
    freshness_seconds: float
    is_stale: bool = False
    is_realtime: bool = False
    is_demo: bool = False
    is_mock: bool = False
    is_fallback: bool = False
    quality_status: QualityStatus
    quality_reason: str
    provider_latency_ms: float | None = None
    request_id: str


class MarketQuote(BaseModel):
    symbol: str
    market: str
    asset_type: str
    price: Decimal | None = None
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    previous_close: Decimal | None = None
    volume: int | None = None
    currency: str | None = None
    quality: DataQualityMetadata


class MarketBar(BaseModel):
    symbol: str
    market: str
    granularity: str
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int | None = None
    quality: DataQualityMetadata


class ProviderAttempt(BaseModel):
    provider_id: str
    priority: int
    error_category: ProviderErrorCategory | None = None
    quality_status: QualityStatus | None = None
    latency_ms: float | None = None
    safe_reason: str = ""


class ItemError(BaseModel):
    symbol: str
    error_category: ProviderErrorCategory
    safe_reason: str
    quality_status: QualityStatus | None = None


class MultiSymbolQuoteResult(BaseModel):
    results: list[MarketQuote]
    item_errors: list[ItemError]
    summary: dict[str, Any]
    request_quality: QualityStatus
    request_id: str
