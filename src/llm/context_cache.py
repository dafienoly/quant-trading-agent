"""稳定上下文前缀缓存，用于提高 DeepSeek 服务端缓存命中概率。"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger


_SYSTEM_INVARIANTS = """## Safety Invariants
- 默认不启用真实自动交易。
- Risk Agent 拥有一票否决权。
- LLM 不得直接决定买卖、创建订单或绕过人工确认。
- 数据源、模型或工具失败时必须 fail closed。
- 密钥只能来自环境变量，不得出现在输出中。
"""

_RUNTIME_RULES = """## Runtime Rules
- 只返回符合给定 schema 的 JSON object。
- 不输出或持久化原始 reasoning content。
- 只允许调用请求中列出的只读工具。
- 工具、JSON 或 schema 校验失败时停止当前任务。
"""


@dataclass(frozen=True)
class PrefixEntry:
    prefix_id: str
    profile: str
    fingerprint: str
    created_at: str
    source_files: list[str] = field(default_factory=list)
    prefix: str = ""


class ContextPrefixCache:
    """只缓存 system/profile/schema，不接收用户 prompt。"""

    def __init__(self, cache_dir: str | Path | None = None) -> None:
        self.cache_dir = Path(
            cache_dir or os.getenv("LLM_CONTEXT_CACHE_DIR", "runtime/llm_context_cache")
        )
        self._lock = threading.RLock()

    def build_prefix(self, profile: str, system_prompt: str, schema_prompt: str) -> PrefixEntry:
        prefix = "\n\n".join(
            (
                _SYSTEM_INVARIANTS.strip(),
                _RUNTIME_RULES.strip(),
                f"## Task Profile\n{profile}",
                f"## Task Instructions\n{system_prompt.strip()}",
                f"## JSON Schema\n{schema_prompt}",
            )
        )
        fingerprint = hashlib.sha256(prefix.encode("utf-8")).hexdigest()
        with self._lock:
            cached = self.load(profile, fingerprint)
            if cached is not None and cached.prefix == prefix:
                return cached

            entry = PrefixEntry(
                prefix_id=f"{profile}:v1:{fingerprint[:16]}",
                profile=profile,
                fingerprint=fingerprint,
                created_at=datetime.now(timezone.utc).isoformat(),
                source_files=[
                    "AGENTS.md",
                    "docs/process/AGENT_DEVELOPMENT_PIPELINE.md",
                    "docs/policy/RISK_POLICY.md",
                ],
                prefix=prefix,
            )
            self._save(entry)
            return entry

    def load(self, profile: str, fingerprint: str) -> PrefixEntry | None:
        with self._lock:
            path = self._path(profile, fingerprint)
            if not path.is_file():
                return None
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                return PrefixEntry(**payload)
            except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
                logger.warning("读取 LLM 前缀缓存失败 path={}: {}", path.name, exc)
                return None

    def _save(self, entry: PrefixEntry) -> None:
        path = self._path(entry.profile, entry.fingerprint)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(asdict(entry), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)

    def _path(self, profile: str, fingerprint: str) -> Path:
        safe_profile = "".join(character for character in profile if character.isalnum() or character in "-_")
        if not safe_profile:
            raise ValueError("invalid profile for cache path")
        return self.cache_dir / safe_profile / f"{fingerprint}.json"
