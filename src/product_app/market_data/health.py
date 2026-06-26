from __future__ import annotations

import statistics
from datetime import datetime, timezone
from typing import Any

from src.product_app.market_data.contracts import ProviderErrorCategory


class _ProviderStats:
    def __init__(self) -> None:
        self.total_success: int = 0
        self.total_failures: int = 0
        self.consecutive_failures: int = 0
        self.latencies: list[float] = []
        self.last_success_at: datetime | None = None
        self.last_failure_at: datetime | None = None
        self.last_latency_ms: float = 0.0
        self.error_categories: dict[str, int] = {}
        self.fallback_activation_count: int = 0
        self.updated_at: datetime | None = None


class ProviderHealthAggregator:
    def __init__(self) -> None:
        self._stats: dict[str, _ProviderStats] = {}

    def _get_stats(self, provider_id: str) -> _ProviderStats:
        if provider_id not in self._stats:
            self._stats[provider_id] = _ProviderStats()
        return self._stats[provider_id]

    def record_success(
        self,
        provider_id: str,
        latency_ms: float,
        is_fallback: bool = False,
    ) -> None:
        stats = self._get_stats(provider_id)
        stats.total_success += 1
        stats.consecutive_failures = 0
        stats.last_success_at = datetime.now(timezone.utc)
        stats.last_latency_ms = latency_ms
        stats.latencies.append(latency_ms)
        stats.updated_at = datetime.now(timezone.utc)
        if is_fallback:
            stats.fallback_activation_count += 1

    def record_failure(
        self,
        provider_id: str,
        error_category: ProviderErrorCategory | None = None,
        latency_ms: float | None = None,
    ) -> None:
        stats = self._get_stats(provider_id)
        stats.total_failures += 1
        stats.consecutive_failures += 1
        stats.last_failure_at = datetime.now(timezone.utc)
        if latency_ms is not None:
            stats.last_latency_ms = latency_ms
        if error_category is not None:
            key = error_category.value
            stats.error_categories[key] = stats.error_categories.get(key, 0) + 1
        stats.updated_at = datetime.now(timezone.utc)

    def snapshot(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for provider_id, stats in self._stats.items():
            total = stats.total_success + stats.total_failures
            availability = stats.total_success / total if total > 0 else 0.0
            latencies = stats.latencies
            p50 = statistics.median(latencies) if latencies else 0.0
            p95 = _percentile(sorted(latencies), 95) if len(latencies) > 1 else (latencies[0] if latencies else 0.0)

            result[provider_id] = {
                "availability": availability,
                "last_success_at": stats.last_success_at,
                "last_failure_at": stats.last_failure_at,
                "consecutive_failures": stats.consecutive_failures,
                "latency_p50_ms": round(p50, 2),
                "latency_p95_ms": round(p95, 2),
                "latency_last_ms": stats.last_latency_ms,
                "error_category_summary": dict(stats.error_categories),
                "circuit_breaker_status": "closed" if stats.consecutive_failures < 5 else "open",
                "fallback_activation_count": stats.fallback_activation_count,
                "freshness_summary": {},
                "updated_at": stats.updated_at,
                "total_success": stats.total_success,
                "total_failures": stats.total_failures,
            }
        return result


def _percentile(sorted_data: list[float], percentile: float) -> float:
    if not sorted_data:
        return 0.0
    k = (len(sorted_data) - 1) * percentile / 100.0
    f = int(k)
    c = f + 1
    if c >= len(sorted_data):
        return sorted_data[-1]
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])
