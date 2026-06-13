"""Usage tracking — token, cache hit/miss, latency, tool round statistics.

Every DeepSeekRuntime call passes through `UsageTracker.record()` so that
metrics are available for observability endpoints and log analysis.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from loguru import logger


@dataclass
class UsageRecord:
    """Observable metrics from a single DeepSeek API call."""

    request_id: str
    profile: str
    model: str
    provider: str = "deepseek"
    start_time: float = 0.0
    end_time: float = 0.0
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    prompt_cache_hit_tokens: int | None = None
    prompt_cache_miss_tokens: int | None = None
    tool_call_count: int = 0
    tool_round_count: int = 0
    status: str = "ok"
    error_type: str | None = None

    @property
    def latency_seconds(self) -> float:
        if self.end_time and self.start_time:
            return self.end_time - self.start_time
        return 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "profile": self.profile,
            "model": self.model,
            "provider": self.provider,
            "latency_seconds": round(self.latency_seconds, 3),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "prompt_cache_hit_tokens": self.prompt_cache_hit_tokens,
            "prompt_cache_miss_tokens": self.prompt_cache_miss_tokens,
            "tool_call_count": self.tool_call_count,
            "tool_round_count": self.tool_round_count,
            "status": self.status,
            "error_type": self.error_type,
        }


class UsageTracker:
    """Thread-safe in-memory usage tracker with optional log persistence.

    Default capacity: 1000 records. Older records are dropped silently.
    """

    def __init__(self, max_records: int = 1000) -> None:
        self._max_records = max_records
        self._records: list[UsageRecord] = []
        self._counter = 0

    def record(self, **kwargs: Any) -> UsageRecord:
        """Create and store a UsageRecord from keyword arguments."""
        self._counter += 1
        record = UsageRecord(
            request_id=f"req-{self._counter}",
            start_time=kwargs.pop("start_time", time.time()),
            **kwargs,
        )
        record.end_time = kwargs.get("end_time", time.time())
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records.pop(0)
        return record

    def summary(self) -> dict[str, Any]:
        """Return a snapshot summary of all tracked records."""
        total = len(self._records)
        if total == 0:
            return {"total_calls": 0}
        ok_count = sum(1 for r in self._records if r.status == "ok")
        error_count = total - ok_count
        total_latency = sum(r.latency_seconds for r in self._records)
        total_tokens = sum((r.total_tokens or 0) for r in self._records)
        cache_hit_tokens = sum((r.prompt_cache_hit_tokens or 0) for r in self._records)
        return {
            "total_calls": total,
            "ok_calls": ok_count,
            "error_calls": error_count,
            "avg_latency_seconds": round(total_latency / total, 3) if total else 0.0,
            "total_tokens": total_tokens,
            "total_cache_hit_tokens": cache_hit_tokens,
        }

    def extract_usage_from_response(self, response: Any) -> dict[str, Any]:
        """Extract usage metrics from an OpenAI-compatible response object.

        Fields that are absent from the SDK response will be set to ``None``.
        """
        usage: dict[str, Any] = {}
        if response is None or not hasattr(response, "usage") or response.usage is None:
            return {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None}

        resp_usage = response.usage
        usage["prompt_tokens"] = getattr(resp_usage, "prompt_tokens", None)
        usage["completion_tokens"] = getattr(resp_usage, "completion_tokens", None)
        usage["total_tokens"] = getattr(resp_usage, "total_tokens", None)

        # DeepSeek-specific cache fields (may not exist in all SDK versions)
        usage["prompt_cache_hit_tokens"] = getattr(resp_usage, "prompt_cache_hit_tokens", None)
        usage["prompt_cache_miss_tokens"] = getattr(resp_usage, "prompt_cache_miss_tokens", None)

        return usage

    def log_usage(self, record: UsageRecord) -> None:
        """Write a structured usage log line."""
        logger.info(
            "LLM usage: request_id={request_id} profile={profile} model={model} "
            "latency={latency}s tokens={total} cache_hit={cache_hit}",
            request_id=record.request_id,
            profile=record.profile,
            model=record.model,
            latency=round(record.latency_seconds, 3),
            total=record.total_tokens,
            cache_hit=record.prompt_cache_hit_tokens,
        )


# Module-level singleton
_tracker: UsageTracker | None = None


def get_usage_tracker() -> UsageTracker:
    global _tracker
    if _tracker is None:
        _tracker = UsageTracker()
    return _tracker
