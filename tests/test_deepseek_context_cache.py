"""Context Prefix Cache 单元测试

验证本地前缀缓存和 fingerprint 管理功能。
"""
from __future__ import annotations

import json

from src.llm.context_cache import ContextPrefixCache


class TestContextPrefixCache:
    """ContextPrefixCache 功能测试"""

    def test_build_prefix_creates_entry(self, tmp_path):
        """build_prefix() 创建缓存条目并持久化"""
        cache = ContextPrefixCache(cache_dir=str(tmp_path))
        entry = cache.build_prefix(
            profile="bugfix_analysis",
            system_prompt="Analyze this bug.",
        )

        assert entry.profile == "bugfix_analysis"
        assert entry.fingerprint is not None
        assert entry.prefix_id.startswith("bugfix_analysis:v1:")
        assert entry.prefix is not None
        assert "## Safety Invariants" in entry.prefix
        assert "Analyze this bug." in entry.prefix

    def test_cache_file_persisted(self, tmp_path):
        """build_prefix() 持久化文件到磁盘"""
        cache = ContextPrefixCache(cache_dir=str(tmp_path))
        entry = cache.build_prefix(
            profile="test_profile",
            system_prompt="test",
        )

        cache_path = tmp_path / "test_profile" / f"{entry.fingerprint}.json"
        assert cache_path.exists()

        data = json.loads(cache_path.read_text(encoding="utf-8"))
        assert data["profile"] == "test_profile"
        assert data["fingerprint"] == entry.fingerprint
        assert "created_at" in data

    def test_load_existing_entry(self, tmp_path):
        """load() 能读取之前缓存的条目"""
        cache = ContextPrefixCache(cache_dir=str(tmp_path))
        original = cache.build_prefix(
            profile="load_test",
            system_prompt="test prompt",
        )

        loaded = cache.load(original.profile, original.fingerprint)
        assert loaded is not None
        assert loaded.prefix_id == original.prefix_id
        assert loaded.prefix == original.prefix

    def test_load_nonexistent_entry(self, tmp_path):
        """load() 不存在的条目返回 None"""
        cache = ContextPrefixCache(cache_dir=str(tmp_path))
        loaded = cache.load("nonexistent", "abcdef123456")
        assert loaded is None

    def test_fingerprint_deterministic(self):
        """fingerprint() 对于相同输入返回相同值"""
        cache = ContextPrefixCache()
        fp1 = cache.fingerprint("same content")
        fp2 = cache.fingerprint("same content")
        assert fp1 == fp2

    def test_fingerprint_different_for_different_input(self):
        """fingerprint() 对于不同输入返回不同值"""
        cache = ContextPrefixCache()
        fp1 = cache.fingerprint("content A")
        fp2 = cache.fingerprint("content B")
        assert fp1 != fp2

    def test_prefix_contains_system_invariants(self):
        """build_prefix() 包含安全不变量"""
        cache = ContextPrefixCache()
        entry = cache.build_prefix(
            profile="signal_explanation",
            system_prompt="Explain signal.",
        )
        assert "Risk Agent has one-veto power" in entry.prefix
        assert "LLM must not directly decide buy or sell" in entry.prefix

    def test_prefix_with_json_schema(self, tmp_path):
        """build_prefix() 含 JSON schema 提示"""
        cache = ContextPrefixCache(cache_dir=str(tmp_path))
        entry = cache.build_prefix(
            profile="bugfix_analysis",
            system_prompt="Analyze.",
            json_schema_prompt='{"type": "object", "properties": {...}}',
        )
        assert "## JSON Schema" in entry.prefix
        assert "properties" in entry.prefix

    def test_multiple_profiles_independent_cache(self, tmp_path):
        """不同 profile 的缓存相互独立"""
        cache = ContextPrefixCache(cache_dir=str(tmp_path))

        entry_a = cache.build_prefix(profile="profile_a", system_prompt="prompt a")
        entry_b = cache.build_prefix(profile="profile_b", system_prompt="prompt b")

        assert entry_a.fingerprint != entry_b.fingerprint
        assert (tmp_path / "profile_a" / f"{entry_a.fingerprint}.json").exists()
        assert (tmp_path / "profile_b" / f"{entry_b.fingerprint}.json").exists()
