"""AgentConversation 单元测试

验证多轮消息管理、脱敏持久化和 TTL 清理。
"""
from __future__ import annotations

import os
import time

from src.llm.conversation import AgentConversation, _sanitize_message


class TestAgentConversation:
    """AgentConversation 功能测试"""

    def test_add_system_and_user(self):
        """system 和 user 消息正确追加"""
        conv = AgentConversation(profile="test")
        conv.add_system("You are a helpful assistant.")
        conv.add_user("Hello")

        assert len(conv.messages) == 2
        assert conv.messages[0]["role"] == "system"
        assert conv.messages[0]["content"] == "You are a helpful assistant."
        assert conv.messages[1]["role"] == "user"
        assert conv.messages[1]["content"] == "Hello"

    def test_add_system_replaces_first(self):
        """多次 add_system 替换第一条消息"""
        conv = AgentConversation(profile="test")
        conv.add_system("First system")
        conv.add_system("Replaced system")

        assert len(conv.messages) == 1
        assert conv.messages[0]["content"] == "Replaced system"

    def test_add_assistant_and_tool(self):
        """assistant 和 tool 消息正确追加"""
        conv = AgentConversation(profile="test")
        conv.add_user("Hi")
        conv.add_assistant('{"response": "Hello!"}')
        conv.add_tool("read_file", "file contents")

        assert len(conv.messages) == 3
        assert conv.messages[1]["role"] == "assistant"
        assert conv.messages[2]["role"] == "tool"
        assert conv.messages[2]["name"] == "read_file"

    def test_conversation_id_default(self):
        """未指定 conversation_id 时自动生成"""
        conv = AgentConversation(profile="test")
        assert conv.conversation_id is not None
        assert conv.conversation_id.startswith("conv-")

    def test_save_and_load(self, tmp_path):
        """save() 后 load() 恢复会话"""
        storage = tmp_path / "conversations"
        conv = AgentConversation(
            profile="test",
            conversation_id="test_conv_001",
            storage_dir=str(storage),
        )
        conv.add_system("System msg")
        conv.add_user("User msg")
        conv.add_assistant("Assistant msg")
        conv.save()

        loaded = AgentConversation.load("test_conv_001", storage_dir=str(storage))
        assert loaded is not None
        assert loaded.profile == "test"
        assert len(loaded.messages) == 3
        assert loaded.messages[0]["role"] == "system"
        assert loaded.messages[1]["role"] == "user"

    def test_load_nonexistent(self):
        """不存在的 conversation_id 返回 None"""
        loaded = AgentConversation.load("nonexistent_conv")
        assert loaded is None

    def test_save_redacts_secrets(self, tmp_path):
        """save() 持久化时对密钥进行脱敏"""
        storage = tmp_path / "conversations"
        conv = AgentConversation(
            profile="test",
            conversation_id="secret_test",
            storage_dir=str(storage),
        )
        conv.add_user("DEEPSEEK_API_KEY=sk-abc123")
        conv.save()

        loaded = AgentConversation.load("secret_test", storage_dir=str(storage))
        assert loaded is not None
        content = loaded.messages[0]["content"]
        assert "sk-abc123" not in content
        assert "***REDACTED***" in content

    def test_sanitize_message(self):
        """_sanitize_message() 脱敏密钥"""
        msg = {"role": "user", "content": "api_key=sk-abc123"}
        sanitized = _sanitize_message(msg)
        assert "sk-abc123" not in sanitized["content"]
        assert "***REDACTED***" in sanitized["content"]

    def test_sanitize_leaves_normal_text(self):
        """_sanitize_message() 不修改正常文本"""
        msg = {"role": "user", "content": "This is a normal question."}
        sanitized = _sanitize_message(msg)
        assert sanitized["content"] == "This is a normal question."

    def test_cleanup_expired(self, tmp_path):
        """TTL 过期后的文件被清理"""
        storage = tmp_path / "conversations"
        conv = AgentConversation(
            profile="test",
            conversation_id="expired_conv",
            storage_dir=str(storage),
        )
        conv.add_user("Test")
        path = conv.save()

        # Manually set the file's mtime to be old
        old_time = time.time() - 8 * 86400  # 8 days ago
        os.utime(path, (old_time, old_time))

        # Trigger cleanup by saving a new conversation
        conv2 = AgentConversation(
            profile="test",
            conversation_id="new_conv",
            storage_dir=str(storage),
        )
        conv2.add_user("New")
        conv2.save()

        # Old file should be removed
        assert not path.exists()
