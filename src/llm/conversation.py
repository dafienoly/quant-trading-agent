"""Multi-round conversation management.

Handles message appending, serialization, and safe persistence.
Conversations are stored in ``LLM_CONVERSATION_DIR`` (default
``runtime/llm_conversations/``) with a 7-day TTL.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from loguru import logger

SECRET_PATTERNS = [
    re.compile(r"(DEEPSEEK_API_KEY|OPENAI_API_KEY)[=:]\s*\S+", re.IGNORECASE),
    re.compile(r"(api_key|apikey)[=:]\s*\S+", re.IGNORECASE),
    re.compile(r"(token|secret|password|credential)[=:]\s*\S+", re.IGNORECASE),
]


def _sanitize_message(msg: dict[str, Any]) -> dict[str, Any]:
    """Remove potential secrets from a single message dict (in-place copy)."""
    sanitized = dict(msg)
    content = sanitized.get("content", "")
    if isinstance(content, str):
        for pattern in SECRET_PATTERNS:
            content = pattern.sub(r"\1=***REDACTED***", content)
        sanitized["content"] = content
    return sanitized


class AgentConversation:
    """A single multi-round conversation with DeepSeek.

    Usage::
        conv = AgentConversation(profile="bugfix_analysis")
        conv.add_user("Analyze this bug.")
        result = runtime.chat_json(conv.as_request(...))
        conv.add_assistant(result)
        conv.add_tool(name, content)
        conv.save()
    """

    def __init__(
        self,
        profile: str,
        conversation_id: str | None = None,
        storage_dir: str | None = None,
    ) -> None:
        self.profile = profile
        self.conversation_id = conversation_id or f"conv-{int(time.time())}-{id(self)}"
        self.messages: list[dict[str, Any]] = []
        self._storage_dir = Path(
            storage_dir or os.getenv("LLM_CONVERSATION_DIR", "runtime/llm_conversations")
        )
        self._ttl_seconds = 7 * 86400  # 7 days

    # ------------------------------------------------------------------
    # Message helpers
    # ------------------------------------------------------------------

    def add_system(self, content: str) -> None:
        """Add or replace the system message at position 0."""
        if self.messages and self.messages[0].get("role") == "system":
            self.messages[0] = {"role": "system", "content": content}
        else:
            self.messages.insert(0, {"role": "system", "content": content})

    def add_user(self, content: str) -> None:
        self.messages.append({"role": "user", "content": content})

    def add_assistant(self, content: str, **extra: Any) -> None:
        msg: dict[str, Any] = {"role": "assistant", "content": content}
        if extra:
            msg.update(extra)
        self.messages.append(msg)

    def add_tool(self, tool_name: str, content: str) -> None:
        self.messages.append({"role": "tool", "name": tool_name, "content": content})

    def add_tool_calls(self, tool_calls: list[dict[str, Any]]) -> None:
        """Append an assistant message with tool_calls (no content)."""
        self.messages.append({"role": "assistant", "content": None, "tool_calls": tool_calls})

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def save(self) -> Path:
        """Persist conversation to disk with secret redaction."""
        path = self._storage_dir / f"{self.conversation_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "conversation_id": self.conversation_id,
            "profile": self.profile,
            "created_at": time.time(),
            "messages": [_sanitize_message(m) for m in self.messages],
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        self._cleanup_expired()
        return path

    @classmethod
    def load(cls, conversation_id: str, storage_dir: str | None = None) -> AgentConversation | None:
        """Load a conversation from disk. Returns ``None`` if not found or expired."""
        storage = Path(storage_dir or os.getenv("LLM_CONVERSATION_DIR", "runtime/llm_conversations"))
        path = storage / f"{conversation_id}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load conversation {}: {}", conversation_id, exc)
            return None

        # TTL check
        created = data.get("created_at", 0)
        if time.time() - created > 7 * 86400:
            path.unlink(missing_ok=True)
            logger.info("Expired conversation {} removed", conversation_id)
            return None

        conv = cls(profile=data.get("profile", "unknown"), conversation_id=conversation_id)
        conv.messages = data.get("messages", [])
        return conv

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _cleanup_expired(self) -> None:
        """Remove conversation files older than TTL."""
        if not self._storage_dir.exists():
            return
        now = time.time()
        for p in self._storage_dir.glob("*.json"):
            if now - p.stat().st_mtime > self._ttl_seconds:
                p.unlink(missing_ok=True)
