from __future__ import annotations

from types import SimpleNamespace

from src.llm.usage import UsageTracker


def test_usage_extracts_deepseek_cache_fields():
    tracker = UsageTracker()
    response = SimpleNamespace(
        usage=SimpleNamespace(
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            prompt_cache_hit_tokens=7,
            prompt_cache_miss_tokens=3,
        )
    )

    usage = tracker.extract_usage(response)

    assert usage == {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
        "prompt_cache_hit_tokens": 7,
        "prompt_cache_miss_tokens": 3,
    }


def test_usage_summary_tracks_success_and_failure():
    tracker = UsageTracker(max_records=2)
    tracker.record(profile="one", model="m", status="ok", total_tokens=12)
    tracker.record(profile="two", model="m", status="timeout", total_tokens=None)
    tracker.record(profile="three", model="m", status="ok", total_tokens=8)

    summary = tracker.summary()

    assert summary["total_calls"] == 2
    assert summary["ok_calls"] == 1
    assert summary["error_calls"] == 1
    assert summary["total_tokens"] == 8
    records = tracker.snapshot()
    assert records[0]["profile"] == "two"
    assert records[1]["profile"] == "three"
