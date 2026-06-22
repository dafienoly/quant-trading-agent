"""DeepSeek 多轮会话管理与脱敏持久化。"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

from loguru import logger


_SECRET_ASSIGNMENT = re.compile(
    r"(?i)([\"']?(?:deepseek_api_key|openai_api_key|api_key|apikey|token|secret|password|credential)"
    r"[\"']?\s*[:=]\s*[\"']?)([^\"'\s,}]+)"
)
_BEARER_TOKEN = re.compile(r"(?i)(authorization\s*:\s*bearer\s+)(\S+)")
_SAFE_CONVERSATION_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


def sanitize_text(value: str) -> str:
    """脱敏常见密钥、口令和 Bearer token。"""

    value = _SECRET_ASSIGNMENT.sub(r"\1***REDACTED***", value)
    return _BEARER_TOKEN.sub(r"\1***REDACTED***", value)


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize_value(item) for key, item in value.items()}
    return value


def _sanitize_message(message: dict[str, Any], *, persist_reasoning: bool) -> dict[str, Any]:
    sanitized = _sanitize_value(dict(message))
    if not persist_reasoning:
        sanitized.pop("reasoning_content", None)
    return sanitized


class AgentConversation:
    """维护一段按顺序排列的模型对话。"""

    def __init__(
        self,
        profile: str,
        conversation_id: str | None = None,
        storage_dir: str | Path | None = None,
        ttl_seconds: int = 7 * 86400,
    ) -> None:
        self.profile = profile
        self.conversation_id = conversation_id or f"conv-{uuid.uuid4().hex}"
        if not self._is_safe_id(self.conversation_id):
            raise ValueError("invalid conversation_id")
        self.messages: list[dict[str, Any]] = []
        self.storage_dir = Path(
            storage_dir or os.getenv("LLM_CONVERSATION_DIR", "runtime/llm_conversations")
        )
        self.ttl_seconds = max(1, int(ttl_seconds))

    def add_system(self, content: str) -> None:
        message = {"role": "system", "content": content}
        if self.messages and self.messages[0].get("role") == "system":
            self.messages[0] = message
        else:
            self.messages.insert(0, message)

    def add_user(self, content: str) -> None:
        self.messages.append({"role": "user", "content": content})

    def add_assistant(self, content: str | None, **extra: Any) -> None:
        message: dict[str, Any] = {"role": "assistant", "content": content}
        message.update(extra)
        self.messages.append(message)

    def add_tool(self, tool_call_id: str, content: str, *, name: str | None = None) -> None:
        message: dict[str, Any] = {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content,
        }
        if name:
            message["name"] = name
        self.messages.append(message)

    def save(self, *, persist_reasoning: bool = False) -> Path:
        """持久化脱敏会话；默认不保存 reasoning content。"""

        self.storage_dir.mkdir(parents=True, exist_ok=True)
        path = self.storage_dir / f"{self.conversation_id}.json"
        payload = {
            "conversation_id": self.conversation_id,
            "profile": self.profile,
            "updated_at": time.time(),
            "messages": [
                _sanitize_message(message, persist_reasoning=persist_reasoning)
                for message in self.messages
            ],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.cleanup_expired()
        return path

    @classmethod
    def load(
        cls,
        conversation_id: str,
        storage_dir: str | Path | None = None,
        ttl_seconds: int = 7 * 86400,
    ) -> AgentConversation | None:
        if not cls._is_safe_id(conversation_id):
            return None
        directory = Path(
            storage_dir or os.getenv("LLM_CONVERSATION_DIR", "runtime/llm_conversations")
        )
        path = directory / f"{conversation_id}.json"
        if not path.is_file():
            return None
        try:
            if time.time() - path.stat().st_mtime > ttl_seconds:
                path.unlink(missing_ok=True)
                return None
            payload = json.loads(path.read_text(encoding="utf-8"))
            conversation = cls(
                profile=str(payload["profile"]),
                conversation_id=conversation_id,
                storage_dir=directory,
                ttl_seconds=ttl_seconds,
            )
            messages = payload.get("messages")
            if not isinstance(messages, list) or not all(isinstance(item, dict) for item in messages):
                return None
            conversation.messages = messages
            return conversation
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            logger.warning("读取 LLM 会话失败 conversation_id={}: {}", conversation_id, exc)
            return None

    def cleanup_expired(self) -> None:
        if not self.storage_dir.exists():
            return
        now = time.time()
        for path in self.storage_dir.glob("*.json"):
            try:
                if now - path.stat().st_mtime > self.ttl_seconds:
                    path.unlink(missing_ok=True)
            except OSError as exc:
                logger.warning("清理过期 LLM 会话失败 path={}: {}", path.name, exc)

    @staticmethod
    def _is_safe_id(conversation_id: str) -> bool:
        return bool(
            conversation_id
            and conversation_id not in {".", ".."}
            and ".." not in conversation_id
            and _SAFE_CONVERSATION_ID.fullmatch(conversation_id)
        )
