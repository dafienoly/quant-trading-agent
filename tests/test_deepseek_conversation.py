from __future__ import annotations

import json
import os
import time

from src.llm.conversation import AgentConversation, sanitize_text


def test_conversation_round_trip_and_message_order(tmp_path):
    storage = tmp_path / "conversations"
    conversation = AgentConversation(profile="bugfix_analysis", storage_dir=storage)
    conversation.add_system("system")
    conversation.add_user("user")
    conversation.add_assistant("assistant")
    conversation.add_tool("call-1", "tool output")

    path = conversation.save()
    loaded = AgentConversation.load(conversation.conversation_id, storage_dir=storage)

    assert path.name == f"{conversation.conversation_id}.json"
    assert loaded is not None
    assert [message["role"] for message in loaded.messages] == [
        "system",
        "user",
        "assistant",
        "tool",
    ]


def test_conversation_save_redacts_nested_secrets_and_reasoning(tmp_path):
    storage = tmp_path / "conversations"
    conversation = AgentConversation(profile="bugfix_analysis", storage_dir=storage)
    conversation.add_user("DEEPSEEK_API_KEY=TEST_REDACTION_VALUE")
    conversation.add_assistant(
        None,
        reasoning_content="private chain",
        tool_calls=[
            {
                "id": "call-1",
                "type": "function",
                "function": {
                    "name": "read_note",
                    "arguments": '{"token":"TEST_NESTED_VALUE"}',
                },
            }
        ],
    )

    path = conversation.save()
    persisted = path.read_text(encoding="utf-8")

    assert "TEST_REDACTION_VALUE" not in persisted
    assert "TEST_NESTED_VALUE" not in persisted
    assert "private chain" not in persisted
    assert "reasoning_content" not in persisted
    assert "***REDACTED***" in persisted


def test_load_expired_conversation_removes_file(tmp_path):
    storage = tmp_path / "conversations"
    conversation = AgentConversation(
        profile="bugfix_analysis",
        conversation_id="expired",
        storage_dir=storage,
        ttl_seconds=1,
    )
    conversation.add_user("old")
    path = conversation.save()
    old = time.time() - 10
    os.utime(path, (old, old))

    loaded = AgentConversation.load("expired", storage_dir=storage, ttl_seconds=1)

    assert loaded is None
    assert not path.exists()


def test_invalid_conversation_id_is_rejected(tmp_path):
    assert AgentConversation.load("../escape", storage_dir=tmp_path) is None


def test_sanitize_text_handles_common_secret_formats():
    sanitized = sanitize_text(
        "token: TEST_TOKEN password=TEST_PASSWORD "
        "OPENAI_API_KEY=TEST_KEY Authorization: Bearer TEST_BEARER"
    )

    assert "TEST_TOKEN" not in sanitized
    assert "TEST_PASSWORD" not in sanitized
    assert "TEST_KEY" not in sanitized
    assert "TEST_BEARER" not in sanitized


def test_persisted_json_is_valid(tmp_path):
    conversation = AgentConversation(profile="signal_explanation", storage_dir=tmp_path)
    conversation.add_user("你好")
    data = json.loads(conversation.save().read_text(encoding="utf-8"))

    assert data["profile"] == "signal_explanation"
    assert data["messages"][0]["content"] == "你好"
