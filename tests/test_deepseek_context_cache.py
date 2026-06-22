from __future__ import annotations

import json

from src.llm.context_cache import ContextPrefixCache
from src.llm.schemas import schema_json


def test_prefix_is_stable_and_persisted(tmp_path):
    cache = ContextPrefixCache(cache_dir=tmp_path)

    first = cache.build_prefix("bugfix_analysis", "system json", schema_json("bugfix_analysis"))
    second = cache.build_prefix("bugfix_analysis", "system json", schema_json("bugfix_analysis"))

    assert first.fingerprint == second.fingerprint
    assert first.prefix == second.prefix
    files = list(tmp_path.rglob("*.json"))
    assert len(files) == 1
    persisted = json.loads(files[0].read_text(encoding="utf-8"))
    assert persisted["fingerprint"] == first.fingerprint
    assert "root_cause" in persisted["prefix"]


def test_prefix_changes_when_schema_or_prompt_changes(tmp_path):
    cache = ContextPrefixCache(cache_dir=tmp_path)

    first = cache.build_prefix("bugfix_analysis", "system json", schema_json("bugfix_analysis"))
    second = cache.build_prefix("bugfix_analysis", "different json", schema_json("bugfix_analysis"))

    assert first.fingerprint != second.fingerprint


def test_prefix_cache_does_not_receive_user_prompt(tmp_path):
    cache = ContextPrefixCache(cache_dir=tmp_path)
    secret_user_prompt = "BUG traceback token=should-not-persist"

    entry = cache.build_prefix("bugfix_analysis", "system json", schema_json("bugfix_analysis"))

    assert secret_user_prompt not in entry.prefix
    assert "should-not-persist" not in "".join(
        path.read_text(encoding="utf-8") for path in tmp_path.rglob("*.json")
    )


def test_load_rejects_corrupt_cache(tmp_path):
    cache = ContextPrefixCache(cache_dir=tmp_path)
    entry = cache.build_prefix("bugfix_analysis", "system json", schema_json("bugfix_analysis"))
    path = next(tmp_path.rglob("*.json"))
    path.write_text("not-json", encoding="utf-8")

    assert cache.load("bugfix_analysis", entry.fingerprint) is None
