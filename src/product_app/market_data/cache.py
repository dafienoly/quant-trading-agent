from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from src.product_app.market_data.contracts import FreshnessPolicy, QualityStatus
from src.product_app.market_data.quality import CallerContext


class CachedEntry(BaseModel):
    data: Any
    cache_hit: bool = True
    cache_created_at: datetime
    cache_age_seconds: float
    source_provider: str
    quality_status: QualityStatus
    is_stale: bool = False


_STALE_SENSITIVE_CONTEXTS = frozenset({"signal_generation", "real_trading", "position_sizing"})


class MarketDataCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, CachedEntry]] = {}

    def set(
        self,
        key: str,
        data: Any,
        source_provider: str,
        quality_status: QualityStatus,
    ) -> CachedEntry:
        now = datetime.now(timezone.utc)
        entry = CachedEntry(
            data=data,
            cache_hit=True,
            cache_created_at=now,
            cache_age_seconds=0.0,
            source_provider=source_provider,
            quality_status=quality_status,
            is_stale=False,
        )
        self._store[key] = (time.monotonic(), entry)
        return entry

    def get(
        self,
        key: str,
        freshness_policy: FreshnessPolicy,
        caller_context: CallerContext,
    ) -> CachedEntry | None:
        stored = self._store.get(key)
        if stored is None:
            return None

        created_mono, entry = stored
        age_seconds = time.monotonic() - created_mono
        entry.cache_age_seconds = age_seconds

        is_stale = age_seconds > freshness_policy.max_age_seconds
        if is_stale:
            entry.is_stale = True
            entry.quality_status = QualityStatus.STALE

            if caller_context.name in _STALE_SENSITIVE_CONTEXTS:
                return None

        return entry
