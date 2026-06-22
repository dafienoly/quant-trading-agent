"""DeepSeek Runtime 非敏感用量与延迟统计。"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any

from loguru import logger


@dataclass
class UsageRecord:
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
        return max(0.0, self.end_time - self.start_time)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["latency_seconds"] = round(self.latency_seconds, 3)
        return data


class UsageTracker:
    """有容量上限的线程安全内存指标集合。"""

    def __init__(self, max_records: int = 1000) -> None:
        self.max_records = max(1, int(max_records))
        self._records: list[UsageRecord] = []
        self._lock = threading.Lock()

    def record(self, **values: Any) -> UsageRecord:
        start_time = float(values.pop("start_time", time.time()))
        end_time = float(values.pop("end_time", time.time()))
        record = UsageRecord(
            request_id=str(values.pop("request_id", f"req-{uuid.uuid4().hex}")),
            start_time=start_time,
            end_time=end_time,
            **values,
        )
        with self._lock:
            self._records.append(record)
            if len(self._records) > self.max_records:
                del self._records[: len(self._records) - self.max_records]
        return record

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return [record.to_dict() for record in self._records]

    def summary(self) -> dict[str, Any]:
        with self._lock:
            records = list(self._records)
        if not records:
            return {"total_calls": 0, "ok_calls": 0, "error_calls": 0}
        ok_calls = sum(record.status == "ok" for record in records)
        return {
            "total_calls": len(records),
            "ok_calls": ok_calls,
            "error_calls": len(records) - ok_calls,
            "avg_latency_seconds": round(
                sum(record.latency_seconds for record in records) / len(records), 3
            ),
            "total_tokens": sum(record.total_tokens or 0 for record in records),
            "total_cache_hit_tokens": sum(
                record.prompt_cache_hit_tokens or 0 for record in records
            ),
        }

    @staticmethod
    def extract_usage(response: Any) -> dict[str, int | None]:
        usage = getattr(response, "usage", None)
        return {
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
            "prompt_cache_hit_tokens": getattr(usage, "prompt_cache_hit_tokens", None),
            "prompt_cache_miss_tokens": getattr(usage, "prompt_cache_miss_tokens", None),
        }

    def log(self, record: UsageRecord) -> None:
        logger.info(
            "LLM 调用 profile={} model={} status={} latency={}s tokens={} cache_hit={}",
            record.profile,
            record.model,
            record.status,
            round(record.latency_seconds, 3),
            record.total_tokens,
            record.prompt_cache_hit_tokens,
        )


_tracker: UsageTracker | None = None
_tracker_lock = threading.Lock()


def get_usage_tracker() -> UsageTracker:
    global _tracker
    with _tracker_lock:
        if _tracker is None:
            _tracker = UsageTracker()
        return _tracker
