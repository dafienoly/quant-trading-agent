"""UsageTracker 单元测试

验证 token、cache hit/miss、latency 记录功能。
"""
from __future__ import annotations

import time

from src.llm.usage import UsageTracker, get_usage_tracker


class _FakeResponse:
    """模拟 OpenAI 响应的 usage 字段"""

    class _Usage:
        prompt_tokens = 50
        completion_tokens = 100
        total_tokens = 150
        prompt_cache_hit_tokens = 10
        prompt_cache_miss_tokens = 40

    def __init__(self):
        self.usage = self._Usage()


class TestUsageTracker:
    """UsageTracker 功能测试"""

    def test_record_and_summary(self):
        """record() 后 summary() 返回正确统计"""
        tracker = UsageTracker(max_records=100)
        record = tracker.record(
            profile="test",
            model="deepseek-v4-flash",
            start_time=time.time() - 2,
            end_time=time.time(),
            prompt_tokens=50,
            completion_tokens=100,
            total_tokens=150,
            prompt_cache_hit_tokens=10,
            prompt_cache_miss_tokens=40,
            tool_call_count=2,
            tool_round_count=1,
            status="ok",
        )
        assert record.request_id.startswith("req-")
        assert record.prompt_tokens == 50
        assert record.total_tokens == 150
        assert record.prompt_cache_hit_tokens == 10
        assert record.latency_seconds > 0

        summary = tracker.summary()
        assert summary["total_calls"] == 1
        assert summary["ok_calls"] == 1
        assert summary["total_tokens"] == 150
        assert summary["total_cache_hit_tokens"] == 10

    def test_empty_summary(self):
        """没有记录时 summary 返回零值"""
        tracker = UsageTracker()
        summary = tracker.summary()
        assert summary["total_calls"] == 0

    def test_multiple_records(self):
        """多条记录汇总正确"""
        tracker = UsageTracker()
        for i in range(3):
            tracker.record(
                profile="test",
                model="m",
                start_time=time.time(),
                total_tokens=100,
                status="ok" if i < 2 else "error",
            )

        summary = tracker.summary()
        assert summary["total_calls"] == 3
        assert summary["ok_calls"] == 2
        assert summary["error_calls"] == 1
        assert summary["total_tokens"] == 300

    def test_max_records_drops_old(self):
        """超出 max_records 时丢弃旧记录"""
        tracker = UsageTracker(max_records=3)
        for i in range(5):
            tracker.record(
                profile="test",
                model="m",
                total_tokens=i * 100,
                status="ok",
            )

        summary = tracker.summary()
        assert summary["total_calls"] == 3  # Only 3 kept

    def test_extract_usage_from_response(self):
        """从模拟响应中提取 usage 字段"""
        tracker = UsageTracker()
        fake_response = _FakeResponse()
        usage = tracker.extract_usage_from_response(fake_response)
        assert usage["prompt_tokens"] == 50
        assert usage["completion_tokens"] == 100
        assert usage["total_tokens"] == 150
        assert usage["prompt_cache_hit_tokens"] == 10
        assert usage["prompt_cache_miss_tokens"] == 40

    def test_usage_singleton(self):
        """get_usage_tracker() 返回同一实例"""
        t1 = get_usage_tracker()
        t2 = get_usage_tracker()
        assert t1 is t2
